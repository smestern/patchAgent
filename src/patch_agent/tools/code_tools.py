"""
Code Tools — patchAgent domain layer over sciagent's generic code sandbox.

This module re-exports generic functions from ``sciagent.tools.code_tools``
and adds electrophysiology-specific:
- Physiological bounds for sanity checking
- Warning patterns for ephys-specific coding pitfalls
- ``get_execution_environment`` with ipfx / loadFile / built-in tools
- Code snippets library for common patch-clamp operations
- ``generate_analysis_code`` template helper

The guardrail scanner and bounds checker are configured at import time
so that ``execute_code`` (from sciagent) automatically enforces the
domain-specific rules.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ── Re-export generic infrastructure from sciagent ──────────────────────
from sciagent.tools.code_tools import (            # noqa: F401 — public API
    SAFE_GLOBALS,
    execute_code,
    get_execution_environment as _base_get_execution_environment,
    get_output_dir,
    get_scanner,
    notify_file_loaded,
    set_file_loaded_hook,
    set_output_dir,
    validate_code,
)
from sciagent.guardrails.bounds import BoundsChecker    # noqa: F401
from sciagent.guardrails.validator import (             # noqa: F401
    SANITY_CHECK_HEADER,
    validate_data_integrity,
)

logger = logging.getLogger(__name__)


# =====================================================================
# Domain-specific: Physiological bounds
# =====================================================================

PHYSIOLOGICAL_BOUNDS = {
    "resting_potential_mV": (-100, -40),       # Typical neuron Vm
    "input_resistance_MOhm": (10, 2000),       # Typical Rm range
    "membrane_tau_ms": (1, 100),               # Membrane time constant
    "spike_threshold_mV": (-60, -20),          # AP threshold
    "spike_amplitude_mV": (40, 140),           # AP amplitude
    "spike_width_ms": (0.1, 5.0),              # AP width at half-max
    "firing_rate_Hz": (0, 500),                # Max physiological rate
    "series_resistance_MOhm": (1, 100),        # Rs
    "capacitance_pF": (1, 500),                # Cell capacitance
    "holding_current_pA": (-500, 500),          # Holding current
}

_bounds_checker = BoundsChecker(PHYSIOLOGICAL_BOUNDS)


def check_physiological_bounds(
    value: float,
    parameter: str,
    custom_bounds: Optional[Tuple[float, float]] = None,
) -> Dict[str, Any]:
    """Check if a measured value is within physiologically plausible bounds.

    Delegates to ``sciagent.guardrails.bounds.BoundsChecker``.

    Args:
        value: The measured value.
        parameter: Name of parameter (key in ``PHYSIOLOGICAL_BOUNDS``).
        custom_bounds: Optional ``(min, max)`` to override defaults.

    Returns:
        Dict with ``valid``, ``value``, ``bounds``, ``warning``.
    """
    return _bounds_checker.check(value, parameter, custom_bounds=custom_bounds)


# =====================================================================
# Domain-specific: Ephys warning patterns (added to sciagent scanner)
# =====================================================================

EPHYS_WARNING_PATTERNS: List[Tuple[str, str]] = [
    (
        r"find_peaks\s*\(\s*voltage|find_peaks\s*\(\s*v[^a]",
        "WARNING: Using scipy find_peaks on voltage traces. "
        "Use the detect_spikes tool or ipfx.spike_detector instead — "
        "dV/dt-based detection is more scientifically appropriate.",
    ),
    (
        r"dvdt.*threshold|dv_dt.*threshold|dv\/dt",
        "WARNING: Custom dV/dt threshold code detected. "
        "Use the detect_spikes tool or ipfx.spike_detector.detect_putative_spikes instead.",
    ),
    (
        r"def\s+detect.*spike|def\s+find.*spike|def\s+spike.*detect",
        "WARNING: Custom spike detection function detected. "
        "Use the detect_spikes tool or ipfx.spike_detector instead.",
    ),
    (
        r"def\s+extract.*spike.*feature|def\s+spike.*feature|def\s+ap_feature",
        "WARNING: Custom spike feature extraction detected. "
        "Use extract_spike_features tool or ipfx.feature_extractor.SpikeFeatureExtractor instead.",
    ),
    (
        r"def\s+calc.*input.*resist|def\s+measure.*resist|def\s+compute.*rm",
        "NOTE: Custom input resistance calculation detected. "
        "Consider using calculate_input_resistance tool or ipfx.subthresh_features first "
        "unless custom fitting is needed.",
    ),
    (
        r"def\s+calc.*tau|def\s+fit.*tau|def\s+membrane.*tau",
        "NOTE: Custom time constant calculation detected. "
        "Consider using calculate_time_constant tool or ipfx.subthresh_features first "
        "unless a specialized fit (e.g., bi-exponential decay) is needed.",
    ),
]

# Register ephys warning patterns with the global scanner at import time
_scanner = get_scanner()
_scanner.add_warning_batch(EPHYS_WARNING_PATTERNS)


# =====================================================================
# Domain-specific: check_scientific_rigor (thin wrapper)
# =====================================================================

def check_scientific_rigor(code: str) -> Dict[str, Any]:
    """Check code for violations of scientific rigor principles.

    Delegates to ``sciagent.tools.code_tools.get_scanner().check(code)``
    which already includes both generic forbidden patterns and the
    ephys-specific warning patterns registered above.

    Args:
        code: Python code to check.

    Returns:
        Dict with ``passed``, ``violations`` (blocking), ``warnings`` (non-blocking).
    """
    return _scanner.check(code)


# =====================================================================
# Domain-specific: execution environment with ipfx + patch_agent tools
# =====================================================================

# Libraries available in the sandbox
AVAILABLE_LIBRARIES = [
    "numpy",
    "pandas",
    "scipy",
    "matplotlib",
    "matplotlib.pyplot",
    "ipfx",
]


def get_execution_environment(
    output_dir: Optional["str | Path"] = None,
) -> Dict[str, Any]:
    """Build a sandboxed execution environment for patch-clamp analysis.

    Extends ``sciagent.tools.code_tools.get_execution_environment`` with
    ipfx, loadFile, and all electrophysiology-specific tools.

    Args:
        output_dir: Optional directory to expose as ``OUTPUT_DIR``.

    Returns:
        Dict of globals for ``exec()``.
    """
    env = _base_get_execution_environment(output_dir=output_dir)

    # ── IPFX electrophysiology library ──────────────────────────────
    try:
        import ipfx
        env["ipfx"] = ipfx
    except ImportError:
        pass

    try:
        from ipfx.spike_detector import detect_putative_spikes, find_peak_indexes
        env["detect_putative_spikes"] = detect_putative_spikes
        env["find_peak_indexes"] = find_peak_indexes
    except ImportError:
        pass

    try:
        from ipfx.feature_extractor import (
            SpikeFeatureExtractor,
            SpikeTrainFeatureExtractor,
        )
        env["SpikeFeatureExtractor"] = SpikeFeatureExtractor
        env["SpikeTrainFeatureExtractor"] = SpikeTrainFeatureExtractor
    except ImportError:
        pass

    try:
        from ipfx import subthresh_features as ipfx_subthresh
        env["ipfx_subthresh"] = ipfx_subthresh
    except ImportError:
        pass

    try:
        from ipfx import stimulus_protocol_analysis as ipfx_protocol
        env["ipfx_protocol"] = ipfx_protocol
    except ImportError:
        pass

    try:
        from ipfx import sweep_props as ipfx_sweep_props
        env["ipfx_sweep_props"] = ipfx_sweep_props
    except ImportError:
        pass

    # ── patch_agent loaders ─────────────────────────────────────────
    try:
        from ..loadFile import loadFile, loadABF, loadNWB, NWBRecording
        env["loadFile"] = loadFile
        env["loadABF"] = loadABF
        env["loadNWB"] = loadNWB
        env["NWBRecording"] = NWBRecording
    except ImportError:
        pass

    try:
        from ..utils.data_resolver import resolve_data, DataResolver
        env["resolve_data"] = resolve_data
        env["DataResolver"] = DataResolver
    except ImportError:
        pass

    # ── Built-in wrapper tools (callable inside execute_code) ───────
    try:
        from .spike_tools import (
            detect_spikes as _detect_spikes,
            extract_spike_features as _extract_spike_features,
            extract_spike_train_features as _extract_spike_train_features,
        )
        env["detect_spikes"] = _detect_spikes
        env["extract_spike_features"] = _extract_spike_features
        env["extract_spike_train_features"] = _extract_spike_train_features
    except ImportError:
        pass

    try:
        from .passive_tools import (
            calculate_input_resistance as _calc_rm,
            calculate_time_constant as _calc_tau,
            calculate_sag as _calc_sag,
            calculate_resting_potential as _calc_vrest,
        )
        env["calculate_input_resistance"] = _calc_rm
        env["calculate_time_constant"] = _calc_tau
        env["calculate_sag"] = _calc_sag
        env["calculate_resting_potential"] = _calc_vrest
    except ImportError:
        pass

    try:
        from .qc_tools import (
            run_sweep_qc as _run_qc,
            check_baseline_stability as _check_baseline,
            measure_noise as _measure_noise,
        )
        env["run_sweep_qc"] = _run_qc
        env["check_baseline_stability"] = _check_baseline
        env["measure_noise"] = _measure_noise
    except ImportError:
        pass

    try:
        from .fitting_tools import (
            fit_exponential as _fit_exp,
            fit_iv_curve as _fit_iv,
            fit_fi_curve as _fit_fi,
        )
        env["fit_exponential"] = _fit_exp
        env["fit_iv_curve"] = _fit_iv
        env["fit_fi_curve"] = _fit_fi
    except ImportError:
        pass

    return env


# =====================================================================
# Domain-specific: run_custom_analysis with loadFile
# =====================================================================

def run_custom_analysis(
    code: str,
    file_path: Optional[str] = None,
    data: Optional[Dict[str, Any]] = None,
    validate_first: bool = True,
) -> Dict[str, Any]:
    """Run custom analysis code, optionally loading a data file first.

    Delegates to ``sciagent.tools.code_tools.run_custom_analysis`` with
    ``load_fn`` set to the patchAgent ``loadFile`` loader.

    Args:
        code: Python code to execute.
        file_path: Optional path to data file to load.
        data: Optional pre-loaded data dict.
        validate_first: Whether to validate code before running.

    Returns:
        Execution result dict.
    """
    from sciagent.tools.code_tools import run_custom_analysis as _generic_run

    load_fn = None
    if file_path:
        try:
            from ..loadFile import loadFile
            load_fn = loadFile
        except ImportError:
            return {
                "success": False,
                "error": "loadFile not available — cannot load data file.",
            }

    return _generic_run(
        code=code,
        file_path=file_path,
        data=data,
        validate_first=validate_first,
        load_fn=load_fn,
    )


# =====================================================================
# Domain-specific: Code generation & snippets
# =====================================================================

def generate_analysis_code(
    task_description: str,
    data_info: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Generate Python code template for a custom analysis task.

    This is a template/helper — actual code generation is done by the LLM.

    Args:
        task_description: Description of the analysis to perform.
        data_info: Information about available data.

    Returns:
        Dict with ``template``, ``available_functions``, ``examples``, ``data_info``.
    """
    template = '''"""
Custom Analysis: {task}
Generated for patch-clamp data analysis
"""

import numpy as np
from scipy import signal, stats

# Data is available as:
# - dataX: time array (n_sweeps, n_samples) in seconds
# - dataY: voltage array (mV) or current array (pA)
# - dataC: command/stimulus array

# Your analysis code here:

# Example: Calculate something for each sweep
results = []
for sweep_idx in range(dataY.shape[0]):
    voltage = dataY[sweep_idx]
    time = dataX[sweep_idx]
    current = dataC[sweep_idx]

    # Your per-sweep analysis...
    result = np.mean(voltage)  # Example
    results.append(result)

# Store final results
analysis_result = {{
    "per_sweep": results,
    "mean": np.mean(results),
    "std": np.std(results),
}}

print(f"Analysis complete: {{analysis_result}}")
'''.format(task=task_description)

    available_functions = [
        "loadFile(path) - Load ABF/NWB file, returns (dataX, dataY, dataC)",
        "loadFile(path, return_obj=True) - Also returns NWBRecording/pyabf obj",
        "loadFile(path, protocol_filter=['Long Square']) - Filter NWB sweeps by protocol",
        "loadFile(path, clamp_mode_filter='CC') - Filter NWB sweeps by clamp mode",
        "resolve_data(data) - Flexible data loading with caching",
        "np.* - Full NumPy library",
        "scipy.signal.* - Signal processing (filters, peaks, etc.)",
        "scipy.stats.* - Statistical functions",
        "scipy.optimize.* - Curve fitting and optimization",
        "pd.DataFrame() - Pandas for tabular data",
        "plt.* - Matplotlib for plotting",
    ]

    examples = {
        "filter_data": '''
# Apply a lowpass Bessel filter
from scipy.signal import bessel, filtfilt
b, a = bessel(4, 1000, btype='low', fs=sample_rate)
filtered = filtfilt(b, a, voltage)
''',
        "find_peaks": '''
# Find peaks in a trace
from scipy.signal import find_peaks
peaks, properties = find_peaks(voltage, height=-20, prominence=10)
peak_times = time[peaks]
peak_heights = voltage[peaks]
''',
        "exponential_fit": '''
# Fit exponential decay
from scipy.optimize import curve_fit

def exp_decay(t, amp, tau, offset):
    return amp * np.exp(-t / tau) + offset

popt, pcov = curve_fit(exp_decay, time, voltage, p0=[10, 0.02, -70])
amplitude, tau, offset = popt
''',
        "baseline_subtraction": '''
# Baseline subtraction
baseline_idx = time < 0.1  # First 100ms
baseline = np.mean(voltage[baseline_idx])
voltage_subtracted = voltage - baseline
''',
        "area_under_curve": '''
# Calculate area under curve (e.g., for charge transfer)
from scipy.integrate import trapezoid
area = trapezoid(current, time)  # pA * s = pC
''',
        "cross_correlation": '''
# Cross-correlation between two signals
from scipy.signal import correlate
correlation = correlate(signal1, signal2, mode='full')
lags = np.arange(-len(signal1)+1, len(signal2))
''',
    }

    return {
        "template": template,
        "available_functions": available_functions,
        "examples": examples,
        "data_info": data_info,
    }


