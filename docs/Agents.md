# Agents

This document defines the sub-agents available in patchAgent. Each agent is specialized for a particular aspect of patch-clamp analysis.

## Overview

| Agent | Role | Primary Skills |
|-------|------|----------------|
| `patch-analyst` | Main coordinator | All skills |
| `spike-analyst` | Action potential expert | spike_analysis |
| `passive-analyst` | Membrane properties expert | passive_properties |
| `qc-checker` | Quality control specialist | quality_control |
| `curve-fitter` | Fitting specialist | curve_fitting |

---

## patch-analyst (Main Agent)

**Role**: Primary analysis coordinator

**Description**: The main patch-clamp analysis agent. Orchestrates analysis workflows, delegates to specialist sub-agents when appropriate, and provides comprehensive interpretations.

**Capabilities**:
- Full access to all tools and skills
- Workflow orchestration (e.g., QC → analysis → interpretation)
- Protocol identification
- Result interpretation with biological context

**When to Use**: Default agent for general analysis requests.

---

## spike-analyst

**Role**: Action potential specialist

**Description**: Expert in detecting and characterizing action potentials. Analyzes firing patterns, extracts spike features, and interprets neuronal excitability.

**Capabilities**:
- Spike detection with configurable thresholds
- Individual AP feature extraction (threshold, amplitude, width, kinetics)
- Spike train analysis (adaptation, bursts, ISI statistics)
- Firing pattern classification
- f-I curve construction and rheobase determination

**When to Use**:
- "Detect spikes in this trace"
- "What's the firing rate?"
- "Analyze the action potential features"
- "Is this cell adapting?"
- "Find the rheobase"

---

## passive-analyst

**Role**: Subthreshold membrane properties specialist

**Description**: Expert in passive membrane properties. Calculates input resistance, time constant, sag, and other subthreshold characteristics.

**Capabilities**:
- Input resistance (Rm) calculation
- Membrane time constant (τ) from exponential fits
- Sag ratio quantification
- Resting membrane potential measurement
- Capacitance estimation

**When to Use**:
- "What's the input resistance?"
- "Calculate the time constant"
- "How much sag is there?"
- "Measure the resting potential"

---

## qc-checker

**Role**: Quality control specialist

**Description**: Assesses recording quality and identifies potential issues. Conservative approach to data quality.

**Capabilities**:
- Baseline stability assessment
- Noise level measurement
- Seal resistance estimation
- Access resistance monitoring
- Signal clipping detection
- Comprehensive QC reports

**When to Use**:
- "Check the data quality"
- "Is this recording stable?"
- "Should I exclude this sweep?"
- "What's the noise level?"

---

## curve-fitter

**Role**: Curve fitting specialist

**Description**: Expert in fitting mathematical models to electrophysiology data. Provides various fitting methods with quality metrics.

**Capabilities**:
- Exponential decay/growth fits
- Double exponential fits
- IV curve analysis (linear, polynomial)
- f-I curve fitting (linear, square-root)
- Goodness-of-fit metrics

**When to Use**:
- "Fit an exponential to this decay"
- "Analyze the IV curve"
- "What's the gain from the f-I curve?"
- "Fit a double exponential"

---

## Adding Custom Agents

To add a custom agent:

1. Define the agent configuration in `src/patch_agent/agent.py`
2. Create a system message in `src/patch_agent/prompts/system_messages.py`
3. Document the agent in this file

```python
# Example agent definition
CUSTOM_AGENT = {
    "name": "custom-analyst",
    "display_name": "Custom Analysis Agent",
    "description": "Description of the agent's role",
    "skills": ["skill1", "skill2"],
}
```
