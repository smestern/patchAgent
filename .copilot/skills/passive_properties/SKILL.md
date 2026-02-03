# Passive Properties Skill

## Description
Expert in analyzing subthreshold membrane properties from patch-clamp recordings. Calculates input resistance, membrane time constant, sag ratio, and resting membrane potential.

## When to Use
- User asks about input resistance (Rm, Rin)
- User asks about membrane time constant (tau, τ)
- User asks about sag or Ih current
- User asks about resting membrane potential (Vm, RMP)
- User asks about capacitance (Cm)
- User has hyperpolarizing current step data
- User mentions "passive properties", "membrane properties", "subthreshold"

## Capabilities

### Input Resistance (Rm)
- Calculated from voltage deflection to current step
- Uses steady-state voltage response
- Reports in MΩ
- Formula: Rm = ΔV / ΔI

### Membrane Time Constant (τ)
- Exponential fit to voltage response onset
- Single or double exponential fitting
- Reports in ms
- Indicates membrane charging speed

### Sag Ratio
- Quantifies Ih (hyperpolarization-activated current)
- Ratio of peak to steady-state deflection
- Values: 0 (no sag) to ~0.5 (strong sag)
- Formula: (V_peak - V_steady) / (V_peak - V_baseline)

### Resting Membrane Potential
- Baseline voltage measurement
- Multiple methods: mean, median, mode
- Reports in mV

### Capacitance (Cm)
- Derived from τ and Rm
- Formula: Cm = τ / Rm
- Reports in pF

## Tools Used
- `calculate_input_resistance`: Rm from current steps
- `calculate_time_constant`: τ from exponential fit
- `calculate_sag`: Sag ratio from hyperpolarizing steps
- `calculate_resting_potential`: Baseline Vm
- `fit_exponential`: Custom exponential fitting

## Example Workflows

### Basic Passive Properties
```
1. Load hyperpolarizing current step data
2. calculate_resting_potential() for baseline Vm
3. calculate_input_resistance() for Rm
4. calculate_time_constant() for τ
5. calculate_sag() for sag ratio
6. Derive Cm = τ / Rm
7. Report all properties with units
```

### Multiple Sweep Analysis
```
1. Load file with multiple hyperpolarizing sweeps
2. For each sweep with negative current:
   - Calculate Rm from that sweep
3. Average Rm across sweeps
4. Report mean ± SEM
```

## Parameters Reference

| Parameter | Default | Description |
|-----------|---------|-------------|
| baseline_start | 0 | Start of baseline window (s) |
| baseline_end | 0.1 | End of baseline window (s) |
| response_start | auto | Start of response measurement (s) |
| response_end | auto | End of response measurement (s) |
| fit_duration | 0.1 | Duration for tau fitting (s) |

## Interpretation Guidelines

### Input Resistance
- Typical pyramidal neuron: 100-300 MΩ
- Interneurons often lower: 50-150 MΩ
- Higher Rm = more excitable

### Time Constant
- Typical range: 10-50 ms
- Longer τ = slower temporal integration
- Affects EPSP summation

### Sag Ratio
- No Ih: ~0
- Moderate Ih: 0.1-0.2
- Strong Ih: 0.2-0.4
- Cell type marker (e.g., CA1 pyramidal)

## Notes
- Use hyperpolarizing steps (typically -50 to -100 pA)
- Avoid steps that trigger rebound spikes
- Ensure steady-state is reached before measurement
- Temperature affects all passive properties
