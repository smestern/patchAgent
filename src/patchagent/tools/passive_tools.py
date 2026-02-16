"""
Passive Tools - Subthreshold membrane property analysis.

Tools for calculating input resistance, time constant, sag, and capacitance.
"""

from typing import Union, Dict, Any, Optional, Tuple
import numpy as np
from scipy.optimize import curve_fit

from sciagent.tools.registry import tool


@tool(
    name="calculate_input_resistance",
    description="Calculate input resistance from a hyperpolarizing current step (Rm = ΔV/ΔI)",
    parameters={
        "type": "object",
        "properties": {
            "voltage": {"type": "array", "items": {"type": "number"}, "description": "Voltage trace in mV"},
            "current": {"type": "array", "items": {"type": "number"}, "description": "Current command in pA"},
            "time": {"type": "array", "items": {"type": "number"}, "description": "Time array in seconds"},
        },
        "required": ["voltage", "current", "time"],
    },
)
def calculate_input_resistance(
    voltage: np.ndarray,
    current: np.ndarray,
    time: np.ndarray,
    baseline_start: Optional[float] = None,
    baseline_end: Optional[float] = None,
    response_start: Optional[float] = None,
    response_end: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Calculate input resistance from voltage response to current step.

    Args:
        voltage: Voltage trace (mV), can be 1D (single sweep) or 2D (multiple sweeps)
        current: Current trace (pA)
        time: Time array (seconds)
        baseline_start: Start time for baseline measurement (s)
        baseline_end: End time for baseline measurement (s)
        response_start: Start time for response measurement (s)
        response_end: End time for response measurement (s)

    Returns:
        Dict containing:
            - input_resistance: Rm in MΩ
            - voltage_deflection: Steady-state voltage change (mV)
            - current_amplitude: Current step amplitude (pA)
            - baseline_voltage: Baseline voltage (mV)
    """
    # Handle 2D arrays (use first sweep)
    if voltage.ndim > 1:
        voltage = voltage[0]
        current = current[0]
        time = time[0] if time.ndim > 1 else time

    # Default time windows
    if baseline_start is None:
        baseline_start = time[0]
    if baseline_end is None:
        baseline_end = time[0] + 0.1  # First 100 ms
    if response_start is None:
        # Find when current changes
        current_change_idx = _find_stim_start(current)
        if current_change_idx is not None:
            response_start = time[current_change_idx] + 0.1  # 100 ms after step
        else:
            response_start = time[int(len(time) * 0.6)]
    if response_end is None:
        response_end = response_start + 0.1

    # Get indices
    baseline_mask = (time >= baseline_start) & (time <= baseline_end)
    response_mask = (time >= response_start) & (time <= response_end)

    # Calculate baseline and response
    baseline_v = np.mean(voltage[baseline_mask])
    response_v = np.mean(voltage[response_mask])
    
    # Get current amplitude
    baseline_i = np.mean(current[baseline_mask])
    response_i = np.mean(current[response_mask])
    current_amp = response_i - baseline_i

    # Calculate Rm (V = IR, so R = V/I)
    # Units: mV / pA = GΩ, so multiply by 1000 for MΩ
    voltage_deflection = response_v - baseline_v
    
    if abs(current_amp) < 1e-10:
        return {
            "input_resistance": None,
            "voltage_deflection": float(voltage_deflection),
            "current_amplitude": float(current_amp),
            "baseline_voltage": float(baseline_v),
            "error": "Current amplitude too small",
        }

    input_resistance = (voltage_deflection / current_amp) * 1000  # Convert to MΩ

    return {
        "input_resistance": float(input_resistance),
        "voltage_deflection": float(voltage_deflection),
        "current_amplitude": float(current_amp),
        "baseline_voltage": float(baseline_v),
    }


@tool(
    name="calculate_time_constant",
    description="Fit membrane time constant (tau) from voltage response to current step",
    parameters={
        "type": "object",
        "properties": {
            "voltage": {"type": "array", "items": {"type": "number"}, "description": "Voltage trace in mV"},
            "current": {"type": "array", "items": {"type": "number"}, "description": "Current command in pA"},
            "time": {"type": "array", "items": {"type": "number"}, "description": "Time array in seconds"},
        },
        "required": ["voltage", "current", "time"],
    },
)
def calculate_time_constant(
    voltage: np.ndarray,
    current: np.ndarray,
    time: np.ndarray,
    fit_start: Optional[float] = None,
    fit_duration: float = 0.1,
) -> Dict[str, Any]:
    """
    Calculate membrane time constant from exponential fit to voltage response.

    Args:
        voltage: Voltage trace (mV)
        current: Current trace (pA)
        time: Time array (seconds)
        fit_start: Start time for exponential fit (s), defaults to stim onset
        fit_duration: Duration of fit window (s), default 100 ms

    Returns:
        Dict containing:
            - tau: Membrane time constant (ms)
            - v_rest: Resting/baseline voltage (mV)
            - v_steady: Steady-state voltage (mV)
            - fit_quality: R² of the exponential fit
    """
    # Handle 2D arrays
    if voltage.ndim > 1:
        voltage = voltage[0]
        current = current[0]
        time = time[0] if time.ndim > 1 else time

    # Find stimulus onset
    if fit_start is None:
        stim_idx = _find_stim_start(current)
        if stim_idx is not None:
            fit_start = time[stim_idx]
        else:
            fit_start = time[int(len(time) * 0.2)]

    fit_end = fit_start + fit_duration

    # Get fit window
    fit_mask = (time >= fit_start) & (time <= fit_end)
    fit_time = time[fit_mask] - time[fit_mask][0]  # Normalize to start at 0
    fit_voltage = voltage[fit_mask]

    # Get baseline (before stimulus)
    baseline_mask = time < fit_start
    if np.any(baseline_mask):
        v_rest = np.mean(voltage[baseline_mask][-100:])  # Last 100 points
    else:
        v_rest = voltage[0]

    # Determine if hyperpolarizing or depolarizing
    v_end = fit_voltage[-1]
    is_hyperpol = v_end < v_rest

    # Exponential fit: V(t) = V_steady + (V_rest - V_steady) * exp(-t/tau)
    def exp_func(t, v_steady, tau):
        return v_steady + (v_rest - v_steady) * np.exp(-t / tau)

    try:
        # Initial guess
        p0 = [v_end, 0.02]  # 20 ms initial tau guess
        
        # Bounds
        if is_hyperpol:
            bounds = ([min(fit_voltage) - 20, 0.001], [v_rest + 5, 0.5])
        else:
            bounds = ([v_rest - 5, 0.001], [max(fit_voltage) + 20, 0.5])

        popt, pcov = curve_fit(exp_func, fit_time, fit_voltage, p0=p0, bounds=bounds)
        v_steady, tau = popt

        # Calculate R²
        residuals = fit_voltage - exp_func(fit_time, *popt)
        ss_res = np.sum(residuals**2)
        ss_tot = np.sum((fit_voltage - np.mean(fit_voltage))**2)
        r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0

        return {
            "tau": float(tau * 1000),  # Convert to ms
            "v_rest": float(v_rest),
            "v_steady": float(v_steady),
            "fit_quality": float(r_squared),
        }

    except Exception as e:
        return {
            "tau": None,
            "v_rest": float(v_rest),
            "v_steady": None,
            "fit_quality": None,
            "error": str(e),
        }


@tool(
    name="calculate_sag",
    description="Calculate sag ratio from hyperpolarizing step (Ih indicator)",
    parameters={
        "type": "object",
        "properties": {
            "voltage": {"type": "array", "items": {"type": "number"}, "description": "Voltage trace in mV"},
            "current": {"type": "array", "items": {"type": "number"}, "description": "Current command in pA"},
            "time": {"type": "array", "items": {"type": "number"}, "description": "Time array in seconds"},
        },
        "required": ["voltage", "current", "time"],
    },
)
def calculate_sag(
    voltage: np.ndarray,
    current: np.ndarray,
    time: np.ndarray,
    baseline_start: Optional[float] = None,
    baseline_end: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Calculate sag ratio from hyperpolarizing current step.

    Sag reflects Ih (hyperpolarization-activated current) contribution.
    Sag ratio = (V_peak - V_steady) / (V_peak - V_baseline)

    Args:
        voltage: Voltage trace (mV)
        current: Current trace (pA)
        time: Time array (seconds)
        baseline_start: Start of baseline window (s)
        baseline_end: End of baseline window (s)

    Returns:
        Dict containing:
            - sag_ratio: Sag ratio (0-1, higher = more sag)
            - peak_voltage: Peak hyperpolarization (mV)
            - steady_voltage: Steady-state voltage (mV)
            - baseline_voltage: Baseline voltage (mV)
    """
    # Handle 2D arrays
    if voltage.ndim > 1:
        voltage = voltage[0]
        current = current[0]
        time = time[0] if time.ndim > 1 else time

    # Find stimulus region
    stim_idx = _find_stim_start(current)
    if stim_idx is None:
        stim_idx = int(len(current) * 0.2)

    stim_end_idx = _find_stim_end(current)
    if stim_end_idx is None:
        stim_end_idx = int(len(current) * 0.8)

    # Baseline
    if baseline_start is None:
        baseline_start = time[0]
    if baseline_end is None:
        baseline_end = time[stim_idx] if stim_idx > 10 else time[0] + 0.05

    baseline_mask = (time >= baseline_start) & (time <= baseline_end)
    baseline_v = np.mean(voltage[baseline_mask])

    # Check if hyperpolarizing
    stim_voltage = voltage[stim_idx:stim_end_idx]
    if np.mean(stim_voltage) > baseline_v:
        return {
            "sag_ratio": None,
            "peak_voltage": None,
            "steady_voltage": None,
            "baseline_voltage": float(baseline_v),
            "error": "Not a hyperpolarizing step",
        }

    # Peak (most negative point)
    peak_idx = stim_idx + np.argmin(stim_voltage)
    peak_v = voltage[peak_idx]

    # Steady-state (last 10% of stimulus)
    steady_start = stim_idx + int((stim_end_idx - stim_idx) * 0.9)
    steady_v = np.mean(voltage[steady_start:stim_end_idx])

    # Calculate sag ratio
    peak_deflection = baseline_v - peak_v
    steady_deflection = baseline_v - steady_v

    if peak_deflection > 0:
        sag_ratio = (peak_v - steady_v) / (peak_v - baseline_v)
    else:
        sag_ratio = 0.0

    return {
        "sag_ratio": float(sag_ratio),
        "peak_voltage": float(peak_v),
        "steady_voltage": float(steady_v),
        "baseline_voltage": float(baseline_v),
    }


@tool(
    name="calculate_resting_potential",
    description="Calculate resting membrane potential from baseline period",
    parameters={
        "type": "object",
        "properties": {
            "voltage": {"type": "array", "items": {"type": "number"}, "description": "Voltage trace in mV"},
            "time": {"type": "array", "items": {"type": "number"}, "description": "Time array in seconds"},
        },
        "required": ["voltage", "time"],
    },
)
def calculate_resting_potential(
    voltage: np.ndarray,
    time: np.ndarray,
    window_start: Optional[float] = None,
    window_end: Optional[float] = None,
    method: str = "mean",
) -> Dict[str, Any]:
    """
    Calculate resting membrane potential.

    Args:
        voltage: Voltage trace (mV)
        time: Time array (seconds)
        window_start: Start of measurement window (s)
        window_end: End of measurement window (s)
        method: 'mean', 'median', or 'mode'

    Returns:
        Dict containing:
            - resting_potential: Vm at rest (mV)
            - std: Standard deviation (mV)
            - method: Method used
    """
    # Handle 2D arrays
    if voltage.ndim > 1:
        voltage = voltage[0]
        time = time[0] if time.ndim > 1 else time

    # Default to first 100 ms
    if window_start is None:
        window_start = time[0]
    if window_end is None:
        window_end = time[0] + 0.1

    window_mask = (time >= window_start) & (time <= window_end)
    window_voltage = voltage[window_mask]

    if method == "mean":
        resting_potential = np.mean(window_voltage)
    elif method == "median":
        resting_potential = np.median(window_voltage)
    elif method == "mode":
        # Use histogram-based mode
        hist, bin_edges = np.histogram(window_voltage, bins=50)
        mode_idx = np.argmax(hist)
        resting_potential = (bin_edges[mode_idx] + bin_edges[mode_idx + 1]) / 2
    else:
        return {"error": f"Unknown method: {method}"}

    return {
        "resting_potential": float(resting_potential),
        "std": float(np.std(window_voltage)),
        "method": method,
    }


def _find_stim_start(current: np.ndarray) -> Optional[int]:
    """Find the index where stimulus starts (first significant change)."""
    diff = np.abs(np.diff(current))
    threshold = np.std(diff) * 3
    changes = np.where(diff > threshold)[0]
    if len(changes) > 0:
        return changes[0]
    return None


def _find_stim_end(current: np.ndarray) -> Optional[int]:
    """Find the index where stimulus ends (returns to baseline)."""
    diff = np.abs(np.diff(current))
    threshold = np.std(diff) * 3
    changes = np.where(diff > threshold)[0]
    if len(changes) > 1:
        return changes[-1]
    return None
