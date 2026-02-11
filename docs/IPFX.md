# IPFX API Reference for patchAgent

> **Source**: [AllenInstitute/ipfx](https://github.com/AllenInstitute/ipfx) v2.1.x  
> **Docs**: [ipfx.readthedocs.io](https://ipfx.readthedocs.io/en/latest/)  
> **Purpose**: This document provides the correct IPFX API surface that patchAgent
> wraps or exposes to the LLM. It is the authoritative reference for parameter
> names, types, defaults, and return values.

---

## Table of Contents

1. [ipfx.feature_extractor](#1-ipfxfeature_extractor)
   - [SpikeFeatureExtractor](#spikefeatureextractor)
   - [SpikeTrainFeatureExtractor](#spiketrainfeatureextractor)
2. [ipfx.spike_detector](#2-ipfxspike_detector)
3. [ipfx.subthresh_features](#3-ipfxsubthresh_features)
4. [ipfx.spike_train_features](#4-ipfxspike_train_features)
5. [Common Pitfalls](#5-common-pitfalls)
6. [Quick-Start Recipes](#6-quick-start-recipes)

---

## 1. `ipfx.feature_extractor`

### `SpikeFeatureExtractor`

High-level class that detects spikes and computes per-spike features in a single
call. This is the primary entry point for spike analysis.

```python
from ipfx.feature_extractor import SpikeFeatureExtractor
```

#### Constructor

```python
SpikeFeatureExtractor(
    start=None,          # float | None — start of analysis window (seconds)
    end=None,            # float | None — end of analysis window (seconds)
    filter=10.0,         # float — Bessel low-pass filter cutoff in **kHz** (NOT Hz)
    dv_cutoff=20.0,      # float — minimum dV/dt to qualify as spike, in **V/s**
    max_interval=0.005,  # float — max time between threshold and peak (seconds)
    min_height=2.0,      # float — min threshold-to-peak height (mV)
    min_peak=-30.0,      # float — min absolute peak voltage (mV)
    thresh_frac=0.05,    # float — fraction of avg upstroke for threshold refinement
    reject_at_stim_start_interval=0,  # float — reject spikes within this many
                         #   seconds of `start` (useful for stimulus artefacts)
)
```

> **⚠ The parameter is `filter`, NOT `filter_frequency`.**  
> `SpikeFeatureExtractor` uses `filter` (in kHz). The separate class
> `SpikeTrainFeatureExtractor` uses `filter_frequency` (also in kHz but for
> subthreshold analysis). Do not confuse them.

#### `.process(t, v, i) → pandas.DataFrame`

Detect spikes and extract per-spike features.

**Arguments**:
| Param | Type | Units | Description |
|-------|------|-------|-------------|
| `t` | `np.ndarray` | seconds | 1-D time array |
| `v` | `np.ndarray` | mV | 1-D voltage array (same length as `t`) |
| `i` | `np.ndarray` | pA | 1-D current/stimulus array (same length as `t`) |

**Returns**: `pandas.DataFrame` — one row per detected spike. Returns an
**empty DataFrame** (not `None`) when no spikes are found.

**DataFrame columns** (all present when spikes are found):

| Column | Units | Description |
|--------|-------|-------------|
| `threshold_index` | — | Index into `v` where spike threshold is crossed |
| `threshold_t` | s | Time of threshold crossing |
| `threshold_v` | mV | Voltage at threshold |
| `threshold_i` | pA | Current at threshold |
| `peak_index` | — | Index of spike peak |
| `peak_t` | s | Time of peak |
| `peak_v` | mV | Voltage at peak |
| `peak_i` | pA | Current at peak |
| `trough_index` | — | Index of post-spike trough |
| `trough_t` | s | Time of trough |
| `trough_v` | mV | Voltage at trough |
| `trough_i` | pA | Current at trough |
| `upstroke` | V/s | Max dV/dt during upstroke |
| `upstroke_index` | — | Index of max upstroke |
| `upstroke_t` | s | Time of max upstroke |
| `upstroke_v` | mV | Voltage at max upstroke |
| `downstroke` | V/s | Min dV/dt during downstroke (negative value) |
| `downstroke_index` | — | Index of min downstroke |
| `downstroke_t` | s | Time of min downstroke |
| `downstroke_v` | mV | Voltage at min downstroke |
| `width` | s | Spike width at half-height |
| `upstroke_downstroke_ratio` | — | `upstroke / abs(downstroke)` |
| `clipped` | bool | `True` if spike was cut off by end of window |
| `isi_type` | str | `"direct"` or `"detour"` (reset type after spike) |
| `fast_trough_index`, `_t`, `_v`, `_i` | — | Fast trough (end of spike) |
| `adp_index`, `_t`, `_v`, `_i` | — | After-depolarization (if present) |
| `slow_trough_index`, `_t`, `_v`, `_i` | — | Slow trough (min before next spike) |

#### Other Methods

```python
extractor.spike_feature_keys(spikes_df)
# → list of str — all available column names

extractor.spike_feature(spikes_df, key, include_clipped=False)
# → np.ndarray — values of `key` for each spike (excluding clipped by default)

extractor.spikes(spikes_df)
# → list of dict — one dict per spike (same as spikes_df.to_dict('records'))

extractor.is_spike_feature_affected_by_clipping(key)
# → bool — True if `key` is unreliable for clipped spikes
```

#### AFFECTED_BY_CLIPPING

These features are excluded for clipped spikes by default:
`trough_*`, `downstroke*`, `fast_trough_*`, `adp_*`, `slow_trough_*`,
`isi_type`, `width`, `upstroke_downstroke_ratio`.

---

### `SpikeTrainFeatureExtractor`

Computes train-level (whole-sweep) features from spike data.

```python
from ipfx.feature_extractor import SpikeTrainFeatureExtractor
```

#### Constructor

```python
SpikeTrainFeatureExtractor(
    start,                      # float — REQUIRED, start of stimulus interval (seconds)
    end,                        # float — REQUIRED, end of stimulus interval (seconds)
    burst_tol=0.5,              # float — tolerance for burst detection (mV)
    pause_cost=1.0,             # float — cost weight for pause detection
    deflect_type=None,          # str | None — "min" or "max" for voltage deflection
    stim_amp_fn=None,           # callable | None — fn(t, i, start) → stimulus amplitude
    baseline_interval=0.1,      # float — seconds before start for baseline (s)
    filter_frequency=1.0,       # float — filter for baseline detection in **kHz**
    sag_baseline_interval=0.03, # float — baseline interval for sag calc (s)
    peak_width=0.005,           # float — window for robust peak estimate (s)
)
```

> **Note**: `start` and `end` are **required** (positional) — unlike
> `SpikeFeatureExtractor` where they are optional.

#### `.process(t, v, i, spikes_df, extra_features=None, exclude_clipped=False) → dict`

**Arguments**:
| Param | Type | Description |
|-------|------|-------------|
| `t` | `np.ndarray` | Time array (seconds) |
| `v` | `np.ndarray` | Voltage array (mV) |
| `i` | `np.ndarray` | Current array (pA) |
| `spikes_df` | `pd.DataFrame` | **REQUIRED** — the DataFrame returned by `SpikeFeatureExtractor.process()` |
| `extra_features` | `list[str]` or `None` | Optional list of extra features to compute |
| `exclude_clipped` | `bool` | Whether to exclude clipped spikes |

**Returns**: `dict` with keys:

| Key | Type | Description |
|-----|------|-------------|
| `adapt` | `float` | Adaptation index (normalized ISI differences) |
| `latency` | `float` | Time to first spike from `start` (seconds) |
| `isi_cv` | `float` | Coefficient of variation of ISIs |
| `mean_isi` | `float` | Mean inter-spike interval (seconds) |
| `median_isi` | `float` | Median ISI (seconds) |
| `first_isi` | `float` | First ISI (seconds) |
| `avg_rate` | `float` | Average firing rate (spikes/s) |

**`extra_features`** — pass a list of strings to request additional computations:

| Feature string | Added key | Description |
|----------------|-----------|-------------|
| `"peak_deflect"` | `peak_deflect` | `(deflect_v, deflect_index)` tuple |
| `"stim_amp"` | `stim_amp` | Stimulus amplitude (requires `stim_amp_fn`) |
| `"v_baseline"` | `v_baseline` | Baseline voltage before stimulus |
| `"sag"` | `sag` | Sag fraction |
| `"pause"` | `pause` | `(n_pauses, pause_frac)` — **deprecated** |
| `"burst"` | `burst` | `(max_burstiness, n_bursts)` — **deprecated** |
| `"delay"` | `delay` | `(delay_ratio, tau)` — **deprecated** |

---

## 2. `ipfx.spike_detector`

Low-level spike detection functions. `SpikeFeatureExtractor` calls these
internally, but they can be used directly for custom pipelines.

```python
from ipfx.spike_detector import (
    detect_putative_spikes,
    find_peak_indexes,
    filter_putative_spikes,
    find_upstroke_indexes,
    refine_threshold_indexes,
    check_thresholds_and_peaks,
    find_trough_indexes,
    find_downstroke_indexes,
    find_clipped_spikes,
)
```

### Core functions

#### `detect_putative_spikes(v, t, start=None, end=None, filter=10., dv_cutoff=20., dvdt=None)`

Initial spike detection via dV/dt threshold crossing.

| Param | Type | Default | Units | Description |
|-------|------|---------|-------|-------------|
| `v` | `np.ndarray` | — | mV | Voltage time series |
| `t` | `np.ndarray` | — | s | Time array |
| `start` | `float` | `None` | s | Start of detection window |
| `end` | `float` | `None` | s | End of detection window |
| `filter` | `float` | `10.0` | **kHz** | Bessel filter cutoff |
| `dv_cutoff` | `float` | `20.0` | **V/s** | dV/dt threshold for spike detection |
| `dvdt` | `np.ndarray` | `None` | V/s | Pre-computed derivative (skip filtering) |

**Returns**: `np.ndarray` — indices of putative spike thresholds in the original
array (not the windowed sub-array).

#### `find_peak_indexes(v, t, spike_indexes, end=None)`

Find the voltage peak between each threshold and the next threshold (or end).

**Returns**: `np.ndarray` — indices of spike peaks.

#### `filter_putative_spikes(v, t, spike_indexes, peak_indexes, min_height=2., min_peak=-30., filter=10., dvdt=None)`

Remove events that don't meet height or absolute peak criteria.

**Returns**: `(spike_indexes, peak_indexes)` — filtered arrays.

#### `find_upstroke_indexes(v, t, spike_indexes, peak_indexes, filter=10., dvdt=None)`

Find the index of maximum dV/dt between each threshold and its peak.

**Returns**: `np.ndarray` — upstroke indices.

#### `refine_threshold_indexes(v, t, upstroke_indexes, thresh_frac=0.05, filter=10., dvdt=None)`

Refine threshold to the point where dV/dt first exceeds `thresh_frac` of the
average upstroke value, searching backward from the upstroke.

**Returns**: `np.ndarray` — refined threshold indices.

#### `check_thresholds_and_peaks(v, t, spike_indexes, peak_indexes, upstroke_indexes, start=None, end=None, max_interval=0.005, thresh_frac=0.05, filter=10., dvdt=None, tol=1.0, reject_at_stim_start_interval=0.)`

Validate and merge overlapping threshold-peak pairs; drop pairs that are too far
apart.

**Returns**: `(spike_indexes, peak_indexes, upstroke_indexes, clipped)` — all
`np.ndarray`.

#### `find_trough_indexes(v, t, spike_indexes, peak_indexes, clipped=None, end=None)`

Find minimum voltage between consecutive spikes. Clipped spikes get `np.nan`.

**Returns**: `np.ndarray` (may contain `np.nan` for clipped spikes).

#### `find_downstroke_indexes(v, t, peak_indexes, trough_indexes, clipped=None, filter=10., dvdt=None)`

Find minimum dV/dt between peak and trough. Clipped spikes get `np.nan`.

**Returns**: `np.ndarray`.

---

## 3. `ipfx.subthresh_features`

Subthreshold / passive membrane property functions. These operate on
**hyperpolarizing** current-step responses.

```python
from ipfx.subthresh_features import (
    input_resistance,
    time_constant,
    sag,
    voltage_deflection,
    baseline_voltage,
    fit_membrane_time_constant,
)
```

### `input_resistance(t_set, i_set, v_set, start, end, baseline_interval=0.1)`

> **⚠ Takes lists of arrays (multiple sweeps), NOT single arrays.**

| Param | Type | Units | Description |
|-------|------|-------|-------------|
| `t_set` | `list[np.ndarray]` | s | List of time arrays, one per sweep |
| `i_set` | `list[np.ndarray]` | pA | List of current arrays |
| `v_set` | `list[np.ndarray]` | mV | List of voltage arrays |
| `start` | `float` | s | Start of stimulus interval |
| `end` | `float` | s | End of stimulus interval |
| `baseline_interval` | `float` | s | Duration before `start` for baseline |

**Returns**: `float` — input resistance in **MΩ**.

**Algorithm**: Finds peak voltage deflection in each sweep, then fits a linear
regression of V vs I. Slope × 1000 = resistance in MΩ. If only one sweep, uses
baseline voltage as a second data point (I = 0).

### `time_constant(t, v, i, start, end, max_fit_end=None, frac=0.1, baseline_interval=0.1, min_snr=20.)`

> **⚠ The function is called `time_constant`, NOT `membrane_time_constant`.**  
> `fit_membrane_time_constant` is a separate, lower-level function.

| Param | Type | Units | Description |
|-------|------|-------|-------------|
| `t` | `np.ndarray` | s | Time array |
| `v` | `np.ndarray` | mV | Voltage array |
| `i` | `np.ndarray` | pA | Current array |
| `start` | `float` | s | Start of stimulus |
| `end` | `float` | s | End of stimulus |
| `max_fit_end` | `float\|None` | s | Limit fit window end |
| `frac` | `float` | — | Fraction of deflection to find fit start (default 0.1) |
| `baseline_interval` | `float` | s | Duration before `start` for baseline |
| `min_snr` | `float` | — | Minimum signal-to-noise ratio; returns `np.nan` if too low |

**Returns**: `float` — membrane time constant τ in **seconds**. Returns `np.nan`
if SNR is too low or fit fails.

**Algorithm**: Fits `y0 + a * exp(-inv_tau * x)` to the voltage response between
`frac * deflection` and peak deflection. Returns `1 / inv_tau`.

### `sag(t, v, i, start, end, peak_width=0.005, baseline_interval=0.03)`

| Param | Type | Units | Description |
|-------|------|-------|-------------|
| `t` | `np.ndarray` | s | Time array |
| `v` | `np.ndarray` | mV | Voltage array |
| `i` | `np.ndarray` | pA | Current array |
| `start` | `float` | s | Start of stimulus |
| `end` | `float` | s | End of stimulus |
| `peak_width` | `float` | s | Window for robust peak averaging (default 5 ms) |
| `baseline_interval` | `float` | s | Baseline window before `start` (default 30 ms) |

**Returns**: `float` — sag fraction: `(V_peak_avg - V_steady) / (V_peak_avg - V_baseline)`.

A sag of 0 means no relaxation (no Ih). Values > 0 indicate Ih-mediated sag.

### `voltage_deflection(t, v, i, start, end, deflect_type=None)`

| Param | Type | Description |
|-------|------|-------------|
| `deflect_type` | `str\|None` | `"min"`, `"max"`, or `None` (auto-detect from current sign) |

**Returns**: `(deflect_v, deflect_index)` — peak voltage and its index.

### `baseline_voltage(t, v, start, baseline_interval=0.1, baseline_detect_thresh=0.3, filter_frequency=1.0)`

**Returns**: `float` — average voltage during baseline interval before `start`.
Returns `np.nan` if no sufficiently flat interval is found.

### `fit_membrane_time_constant(t, v, start, end, rmse_max_tol=1.0)`

Low-level exponential fit. Use `time_constant()` instead for most purposes.

**Returns**: `(a, inv_tau, y0)` — coefficients of `y0 + a * exp(-inv_tau * x)`.
Returns `(np.nan, np.nan, np.nan)` if fit fails or RMSE exceeds tolerance.

---

## 4. `ipfx.spike_train_features`

Train-level feature functions. Most are called internally by
`SpikeTrainFeatureExtractor.process()`, but can be used directly.

```python
from ipfx.spike_train_features import (
    basic_spike_train_features,
    adaptation_index,
    average_rate,
    latency,
    get_isis,
    fit_fi_slope,
    norm_diff,
    detect_pauses,    # deprecated
    detect_bursts,    # deprecated
)
```

### `basic_spike_train_features(t, spikes_df, start, end, exclude_clipped=False)`

| Param | Type | Description |
|-------|------|-------------|
| `t` | `np.ndarray` | Time array (seconds) |
| `spikes_df` | `pd.DataFrame` | DataFrame from `SpikeFeatureExtractor.process()` |
| `start` | `float` | Start of stimulus interval |
| `end` | `float` | End of stimulus interval |

**Returns**: `dict` with keys: `adapt`, `latency`, `isi_cv`, `mean_isi`,
`median_isi`, `first_isi`, `avg_rate`. Returns `{"avg_rate": 0}` if no spikes.

### `adaptation_index(isis)`

Normalized difference of consecutive ISIs: mean of `(ISI[i+1] - ISI[i]) / (ISI[i+1] + ISI[i])`.

**Returns**: `float` (or `np.nan` if ≤ 1 ISI).

### `average_rate(t, spikes, start, end)`

| Param | Type | Description |
|-------|------|-------------|
| `spikes` | `np.ndarray` | Array of spike **indices** (NOT times) |

**Returns**: `float` — firing rate in spikes/second.

### `latency(t, spikes, start)`

**Returns**: `float` — time from `start` to first spike (seconds).

### `get_isis(t, spikes)`

**Returns**: `np.ndarray` — inter-spike intervals in seconds. Empty array if ≤ 1 spike.

### `fit_fi_slope(stim_amps, avg_rates)`

Linear fit of firing rate vs stimulus amplitude.

| Param | Type | Units |
|-------|------|-------|
| `stim_amps` | `array-like` | pA |
| `avg_rates` | `array-like` | Hz |

**Returns**: `float` — slope in Hz/pA. Raises `FeatureError` if < 2 data points.

### `detect_pauses(isis, isi_types, cost_weight=1.0)` ⚠ deprecated

Detect unusually long ISIs. Requires `isi_type` column from spike DataFrame.

### `detect_bursts(isis, isi_types, fast_tr_v, fast_tr_t, slow_tr_v, slow_tr_t, thr_v, tol=0.5, pause_cost=1.0)` ⚠ deprecated

Detect bursts based on ISI transitions between "direct" and "detour" resets.

---

## 5. Common Pitfalls

### `filter` vs `filter_frequency`

| Class | Parameter | Units | Default |
|-------|-----------|-------|---------|
| `SpikeFeatureExtractor` | `filter` | **kHz** | 10.0 |
| `SpikeTrainFeatureExtractor` | `filter_frequency` | **kHz** | 1.0 |
| `detect_putative_spikes()` | `filter` | **kHz** | 10.0 |

**`SpikeFeatureExtractor` does NOT accept `filter_frequency`.** Passing it as a
keyword argument will raise `TypeError`.

### `filter` must be below Nyquist

The Bessel low-pass filter coefficient must be strictly < 1.0, i.e., the `filter`
cutoff (kHz) must be strictly less than the Nyquist frequency (sample_rate / 2).
The default `filter=10` kHz will crash on 20 kHz data because Nyquist = 10 kHz.

```python
# 20 kHz sampling → Nyquist = 10 kHz → filter=10 FAILS
spfx = SpikeFeatureExtractor(filter=10.0, ...)  # ValueError!

# Fix: pass filter=None to disable Bessel smoothing on low-rate data
spfx = SpikeFeatureExtractor(filter=None, ...)   # OK
```

### DataFrame index columns are float64

`SpikeFeatureExtractor.process()` returns a DataFrame whose index columns
(`threshold_index`, `peak_index`, `trough_index`, etc.) are **float64**, not int.
Cast to `int` before using them to index into arrays.

```python
peak_idx = spikes_df["peak_index"].values.astype(int)
peak_voltages = voltage[peak_idx]
```

### `dv_cutoff` units

`dv_cutoff` is in **V/s** (volts per second), NOT mV/ms. Numerically they are
equivalent (20 V/s = 20 mV/ms), but be aware when reading or documenting.

### `input_resistance` takes sweep sets

`ipfx.subthresh_features.input_resistance()` expects **lists** of arrays
(`t_set`, `i_set`, `v_set`) — one array per sweep. Passing single arrays will
cause errors or incorrect results.

```python
# WRONG — single arrays
Rm = input_resistance(t, i, v, start, end)

# CORRECT — wrap in lists
Rm = input_resistance([t], [i], [v], start, end)

# CORRECT — multiple sweeps
Rm = input_resistance(
    [t0, t1, t2],
    [i0, i1, i2],
    [v0, v1, v2],
    start, end
)
```

### `time_constant` not `membrane_time_constant`

The public function is `ipfx.subthresh_features.time_constant()`.  
`fit_membrane_time_constant()` is a lower-level helper that returns raw fit
coefficients (a, inv_tau, y0) rather than τ in seconds.

### `process()` returns empty DataFrame

When no spikes are found, `SpikeFeatureExtractor.process()` returns an **empty
`pandas.DataFrame`**, not `None` or an empty dict. Check with:

```python
spikes_df = ext.process(t, v, i)
if spikes_df.empty:
    print("No spikes found")
```

### `SpikeTrainFeatureExtractor.process()` requires `spikes_df`

Unlike `SpikeFeatureExtractor.process(t, v, i)` which takes 3 args,
`SpikeTrainFeatureExtractor.process()` requires **4 positional args**:
`(t, v, i, spikes_df)`. You must run spike detection first.

```python
# Two-step pipeline:
spfx = SpikeFeatureExtractor(start=start, end=end)
spikes_df = spfx.process(t, v, i)

sptx = SpikeTrainFeatureExtractor(start=start, end=end)
train_features = sptx.process(t, v, i, spikes_df)  # 4 args!
```

### Argument order

`SpikeFeatureExtractor.process()` takes `(t, v, i)` — time first.  
`ipfx.subthresh_features.time_constant()` takes `(t, v, i, start, end)` — time first.  
`ipfx.subthresh_features.input_resistance()` takes `(t_set, i_set, v_set, ...)` — **current before voltage**.

---

## 6. Quick-Start Recipes

### Detect spikes and extract features

```python
import numpy as np
from ipfx.feature_extractor import SpikeFeatureExtractor, SpikeTrainFeatureExtractor

# Assumes t (seconds), v (mV), i (pA) are loaded
start, end = t[0], t[-1]

# Spike detection + per-spike features
spfx = SpikeFeatureExtractor(start=start, end=end, dv_cutoff=20.0, min_peak=-30.0)
spikes_df = spfx.process(t, v, i)

if not spikes_df.empty:
    print(f"Found {len(spikes_df)} spikes")
    print(f"Threshold voltages: {spikes_df['threshold_v'].values}")
    print(f"Peak voltages: {spikes_df['peak_v'].values}")
    print(f"Widths (ms): {spikes_df['width'].values * 1000}")

    # Train-level features
    sptx = SpikeTrainFeatureExtractor(start=start, end=end)
    train = sptx.process(t, v, i, spikes_df)
    print(f"Firing rate: {train['avg_rate']:.1f} Hz")
    print(f"Adaptation index: {train['adapt']:.3f}")
```

### Measure passive properties

```python
from ipfx.subthresh_features import time_constant, sag, input_resistance

# Single sweep — time constant and sag
# (use a hyperpolarizing step sweep)
tau = time_constant(t, v, i, stim_start, stim_end)
sag_ratio = sag(t, v, i, stim_start, stim_end)

# Multiple sweeps — input resistance
# Provide lists of arrays from several hyperpolarizing sweeps
Rm = input_resistance(
    [t0, t1, t2],  # time arrays
    [i0, i1, i2],  # current arrays (note: i before v!)
    [v0, v1, v2],  # voltage arrays
    stim_start, stim_end
)
print(f"Rm = {Rm:.1f} MΩ, tau = {tau*1000:.1f} ms, sag = {sag_ratio:.3f}")
```

### Build an f-I curve

```python
from ipfx.feature_extractor import SpikeFeatureExtractor
from ipfx.spike_train_features import fit_fi_slope

stim_amps = []  # pA
avg_rates = []  # Hz

for sweep_idx in range(n_sweeps):
    v_sweep = dataY[sweep_idx]
    t_sweep = dataX[sweep_idx]
    i_sweep = dataC[sweep_idx]
    stim_amp = i_sweep[int(len(i_sweep) * 0.5)]  # or measure properly

    ext = SpikeFeatureExtractor(start=stim_start, end=stim_end)
    spikes = ext.process(t_sweep, v_sweep, i_sweep)

    rate = len(spikes) / (stim_end - stim_start) if not spikes.empty else 0.0
    stim_amps.append(stim_amp)
    avg_rates.append(rate)

slope = fit_fi_slope(np.array(stim_amps), np.array(avg_rates))
print(f"f-I slope: {slope:.2f} Hz/pA")
```

### Use low-level spike_detector directly

```python
from ipfx.spike_detector import detect_putative_spikes, find_peak_indexes, filter_putative_spikes

spike_idx = detect_putative_spikes(v, t, start=0.5, end=1.5, dv_cutoff=20.0)
peak_idx = find_peak_indexes(v, t, spike_idx, end=1.5)
spike_idx, peak_idx = filter_putative_spikes(v, t, spike_idx, peak_idx,
                                              min_height=2.0, min_peak=-30.0)
print(f"Detected {len(spike_idx)} spikes, peaks at t = {t[peak_idx]}")
```

---

*Last updated: 2026-02-10*
