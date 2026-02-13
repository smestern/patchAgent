"""
Tests for the restructured system prompt and read_doc tool.

Tests cover:
  - System prompt composition (all expected sections present, no duplication)
  - read_doc tool functionality (list, read, errors)
  - INCREMENTAL_EXECUTION_POLICY presence in base messages
  - Prompt size is reasonable
"""

import importlib
import sys
import textwrap
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Direct-import helpers (avoids pulling in pyabf / ipfx / copilot)
# ---------------------------------------------------------------------------

_patch_src = Path(__file__).resolve().parent.parent / "src"
_sci_src = Path(__file__).resolve().parent.parent.parent / "sciagent" / "src"

# Import sciagent.prompts.base_messages
_bm_path = _sci_src / "sciagent" / "prompts" / "base_messages.py"
_bm_spec = importlib.util.spec_from_file_location("base_messages", _bm_path)
_bm = importlib.util.module_from_spec(_bm_spec)
_bm_spec.loader.exec_module(_bm)

# Import sciagent.tools.doc_tools
_dt_path = _sci_src / "sciagent" / "tools" / "doc_tools.py"
_dt_spec = importlib.util.spec_from_file_location("doc_tools", _dt_path)
_dt = importlib.util.module_from_spec(_dt_spec)
_dt_spec.loader.exec_module(_dt)

# Make sciagent.prompts.base_messages importable so system_messages can find it
sys.modules.setdefault("sciagent", type(sys)("sciagent"))
sys.modules.setdefault("sciagent.prompts", type(sys)("sciagent.prompts"))
sys.modules["sciagent.prompts.base_messages"] = _bm

# Import patch_agent.prompts.system_messages
_sm_path = _patch_src / "patch_agent" / "prompts" / "system_messages.py"
_sm_spec = importlib.util.spec_from_file_location("system_messages", _sm_path)
_sm = importlib.util.module_from_spec(_sm_spec)
_sm_spec.loader.exec_module(_sm)


# ── System prompt tests ─────────────────────────────────────────────


class TestSystemPromptComposition:
    """Verify the restructured system prompt has all required sections."""

    @pytest.fixture(autouse=True)
    def _build_prompt(self):
        self.prompt = _sm.build_patch_system_message()

    def test_contains_identity(self):
        assert "expert electrophysiology analysis assistant" in self.prompt

    def test_contains_mandatory_workflow(self):
        assert "## MANDATORY ANALYSIS WORKFLOW" in self.prompt

    def test_contains_protocol_discovery(self):
        assert "Phase 1: Protocol Discovery" in self.prompt

    def test_contains_single_sweep_validation(self):
        assert "Phase 2: Single-Sweep Validation" in self.prompt

    def test_contains_full_analysis_phase(self):
        assert "Phase 3: Full Analysis" in self.prompt

    def test_contains_tool_policy(self):
        assert "## TOOL & LIBRARY USAGE" in self.prompt

    def test_contains_priority_order(self):
        assert "Priority Order (STRICT)" in self.prompt

    def test_priority_order_appears_once(self):
        count = self.prompt.count("Priority Order")
        assert count == 1, f"'Priority Order' appears {count} times (expected 1)"

    def test_contains_ipfx_pitfalls(self):
        assert "IPFX Critical Pitfalls" in self.prompt

    def test_contains_filter_warning(self):
        assert "filter_frequency" in self.prompt

    def test_contains_data_formats(self):
        assert "## Data Formats" in self.prompt

    def test_contains_sanity_checks(self):
        assert "## MANDATORY SANITY CHECKS" in self.prompt

    def test_contains_bounds_table(self):
        assert "Input resistance" in self.prompt
        assert "Resting potential" in self.prompt

    def test_contains_delegation_warning(self):
        assert "Do NOT delegate" in self.prompt

    def test_contains_read_doc_reference(self):
        assert "read_doc" in self.prompt

    def test_contains_scientific_rigor(self):
        """Generic section from sciagent should be included."""
        assert "SCIENTIFIC RIGOR PRINCIPLES" in self.prompt

    def test_contains_incremental_execution(self):
        """New generic section from sciagent should be included."""
        assert "INCREMENTAL EXECUTION PRINCIPLE" in self.prompt

    def test_contains_reproducible_script(self):
        assert "Reproducible Script Generation" in self.prompt

    def test_no_key_analyses_section(self):
        """KEY_ANALYSES was removed — should not appear."""
        assert "## Key Analysis Types" not in self.prompt

    def test_prompt_size_reasonable(self):
        """Prompt should be under 6000 words to stay lean."""
        word_count = len(self.prompt.split())
        assert word_count < 6000, f"Prompt is {word_count} words (target: <6000)"