# Code snippets library for common operations
CODE_SNIPPETS = {
    "detect_events": '''
def detect_events(trace, threshold, min_distance=10):
    """Detect threshold crossings in a trace."""
    above = trace > threshold
    crossings = np.where(np.diff(above.astype(int)) == 1)[0]

    # Filter by minimum distance
    if len(crossings) > 1:
        keep = [crossings[0]]
        for c in crossings[1:]:
            if c - keep[-1] >= min_distance:
                keep.append(c)
        crossings = np.array(keep)

    return crossings
''',
    "calculate_derivative": '''
def calculate_derivative(voltage, time):
    """Calculate dV/dt from voltage trace."""
    dt = np.mean(np.diff(time))
    dvdt = np.gradient(voltage, dt)
    return dvdt  # mV/s, divide by 1000 for mV/ms
''',
    "align_to_event": '''
def align_to_event(traces, event_indices, window_before=100, window_after=200):
    """Align traces to detected events."""
    aligned = []
    for trace, events in zip(traces, event_indices):
        for ev in events:
            start = ev - window_before
            end = ev + window_after
            if start >= 0 and end < len(trace):
                aligned.append(trace[start:end])
    return np.array(aligned)
''',
    "measure_rise_time": '''
def measure_rise_time(trace, time, baseline_end, peak_time, pct_low=10, pct_high=90):
    """Measure 10-90% rise time."""
    baseline = np.mean(trace[time < baseline_end])
    peak_idx = np.argmin(np.abs(time - peak_time))
    peak_val = trace[peak_idx]

    amplitude = peak_val - baseline
    thresh_low = baseline + amplitude * (pct_low / 100)
    thresh_high = baseline + amplitude * (pct_high / 100)

    # Find crossing times
    rising = trace[:peak_idx]
    t_low = time[np.where(rising > thresh_low)[0][0]]
    t_high = time[np.where(rising > thresh_high)[0][0]]

    return t_high - t_low
''',
    "spectral_analysis": '''
def spectral_analysis(trace, sample_rate):
    """Compute power spectral density."""
    from scipy.signal import welch
    freqs, psd = welch(trace, fs=sample_rate, nperseg=1024)
    return freqs, psd
''',
}


def get_code_snippet(name: str) -> Optional[str]:
    """Get a code snippet by name."""
    return CODE_SNIPPETS.get(name)


def list_code_snippets() -> List[str]:
    """List available code snippets."""
    return list(CODE_SNIPPETS.keys())
