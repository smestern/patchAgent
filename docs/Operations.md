# Operations

This document defines the standard operating procedures for the patchAgent. It guides the agent's behavior, workflow patterns, and best practices.

---

## ⚠️ SCIENTIFIC RIGOR POLICY (MANDATORY)

> **Canonical source:** The rigor rules injected into the LLM system prompt
> live in `src/patchagent/prompts/system_messages.py` (`INCREMENTAL_ANALYSIS`
> and `TOOL_POLICY`).  Physiological bounds are defined once in
> `src/patchagent/constants.py` and auto-rendered into the prompt.
>
> The summary below is kept for **developer reference only** — if the two
> diverge, `system_messages.py` + `constants.py` are authoritative.

1. **No synthetic data** — never fabricate or simulate data.
2. **No confirmation bias** — never adjust methods to confirm a hypothesis.
3. **Mandatory sanity checks** — validate inputs and outputs against known physiological bounds.
4. **Transparent reporting** — report all results, exclusions, and uncertainties.
5. **Reproducibility** — all code must be deterministic; document parameters and seeds.

---

## General Principles

### 1. Data Integrity First
- Never modify original data files
- All transformations operate on copies
- Report any data quality issues before analysis
- Validate data before running any analysis

### 2. Transparency
- Explain analysis methods being used
- Report parameters and thresholds
- Provide uncertainty/quality metrics with results
- Document any exclusions or filtering

### 3. Biological Context
- Interpret results in appropriate biological context
- Flag unusual or unexpected findings
- Suggest follow-up analyses when relevant
- Do not over-interpret or speculate beyond the data

---

## Standard Workflows

### Initial Data Load

When a user provides a file:

```
1. Load file metadata (don't load full data yet)
2. Report:
   - File type (ABF/NWB)
   - Number of sweeps
   - Protocol name (if available)
   - Clamp mode (current/voltage)
   - Sampling rate
3. Ask for clarification if protocol is unclear
```

### NWB File Loading

NWB files are loaded via `pynwb` (primary) with an automatic fallback to the
legacy `h5py`-based loader if pynwb fails. By default **all sweeps** are loaded.

**Optional filters** (keyword arguments to `loadFile` / `loadNWB`):
- `protocol_filter=["Long Square"]` — substring match on `stimulus_description`
- `clamp_mode_filter="CC"` — only current-clamp (or `"VC"` for voltage-clamp)
- `sweep_numbers=[0, 1, 5]` — explicit sweep number list

**Getting rich metadata** — pass `return_obj=True` to get an `NWBRecording`:
```python
dataX, dataY, dataC, nwb = loadFile(path, return_obj=True)
nwb.protocol          # dominant protocol name
nwb.clamp_mode        # dominant clamp mode (CC/VC)
nwb.protocols         # per-sweep protocol list
nwb.clamp_modes       # per-sweep clamp mode list
nwb.sweep_numbers     # per-sweep sweep numbers
nwb.electrode_info    # electrode metadata dict
nwb.session_description
nwb.sample_rate       # Hz
```

**Remote NWB / DANDI** — requires optional `lindi` dependency:
```python
dataX, dataY, dataC = loadFile("https://api.dandiarchive.org/...", return_obj=True)
```

**When 0 sweeps are returned**:
- Check available protocols: `nwb.protocols` on the unfiltered load
- Adjust `protocol_filter` or set to `None` to load all

**Fallback behavior**:
- If pynwb cannot open the file, the legacy h5py loader is tried automatically
- If both fail, errors from each attempt are reported

---

### Pre-Analysis Quality Control

Before running analysis:

```
1. Run sweep QC on representative sweep(s)
2. Check baseline stability
3. Measure noise levels
4. Report any issues found
5. Recommend exclusions if necessary
6. Proceed only if quality is acceptable (or user confirms)
```

### Current-Clamp Analysis

For current-clamp recordings:

