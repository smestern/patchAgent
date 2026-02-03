"""
patchAgent - A scientific analysis agent for patch-clamp electrophysiology

Powered by the GitHub Copilot SDK.
"""

__version__ = "0.1.0"

from .loadFile import loadFile, loadABF, loadNWB
from .agent import PatchAgent, create_agent, AGENT_CONFIG

__all__ = [
    # Version
    "__version__",
    # File loading
    "loadFile",
    "loadABF",
    "loadNWB",
    # Agent
    "PatchAgent",
    "create_agent",
    "AGENT_CONFIG",
]
