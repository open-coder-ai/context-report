"""Regenerating the paper's figures matches the committed SVGs by name, by XML validity, and
(within one matplotlib release) by bytes.
"""

from __future__ import annotations

import importlib.util
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

matplotlib = pytest.importorskip(
    "matplotlib", reason="figures need the dev extra's matplotlib; skip if absent"
)

# The exact matplotlib release the committed SVGs were generated with. Font metrics and path
# serialization differ across matplotlib versions (confirmed: 3.10.9 vs 3.11.1 produce different
# bytes for the same statements), so the byte-compare test below only runs on this exact version;
# elsewhere it skips rather than failing on a difference that is not a figure bug.
COMMITTED_MATPLOTLIB_VERSION = "3.11.1"

ROOT = Path(__file__).resolve().parents[1]
FIGURES_DIR = ROOT / "paper" / "figures"
SCRIPT = FIGURES_DIR / "make_figures.py"

EXPECTED_NAMES = {
    "fig-pipeline.svg",
    "fig-two-models.svg",
    "fig-catalog-status.svg",
    "fig-latency.svg",
    "fig-context-tokens.svg",
    "fig-chock-reachability.svg",
}


def _load_module():
    spec = importlib.util.spec_from_file_location("make_figures", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _regenerate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_module()
    monkeypatch.setattr(sys, "argv", ["make_figures.py", "--out-dir", str(tmp_path)])
    module.main()


def test_regenerating_produces_exactly_the_committed_file_names(tmp_path, monkeypatch) -> None:
    _regenerate(tmp_path, monkeypatch)
    produced = {p.name for p in tmp_path.glob("*.svg")}
    assert produced == EXPECTED_NAMES


def test_every_committed_figure_exists_and_parses_as_xml() -> None:
    committed = {p.name for p in FIGURES_DIR.glob("*.svg")}
    assert committed == EXPECTED_NAMES
    for name in EXPECTED_NAMES:
        ET.parse(FIGURES_DIR / name)  # noqa: S314 -- our own committed SVG, not untrusted input


def test_regenerated_output_parses_as_xml(tmp_path, monkeypatch) -> None:
    _regenerate(tmp_path, monkeypatch)
    for name in EXPECTED_NAMES:
        ET.parse(tmp_path / name)  # noqa: S314 -- freshly regenerated, not untrusted input


def test_regenerated_output_byte_matches_committed(tmp_path, monkeypatch) -> None:
    """Same statements in, same SVG bytes out — verified only against the matplotlib version the
    committed SVGs were generated with (see COMMITTED_MATPLOTLIB_VERSION above); a different
    matplotlib version renders the same figures with different font metrics and path data byte for
    byte, which is that library's known cross-version instability, not a regenerated-figure bug.
    On any other version this test is a no-op skip, and the two checks above (name, XML validity)
    are the ones that actually run everywhere the dev extra installs matplotlib.
    """
    if matplotlib.__version__ != COMMITTED_MATPLOTLIB_VERSION:
        pytest.skip(
            f"byte-compare only verified against matplotlib=={COMMITTED_MATPLOTLIB_VERSION}; "
            f"this environment has {matplotlib.__version__}, a known source of drift"
        )
    _regenerate(tmp_path, monkeypatch)
    mismatches = [
        name
        for name in EXPECTED_NAMES
        if (FIGURES_DIR / name).read_bytes() != (tmp_path / name).read_bytes()
    ]
    assert not mismatches, f"byte mismatch against committed SVGs (see docstring): {mismatches}"