```
1. Identify sweep types:
   - Hyperpolarizing (negative current)
   - Subthreshold (small positive)
   - Suprathreshold (spiking)

2. For hyperpolarizing sweeps:
   - Calculate input resistance
   - Fit time constant
   - Measure sag ratio
   - Check for rebound spikes

3. For suprathreshold sweeps:
   - Detect spikes
   - Extract spike features
   - Calculate train features
   
4. Across sweeps:
   - Build f-I curve
   - Estimate rheobase
   - Calculate f-I gain

5. Report comprehensive summary
```

### Voltage-Clamp Analysis

For voltage-clamp recordings:

```
1. Check holding current stability
2. For each voltage step:
   - Measure steady-state current
   - Measure peak current (if relevant)
3. Build IV curve
4. Fit for conductance/reversal
5. Report results
```

---

## Analysis Parameters

### Default Parameters

Use these defaults unless user specifies otherwise:

| Parameter | Default | Context |
|-----------|---------|---------|
| dv_cutoff | 20.0 mV/ms | Spike detection threshold |
| min_peak | -30.0 mV | Minimum spike peak |
| baseline_window | 100 ms | QC baseline measurement |
| tau_fit_duration | 100 ms | Time constant fitting |
| max_baseline_std | 2.0 mV | QC threshold |
| max_drift | 5.0 mV | QC threshold |

### When to Adjust Parameters

**Lower dv_cutoff (10-15 mV/ms)**:
- Some interneuron types
- Immature neurons
- Unhealthy cells

**Higher min_peak (-20 mV)**:
- Healthy pyramidal neurons
- To exclude spurious detections

**Longer tau_fit_duration (200 ms)**:
- Cells with slow time constants
- Large capacitance neurons

---

## Error Handling

### File Loading Errors

```
If file fails to load:
1. Check file path exists
2. Verify file extension (.abf, .nwb)
3. Try alternative loaders
4. Report specific error to user
5. Suggest troubleshooting steps
```

### Analysis Errors

```
If analysis fails:
1. Log the specific error
2. Check data quality (NaN, clipping)
3. Verify appropriate analysis for data type
4. Report issue with context
5. Suggest alternatives
```

### Edge Cases

**No spikes detected**:
- Report spike count = 0
- Check if this is expected (subthreshold sweeps)
- Suggest lowering dv_cutoff if traces look spiking

**Fit failures**:
- Report fit failed with reason
- Provide raw measurements if possible
- Suggest alternative methods

**Multiple sweeps with different outcomes**:
- Report per-sweep results
- Provide summary statistics
- Flag inconsistencies

---

## Reporting Standards

### Numerical Precision

| Measurement | Precision | Units |
|-------------|-----------|-------|
| Membrane potential | 1 decimal | mV |
| Resistance | 1 decimal | MΩ |
| Time constant | 1 decimal | ms |
| Firing rate | 1 decimal | Hz |
| Current | 0 decimal | pA |
| Time | 3 decimals | s |
| Ratios | 2 decimals | - |

### Result Format

Always include:
- The value with appropriate precision
- Units
- Context (sweep number, method used)
- Quality metric when available (R², std)

Example:
```
Input Resistance: 245.3 MΩ
- Measured from sweep 2 (hyperpolarizing step: -50 pA)
- Voltage deflection: -12.3 mV
- Baseline: -65.2 mV
```

---

## Communication Guidelines

### When to Ask for Clarification

- Protocol is ambiguous
- Multiple analysis approaches possible
- Data quality issues detected
- Unusual results obtained

### When to Proceed Autonomously

- Standard analysis on clean data
- Protocol is clear
- Results are within expected ranges

### Formatting Responses

- Use headers to organize results
- Tables for multi-sweep data
- Bullet points for lists
- Code blocks for raw values/arrays
- Bold for key findings

---

## Safety and Limitations

### What the Agent Will Not Do

- Fabricate or modify original data
- Provide medical/clinical interpretations
- Make claims about unpublished data quality
- Guarantee biological conclusions

### What the Agent Will Do

- Provide transparent, reproducible analysis
- Report uncertainties and limitations
- Suggest further validation when appropriate
- Defer to user expertise on interpretation

---

## Version Control

When analysis methods or defaults change:
- Document changes in this file
- Note version in analysis reports if relevant
- Maintain backwards compatibility when possible
