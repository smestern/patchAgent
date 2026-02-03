"""
Fitting Tools - Curve fitting for electrophysiology analysis.

Tools for exponential fits, IV curves, and f-I relationships.
"""

from typing import Union, Dict, Any, Optional, List, Tuple
import numpy as np
from scipy.optimize import curve_fit


def fit_exponential(
    y: np.ndarray,
    x: np.ndarray,
    fit_type: str = "decay",
    p0: Optional[List[float]] = None,
) -> Dict[str, Any]:
    """
    Fit exponential decay or growth to data.

    Args:
        y: Y values (e.g., voltage)
        x: X values (e.g., time)
        fit_type: 'decay' or 'growth'
        p0: Initial parameter guess [amplitude, tau, offset]

    Returns:
        Dict containing:
            - amplitude: Exponential amplitude
            - tau: Time constant
            - offset: Baseline offset
            - r_squared: Goodness of fit
            - fitted_values: Fitted y values
    """
    if fit_type == "decay":
        def exp_func(t, amp, tau, offset):
            return amp * np.exp(-t / tau) + offset
    else:  # growth
        def exp_func(t, amp, tau, offset):
            return amp * (1 - np.exp(-t / tau)) + offset

    # Normalize x to start at 0
    x_norm = x - x[0]

    # Initial guess
    if p0 is None:
        amp_guess = y[0] - y[-1] if fit_type == "decay" else y[-1] - y[0]
        tau_guess = (x[-1] - x[0]) / 3
        offset_guess = y[-1] if fit_type == "decay" else y[0]
        p0 = [amp_guess, tau_guess, offset_guess]

    try:
        # Bounds to keep tau positive
        bounds = ([-np.inf, 1e-6, -np.inf], [np.inf, np.inf, np.inf])
        popt, pcov = curve_fit(exp_func, x_norm, y, p0=p0, bounds=bounds, maxfev=5000)
        
        amp, tau, offset = popt

        # Calculate R²
        y_fit = exp_func(x_norm, *popt)
        residuals = y - y_fit
        ss_res = np.sum(residuals**2)
        ss_tot = np.sum((y - np.mean(y))**2)
        r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0

        return {
            "amplitude": float(amp),
            "tau": float(tau),
            "offset": float(offset),
            "r_squared": float(r_squared),
            "fitted_values": y_fit,
            "success": True,
        }

    except Exception as e:
        return {
            "amplitude": None,
            "tau": None,
            "offset": None,
            "r_squared": None,
            "fitted_values": None,
            "success": False,
            "error": str(e),
        }


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
        raise ValueError(f"Unknown fit_type: {fit_type}")


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
        raise ValueError(f"Unknown fit_type: {fit_type}")


def fit_double_exponential(
    y: np.ndarray,
    x: np.ndarray,
    p0: Optional[List[float]] = None,
) -> Dict[str, Any]:
    """
    Fit double exponential decay to data.

    y = A1 * exp(-x/tau1) + A2 * exp(-x/tau2) + offset

    Args:
        y: Y values
        x: X values
        p0: Initial guess [A1, tau1, A2, tau2, offset]

    Returns:
        Dict containing fit parameters and quality metrics
    """
    def double_exp(t, a1, tau1, a2, tau2, offset):
        return a1 * np.exp(-t / tau1) + a2 * np.exp(-t / tau2) + offset

    x_norm = x - x[0]

    if p0 is None:
        # Initial guesses
        amp_total = y[0] - y[-1]
        p0 = [amp_total * 0.7, (x[-1] - x[0]) / 5,
              amp_total * 0.3, (x[-1] - x[0]) / 2,
              y[-1]]

    try:
        bounds = ([0, 1e-6, 0, 1e-6, -np.inf],
                  [np.inf, np.inf, np.inf, np.inf, np.inf])
        popt, pcov = curve_fit(double_exp, x_norm, y, p0=p0, bounds=bounds, maxfev=10000)

        a1, tau1, a2, tau2, offset = popt

        # Ensure tau1 < tau2 (fast and slow components)
        if tau1 > tau2:
            a1, a2 = a2, a1
            tau1, tau2 = tau2, tau1

        y_fit = double_exp(x_norm, *popt)
        ss_res = np.sum((y - y_fit)**2)
        ss_tot = np.sum((y - np.mean(y))**2)
        r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0

        return {
            "amplitude_fast": float(a1),
            "tau_fast": float(tau1),
            "amplitude_slow": float(a2),
            "tau_slow": float(tau2),
            "offset": float(offset),
            "r_squared": float(r_squared),
            "fitted_values": y_fit,
            "success": True,
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }
