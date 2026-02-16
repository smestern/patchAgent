"""
Tests for new features: NaN cleaning, validate_nwb, list_protocols,
expanded alt_names, and code snippets.
"""

import importlib
import textwrap
from pathlib import Path

import numpy as np
import pytest

# ── Direct-import modules to avoid heavy dependencies ───────────────

_src = Path(__file__).resolve().parent.parent / "src"

# nan_utils
_nan_path = _src / "patchagent" / "utils" / "nan_utils.py"
_nan_spec = importlib.util.spec_from_file_location("nan_utils", _nan_path)
_nan_mod = importlib.util.module_from_spec(_nan_spec)
_nan_spec.loader.exec_module(_nan_mod)
clean_nans = _nan_mod.clean_nans

# protocol_loader (for alt_names matching tests)
_pl_path = _src / "patchagent" / "utils" / "protocol_loader.py"
_pl_spec = importlib.util.spec_from_file_location("protocol_loader", _pl_path)
_pl_mod = importlib.util.module_from_spec(_pl_spec)
_pl_spec.loader.exec_module(_pl_mod)
find_matching_protocol = _pl_mod.find_matching_protocol
load_protocols = _pl_mod.load_protocols
format_protocols_for_prompt = _pl_mod.format_protocols_for_prompt


# ── Fixtures ────────────────────────────────────────────────────────


@pytest.fixture()
def bundled_protocols() -> list[dict]:
    """Load the real bundled protocol YAML files from the repo."""
    bundled_dir = Path(__file__).resolve().parent.parent / "protocols"
    if not bundled_dir.is_dir():
        pytest.skip("Bundled protocols directory not found")
    return load_protocols(dirs=[bundled_dir])


@pytest.fixture()
def proto_with_alt(tmp_path: Path) -> list[dict]:
    """Create a protocol with alt_names for matching tests."""
    d = tmp_path / "protocols"
    d.mkdir()
    (d / "long_square.yaml").write_text(
        textwrap.dedent("""\
        protocol:
          name: "Long Square"
          alt_names: ["LS", "LongSquare", "LSFINEST", "LSCOARSE",
                      "X2LP", "LP_Search", "C1LS", "Long",
                      "C1LSFINEST", "C1LSCOARSE", "X2LP_Search"]
          type: "current_clamp"
          description: "1s current steps"
        """),
        encoding="utf-8",
    )
    (d / "short_square.yaml").write_text(
        textwrap.dedent("""\
        protocol:
          name: "Short Square"
          alt_names: ["SS", "ShortSquare", "SSFINEST",
                      "X5SP", "X6SP", "SP_", "Short", "C1SS"]
          type: "current_clamp"
          description: "3ms current pulses"
        """),
        encoding="utf-8",
    )
    (d / "ramp.yaml").write_text(
        textwrap.dedent("""\
        protocol:
          name: "Ramp"
          alt_names: ["CurrentRamp", "LinearRamp", "X7Ramp", "C1Ramp"]
          type: "current_clamp"
          description: "Linear current ramp"
        """),
        encoding="utf-8",
    )
    (d / "hyperpol.yaml").write_text(
        textwrap.dedent("""\
        protocol:
          name: "Hyperpol Steps"
          alt_names: ["HyperpolSteps", "Hyperpolarizing", "SubThreshold",
                      "X1PS", "SupraThresh", "X4PS", "SubThresh"]
          type: "current_clamp"
          description: "Hyperpolarizing steps"
        """),
        encoding="utf-8",
    )
    return load_protocols(dirs=[d])


# =====================================================================
# NaN Cleaning Tests
# =====================================================================


class TestCleanNans:
    """Tests for the clean_nans utility."""

    def test_no_nans_unchanged(self):
        """Arrays without NaN should pass through unchanged."""
        x = np.array([[0, 1, 2, 3], [0, 1, 2, 3]], dtype=float)
        y = np.array([[10, 20, 30, 40], [50, 60, 70, 80]], dtype=float)
        c = np.array([[1, 1, 1, 0], [2, 2, 2, 0]], dtype=float)
        rx, ry, rc = clean_nans(x, y, c)
        assert isinstance(rx, np.ndarray)
        assert rx.shape == (2, 4)
        np.testing.assert_array_equal(rx, x)
        np.testing.assert_array_equal(ry, y)
        np.testing.assert_array_equal(rc, c)

    def test_uniform_nan_padding(self):
        """All sweeps padded to same length → strip NaNs, return 2D."""
        x = np.array([[0, 1, np.nan, np.nan], [0, 1, np.nan, np.nan]])
        y = np.array([[10, 20, np.nan, np.nan], [30, 40, np.nan, np.nan]])
        c = np.array([[1, 1, np.nan, np.nan], [2, 2, np.nan, np.nan]])
        rx, ry, rc = clean_nans(x, y, c)
        assert isinstance(rx, np.ndarray)
        assert rx.shape == (2, 2)
        np.testing.assert_array_equal(rx, [[0, 1], [0, 1]])

    def test_variable_length_returns_list(self):
        """Sweeps of different live-data lengths → return list of arrays."""
        x = np.array([[0, 1, 2, np.nan], [0, 1, np.nan, np.nan]])
        y = np.array([[10, 20, 30, np.nan], [40, 50, np.nan, np.nan]])
        c = np.array([[1, 1, 1, np.nan], [2, 2, np.nan, np.nan]])
        rx, ry, rc = clean_nans(x, y, c)
        assert isinstance(rx, list)
        assert len(rx) == 2
        assert len(rx[0]) == 3
        assert len(rx[1]) == 2
        np.testing.assert_array_equal(rx[0], [0, 1, 2])
        np.testing.assert_array_equal(rx[1], [0, 1])

    def test_single_sweep(self):
        """1-D input (single sweep) should work."""
        x = np.array([0, 1, 2, np.nan, np.nan])
        y = np.array([10, 20, 30, np.nan, np.nan])
        c = np.array([1, 1, 1, np.nan, np.nan])
        rx, ry, rc = clean_nans(x, y, c)
        assert rx.ndim == 1
        assert len(rx) == 3
        np.testing.assert_array_equal(rx, [0, 1, 2])

    def test_nan_in_only_one_array(self):
        """NaN in any one array should truncate all three."""
        x = np.array([[0, 1, 2, 3], [0, 1, 2, 3]])
        y = np.array([[10, 20, np.nan, np.nan], [30, 40, 50, np.nan]])
        c = np.array([[1, 1, 1, 1], [2, 2, 2, 2]])
        rx, ry, rc = clean_nans(x, y, c)
        # Sweep 0: truncated at index 2, Sweep 1: at index 3
        assert isinstance(rx, list)
        assert len(rx[0]) == 2
        assert len(rx[1]) == 3


