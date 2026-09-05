"""One row of a context-report: an attribute assertion with a basis; invalid rows fail early."""

from __future__ import annotations

import hashlib
import json
import math
import statistics
from dataclasses import dataclass, field
from typing import Any

STATEMENT_TYPE = "https://in-toto.io/Statement/v1"
PREDICATE_TYPE = "https://open-coder-ai.github.io/context-report/attestation/v0.1"

RE_DERIVABLE = "re-derivable"
CLAIMED = "claimed"

PASSED, WARNED, FAILED = "PASSED", "WARNED", "FAILED"
NOT_AVAILABLE, ERROR, NOT_APPLICABLE = "NotAvailable", "Error", "NotApplicable"
NOT_MEASURED = frozenset({NOT_AVAILABLE, ERROR, NOT_APPLICABLE})

ATTRIBUTES = (
    "conformance",
    "reachability",
    "decision",
    "fault.scriptMissing",
    "fault.interpreterMissing",
    "fault.timeout",
    "fault.malformedOutput",
    "cost.latency_ms",
    "cost.context_tokens",
    "interference",
    "efficacy",
)
PERCENTILES = (50, 95, 99)


def input_hash(*parts: object) -> str:
    """Glama-style inputHash: sha256 over canonical JSON of the exact inputs; order-sensitive."""
    blob = json.dumps(parts, sort_keys=True, separators=(",", ":"), default=str)
    return "sha256:" + hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _percentile(sorted_samples: list[float], pct: float) -> float:
    """Nearest-rank percentile (ceil), deterministic and free of interpolation choices."""
    rank = max(1, math.ceil(pct / 100 * len(sorted_samples)))
    return float(sorted_samples[rank - 1])


@dataclass(frozen=True)
class Measurement:
    """A measured distribution, percentile-keyed after JMH."""

    unit: str
    n: int
    percentiles: dict[str, float] = field(default_factory=dict)
    min: float | None = None
    max: float | None = None
    mean: float | None = None
    stddev: float | None = None

    @classmethod
    def from_samples(cls, samples: list[float], unit: str) -> Measurement:
        if not samples:
            raise ValueError("a measurement needs at least one sample")
        ordered = sorted(float(s) for s in samples)
        return cls(
            unit=unit,
            n=len(ordered),
            percentiles={str(p): _percentile(ordered, p) for p in PERCENTILES},
            min=ordered[0],
            max=ordered[-1],
            mean=statistics.fmean(ordered),
            stddev=statistics.stdev(ordered) if len(ordered) > 1 else 0.0,
        )

    def to_dict(self) -> dict[str, Any]:
        return _drop_none(
            {
                "unit": self.unit,
                "n": self.n,
                "percentiles": self.percentiles or None,
                "min": self.min,
                "max": self.max,
                "mean": self.mean,
                "stddev": self.stddev,
            }
        )


@dataclass(frozen=True)
class Estimate:
    """A point estimate with its interval, after Criterion and CycloneDX."""

    point_estimate: float
    confidence_level: float
    lower_bound: float
    upper_bound: float
    standard_error: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return _drop_none(
            {
                "pointEstimate": self.point_estimate,
                "standardError": self.standard_error,
                "confidenceInterval": {
                    "confidenceLevel": self.confidence_level,
                    "lowerBound": self.lower_bound,
                    "upperBound": self.upper_bound,
                },
            }
        )


@dataclass(frozen=True)
class Row:
    """An attribute assertion. Schema invariants are enforced here, so a bad row never leaves."""

    attribute: str
    basis: str
    result: str
    input_hash: str | None = None
    conditions: dict[str, Any] | None = None
    values: dict[str, Any] | None = None
    measurement: Measurement | None = None
    estimate: Estimate | None = None
    evidence: tuple[dict[str, Any], ...] = ()
    reasoning: str | None = None
    environment_sensitive: bool | None = None
    environment: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        if self.attribute not in ATTRIBUTES and not self.attribute.startswith("x-"):
            raise ValueError(f"{self.attribute!r} is not a v0.1 attribute and lacks the x- prefix")
        if self.basis not in (RE_DERIVABLE, CLAIMED):
            raise ValueError(f"basis must be {RE_DERIVABLE!r} or {CLAIMED!r}, not {self.basis!r}")
        if self.result not in (PASSED, WARNED, FAILED, *NOT_MEASURED):
            raise ValueError(f"unknown result {self.result!r}")
        if self.basis == RE_DERIVABLE and not self.input_hash:
            raise ValueError(f"{self.attribute}: a re-derivable row must carry an inputHash")
        if self.result in NOT_MEASURED and not self.reasoning:
            raise ValueError(f"{self.attribute}: an unmeasured row ({self.result}) must say why")
        if self.attribute == "efficacy" and self.basis != CLAIMED:
            raise ValueError("efficacy is stochastic by construction; it is always claimed")

    def to_dict(self) -> dict[str, Any]:
        return _drop_none(
            {
                "attribute": self.attribute,
                "basis": self.basis,
                "result": self.result,
                "inputHash": self.input_hash,
                "environmentSensitive": self.environment_sensitive,
                "environment": self.environment,
                "conditions": self.conditions,
                "values": self.values,
                "measurement": self.measurement.to_dict() if self.measurement else None,
                "estimate": self.estimate.to_dict() if self.estimate else None,
                "evidence": list(self.evidence) or None,
                "reasoning": self.reasoning,
            }
        )


def not_measured(
    attribute: str,
    result: str,
    reasoning: str,
    *,
    basis: str = RE_DERIVABLE,
    inputs: tuple[object, ...] = (),
) -> Row:
    """The honest row for a check that could not run: never silent, never a pass."""
    if result not in NOT_MEASURED:
        raise ValueError(f"not_measured needs one of {sorted(NOT_MEASURED)}, not {result!r}")
    ih = input_hash(attribute, *inputs) if basis == RE_DERIVABLE else None
    return Row(attribute=attribute, basis=basis, result=result, reasoning=reasoning, input_hash=ih)


def _drop_none(d: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in d.items() if v is not None}
