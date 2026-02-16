"""
patchAgent constants — single source of truth for magic numbers and defaults.

All domain-specific constants live here.  Import from this module instead
of hardcoding values across tools, config, and prompts.
"""

from __future__ import annotations

# ── Model ───────────────────────────────────────────────────────────
DEFAULT_MODEL: str = "GPT-5.3-Codex"

# ── Physiological bounds ────────────────────────────────────────────
# Canonical ranges for patch-clamp parameters.
# Used by config.py (AgentConfig.bounds), code_tools.py (BoundsChecker),
# and system_messages.py (SANITY_CHECKS prompt table).
PHYSIOLOGICAL_BOUNDS: dict[str, tuple[float, float]] = {
    "input_resistance_MOhm":      (10, 2000),
    "membrane_time_constant_ms":  (1, 200),
    "resting_potential_mV":       (-100, -30),
    "sag_ratio":                  (0, 1),
    "capacitance_pF":             (5, 500),
    "access_resistance_MOhm":     (1, 40),
    "series_resistance_MOhm":     (1, 100),
    "spike_threshold_mV":         (-60, -10),
    "spike_amplitude_mV":         (30, 140),
    "spike_width_ms":             (0.1, 5),
    "rheobase_pA":                (0, 2000),
    "max_firing_rate_Hz":         (0, 500),
    "adaptation_ratio":           (0, 2),
    "holding_current_pA":         (-500, 500),
}

# ── Analysis defaults ───────────────────────────────────────────────
DEFAULT_BASELINE_DURATION_S: float = 0.1       # 100 ms
DEFAULT_SAMPLE_RATE_HZ: float = 10_000.0       # 10 kHz (typical patch-clamp)
DEFAULT_WEB_PORT: int = 8080
EXPECTED_AP_AMPLITUDE_MV: float = 80.0         # used for SNR estimate
CLIPPING_TOLERANCE: float = 0.001              # fraction for clipping detection

# ── QC thresholds ───────────────────────────────────────────────────
MAX_BASELINE_STD_MV: float = 2.0
MAX_BASELINE_DRIFT_MV: float = 5.0

# ── Prompt helpers ──────────────────────────────────────────────────
# Human-readable labels for the SANITY_CHECKS prompt table.
# Maps bound key → (display_name, units).
_BOUNDS_DISPLAY: dict[str, tuple[str, str]] = {
    "input_resistance_MOhm":      ("Input resistance",      "MΩ"),
    "membrane_time_constant_ms":  ("Time constant",         "ms"),
    "resting_potential_mV":       ("Resting potential",      "mV"),
    "sag_ratio":                  ("Sag ratio",              "–"),
    "capacitance_pF":             ("Membrane capacitance",   "pF"),
    "access_resistance_MOhm":     ("Access resistance",      "MΩ"),
    "series_resistance_MOhm":     ("Series resistance",      "MΩ"),
    "spike_threshold_mV":         ("Spike threshold",        "mV"),
    "spike_amplitude_mV":         ("AP amplitude",           "mV"),
    "spike_width_ms":             ("Spike width",            "ms"),
    "rheobase_pA":                ("Rheobase",               "pA"),
    "max_firing_rate_Hz":         ("Max firing rate",        "Hz"),
    "adaptation_ratio":           ("Adaptation ratio",       "–"),
    "holding_current_pA":         ("Holding current",        "pA"),
}


def bounds_as_markdown_table() -> str:
    """Render ``PHYSIOLOGICAL_BOUNDS`` as a Markdown table for prompts."""
    lines = ["| Parameter | Typical Range | Units |", "|-----------|---------------|-------|"]
    for key, (lo, hi) in PHYSIOLOGICAL_BOUNDS.items():
        display, units = _BOUNDS_DISPLAY.get(key, (key, ""))
        lines.append(f"| {display} | {lo}–{hi} | {units} |")
    return "\n".join(lines)