# =====================================================================
# Expanded Alt-Names Matching Tests
# =====================================================================


class TestExpandedAltNames:
    """Test that DANDI-style protocol names match correctly."""

    def test_dandi_longsquare_finest(self, proto_with_alt):
        match = find_matching_protocol(proto_with_alt, "C1LSFINEST150112_DA_0")
        assert match is not None
        assert match["name"] == "Long Square"

    def test_dandi_longsquare_coarse(self, proto_with_alt):
        match = find_matching_protocol(proto_with_alt, "C1LSCOARSE150216_DA_0")
        assert match is not None
        assert match["name"] == "Long Square"

    def test_dandi_lp_search(self, proto_with_alt):
        match = find_matching_protocol(proto_with_alt, "X2LP_Search_DA_0")
        assert match is not None
        assert match["name"] == "Long Square"

    def test_dandi_shortsquare(self, proto_with_alt):
        match = find_matching_protocol(proto_with_alt, "C1SSFINEST150112_DA_0")
        assert match is not None
        assert match["name"] == "Short Square"

    def test_dandi_x5sp(self, proto_with_alt):
        match = find_matching_protocol(proto_with_alt, "X5SP_SubThresh_DA_0")
        assert match is not None
        # Should match Short Square via X5SP or Hyperpol via SubThresh
        assert match["name"] in ("Short Square", "Hyperpol Steps")

    def test_dandi_ramp(self, proto_with_alt):
        match = find_matching_protocol(proto_with_alt, "X7Ramp_DA_0")
        assert match is not None
        assert match["name"] == "Ramp"

    def test_dandi_subthresh(self, proto_with_alt):
        match = find_matching_protocol(proto_with_alt, "X1PS_SubThresh_DA_0")
        assert match is not None
        assert match["name"] == "Hyperpol Steps"

    def test_bundled_protocols_have_new_aliases(self, bundled_protocols):
        """Verify the real bundled YAML files contain the expanded alt_names."""
        ls = find_matching_protocol(bundled_protocols, "C1LSFINEST150112_DA_0")
        assert ls is not None, "LSFINEST should match Long Square"
        assert ls["name"] == "Long Square"

        ss = find_matching_protocol(bundled_protocols, "X5SP_SubThresh_DA_0")
        assert ss is not None, "X5SP should match a protocol"

        ramp = find_matching_protocol(bundled_protocols, "X7Ramp_DA_0")
        assert ramp is not None, "X7Ramp should match Ramp"
        assert ramp["name"] == "Ramp"


# =====================================================================
# Known Datasets YAML Tests
# =====================================================================


class TestKnownDatasets:
    """Test that known_datasets.yaml is loaded into the prompt."""

    def test_prompt_includes_known_datasets(self, bundled_protocols):
        """format_protocols_for_prompt should include known dataset info."""
        prompt = format_protocols_for_prompt(bundled_protocols)
        # Should contain the known datasets section if the YAML exists
        bundled_dir = Path(__file__).resolve().parent.parent / "protocols"
        kd_path = bundled_dir / "known_datasets.yaml"
        if kd_path.is_file():
            assert "Known Public Dataset" in prompt
            assert "DANDI_000020" in prompt
        else:
            pytest.skip("known_datasets.yaml not found")


# =====================================================================
# Code Snippets Tests
# =====================================================================


class TestCodeSnippets:
    """Test that the new example code snippets are available."""

    def test_example_snippets_exist(self):
        # Import CODE_SNIPPETS directly
        _ct_path = _src / "patchagent" / "tools" / "code_tools.py"
        _ct_spec = importlib.util.spec_from_file_location(
            "code_tools_test", _ct_path,
            submodule_search_locations=[],
        )
        # We can't fully import code_tools due to sciagent dep, so just
        # check that the file text contains our snippet keys.
        content = _ct_path.read_text(encoding="utf-8")
        assert '"fi_curve_analysis"' in content
        assert '"passive_properties"' in content
        assert '"spike_analysis"' in content

    def test_example_files_exist(self):
        """Standalone example .py files should exist in examples/."""
        examples_dir = Path(__file__).resolve().parent.parent / "examples"
        assert (examples_dir / "fi_curve_analysis.py").is_file()
        assert (examples_dir / "passive_properties.py").is_file()
        assert (examples_dir / "spike_analysis.py").is_file()