class TestSubAgentMessages:
    """Verify sub-agent messages include delegation warning."""

    def test_qc_checker_has_defer_note(self):
        assert "defer" in _sm.QC_CHECKER_SYSTEM_MESSAGE.lower()

    def test_spike_analyst_has_defer_note(self):
        assert "defer" in _sm.SPIKE_ANALYST_SYSTEM_MESSAGE.lower()

    def test_passive_analyst_has_defer_note(self):
        assert "defer" in _sm.PASSIVE_ANALYST_SYSTEM_MESSAGE.lower()


# ── Base messages tests ──────────────────────────────────────────────


class TestBaseMessages:
    """Verify sciagent base_messages changes."""

    def test_incremental_policy_exists(self):
        assert hasattr(_bm, "INCREMENTAL_EXECUTION_POLICY")

    def test_incremental_policy_content(self):
        assert "Examine structure" in _bm.INCREMENTAL_EXECUTION_POLICY
        assert "Validate on one unit" in _bm.INCREMENTAL_EXECUTION_POLICY

    def test_build_includes_incremental(self):
        msg = _bm.build_system_message()
        assert "INCREMENTAL EXECUTION PRINCIPLE" in msg

    def test_build_can_disable_incremental(self):
        msg = _bm.build_system_message(incremental_policy=False)
        assert "INCREMENTAL EXECUTION PRINCIPLE" not in msg

    def test_code_policy_no_priority_order(self):
        """Priority order was removed from generic CODE_EXECUTION_POLICY."""
        assert "Priority Order for Analysis" not in _bm.CODE_EXECUTION_POLICY


# ── read_doc tool tests ──────────────────────────────────────────────


class TestReadDoc:
    """Test the read_doc tool."""

    @pytest.fixture(autouse=True)
    def _setup_docs(self, tmp_path: Path):
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        (docs_dir / "IPFX.md").write_text("# IPFX Reference\nSome content.", encoding="utf-8")
        (docs_dir / "Tools.md").write_text("# Tools\nTool reference.", encoding="utf-8")
        (docs_dir / "Operations.md").write_text("# Operations\nWorkflow.", encoding="utf-8")
        _dt.set_docs_dir(docs_dir)
        yield
        _dt.set_docs_dir(None)  # cleanup

    def test_list_docs(self):
        result = _dt.read_doc("list")
        assert "available_docs" in result
        assert "IPFX" in result["available_docs"]
        assert "Tools" in result["available_docs"]
        assert "Operations" in result["available_docs"]

    def test_list_docs_empty_name(self):
        result = _dt.read_doc("")
        assert "available_docs" in result

    def test_read_existing_doc(self):
        result = _dt.read_doc("IPFX")
        assert "content" in result
        assert "# IPFX Reference" in result["content"]
        assert result["name"] == "IPFX"

    def test_read_case_insensitive(self):
        result = _dt.read_doc("ipfx")
        assert "content" in result
        assert "# IPFX Reference" in result["content"]

    def test_read_with_extension(self):
        result = _dt.read_doc("IPFX.md")
        assert "content" in result

    def test_read_nonexistent(self):
        result = _dt.read_doc("NoSuchDoc")
        assert "error" in result
        assert "available" in result

    def test_no_docs_dir(self):
        _dt.set_docs_dir(None)
        _dt._docs_dir = None
        result = _dt.read_doc("IPFX")
        assert "error" in result


# ── Integration: real docs directory ─────────────────────────────────


class TestRealDocs:
    """Verify that the actual patchAgent/docs/ directory works with read_doc."""

    @pytest.fixture(autouse=True)
    def _setup_real_docs(self):
        real_docs = Path(__file__).resolve().parent.parent / "docs"
        if real_docs.is_dir():
            _dt.set_docs_dir(real_docs)
            self.has_docs = True
        else:
            self.has_docs = False
        yield
        _dt.set_docs_dir(None)

    def test_can_list_real_docs(self):
        if not self.has_docs:
            pytest.skip("docs/ directory not found")
        result = _dt.read_doc("list")
        assert "available_docs" in result
        # Expect at least these docs
        for name in ("IPFX", "Tools", "Operations", "Protocol", "Agents", "Skills"):
            assert name in result["available_docs"], f"Missing doc: {name}"

    def test_can_read_ipfx(self):
        if not self.has_docs:
            pytest.skip("docs/ directory not found")
        result = _dt.read_doc("IPFX")
        assert "content" in result
        assert "SpikeFeatureExtractor" in result["content"]
