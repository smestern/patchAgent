"""
Tests for the protocol loader system.

Covers: discovery, loading, prompt formatting, and auto-matching.
"""

import importlib
import sys
import textwrap
from pathlib import Path

import pytest

# Import the protocol_loader module directly to avoid pulling in the full
# patch_agent package (which requires pyabf, ipfx, etc.).
_src = Path(__file__).resolve().parent.parent / "src"
_mod_path = _src / "patch_agent" / "utils" / "protocol_loader.py"
_spec = importlib.util.spec_from_file_location("protocol_loader", _mod_path)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

discover_protocol_dirs = _mod.discover_protocol_dirs
find_matching_protocol = _mod.find_matching_protocol
format_protocols_for_prompt = _mod.format_protocols_for_prompt
load_protocols = _mod.load_protocols


# ── Fixtures ────────────────────────────────────────────────────────


@pytest.fixture()
def proto_dir(tmp_path: Path) -> Path:
    """Create a temp directory with a valid protocol YAML file."""
    d = tmp_path / "protocols"
    d.mkdir()
    (d / "long_square.yaml").write_text(
        textwrap.dedent("""\
        protocol:
          name: "Long Square"
          type: "current_clamp"
          description: "1s current steps"
          timing:
            sweep_duration: 2.0
            stimulus_duration: 1.0
          stimulus:
            type: "step"
            start_amplitude: -100
            end_amplitude: 300
            step_size: 20
          expected_responses:
            - "passive_response"
            - "action_potentials"
          analysis_recommendations:
            - "input_resistance"
            - "fi_curve"
            - "spike_features"
        """),
        encoding="utf-8",
    )
    return d


@pytest.fixture()
def two_dirs(tmp_path: Path) -> tuple[Path, Path]:
    """Create two protocol dirs: user (high priority) and bundled (low)."""
    user_dir = tmp_path / "user" / "protocols"
    user_dir.mkdir(parents=True)
    bundled_dir = tmp_path / "bundled" / "protocols"
    bundled_dir.mkdir(parents=True)

    # Bundled version
    (bundled_dir / "long_square.yaml").write_text(
        textwrap.dedent("""\
        protocol:
          name: "Long Square"
          type: "current_clamp"
          description: "Bundled default"
          analysis_recommendations:
            - "input_resistance"
        """),
        encoding="utf-8",
    )

    # User override
    (user_dir / "long_square.yaml").write_text(
        textwrap.dedent("""\
        protocol:
          name: "Long Square"
          type: "current_clamp"
          description: "User override"
          analysis_recommendations:
            - "input_resistance"
            - "fi_curve"
        """),
        encoding="utf-8",
    )

    return user_dir, bundled_dir


# ── Loading tests ───────────────────────────────────────────────────


class TestLoadProtocols:
    def test_load_valid_yaml(self, proto_dir: Path):
        protocols = load_protocols(dirs=[proto_dir])
        assert len(protocols) == 1
        p = protocols[0]
        assert p["name"] == "Long Square"
        assert p["type"] == "current_clamp"
        assert "fi_curve" in p["analysis_recommendations"]

    def test_load_missing_dir(self):
        protocols = load_protocols(dirs=[Path("/nonexistent/path")])
        assert protocols == []

    def test_load_empty_dir(self, tmp_path: Path):
        empty = tmp_path / "empty_protocols"
        empty.mkdir()
        protocols = load_protocols(dirs=[empty])
        assert protocols == []

    def test_load_no_dirs(self):
        protocols = load_protocols(dirs=[])
        assert protocols == []

    def test_malformed_yaml_skipped(self, tmp_path: Path):
        d = tmp_path / "protocols"
        d.mkdir()
        (d / "bad.yaml").write_text(":::not valid yaml:::", encoding="utf-8")
        (d / "good.yaml").write_text(
            "protocol:\n  name: 'Good'\n  type: 'current_clamp'\n",
            encoding="utf-8",
        )
        protocols = load_protocols(dirs=[d])
        assert len(protocols) == 1
        assert protocols[0]["name"] == "Good"

    def test_missing_name_skipped(self, tmp_path: Path):
        d = tmp_path / "protocols"
        d.mkdir()
        (d / "no_name.yaml").write_text(
            "protocol:\n  type: 'current_clamp'\n",
            encoding="utf-8",
        )
        protocols = load_protocols(dirs=[d])
        assert protocols == []

    def test_user_dir_overrides_bundled(self, two_dirs: tuple[Path, Path]):
        user_dir, bundled_dir = two_dirs
        # User dir listed first → higher priority
        protocols = load_protocols(dirs=[user_dir, bundled_dir])
        assert len(protocols) == 1
        assert protocols[0]["description"] == "User override"
        assert "fi_curve" in protocols[0]["analysis_recommendations"]

    def test_flat_format_accepted(self, tmp_path: Path):
        """YAML files without the top-level `protocol:` wrapper should work."""
        d = tmp_path / "protocols"
        d.mkdir()
        (d / "flat.yaml").write_text(
            "name: 'Flat Protocol'\ntype: 'voltage_clamp'\n",
            encoding="utf-8",
        )
        protocols = load_protocols(dirs=[d])
        assert len(protocols) == 1
        assert protocols[0]["name"] == "Flat Protocol"


