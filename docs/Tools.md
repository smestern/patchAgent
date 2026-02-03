# Tools Reference

This document describes the tools available in patchAgent. Tools are the building blocks that agents use to perform analysis.

## Tool Categories

- [I/O Tools](#io-tools) - File loading and data access
- [Spike Tools](#spike-tools) - Action potential analysis
- [Passive Tools](#passive-tools) - Membrane property analysis
- [QC Tools](#qc-tools) - Quality control
- [Fitting Tools](#fitting-tools) - Curve fitting

---

## I/O Tools

### load_file

Load an electrophysiology file (ABF or NWB).

```python
load_file(file_path: str, return_metadata: bool = False) -> Dict
```

**Parameters**:
| Name | Type | Description |
|------|------|-------------|
| file_path | str | Path to .abf or .nwb file |
| return_metadata | bool | Include file metadata (default: False) |

**Returns**:
```python
{
    "dataX": np.ndarray,    # Time (n_sweeps, n_samples)
    "dataY": np.ndarray,    # Voltage/response
    "dataC": np.ndarray,    # Current/command
    "n_sweeps": int,
    "n_samples": int,
    "metadata": dict        # If return_metadata=True
}
```

---

### get_file_metadata

Get metadata from a file without loading full data.

```python
get_file_metadata(file_path: str) -> Dict
```

**Returns**:
```python
{
    "file_type": str,           # 'abf' or 'nwb'
    "sweep_count": int,
    "sample_rate": float,       # Hz
    "protocol": str,
    "sweep_length_sec": float,
    "channel_count": int,
    "clamp_mode": str,          # 'current_clamp' or 'voltage_clamp'
    "units": {
        "response": str,
        "command": str,
        "time": str
    }
}
```

---

### get_sweep_data

Get data for a specific sweep.

```python
get_sweep_data(data: Union[str, Dict], sweep_number: int, channel: int = 0) -> Dict
```

**Returns**:
```python
{
    "time": np.ndarray,
    "voltage": np.ndarray,
    "current": np.ndarray,
    "sweep_number": int
}
```

---

### list_sweeps

List available sweeps with basic info.

```python
list_sweeps(data: Union[str, Dict]) -> Dict
```

**Returns**:
```python
{
    "sweep_count": int,
    "sweep_indices": List[int],
    "sweep_info": [
        {"index": int, "duration_sec": float, "stim_amplitude": float},
        ...
    ]
}
```

---

## Spike Tools

### detect_spikes

Detect action potentials in a voltage trace.

```python
detect_spikes(
    voltage: np.ndarray,
    time: np.ndarray,
    current: Optional[np.ndarray] = None,
    dv_cutoff: float = 20.0,
    min_peak: float = -30.0,
    min_height: float = 2.0
) -> Dict
```

**Parameters**:
| Name | Type | Default | Description |
|------|------|---------|-------------|
| voltage | ndarray | required | Voltage trace (mV) |
| time | ndarray | required | Time array (s) |
| dv_cutoff | float | 20.0 | dV/dt threshold (mV/ms) |
| min_peak | float | -30.0 | Minimum peak voltage (mV) |

**Returns**:
```python
{
    "spike_count": int,
    "spike_times": np.ndarray,
    "spike_indices": np.ndarray,
    "threshold_indices": np.ndarray
}
```

---

### extract_spike_features

Extract detailed features for each spike.

```python
extract_spike_features(
    voltage: np.ndarray,
    time: np.ndarray,
    current: Optional[np.ndarray] = None,
    dv_cutoff: float = 20.0,
    min_peak: float = -30.0
) -> Dict
```

**Returns**:
```python
{
    "spike_count": int,
    "features": [
        {
            "threshold_v": float,
            "threshold_t": float,
            "peak_v": float,
            "peak_t": float,
            "trough_v": float,
            "width": float,
            "upstroke": float,
            "downstroke": float
        },
        ...
    ]
}
```

---

### extract_spike_train_features

Extract spike train-level features.

```python
extract_spike_train_features(
    voltage: np.ndarray,
    time: np.ndarray,
    current: Optional[np.ndarray] = None
) -> Dict
```

**Returns**:
```python
{
    "spike_count": int,
    "avg_rate": float,          # Hz
    "latency": float,           # s
    "adaptation_index": float,
    "isi_cv": float,
    "mean_isi": float,          # ms
    "isi_values": np.ndarray    # ms
}
```

---

## Passive Tools

### calculate_input_resistance

Calculate input resistance from current step.

```python
calculate_input_resistance(
    voltage: np.ndarray,
    current: np.ndarray,
    time: np.ndarray,
    baseline_start: Optional[float] = None,
    baseline_end: Optional[float] = None,
    response_start: Optional[float] = None,
    response_end: Optional[float] = None
) -> Dict
```

**Returns**:
```python
{
    "input_resistance": float,      # MΩ
    "voltage_deflection": float,    # mV
    "current_amplitude": float,     # pA
    "baseline_voltage": float       # mV
}
```

---

### calculate_time_constant

Calculate membrane time constant.

```python
calculate_time_constant(
    voltage: np.ndarray,
    current: np.ndarray,
    time: np.ndarray,
    fit_start: Optional[float] = None,
    fit_duration: float = 0.1
) -> Dict
```

**Returns**:
```python
{
    "tau": float,           # ms
    "v_rest": float,        # mV
    "v_steady": float,      # mV
    "fit_quality": float    # R²
}
```

---

### calculate_sag

Calculate sag ratio from hyperpolarizing step.

```python
calculate_sag(
    voltage: np.ndarray,
    current: np.ndarray,
    time: np.ndarray
) -> Dict
```

**Returns**:
```python
{
    "sag_ratio": float,         # 0-1
    "peak_voltage": float,      # mV
    "steady_voltage": float,    # mV
    "baseline_voltage": float   # mV
}
```

---

### calculate_resting_potential

Calculate resting membrane potential.

```python
calculate_resting_potential(
    voltage: np.ndarray,
    time: np.ndarray,
    window_start: Optional[float] = None,
    window_end: Optional[float] = None,
    method: str = "mean"
) -> Dict
```

**Returns**:
```python
{
    "resting_potential": float,  # mV
    "std": float,                # mV
    "method": str
}
```

---

## QC Tools

### run_sweep_qc

Comprehensive sweep quality control.

```python
run_sweep_qc(
    voltage: np.ndarray,
    current: np.ndarray,
    time: np.ndarray,
    baseline_window: float = 0.1,
    max_baseline_std: float = 2.0,
    max_drift: float = 5.0
) -> Dict
```

**Returns**:
```python
{
    "passed": bool,
    "checks": {
        "baseline_stability": {...},
        "noise": {...},
        "clipping": {...}
    },
    "issues": List[str]
}
```

---

### check_baseline_stability

Check baseline voltage stability.

```python
check_baseline_stability(
    voltage: np.ndarray,
    time: np.ndarray,
    window_start: Optional[float] = None,
    window_duration: float = 0.1
) -> Dict
```

**Returns**:
```python
{
    "mean": float,
    "std": float,
    "drift": float,
    "is_stable": bool
}
```

---

### measure_noise

Measure noise level in trace.

```python
measure_noise(
    voltage: np.ndarray,
    time: np.ndarray,
    window_start: Optional[float] = None,
    window_duration: float = 0.1,
    high_pass_cutoff: float = 100.0
) -> Dict
```

**Returns**:
```python
{
    "rms_noise": float,      # mV
    "peak_to_peak": float,   # mV
    "snr": float             # estimated SNR
}
```

---

## Fitting Tools

### fit_exponential

Fit exponential decay or growth.

```python
fit_exponential(
    y: np.ndarray,
    x: np.ndarray,
    fit_type: str = "decay",
    p0: Optional[List[float]] = None
) -> Dict
```

**Returns**:
```python
{
    "amplitude": float,
    "tau": float,
    "offset": float,
    "r_squared": float,
    "fitted_values": np.ndarray,
    "success": bool
}
```

---

### fit_iv_curve

Fit current-voltage relationship.

```python
fit_iv_curve(
    voltages: np.ndarray,
    currents: np.ndarray,
    fit_type: str = "linear",
    voltage_range: Optional[Tuple[float, float]] = None
) -> Dict
```

**Returns**:
```python
{
    "slope": float,                  # nS (conductance)
    "intercept": float,
    "r_squared": float,
    "reversal_potential": float,     # mV
    "input_resistance": float,       # MΩ
    "fitted_values": np.ndarray
}
```

---

### fit_fi_curve

Fit frequency-current relationship.

```python
fit_fi_curve(
    currents: np.ndarray,
    firing_rates: np.ndarray,
    fit_type: str = "linear",
    current_range: Optional[Tuple[float, float]] = None
) -> Dict
```

**Returns**:
```python
{
    "gain": float,              # Hz/pA
    "rheobase": float,          # pA
    "r_squared": float,
    "max_rate": float,          # Hz
    "fitted_values": np.ndarray
}
```

---

### fit_double_exponential

Fit double exponential decay.

```python
fit_double_exponential(
    y: np.ndarray,
    x: np.ndarray,
    p0: Optional[List[float]] = None
) -> Dict
```

**Returns**:
```python
{
    "amplitude_fast": float,
    "tau_fast": float,
    "amplitude_slow": float,
    "tau_slow": float,
    "offset": float,
    "r_squared": float,
    "fitted_values": np.ndarray,
    "success": bool
}
```
