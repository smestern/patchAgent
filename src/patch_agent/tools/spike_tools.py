"""
Spike Tools - Action potential detection and feature extraction.

Wraps IPFX spike detection and feature extraction functionality.
"""

from typing import Union, Dict, Any, List, Optional
import numpy as np


def detect_spikes(
    voltage: np.ndarray,
    time: np.ndarray,
    current: Optional[np.ndarray] = None,
    dv_cutoff: float = 20.0,
    min_peak: float = -30.0,
    min_height: float = 2.0,
    filter_frequency: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Detect action potentials in a voltage trace.

    Args:
        voltage: Voltage trace array (mV)
        time: Time array (seconds)
        current: Current/stimulus array (pA), optional
        dv_cutoff: dV/dt threshold for spike detection (mV/ms), default 20
        min_peak: Minimum peak voltage to count as spike (mV), default -30
        min_height: Minimum height from threshold to peak (mV), default 2
        filter_frequency: Optional filter frequency for smoothing (Hz)

    Returns:
        Dict containing:
            - spike_count: Number of spikes detected
            - spike_times: Array of spike times (seconds)
            - spike_indices: Array of spike peak indices
            - threshold_indices: Array of threshold crossing indices
    """
    try:
        from ipfx.spike_detector import detect_putative_spikes, find_peak_indexes
    except ImportError:
        #logging.warning("IPFX not available, using fallback spike detection")
        print("Warning: IPFX not available, using fallback spike detection")
        #return _detect_spikes_fallback(voltage, time, dv_cutoff, min_peak)

    # Calculate sampling rate
    dt = time[1] - time[0]
    sample_rate = 1.0 / dt

    # Convert dv_cutoff from mV/ms to V/s for IPFX
    dvdt_threshold = dv_cutoff  # IPFX uses mV/ms

    # Detect spikes
    spike_indices = detect_putative_spikes(
        voltage,
        time,
        dv_cutoff=dvdt_threshold,
        thresh_frac=0.05,
    )

    if len(spike_indices) == 0:
        return {
            "spike_count": 0,
            "spike_times": np.array([]),
            "spike_indices": np.array([]),
            "threshold_indices": np.array([]),
        }

    # Find peaks
    peak_indices = find_peak_indexes(voltage, spike_indices)

    # Filter by min_peak
    valid_mask = voltage[peak_indices] >= min_peak
    spike_indices = spike_indices[valid_mask]
    peak_indices = peak_indices[valid_mask]

    spike_times = time[peak_indices]

    return {
        "spike_count": len(spike_indices),
        "spike_times": spike_times,
        "spike_indices": peak_indices,
        "threshold_indices": spike_indices,
    }


def extract_spike_features(
    voltage: np.ndarray,
    time: np.ndarray,
    current: Optional[np.ndarray] = None,
    dv_cutoff: float = 20.0,
    min_peak: float = -30.0,
) -> Dict[str, Any]:
    """
    Extract detailed features for each detected spike.

    Args:
        voltage: Voltage trace array (mV)
        time: Time array (seconds)
        current: Current/stimulus array (pA), optional
        dv_cutoff: dV/dt threshold for spike detection (mV/ms)
        min_peak: Minimum peak voltage to count as spike (mV)

    Returns:
        Dict containing:
            - spike_count: Number of spikes
            - features: List of dicts, one per spike, containing:
                - threshold_v: Threshold voltage (mV)
                - threshold_t: Threshold time (s)
                - peak_v: Peak voltage (mV)
                - peak_t: Peak time (s)
                - trough_v: Trough voltage (mV)
                - width: Spike width at half-height (ms)
                - upstroke: Maximum upstroke velocity (mV/ms)
                - downstroke: Maximum downstroke velocity (mV/ms)
    """
    try:
        from ipfx.feature_extractor import SpikeFeatureExtractor
    except ImportError:
        return {"spike_count": 0, "features": [], "error": "IPFX not available"}

    # Calculate dt
    dt = time[1] - time[0]

    # Handle current
    if current is None:
        current = np.zeros_like(voltage)

    # Create feature extractor
    extractor = SpikeFeatureExtractor(
        start=time[0],
        end=time[-1],
        dv_cutoff=dv_cutoff,
        min_peak=min_peak,
    )

    # Process
    try:
        features = extractor.process(time, voltage, current)
    except Exception as e:
        return {"spike_count": 0, "features": [], "error": str(e)}

    # Convert to list of dicts
    spike_features = []
    for i in range(len(features.get("threshold_v", []))):
        spike_dict = {}
        for key in features.keys():
            if isinstance(features[key], (list, np.ndarray)) and len(features[key]) > i:
                spike_dict[key] = float(features[key][i])
        spike_features.append(spike_dict)

    return {
        "spike_count": len(spike_features),
        "features": spike_features,
    }


def extract_spike_train_features(
    voltage: np.ndarray,
    time: np.ndarray,
    current: Optional[np.ndarray] = None,
    dv_cutoff: float = 20.0,
    min_peak: float = -30.0,
) -> Dict[str, Any]:
    """
    Extract spike train-level features (adaptation, bursts, etc.).

    Args:
        voltage: Voltage trace array (mV)
        time: Time array (seconds)
        current: Current/stimulus array (pA), optional
        dv_cutoff: dV/dt threshold for spike detection
        min_peak: Minimum peak voltage

    Returns:
        Dict containing:
            - spike_count: Number of spikes
            - avg_rate: Average firing rate (Hz)
            - latency: Time to first spike (s)
            - adaptation_index: Spike frequency adaptation index
            - isi_cv: Coefficient of variation of ISIs
            - mean_isi: Mean inter-spike interval (ms)
            - isi_values: Array of ISI values (ms)
    """
    # First detect spikes
    detection = detect_spikes(voltage, time, current, dv_cutoff, min_peak)

    if detection["spike_count"] < 2:
        return {
            "spike_count": detection["spike_count"],
            "avg_rate": detection["spike_count"] / (time[-1] - time[0]),
            "latency": detection["spike_times"][0] - time[0] if detection["spike_count"] > 0 else None,
            "adaptation_index": None,
            "isi_cv": None,
            "mean_isi": None,
            "isi_values": np.array([]),
        }

    spike_times = detection["spike_times"]
    
    # Calculate ISIs
    isis = np.diff(spike_times) * 1000  # Convert to ms
    
    # Calculate features
    avg_rate = len(spike_times) / (time[-1] - time[0])
    latency = spike_times[0] - time[0]
    mean_isi = np.mean(isis)
    isi_cv = np.std(isis) / mean_isi if mean_isi > 0 else 0

    # Adaptation index (ratio of last ISI to first ISI)
    if len(isis) >= 2:
        adaptation_index = isis[-1] / isis[0]
    else:
        adaptation_index = 1.0

    return {
        "spike_count": detection["spike_count"],
        "avg_rate": float(avg_rate),
        "latency": float(latency),
        "adaptation_index": float(adaptation_index),
        "isi_cv": float(isi_cv),
        "mean_isi": float(mean_isi),
        "isi_values": isis,
    }


def _detect_spikes_fallback(
    voltage: np.ndarray,
    time: np.ndarray,
    dv_cutoff: float = 20.0,
    min_peak: float = -30.0,
) -> Dict[str, Any]:
    """Fallback spike detection without IPFX."""
    from scipy.signal import find_peaks

    # Simple peak detection
    peaks, properties = find_peaks(voltage, height=min_peak, prominence=5)

    spike_times = time[peaks]

    return {
        "spike_count": len(peaks),
        "spike_times": spike_times,
        "spike_indices": peaks,
        "threshold_indices": np.array([]),  # Not calculated in fallback
        "method": "fallback_scipy",
    }