# ── Matching tests ──────────────────────────────────────────────────


class TestFindMatchingProtocol:
    @pytest.fixture()
    def protocols(self, proto_dir: Path) -> list[dict]:
        return load_protocols(dirs=[proto_dir])

    def test_exact_match(self, protocols):
        match = find_matching_protocol(protocols, "Long Square")
        assert match is not None
        assert match["name"] == "Long Square"

    def test_case_insensitive(self, protocols):
        match = find_matching_protocol(protocols, "long square")
        assert match is not None
        assert match["name"] == "Long Square"

    def test_substring_match(self, protocols):
        match = find_matching_protocol(protocols, "LongSquare_300pA")
        assert match is not None
        assert match["name"] == "Long Square"

    def test_reverse_substring(self, protocols):
        """File protocol name is a substring of the defined protocol name."""
        match = find_matching_protocol(protocols, "Long")
        assert match is not None

    def test_no_match(self, protocols):
        match = find_matching_protocol(protocols, "Totally Unknown Protocol")
        assert match is None

    def test_empty_name(self, protocols):
        assert find_matching_protocol(protocols, "") is None

    def test_empty_protocols(self):
        assert find_matching_protocol([], "Long Square") is None

    def test_normalised_separators(self, protocols):
        """Underscores and hyphens are treated as spaces during matching."""
        match = find_matching_protocol(protocols, "long_square")
        assert match is not None
        match2 = find_matching_protocol(protocols, "long-square")
        assert match2 is not None


# ── Prompt formatting tests ─────────────────────────────────────────


class TestFormatProtocols:
    def test_empty(self):
        assert format_protocols_for_prompt([]) == ""

    def test_contains_protocol_name(self, proto_dir: Path):
        protocols = load_protocols(dirs=[proto_dir])
        text = format_protocols_for_prompt(protocols)
        assert "Long Square" in text
        assert "current_clamp" in text
        assert "fi_curve" in text

    def test_multiple_protocols(self, tmp_path: Path):
        d = tmp_path / "protocols"
        d.mkdir()
        (d / "a.yaml").write_text(
            "protocol:\n  name: 'Proto A'\n  type: 'current_clamp'\n",
            encoding="utf-8",
        )
        (d / "b.yaml").write_text(
            "protocol:\n  name: 'Proto B'\n  type: 'voltage_clamp'\n",
            encoding="utf-8",
        )
        protocols = load_protocols(dirs=[d])
        text = format_protocols_for_prompt(protocols)
        assert "Proto A" in text
        assert "Proto B" in text


# ── Discovery tests ─────────────────────────────────────────────────


class TestDiscoverProtocolDirs:
    def test_extra_dir_included(self, proto_dir: Path):
        dirs = discover_protocol_dirs(extra_dir=proto_dir)
        assert proto_dir in dirs

    def test_nonexistent_extra_dir(self):
        dirs = discover_protocol_dirs(extra_dir="/nonexistent/protocols")
        # Should not crash; the nonexistent dir is simply not included
        assert Path("/nonexistent/protocols") not in dirs
