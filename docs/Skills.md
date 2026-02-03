# Skills

This document provides an overview of the skills available to patchAgent. Each skill is defined in detail in its own file under `.copilot/skills/`.

## Skill Overview

| Skill | Location | Description |
|-------|----------|-------------|
| Spike Analysis | [.copilot/skills/spike_analysis/SKILL.md](../.copilot/skills/spike_analysis/SKILL.md) | Action potential detection and feature extraction |
| Passive Properties | [.copilot/skills/passive_properties/SKILL.md](../.copilot/skills/passive_properties/SKILL.md) | Subthreshold membrane property analysis |
| Quality Control | [.copilot/skills/quality_control/SKILL.md](../.copilot/skills/quality_control/SKILL.md) | Recording quality assessment |
| Curve Fitting | [.copilot/skills/curve_fitting/SKILL.md](../.copilot/skills/curve_fitting/SKILL.md) | Mathematical model fitting |

---

## Spike Analysis

**File**: `.copilot/skills/spike_analysis/SKILL.md`

**Purpose**: Detect and analyze action potentials in current-clamp recordings.

**Key Capabilities**:
- dV/dt threshold-based spike detection
- Individual spike features (threshold, amplitude, width, kinetics)
- Spike train features (adaptation, ISI, bursts)
- f-I curve analysis

**Trigger Keywords**: spike, action potential, AP, firing, threshold, rheobase

---

## Passive Properties

**File**: `.copilot/skills/passive_properties/SKILL.md`

**Purpose**: Calculate subthreshold membrane properties.

**Key Capabilities**:
- Input resistance (Rm)
- Membrane time constant (τ)
- Sag ratio (Ih contribution)
- Resting membrane potential
- Capacitance estimation

**Trigger Keywords**: input resistance, Rm, tau, time constant, sag, passive, subthreshold

---

## Quality Control

**File**: `.copilot/skills/quality_control/SKILL.md`

**Purpose**: Assess recording quality and identify issues.

**Key Capabilities**:
- Baseline stability
- Noise measurement
- Seal/access resistance
- Signal clipping detection

**Trigger Keywords**: quality, QC, noise, stable, drift, check

---

## Curve Fitting

**File**: `.copilot/skills/curve_fitting/SKILL.md`

**Purpose**: Fit mathematical models to data.

**Key Capabilities**:
- Exponential fits (single, double)
- IV curve analysis
- f-I curve fitting
- Goodness-of-fit metrics

**Trigger Keywords**: fit, curve, exponential, IV, f-I, regression

---

## Adding New Skills

1. Create a new directory: `.copilot/skills/<skill_name>/`
2. Add `SKILL.md` with the skill definition
3. Update this document with the new skill

### Skill File Template

```markdown
# Skill Name

## Description
Brief description of the skill's purpose.

## When to Use
- Trigger condition 1
- Trigger condition 2

## Capabilities
### Capability 1
Details...

### Capability 2
Details...

## Tools Used
- tool_1
- tool_2

## Example Workflows
### Workflow 1
```
1. Step 1
2. Step 2
```

## Parameters Reference
| Parameter | Default | Description |
|-----------|---------|-------------|
| param1    | value   | description |

## Notes
Additional information...
```
