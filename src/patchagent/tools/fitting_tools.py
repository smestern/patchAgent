"""
Fitting Tools — Curve fitting for electrophysiology analysis.

Generic fits (exponential, double-exponential) are re-exported from
``sciagent.tools.fitting_tools``.  Domain-specific fits (IV curves,
f-I relationships) are defined here.
"""

from typing import Union, Dict, Any, Optional, List, Tuple
import numpy as np
from scipy.optimize import curve_fit

from sciagent.tools.registry import tool

# ── Re-export generic fits from sciagent ────────────────────────────────────────
from sciagent.tools.fitting_tools import (  # noqa: F401
    fit_exponential,
    fit_double_exponential,
)


@tool(
    name="fit_iv_curve",
    description="Fit IV curve to extract conductance and reversal potential",
    parameters={
        "type": "object",
        "properties": {
            "currents": {"type": "array", "items": {"type": "number"}, "description": "Current values in pA"},
            "voltages": {"type": "array", "items": {"type": "number"}, "description": "Voltage values in mV"},
        },
        "required": ["currents", "voltages"],
    },
)
def fit_iv_curve(
    voltages: np.ndarray,
    currents: np.ndarray,
    fit_type: str = "linear",
    voltage_range: Optional[Tuple[float, float]] = None,
) -> Dict[str, Any]:
    """
    Fit I-V (current-voltage) relationship.

    Args:
        voltages: Array of voltage values (mV)
        currents: Array of current values (pA)
        fit_type: 'linear' or 'polynomial'
        voltage_range: Optional (min, max) voltage range for fitting

    Returns:
        Dict containing:
            - slope: Conductance (pA/mV = nS)
            - intercept: Reversal potential or offset
            - r_squared: Goodness of fit
            - reversal_potential: Estimated reversal potential (mV)
            - input_resistance: Derived Rm (MΩ)
    """
    # Apply voltage range filter
    if voltage_range is not None:
        mask = (voltages >= voltage_range[0]) & (voltages <= voltage_range[1])
        voltages = voltages[mask]
        currents = currents[mask]

    if len(voltages) < 2:
        return {
            "slope": None,
            "intercept": None,
            "r_squared": None,
            "reversal_potential": None,
            "input_resistance": None,
            "error": "Insufficient data points",
        }

    if fit_type == "linear":
        # Linear fit: I = g * (V - E_rev) = g*V - g*E_rev
        # So: I = slope * V + intercept
        # slope = g (conductance), intercept = -g * E_rev
        coeffs = np.polyfit(voltages, currents, 1)
        slope, intercept = coeffs

        # Calculate fitted values
        fitted = np.polyval(coeffs, voltages)

        # R²
        ss_res = np.sum((currents - fitted)**2)
        ss_tot = np.sum((currents - np.mean(currents))**2)
        r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0

        # Reversal potential (where I = 0)
        if abs(slope) > 1e-10:
            reversal_potential = -intercept / slope
        else:
            reversal_potential = None

        # Input resistance (1/conductance), convert nS to MΩ
        if abs(slope) > 1e-10:
            input_resistance = 1000 / abs(slope)  # MΩ
        else:
            input_resistance = None

        return {
            "slope": float(slope),
            "intercept": float(intercept),
            "r_squared": float(r_squared),
            "reversal_potential": float(reversal_potential) if reversal_potential else None,
            "input_resistance": float(input_resistance) if input_resistance else None,
            "fit_type": "linear",
            "fitted_values": fitted,
        }

    elif fit_type == "polynomial":
        # Polynomial fit for non-linear IV curves
        coeffs = np.polyfit(voltages, currents, 3)
        fitted = np.polyval(coeffs, voltages)

        ss_res = np.sum((currents - fitted)**2)
        ss_tot = np.sum((currents - np.mean(currents))**2)
        r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0

        # Find zero crossing for reversal potential
        v_fine = np.linspace(voltages.min(), voltages.max(), 1000)
        i_fine = np.polyval(coeffs, v_fine)
        zero_crossings = np.where(np.diff(np.sign(i_fine)))[0]
        
        if len(zero_crossings) > 0:
            reversal_potential = v_fine[zero_crossings[0]]
        else:
            reversal_potential = None

        return {
            "coefficients": coeffs.tolist(),
            "r_squared": float(r_squared),
            "reversal_potential": float(reversal_potential) if reversal_potential else None,
            "fit_type": "polynomial",
            "fitted_values": fitted,
        }

    else:
        return {"error": f"Unknown fit_type: {fit_type}"}


