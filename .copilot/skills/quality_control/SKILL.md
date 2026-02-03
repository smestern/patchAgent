# Quality Control Skill

## Description
Expert in assessing patch-clamp recording quality. Evaluates seal resistance, access resistance, baseline stability, noise levels, and overall recording integrity.

## When to Use
- User asks about recording quality or data quality
- User asks about seal resistance or access resistance
- User mentions noise, stability, or drift
- Before running analysis, to validate data
- User asks to "check" or "validate" recordings
- User asks about QC criteria or thresholds

## Capabilities

### Baseline Stability
- Measures voltage drift over time
- Calculates baseline standard deviation
- Flags unstable recordings
- Thresholds: std < 2 mV, drift < 5 mV

### Noise Assessment
- RMS noise measurement
- Peak-to-peak noise
- High-pass filtering to isolate noise
- Signal-to-noise ratio estimation

### Seal Resistance
- Estimated from test pulse responses
- Minimum acceptable: >1 GΩ for whole-cell
- Critical for low-noise recordings

### Access Resistance (Ra)
- Series resistance monitoring
- Changes indicate seal problems
- Affects voltage-clamp accuracy

### Signal Clipping
- Detects amplifier saturation
- Identifies data loss regions

## Tools Used
- `run_sweep_qc`: Comprehensive sweep QC
- `check_baseline_stability`: Baseline analysis
- `measure_noise`: Noise quantification
- `check_seal_resistance`: Seal quality

## QC Criteria

### Whole-Cell Current-Clamp
| Parameter | Acceptable | Ideal |
|-----------|------------|-------|
| Baseline std | < 3 mV | < 1 mV |
| Baseline drift | < 10 mV | < 3 mV |
| Resting Vm | -50 to -80 mV | -60 to -70 mV |
| Rm | > 50 MΩ | > 100 MΩ |

### Whole-Cell Voltage-Clamp
| Parameter | Acceptable | Ideal |
|-----------|------------|-------|
| Ra | < 30 MΩ | < 15 MΩ |
| Ra change | < 30% | < 15% |
| Holding current | stable | < 100 pA |
| Noise | < 10 pA RMS | < 5 pA RMS |

## Example Workflows

### Pre-Analysis QC Check
```
1. Load file
2. run_sweep_qc() on baseline sweep
3. Check returned issues list
4. If passed: proceed with analysis
5. If failed: report issues to user
```

### Batch QC Assessment
```
1. For each file in batch:
   - run_sweep_qc() on first sweep
   - Record pass/fail and issues
2. Generate QC summary table
3. Recommend exclusions
```

### Detailed Quality Report
```
1. check_baseline_stability() - voltage stability
2. measure_noise() - noise levels
3. Calculate Rm from test sweep
4. Compile comprehensive QC report
5. Flag any concerns
```

## Common Issues and Solutions

### High Baseline Noise
- Possible causes: poor seal, electrical interference
- Check: ground connections, Faraday cage
- May exclude from sensitive analyses

### Baseline Drift
- Possible causes: cell health declining, temperature
- Check: time course of experiment
- May need to exclude late sweeps

### Signal Clipping
- Cause: gain too high, large signals
- Solution: adjust amplifier settings
- Cannot recover clipped data

### Unstable Access Resistance
- Cause: seal degradation, pipette clog
- Check: Ra over time
- May indicate experiment end

## Notes
- Run QC before any quantitative analysis
- Document QC criteria used
- Conservative exclusion protects data quality
- Some analyses are more sensitive to QC issues
