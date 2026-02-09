"""
PatchAgent domain configuration.

Centralises all patch-clamp-specific settings (branding, bounds,
forbidden patterns, accepted file types, suggestion chips).
"""

from sciagent.config import AgentConfig, SuggestionChip

# Physiological bounds for patch-clamp parameters
PHYSIOLOGICAL_BOUNDS = {
    "input_resistance_MOhm": (10, 2000),
    "membrane_time_constant_ms": (1, 200),
    "resting_potential_mV": (-100, -30),
    "sag_ratio": (0, 1),
    "capacitance_pF": (5, 200),
    "access_resistance_MOhm": (1, 40),
    "spike_threshold_mV": (-60, -10),
    "spike_amplitude_mV": (30, 140),
    "spike_width_ms": (0.1, 5),
    "rheobase_pA": (0, 2000),
    "max_firing_rate_Hz": (0, 500),
    "adaptation_ratio": (0, 2),
}

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
    extra_libraries=[
        "ipfx",
        "pyabf",
        "pynwb",
        "h5py",
    ],
    model="claude-sonnet-4.5",
    output_dir="patchagent_output",
)