@tool(
    name="fit_fi_curve",
    description="Fit f-I curve to extract gain and rheobase",
    parameters={
        "type": "object",
        "properties": {
            "currents": {"type": "array", "items": {"type": "number"}, "description": "Current steps in pA"},
            "firing_rates": {"type": "array", "items": {"type": "number"}, "description": "Firing rates in Hz"},
        },
        "required": ["currents", "firing_rates"],
    },
)
def fit_fi_curve(
    currents: np.ndarray,
    firing_rates: np.ndarray,
    fit_type: str = "linear",
    current_range: Optional[Tuple[float, float]] = None,
) -> Dict[str, Any]:
    """
    Fit f-I (frequency-current) relationship.

    Args:
        currents: Array of injected current values (pA)
        firing_rates: Array of firing rates (Hz)
        fit_type: 'linear', 'sigmoid', or 'sqrt'
        current_range: Optional (min, max) current range for fitting

    Returns:
        Dict containing:
            - gain: f-I gain (Hz/pA)
            - rheobase: Estimated rheobase current (pA)
            - r_squared: Goodness of fit
            - max_rate: Maximum firing rate
            - fitted_values: Fitted firing rate values
    """
    # Apply current range filter
    if current_range is not None:
        mask = (currents >= current_range[0]) & (currents <= current_range[1])
        currents = currents[mask]
        firing_rates = firing_rates[mask]

    if len(currents) < 2:
        return {
            "gain": None,
            "rheobase": None,
            "r_squared": None,
            "max_rate": None,
            "fitted_values": None,
            "error": "Insufficient data points",
        }

    # Find rheobase (first current with firing)
    firing_mask = firing_rates > 0
    if np.any(firing_mask):
        rheobase = currents[firing_mask].min()
    else:
        rheobase = None

    if fit_type == "linear":
        # Only fit suprathreshold portion
        if rheobase is not None:
            supra_mask = currents >= rheobase
            if np.sum(supra_mask) < 2:
                supra_mask = firing_rates > 0
        else:
            supra_mask = firing_rates > 0

        if np.sum(supra_mask) < 2:
            return {
                "gain": None,
                "rheobase": float(rheobase) if rheobase else None,
                "r_squared": None,
                "max_rate": float(np.max(firing_rates)),
                "fitted_values": None,
                "error": "Insufficient suprathreshold data",
            }

        currents_fit = currents[supra_mask]
        rates_fit = firing_rates[supra_mask]

        coeffs = np.polyfit(currents_fit, rates_fit, 1)
        gain, intercept = coeffs

        fitted = np.polyval(coeffs, currents_fit)

        ss_res = np.sum((rates_fit - fitted)**2)
        ss_tot = np.sum((rates_fit - np.mean(rates_fit))**2)
        r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0

        # Full fitted curve (including subthreshold = 0)
        fitted_full = np.maximum(0, np.polyval(coeffs, currents))

        return {
            "gain": float(gain),
            "rheobase": float(rheobase) if rheobase else None,
            "r_squared": float(r_squared),
            "max_rate": float(np.max(firing_rates)),
            "fitted_values": fitted_full,
            "fit_type": "linear",
        }

    elif fit_type == "sqrt":
        # Square root fit: f = k * sqrt(I - I_rheo)
        if rheobase is None:
            rheobase = 0

        supra_mask = currents > rheobase
        if np.sum(supra_mask) < 2:
            return {
                "gain": None,
                "rheobase": float(rheobase),
                "r_squared": None,
                "max_rate": float(np.max(firing_rates)),
                "fitted_values": None,
                "error": "Insufficient suprathreshold data",
            }

        currents_fit = currents[supra_mask] - rheobase
        rates_fit = firing_rates[supra_mask]

        def sqrt_func(i, k):
            return k * np.sqrt(i)

        try:
            popt, _ = curve_fit(sqrt_func, currents_fit, rates_fit)
            k = popt[0]

            fitted = sqrt_func(currents_fit, k)
            ss_res = np.sum((rates_fit - fitted)**2)
            ss_tot = np.sum((rates_fit - np.mean(rates_fit))**2)
            r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0

            # Full curve
            fitted_full = np.zeros_like(currents, dtype=float)
            fitted_full[supra_mask] = sqrt_func(currents[supra_mask] - rheobase, k)

            return {
                "gain_coefficient": float(k),
                "rheobase": float(rheobase),
                "r_squared": float(r_squared),
                "max_rate": float(np.max(firing_rates)),
                "fitted_values": fitted_full,
                "fit_type": "sqrt",
            }

        except Exception as e:
            return {
                "gain": None,
                "rheobase": float(rheobase),
                "r_squared": None,
                "max_rate": float(np.max(firing_rates)),
                "fitted_values": None,
                "error": str(e),
            }

    else:
        return {"error": f"Unknown fit_type: {fit_type}"}



# fit_double_exponential is re-exported from sciagent (see top of file)
