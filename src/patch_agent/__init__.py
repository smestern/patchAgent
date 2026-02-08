"""
patchAgent - A scientific analysis agent for patch-clamp electrophysiology

Powered by the GitHub Copilot SDK.
"""

__version__ = "0.1.0"

from .loadFile import loadFile, loadABF, loadNWB, NWBRecording

# Agent imports are guarded because the Copilot SDK may not be installed
# in every environment (e.g. when only using the CLI entry-point discovery
# or the direct tool API).
try:
    from .agent import PatchAgent, create_agent, AGENT_CONFIG
except ImportError:
    PatchAgent = None  # type: ignore[assignment,misc]
    create_agent = None  # type: ignore[assignment]
    AGENT_CONFIG = None  # type: ignore[assignment]

__all__ = [
    # Version
    "__version__",
    # File loading
    "loadFile",
    "loadABF",
    "loadNWB",
    "NWBRecording",
    # Agent
    "PatchAgent",
    "create_agent",
    "AGENT_CONFIG",
]
