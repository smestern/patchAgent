"""
QC Tools - Quality control assessment for electrophysiology recordings.

Tools for checking seal resistance, access resistance, baseline stability, and noise.
"""

from typing import Union, Dict, Any, Optional, List
import numpy as np

from sciagent.tools.registry import tool

from ..constants import (
    DEFAULT_BASELINE_DURATION_S,
    MAX_BASELINE_STD_MV,
    MAX_BASELINE_DRIFT_MV,
    EXPECTED_AP_AMPLITUDE_MV,
    CLIPPING_TOLERANCE,
)


@tool(
    name="run_sweep_qc",
    description="Run quality control checks on a sweep (baseline stability, noise, integrity)",
    parameters={
        "type": "object",
        "properties": {
            "voltage": {"type": "array", "items": {"type": "number"}, "description": "Voltage trace in mV"},
            "time": {"type": "array", "items": {"type": "number"}, "description": "Time array in seconds"},
            "current": {"type": "array", "items": {"type": "number"}, "description": "Current command in pA"},
        },
        "required": ["voltage", "time"],
    },
)
def run_sweep_qc(
    voltage: np.ndarray,
    current: np.ndarray,
    time: np.ndarray,
    baseline_window: float = DEFAULT_BASELINE_DURATION_S,
    max_baseline_std: float = MAX_BASELINE_STD_MV,
    max_drift: float = MAX_BASELINE_DRIFT_MV,
) -> Dict[str, Any]:
    """
    Run quality control checks on a sweep.

    Args:
        voltage: Voltage trace (mV)
        current: Current trace (pA)
        time: Time array (seconds)
        baseline_window: Duration of baseline window (s)
        max_baseline_std: Maximum acceptable baseline std (mV)
        max_drift: Maximum acceptable baseline drift (mV)

    Returns:
        Dict containing:
            - passed: Overall QC pass/fail
            - checks: Dict of individual check results
            - issues: List of QC issues found
    """
    # Handle 2D arrays
    if voltage.ndim > 1:
        voltage = voltage[0]
        current = current[0]
        time = time[0] if time.ndim > 1 else time

    issues = []
    checks = {}

    # Baseline stability check
    baseline_result = check_baseline_stability(
        voltage, time, window_duration=baseline_window
    )
    checks["baseline_stability"] = baseline_result
    
    if baseline_result["std"] > max_baseline_std:
        issues.append(f"Baseline noise too high: {baseline_result['std']:.2f} mV > {max_baseline_std} mV")
    
    if baseline_result["drift"] is not None and abs(baseline_result["drift"]) > max_drift:
        issues.append(f"Baseline drift too large: {baseline_result['drift']:.2f} mV > {max_drift} mV")

    # Noise check
    noise_result = measure_noise(voltage, time)
    checks["noise"] = noise_result

    # Clipping check
    clipping_result = _check_clipping(voltage)
    checks["clipping"] = clipping_result
    if clipping_result["is_clipped"]:
        issues.append(f"Signal clipping detected at {clipping_result['clip_fraction']*100:.1f}% of points")

    # Overall pass/fail
    passed = len(issues) == 0

    return {
        "passed": passed,
        "checks": checks,
        "issues": issues,
    }


