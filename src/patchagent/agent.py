"""
patchAgent — Domain agent for patch-clamp electrophysiology.

Thin subclass of ``sciagent.BaseScientificAgent`` that registers
electrophysiology-specific tools and system prompts.
"""

import logging
from pathlib import Path
from typing import Optional, List

from sciagent import BaseScientificAgent
from sciagent.config import AgentConfig

from patchagent.config import PATCH_CONFIG
from patchagent.constants import DEFAULT_MODEL

logger = logging.getLogger(__name__)


class PatchAgent(BaseScientificAgent):
    """
    Patch-clamp analysis agent.

    Inherits all generic infrastructure (session lifecycle, code sandbox,
    guardrails) from ``BaseScientificAgent`` and adds electrophysiology-
    specific tools, loaders, and expertise.

    Example:
        >>> agent = PatchAgent()
        >>> await agent.start()
        >>> session = await agent.create_session()
        >>> result = await session.send_and_wait({"prompt": "Load my file.abf"})
        >>> await session.destroy()
        >>> await agent.stop()
    """

    def __init__(
        self,
        config: Optional[AgentConfig] = None,
        model: str = DEFAULT_MODEL,
        log_level: str = "info",
        output_dir: Optional[str | Path] = None,
        protocols_dir: Optional[str | Path] = None,
    ):
        cfg = config or PATCH_CONFIG
        super().__init__(config=cfg, model=model, log_level=log_level, output_dir=output_dir)
        self._protocols_dir = protocols_dir
        self._loaded_protocols: list = []

    # ── Tools ───────────────────────────────────────────────────────

    def _load_tools(self) -> list:
        """Load base tools + electrophysiology-specific tools.

        Uses ``sciagent.tools.registry.collect_tools`` to auto-discover
        ``@tool``-decorated functions in each tools module, eliminating
        the need for hand-maintained JSON schemas.
        """
        from sciagent.tools.registry import collect_tools

        from .tools import io_tools, spike_tools, passive_tools, qc_tools, fitting_tools, code_tools

        # check_physiological_bounds is a plain function (no @tool decorator)
        # so it must be registered manually.  All other re-exported sciagent
        # functions already carry _tool_meta from their @tool decorators and
        # are auto-discovered by collect_tools — do NOT register them twice.
        from .tools import check_physiological_bounds

        tools = []
        seen_names: set[str] = set()

        # ── Auto-collect from decorated modules ─────────────────────
        for module in [io_tools, spike_tools, passive_tools, qc_tools, fitting_tools, code_tools]:
            try:
                for name, desc, handler, params in collect_tools(module):
                    if name in seen_names:
                        logger.debug("Skipping duplicate tool '%s'", name)
                        continue
                    seen_names.add(name)
                    tools.append(self._create_tool(name, desc, handler, params))
            except Exception:
                logger.exception("Failed to collect tools from %s", module.__name__)

        # ── Manually register tools without @tool decorators ──────
        tools.append(
            self._create_tool(
                "check_physiological_bounds",
                "Check if a measured value is within physiologically plausible bounds",
                check_physiological_bounds,
                {
                    "type": "object",
                    "properties": {
                        "value": {"type": "number", "description": "Measured value"},
                        "parameter": {"type": "string", "description": "Parameter name (e.g., 'input_resistance_MOhm')"},
                    },
                    "required": ["value", "parameter"],
                },
            ),
        )

        logger.info("Loaded %d tools", len(tools))
        return tools

    # ── System message ──────────────────────────────────────────────

    def _get_system_message(self) -> str:
        """Get the patch-clamp-specific system message.

        Loads any user-defined protocol YAML files and appends them as
        an extra section so the LLM knows which analyses to recommend.
        """
        from .prompts.system_messages import build_patch_system_message
        from .utils.protocol_loader import (
            load_protocols,
            format_protocols_for_prompt,
        )

        self._loaded_protocols = load_protocols(extra_dir=self._protocols_dir)
        protocols_section = format_protocols_for_prompt(self._loaded_protocols)
        return build_patch_system_message(extra_sections=[protocols_section])

    # ── Execution environment ───────────────────────────────────────

    def _get_execution_environment(self) -> dict:
        """Provide patch-clamp libraries to the code sandbox."""
        env = {}
        try:
            from patchagent.loadFile import loadFile
            env["loadFile"] = loadFile
        except ImportError:
            pass
        try:
            import ipfx
            env["ipfx"] = ipfx
        except ImportError:
            pass
        try:
            import pyabf
            env["pyabf"] = pyabf
        except ImportError:
            pass
        return env

    def _get_script_imports(self) -> list[str]:
        """Return domain-specific imports for the reproducible script."""
        return ["pyabf", "ipfx", "numpy", "scipy", "matplotlib", "pandas"]


def create_agent(
    model: str = DEFAULT_MODEL,
    log_level: str = "info",
    output_dir: Optional[str | Path] = None,
    protocols_dir: Optional[str | Path] = None,
) -> PatchAgent:
    """
    Factory function to create a PatchAgent.

    Args:
        model: The model to use
        log_level: Logging level for the SDK
        output_dir: Directory for saving scripts, plots, and analysis outputs.
        protocols_dir: Optional path to a directory containing protocol YAML files.

    Returns:
        Configured PatchAgent instance
    """
    return PatchAgent(
        model=model,
        log_level=log_level,
        output_dir=output_dir,
        protocols_dir=protocols_dir,
    )
