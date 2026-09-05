"""The verifier: checks a report is well-formed and bound, never grades the artifact itself."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from context_report.rows import CLAIMED, NOT_MEASURED, RE_DERIVABLE, STATEMENT_TYPE
from context_report.statement import digest_path, now_utc, validate

SVR_PREDICATE_TYPE = "https://in-toto.io/attestation/svr/v0.2"


@dataclass(frozen=True)
class RowSummary:
    """One attribute row, reduced to what a verifier's summary needs."""

    attribute: str
    basis: str
    result: str
    has_input_hash: bool


@dataclass(frozen=True)
class Verification:
    """The result of checking one statement.

    `ok` means "well-formed and bound": no schema errors, and if a subject_path was given, its
    digest matched subject[0].digest.sha256. It NEVER means "the artifact is good" -- a statement
    can be perfectly well-formed and bound while every row FAILED. The format emits facts per row;
    setting a threshold on those facts is a consumer's decision, not this one's.
    """

    schema_errors: list[str]
    subject_digest_matches: bool | None
    rows: list[RowSummary]
    claimed: list[str]
    rederivable: list[str]
    unmeasured: list[str]
    ok: bool


def verify_statement(stmt: dict[str, Any], *, subject_path: str | None = None) -> Verification:
    """Validate `stmt` against the schema and, if `subject_path` is given, bind it to that file.

    Digest binding recomputes `digest_path(subject_path)` and compares it against
    `subject[0].digest.sha256`; a mismatch means this report describes a different artifact and is
    a hard failure (`ok` is False), never a warning.
    """
    schema_errors = validate(stmt)

    subject_digest_matches: bool | None = None
    if subject_path is not None:
        try:
            expected = stmt["subject"][0]["digest"]["sha256"]
        except (KeyError, IndexError, TypeError):
            expected = None
        subject_digest_matches = expected is not None and digest_path(subject_path) == expected

    attributes = stmt.get("predicate", {}).get("attributes", [])
    row_summaries = [
        RowSummary(
            attribute=a.get("attribute", ""),
            basis=a.get("basis", ""),
            result=a.get("result", ""),
            has_input_hash=bool(a.get("inputHash")),
        )
        for a in attributes
        if isinstance(a, dict)
    ]
    claimed = [r.attribute for r in row_summaries if r.basis == CLAIMED]
    rederivable = [r.attribute for r in row_summaries if r.basis == RE_DERIVABLE]
    unmeasured = [r.attribute for r in row_summaries if r.result in NOT_MEASURED]

    ok = not schema_errors and (subject_digest_matches is None or subject_digest_matches)
    return Verification(
        schema_errors=schema_errors,
        subject_digest_matches=subject_digest_matches,
        rows=row_summaries,
        claimed=claimed,
        rederivable=rederivable,
        unmeasured=unmeasured,
        ok=ok,
    )


class Recomputer(Protocol):
    """A pluggable strategy that reproduces one re-derivable row from the subject on disk."""

    def recompute(self, row: dict[str, Any], subject_path: str) -> dict[str, Any] | None:
        """Return a recomputed row for the same attribute, or None if this recomputer can't help."""
        ...


@dataclass(frozen=True)
class Diff:
    """A re-derivable row as the author reported it, next to what a Recomputer reproduced.

    Only ever built for `re-derivable` rows (see recompute_rows); `claimed` rows have nothing a
    verifier can reproduce.
    """

    attribute: str
    reported_row: dict[str, Any]
    recomputed_row: dict[str, Any]
    matches: bool


def _measurements_match(reported: dict[str, Any], recomputed: dict[str, Any]) -> bool:
    """Exact match, unless the row is environmentSensitive: then unit and n >= 1 on both sides."""
    reported_m, recomputed_m = reported.get("measurement"), recomputed.get("measurement")
    if reported_m is None or recomputed_m is None:
        return False
    if reported.get("environmentSensitive") is not True:
        return reported_m == recomputed_m
    same_unit = reported_m.get("unit") == recomputed_m.get("unit")
    return same_unit and reported_m.get("n", 0) >= 1 and recomputed_m.get("n", 0) >= 1


def _rows_match(reported: dict[str, Any], recomputed: dict[str, Any]) -> bool:
    """Compare what a recomputation can promise: result, values, and the measurement.

    A row marked `environmentSensitive` (latency) re-derives to a comparable distribution, not the
    same numbers, so its measurement is compared on `unit` and `n >= 1` only. Any other measurement
    (a token count) must match exactly: the spec's "Re-derivable is not identical" rule.
    """
    if reported.get("result") != recomputed.get("result"):
        return False
    if reported.get("values") != recomputed.get("values"):
        return False
    if "measurement" in reported or "measurement" in recomputed:
        return _measurements_match(reported, recomputed)
    return True


def recompute_rows(
    stmt: dict[str, Any], subject_path: str, recomputers: list[Recomputer]
) -> list[Diff]:
    """Recompute every `re-derivable` row using the first recomputer able to handle it.

    NEVER applied to `claimed` rows: those are stochastic or author-reported by definition (see
    rows.py's `efficacy` invariant), so there is nothing for a verifier to reproduce.
    """
    diffs = []
    for row in stmt.get("predicate", {}).get("attributes", []):
        if row.get("basis") != RE_DERIVABLE:
            continue
        for recomputer in recomputers:
            recomputed = recomputer.recompute(row, subject_path)
            if recomputed is not None:
                diffs.append(
                    Diff(
                        attribute=row.get("attribute", ""),
                        reported_row=row,
                        recomputed_row=recomputed,
                        matches=_rows_match(row, recomputed),
                    )
                )
                break
    return diffs


@dataclass(frozen=True)
class InputHashPresenceRecomputer:
    """Trivial built-in recomputer: exercises the Recomputer protocol without a real producer.

    Vouches for a row only by checking it carries the `inputHash` rows.py already requires for
    every re-derivable row; it never re-runs the measurement itself.
    """

    def recompute(
        self,
        row: dict[str, Any],
        subject_path: str,  # noqa: ARG002 -- checks presence only
    ) -> dict[str, Any] | None:
        if row.get("inputHash"):
            return dict(row)
        return None


def to_svr(
    verification: Verification,
    *,
    verifier_id: str,
    report_digest_sha256: str,
    policy_uri: str | None = None,
) -> dict[str, Any]:
    """Build an in-toto Statement/v1 whose predicate is an SVR v0.2 verdict over the report.

    The subject is the REPORT's own digest, not the original artifact's: a verdict names the thing
    it judged, which is the statement this Verification was computed from. Per SVR v0.2 the
    predicate carries only verifier{id, policies[]}, timeCreated and properties[] -- no SLSA_
    prefixed values, which belong to VSA, not SVR.
    """
    properties = []
    if not verification.schema_errors:
        properties.append("CONTEXT_REPORT_WELL_FORMED")
    if verification.subject_digest_matches:
        properties.append("CONTEXT_REPORT_SUBJECT_BOUND")
    properties.append(f"CONTEXT_REPORT_CLAIMED_ROWS:{len(verification.claimed)}")

    return {
        "_type": STATEMENT_TYPE,
        "subject": [{"digest": {"sha256": report_digest_sha256}}],
        "predicateType": SVR_PREDICATE_TYPE,
        "predicate": {
            "verifier": {
                "id": verifier_id,
                "policies": [{"uri": policy_uri}] if policy_uri else [],
            },
            "timeCreated": now_utc(),
            "properties": properties,
        },
    }