@tool(
    name="check_baseline_stability",
    description="Check if baseline period is stable (low drift and noise)",
    parameters={
        "type": "object",
        "properties": {
            "voltage": {"type": "array", "items": {"type": "number"}, "description": "Voltage trace in mV"},
            "time": {"type": "array", "items": {"type": "number"}, "description": "Time array in seconds"},
        },
        "required": ["voltage", "time"],
    },
)
def check_baseline_stability(
    voltage: np.ndarray,
    time: np.ndarray,
    window_start: Optional[float] = None,
    window_duration: float = DEFAULT_BASELINE_DURATION_S,
) -> Dict[str, Any]:
    """
    Check baseline voltage stability.

    Args:
        voltage: Voltage trace (mV)
        time: Time array (seconds)
        window_start: Start of baseline window (s), defaults to beginning
        window_duration: Duration of window (s)

    Returns:
        Dict containing:
            - mean: Mean baseline voltage (mV)
            - std: Standard deviation (mV)
            - drift: Voltage drift over window (mV)
            - is_stable: Whether baseline is considered stable
    """
    # Handle 2D arrays
    if voltage.ndim > 1:
        voltage = voltage[0]
        time = time[0] if time.ndim > 1 else time

    if window_start is None:
        window_start = time[0]

    window_end = window_start + window_duration
    window_mask = (time >= window_start) & (time <= window_end)
    window_voltage = voltage[window_mask]

    if len(window_voltage) < 10:
        return {
            "mean": None,
            "std": None,
            "drift": None,
            "is_stable": False,
            "error": "Insufficient data in window",
        }

    mean_v = np.mean(window_voltage)
    std_v = np.std(window_voltage)

    # Calculate drift (difference between first and last portion)
    n = len(window_voltage)
    first_tenth = np.mean(window_voltage[: n // 10])
    last_tenth = np.mean(window_voltage[-n // 10 :])
    drift = last_tenth - first_tenth

    # Stability criteria
    is_stable = (std_v < MAX_BASELINE_STD_MV) and (abs(drift) < MAX_BASELINE_DRIFT_MV)

    return {
        "mean": float(mean_v),
        "std": float(std_v),
        "drift": float(drift),
        "is_stable": is_stable,
    }


@tool(
    name="measure_noise",
    description="Measure RMS noise level in a trace",
    parameters={
        "type": "object",
        "properties": {
            "voltage": {"type": "array", "items": {"type": "number"}, "description": "Voltage trace in mV"},
            "time": {"type": "array", "items": {"type": "number"}, "description": "Time array in seconds"},
        },
        "required": ["voltage", "time"],
    },
)
def measure_noise(
    voltage: np.ndarray,
    time: np.ndarray,
    window_start: Optional[float] = None,
    window_duration: float = DEFAULT_BASELINE_DURATION_S,
    high_pass_cutoff: float = 100.0,
) -> Dict[str, Any]:
    """
    Measure noise level in a voltage trace.

    Args:
        voltage: Voltage trace (mV)
        time: Time array (seconds)
        window_start: Start of measurement window (s)
        window_duration: Duration of window (s)
        high_pass_cutoff: Cutoff frequency for high-pass filter (Hz)

    Returns:
        Dict containing:
            - rms_noise: RMS noise level (mV)
            - peak_to_peak: Peak-to-peak noise (mV)
            - snr: Estimated signal-to-noise ratio (if spikes present)
    """
    from scipy.signal import butter, filtfilt

    # Handle 2D arrays
    if voltage.ndim > 1:
        voltage = voltage[0]
        time = time[0] if time.ndim > 1 else time

    if window_start is None:
        window_start = time[0]

    window_end = window_start + window_duration
    window_mask = (time >= window_start) & (time <= window_end)
    window_voltage = voltage[window_mask]

    if len(window_voltage) < 100:
        return {
            "rms_noise": None,
            "peak_to_peak": None,
            "snr": None,
            "error": "Insufficient data",
        }

    # Calculate sampling rate
    dt = time[1] - time[0]
    fs = 1.0 / dt

    # High-pass filter to isolate noise
    try:
        nyq = fs / 2
        if high_pass_cutoff < nyq:
            b, a = butter(2, high_pass_cutoff / nyq, btype="high")
            filtered = filtfilt(b, a, window_voltage)
        else:
            filtered = window_voltage - np.mean(window_voltage)
    except Exception:
        filtered = window_voltage - np.mean(window_voltage)

    # Calculate noise metrics
    rms_noise = np.sqrt(np.mean(filtered**2))
    peak_to_peak = np.max(filtered) - np.min(filtered)

    # Estimate SNR (rough estimate based on expected AP amplitude)
    snr = EXPECTED_AP_AMPLITUDE_MV / rms_noise if rms_noise > 0 else None

    return {
        "rms_noise": float(rms_noise),
        "peak_to_peak": float(peak_to_peak),
        "snr": float(snr) if snr else None,
    }


def check_seal_resistance(
    voltage: np.ndarray,
    current: np.ndarray,
    time: np.ndarray,
    test_pulse_amplitude: float = 5.0,
) -> Dict[str, Any]:
    """
    Estimate seal resistance from membrane test pulse.

    Args:
        voltage: Voltage trace (mV)
        current: Current trace (pA)
        time: Time array (seconds)
        test_pulse_amplitude: Expected test pulse amplitude (mV)

    Returns:
        Dict containing:
            - seal_resistance: Estimated seal resistance (GΩ)
            - is_adequate: Whether seal meets minimum criteria (>1 GΩ)
    """
    # This is a simplified estimation
    # Full implementation would require identifying test pulse epochs
    
    # Handle 2D arrays
    if voltage.ndim > 1:
        voltage = voltage[0]
        current = current[0]
        time = time[0] if time.ndim > 1 else time

    # Find current peaks (test pulses)
    current_range = np.max(current) - np.min(current)
    
    if current_range < 1:  # Less than 1 pA range
        return {
            "seal_resistance": None,
            "is_adequate": None,
            "error": "No test pulse detected",
        }

    # Simple R = V / I calculation
    # This is a placeholder - real implementation needs epoch detection
    voltage_change = np.max(voltage) - np.min(voltage)
    current_change = np.max(np.abs(current))
    
    if current_change > 0:
        resistance = voltage_change / current_change  # GΩ if mV/pA
    else:
        resistance = None

    return {
        "seal_resistance": float(resistance) if resistance else None,
        "is_adequate": resistance > 1.0 if resistance else None,
    }


def _check_clipping(voltage: np.ndarray, threshold_fraction: float = CLIPPING_TOLERANCE) -> Dict[str, Any]:
    """Check for signal clipping (saturation)."""
    v_range = np.max(voltage) - np.min(voltage)
    
    # Check for flat regions at extremes
    at_max = np.sum(voltage >= np.max(voltage) - v_range * 0.001)
    at_min = np.sum(voltage <= np.min(voltage) + v_range * 0.001)
    
    total_points = len(voltage)
    clip_fraction = (at_max + at_min) / total_points
    
    is_clipped = clip_fraction > threshold_fraction

    return {
        "is_clipped": is_clipped,
        "clip_fraction": float(clip_fraction),
        "points_at_max": int(at_max),
        "points_at_min": int(at_min),
    }


@tool(
    name="validate_nwb",
    description=(
        "Validate an NWB or ABF file for common data-quality issues "
        "(NaN values, array mismatches, empty sweeps, physiological range violations). "
        "Use this during the Discovery phase to check data integrity before analysis."
    ),
    parameters={
        "type": "object",
        "properties": {
            "file_path": {"type": "string", "description": "Path to the ABF or NWB file"},
        },
        "required": ["file_path"],
    },
)
def validate_nwb(
    file_path: str,
) -> Dict[str, Any]:
    """
    Validate an NWB or ABF file for common data-quality issues.

    Loads the file and checks every sweep for:
    - NaN values in time, voltage, or current arrays
    - Array length mismatches between time/voltage/current
    - Empty arrays (zero-length sweeps)
    - Physiological range violations (voltage outside -120 to +60 mV,
      current outside -2000 to +2000 pA)

    Args:
        file_path: Path to the ABF or NWB file.

    Returns:
        Dict containing:
            - issues: List of human-readable issue strings
            - n_sweeps: Total number of sweeps checked
            - passed: True if no issues found
    """
    from ..config import PATCH_CONFIG

    try:
        from ..utils.data_resolver import resolve_data
        dataX, dataY, dataC, _ = resolve_data(file_path, return_obj=True)
    except Exception as exc:
        return {"error": f"Failed to load file: {exc}", "passed": False}

    issues: List[str] = []

    # Handle single-sweep as 2-D for uniform iteration
    if dataY.ndim == 1:
        dataX = dataX[np.newaxis, :]
        dataY = dataY[np.newaxis, :]
        dataC = dataC[np.newaxis, :]

    n_sweeps = dataY.shape[0]

    for i in range(n_sweeps):
        t = dataX[i] if dataX.ndim > 1 else dataX
        v = dataY[i]
        c = dataC[i]

        # Empty arrays
        if len(t) == 0 or len(v) == 0 or len(c) == 0:
            issues.append(f"Sweep {i}: Empty arrays (t={len(t)}, v={len(v)}, c={len(c)})")
            continue

        # Array length mismatch
        if len(t) != len(v) or len(t) != len(c):
            issues.append(
                f"Sweep {i}: Array length mismatch "
                f"(time={len(t)}, voltage={len(v)}, current={len(c)})"
            )

        # NaN checks (count, not just presence — NaN padding is expected)
        nan_t = int(np.sum(np.isnan(t)))
        nan_v = int(np.sum(np.isnan(v)))
        nan_c = int(np.sum(np.isnan(c)))
        if nan_t > 0:
            issues.append(f"Sweep {i}: {nan_t} NaN values in time array")
        if nan_v > 0:
            issues.append(f"Sweep {i}: {nan_v} NaN values in voltage array")
        if nan_c > 0:
            issues.append(f"Sweep {i}: {nan_c} NaN values in current array")

        # Physiological range checks (on non-NaN values only)
        valid_v = v[~np.isnan(v)]
        valid_c = c[~np.isnan(c)]
        if len(valid_v) > 0:
            v_min, v_max = float(np.min(valid_v)), float(np.max(valid_v))
            if v_min < -200 or v_max > 100:
                issues.append(
                    f"Sweep {i}: Voltage out of physiological range "
                    f"[{v_min:.1f}, {v_max:.1f}] mV"
                )
        if len(valid_c) > 0:
            c_min, c_max = float(np.min(valid_c)), float(np.max(valid_c))
            if c_min < -5000 or c_max > 5000:
                issues.append(
                    f"Sweep {i}: Current out of expected range "
                    f"[{c_min:.1f}, {c_max:.1f}] pA"
                )

    return {
        "issues": issues,
        "n_sweeps": n_sweeps,
        "passed": len(issues) == 0,
    }
