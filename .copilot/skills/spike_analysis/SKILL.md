# Spike Analysis Skill

## Description
Expert in detecting and analyzing action potentials from current-clamp patch-clamp recordings. Provides spike detection, individual spike feature extraction, and spike train analysis.

## When to Use
- User wants to detect action potentials / spikes in a voltage trace
- User asks about firing patterns, firing rate, or spiking behavior
- User needs AP features: threshold, amplitude, width, rise/fall times
- User asks about spike train properties: adaptation, ISI, bursts
- User wants to find rheobase or construct f-I curves
- User mentions "AP", "action potential", "spike", "firing"

## Capabilities

### Spike Detection
- dV/dt threshold-based detection (default 20 mV/ms)
- Configurable minimum peak voltage
- Returns spike times, indices, and count

### Individual Spike Features
- **Threshold**: Voltage and time at AP initiation
- **Peak**: Maximum voltage and timing
- **Trough**: Post-spike minimum voltage
- **Amplitude**: Peak - Threshold
- **Width**: Duration at half-amplitude
- **Upstroke**: Maximum dV/dt during depolarization
- **Downstroke**: Maximum dV/dt during repolarization
- **AHP**: After-hyperpolarization depth

### Spike Train Features
- **Firing Rate**: Average spikes per second
- **Latency**: Time to first spike from stimulus onset
- **ISI Statistics**: Mean, CV, distribution
- **Adaptation Index**: Ratio of late to early ISIs
- **Burst Detection**: Identification of high-frequency bursts
- **Pause Detection**: Identification of firing gaps

## Tools Used
- `detect_spikes`: Initial spike detection
- `extract_spike_features`: Detailed per-spike features
- `extract_spike_train_features`: Train-level analysis

## Example Workflows

### Basic Spike Count
```
1. Load file or receive voltage array
2. detect_spikes(voltage, time, dv_cutoff=20, min_peak=-30)
3. Report spike count and times
```

### Full Spike Analysis
```
1. Load file
2. detect_spikes() for initial detection
3. extract_spike_features() for detailed AP analysis
4. extract_spike_train_features() for train properties
5. Interpret firing pattern (regular, adapting, bursting, etc.)
```

### f-I Curve Construction
```
1. Load multi-sweep file with current steps
2. For each sweep:
   - detect_spikes() to count spikes
   - Record (current_amplitude, spike_count/duration)
3. fit_fi_curve() to get gain and rheobase
4. Report f-I relationship
```

## Parameters Reference

| Parameter | Default | Description |
|-----------|---------|-------------|
| dv_cutoff | 20.0 | dV/dt threshold (mV/ms) |
| min_peak | -30.0 | Minimum peak voltage (mV) |
| min_height | 2.0 | Minimum threshold-to-peak height (mV) |

## Notes
- Lower dv_cutoff may be needed for some cell types (e.g., 10 mV/ms)
- Adjust min_peak for cells with lower AP amplitudes
- IPFX is used when available; scipy fallback otherwise
