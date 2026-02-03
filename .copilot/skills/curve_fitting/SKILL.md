# Curve Fitting Skill

## Description
Expert in fitting mathematical models to electrophysiology data. Provides exponential fits, IV curve analysis, f-I curve characterization, and general curve fitting utilities.

## When to Use
- User asks to fit data or find a curve
- User asks about IV curves or current-voltage relationships
- User asks about f-I curves or frequency-current relationships
- User needs exponential decay or growth fits
- User asks about time constants from fits
- User mentions "regression", "fit", "curve"

## Capabilities

### Exponential Fitting
- Single exponential decay: y = A·exp(-t/τ) + offset
- Single exponential growth: y = A·(1 - exp(-t/τ)) + offset
- Double exponential: fast and slow components
- Returns amplitude, time constant, R²

### IV Curve Analysis
- Linear fit for ohmic relationships
- Polynomial fit for non-linear curves
- Extracts conductance (slope)
- Estimates reversal potential
- Derives input resistance

### f-I Curve Analysis
- Linear fit for gain calculation
- Square-root fit for Type I neurons
- Rheobase estimation
- Maximum firing rate

### General Fitting
- Polynomial fits of arbitrary order
- Custom function fitting
- Goodness-of-fit metrics

## Tools Used
- `fit_exponential`: Single exponential fits
- `fit_double_exponential`: Bi-exponential fits
- `fit_iv_curve`: Current-voltage relationships
- `fit_fi_curve`: Frequency-current relationships

## Example Workflows

### Time Constant from Voltage Response
```
1. Extract voltage response to current step
2. Identify fit window (step onset to ~100 ms)
3. fit_exponential(voltage, time, fit_type='decay')
4. Report τ and fit quality (R²)
```

### IV Curve from Voltage-Clamp
```
1. For each voltage step:
   - Measure steady-state current
   - Record (voltage, current) pair
2. fit_iv_curve(voltages, currents, fit_type='linear')
3. Report conductance, reversal potential
```

### f-I Curve from Current-Clamp
```
1. For each current step:
   - Count spikes
   - Calculate firing rate
   - Record (current, rate) pair
2. fit_fi_curve(currents, rates, fit_type='linear')
3. Report gain (Hz/pA) and rheobase
```

### Double Exponential for EPSC Decay
```
1. Extract EPSC waveform
2. Identify decay phase
3. fit_double_exponential(current, time)
4. Report τ_fast, τ_slow, amplitudes
```

## Parameters Reference

### fit_exponential
| Parameter | Default | Description |
|-----------|---------|-------------|
| fit_type | 'decay' | 'decay' or 'growth' |
| p0 | auto | Initial guess [amp, tau, offset] |

### fit_iv_curve
| Parameter | Default | Description |
|-----------|---------|-------------|
| fit_type | 'linear' | 'linear' or 'polynomial' |
| voltage_range | None | Optional (min, max) filter |

### fit_fi_curve
| Parameter | Default | Description |
|-----------|---------|-------------|
| fit_type | 'linear' | 'linear' or 'sqrt' |
| current_range | None | Optional (min, max) filter |

## Interpretation Guidelines

### Exponential Fits
- R² > 0.95: Excellent fit
- R² 0.90-0.95: Good fit
- R² < 0.90: Consider different model

### IV Curve Slopes
- Positive slope: outward rectification
- Negative slope: inward rectification
- Zero crossing: reversal potential

### f-I Gain
- Type I neurons: often sqrt relationship
- Type II neurons: often linear after threshold
- Typical gain: 0.1-0.5 Hz/pA

## Notes
- Always check R² to validate fit quality
- Visualize fits when possible
- Consider biological plausibility
- Multiple models may fit similarly - use simplest
- Outliers can strongly affect fits
