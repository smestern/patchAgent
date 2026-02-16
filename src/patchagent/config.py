"""
PatchAgent domain configuration.

Centralises all patch-clamp-specific settings (branding, bounds,
forbidden patterns, accepted file types, suggestion chips).
"""

from pathlib import Path

from sciagent.config import AgentConfig, SuggestionChip

from .constants import DEFAULT_MODEL, PHYSIOLOGICAL_BOUNDS  # noqa: F401 — re-export

# Resolve docs directory relative to the patchAgent package root
_PACKAGE_ROOT = Path(__file__).resolve().parent.parent.parent
_DOCS_DIR = _PACKAGE_ROOT / "docs"

# Forbidden code patterns (patch-clamp-specific additions)
PATCH_FORBIDDEN_PATTERNS = [
    (r"np\.random\.\w+\(.*\bsize\s*=", "Synthetic data generation"),
    (r"voltage\s*=\s*np\.(random|linspace|arange)", "Synthetic voltage trace"),
    (r"current\s*=\s*np\.(random|linspace|arange)", "Synthetic current trace"),
]

# Warning patterns (patch-clamp-specific)
PATCH_WARNING_PATTERNS = [
    (r"find_peaks.*voltage|find_peaks.*trace", "Use built-in detect_spikes or IPFX instead of find_peaks on voltage"),
    (r"from scipy\.signal import find_peaks", "Use detect_spikes/IPFX for spike detection, not find_peaks"),
]

PATCH_CONFIG = AgentConfig(
    name="patch-analyst",
    display_name="PatchAgent",
    description="AI assistant for patch-clamp electrophysiology analysis",
    instructions="Expert agent for analyzing patch-clamp electrophysiology recordings",
    accepted_file_types=[".abf", ".nwb"],
    logo_emoji="🧪",
    accent_color="#3fb950",
    github_url="https://github.com/smestern/patchAgent",
    suggestion_chips=[
        SuggestionChip("Summarize file", "Load and summarize this recording"),
        SuggestionChip("Detect spikes", "Detect spikes in sweep 0 and extract features"),
        SuggestionChip("Input resistance", "Calculate input resistance from the hyperpolarizing step"),
        SuggestionChip("Run QC", "Run quality control on all sweeps and flag failures"),
        SuggestionChip("Plot voltage", "Plot the voltage trace for sweep 0"),
        SuggestionChip("Fit tau", "Fit the membrane time constant from a subthreshold sweep"),
    ],
    bounds=PHYSIOLOGICAL_BOUNDS,
    forbidden_patterns=PATCH_FORBIDDEN_PATTERNS,
    warning_patterns=PATCH_WARNING_PATTERNS,
    extra_libraries={
        "ipfx": "ipfx",
        "pyabf": "pyabf",
        "pynwb": "pynwb",
        "h5py": "h5py",
    },
    model=DEFAULT_MODEL,
    output_dir="patchagent_output",
    docs_dir=str(_DOCS_DIR),
)
