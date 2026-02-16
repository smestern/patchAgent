"""
Spike Tools - Action potential detection and feature extraction.

Wraps IPFX spike detection and feature extraction functionality.
"""

from typing import Union, Dict, Any, List, Optional
import numpy as np

from sciagent.tools.registry import tool


@tool(
    name="detect_spikes",
    description="Detect action potentials in a voltage trace using dV/dt threshold",
    parameters={
        "type": "object",
        "properties": {
            "voltage": {"type": "array", "items": {"type": "number"}, "description": "Voltage trace in mV"},
            "time": {"type": "array", "items": {"type": "number"}, "description": "Time array in seconds"},
            "dv_cutoff": {"type": "number", "description": "dV/dt threshold in mV/ms (default: 20)"},
            "min_peak": {"type": "number", "description": "Minimum peak voltage in mV (default: -30)"},
        },
        "required": ["voltage", "time"],
    },
)
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
        from ipfx.feature_extractor import SpikeFeatureExtractor
    except ImportError:
        print("Warning: IPFX not available, using fallback spike detection")
        return _detect_spikes_fallback(voltage, time, dv_cutoff, min_peak)

    # Calculate sampling rate and convert filter to kHz for IPFX
    dt = time[1] - time[0]
    filter_khz = filter_calculator(dt, filter_frequency)

    spfx = SpikeFeatureExtractor(
        filter=filter_khz,  # IPFX expects kHz (default 10)
        start=time[0],
        end=time[-1],
        dv_cutoff=dv_cutoff,
        min_peak=min_peak,
        min_height=min_height,
    )

    # Detect spikes
    spike_df = spfx.process(time, voltage, current if current is not None else np.zeros_like(voltage))

    if spike_df.empty:
        return {
            "spike_count": 0,
            "spike_times": np.array([]),
            "spike_indices": np.array([]),
            "threshold_indices": np.array([]),
        }

    spike_indices = spike_df["threshold_index"].values.astype(int)

    # Find peaks
    peak_indices = spike_df["peak_index"].values.astype(int)

    spike_times = time[peak_indices]

    return {
        "spike_count": len(spike_indices),
        "spike_times": spike_times,
        "spike_indices": spike_indices,
        "peak_indices": peak_indices,
        "threshold_indices": spike_indices,
    }


@tool(
    name="extract_spike_features",
    description="Extract features from detected spikes (threshold, amplitude, width, kinetics)",
    parameters={
        "type": "object",
        "properties": {
            "voltage": {"type": "array", "items": {"type": "number"}, "description": "Voltage trace in mV"},
            "time": {"type": "array", "items": {"type": "number"}, "description": "Time array in seconds"},
        },
        "required": ["voltage", "time"],
    },
)
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

    # Calculate filter frequency in kHz for IPFX
    dt = time[1] - time[0]
    filter_khz = filter_calculator(dt)

    # Handle current
    if current is None:
        current = np.zeros_like(voltage)

    # Create feature extractor
    extractor = SpikeFeatureExtractor(
        filter=filter_khz,  # IPFX expects kHz (default 10)
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

    # Convert DataFrame to list of dicts
    if features.empty:
        return {"spike_count": 0, "features": []}

    spike_features = []
    for _, row in features.iterrows():
        spike_dict = {}
        for key in features.columns:
            val = row[key]
            if isinstance(val, (np.floating, float, np.integer, int)):
                spike_dict[key] = float(val)
            elif isinstance(val, (bool, np.bool_)):
                spike_dict[key] = bool(val)
            elif val is not None and not (isinstance(val, float) and np.isnan(val)):
                spike_dict[key] = val
        spike_features.append(spike_dict)

    return {
        "spike_count": len(spike_features),
        "features": spike_features,
    }


@tool(
    name="extract_spike_train_features",
    description="Extract spike train features (firing rate, adaptation, ISI statistics)",
    parameters={
        "type": "object",
        "properties": {
            "voltage": {"type": "array", "items": {"type": "number"}, "description": "Voltage trace in mV"},
            "time": {"type": "array", "items": {"type": "number"}, "description": "Time array in seconds"},
        },
        "required": ["voltage", "time"],
    },
)
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


def filter_calculator(dt, filter_frequency: Optional[float] = None) -> Optional[float]:
    """Calculate filter parameters for IPFX based on sampling interval.

    IPFX uses a Bessel low-pass filter whose coefficient must be strictly < 1.0,
    meaning the filter cutoff must be strictly below the Nyquist frequency
    (sample_rate / 2).  The default IPFX filter is 10 kHz, which works for
    high-rate recordings (e.g., 50 kHz) but fails at 20 kHz sampling because
    the Nyquist frequency is exactly 10 kHz.

    Strategy:
      - If a user-supplied filter_frequency (Hz) is given and is safely below
        Nyquist, convert it to kHz and use it.
      - Otherwise, use the IPFX default (10 kHz) only if the sampling rate is
        high enough; for lower rates, skip filtering (return None) so IPFX
        computes dv/dt without a Bessel filter.
    """
    sample_rate = 1.0 / dt            # Hz
    nyquist = sample_rate / 2.0       # Hz
    default_filter_khz = 10.0         # IPFX default, in kHz
    default_filter_hz = default_filter_khz * 1000.0

    # User-supplied filter (Hz): use it if strictly below Nyquist
    if filter_frequency is not None:
        if filter_frequency < nyquist:
            return filter_frequency / 1000.0   # convert Hz → kHz for IPFX
        else:
            return None   # requested filter ≥ Nyquist; skip filtering

    # No explicit filter – use default 10 kHz when safe
    if default_filter_hz < nyquist:
        return default_filter_khz
    else:
        return None  # default would hit or exceed Nyquist; skip filtering