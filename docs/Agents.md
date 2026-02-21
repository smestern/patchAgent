# Agents

This document defines the sub-agents available in patchAgent.  Each
agent is specialized for a particular aspect of patch-clamp analysis and
is available as a VS Code Copilot Chat agent (`.github/agents/`) and a
Claude Code sub-agent (`.claude/agents/`).

## Overview

| Agent | Role | File (VS Code) | File (Claude) |
|-------|------|-----------------|---------------|
| `patch-analyst` | Main coordinator | *Python class* | *Python class* |
| `analysis-planner` | Step-by-step planning | `.github/agents/analysis-planner.agent.md` | `.claude/agents/analysis-planner.md` |
| `data-qc` | Data quality control | `.github/agents/data-qc.agent.md` | `.claude/agents/data-qc.md` |
| `qc-checker` | Patch-clamp QC specialist | `.github/agents/qc-checker.agent.md` | `.claude/agents/qc-checker.md` |
| `spike-analyst` | Action potential expert | `.github/agents/spike-analyst.agent.md` | `.claude/agents/spike-analyst.md` |
| `passive-analyst` | Membrane properties expert | `.github/agents/passive-analyst.agent.md` | `.claude/agents/passive-analyst.md` |
| `rigor-reviewer` | Scientific rigor audit | `.github/agents/rigor-reviewer.agent.md` | `.claude/agents/rigor-reviewer.md` |
| `report-writer` | Publication-quality reports | `.github/agents/report-writer.agent.md` | `.claude/agents/report-writer.md` |
| `code-reviewer` | Script review & best practices | `.github/agents/code-reviewer.agent.md` | `.claude/agents/code-reviewer.md` |

## Handoff Workflow

Agents connect via handoff buttons to form a complete analysis pipeline:

```
analysis-planner
  ├─→ data-qc
  │     └─→ qc-checker
  │           ├─→ spike-analyst ──→ rigor-reviewer ──→ report-writer
  │           └─→ passive-analyst ─→ rigor-reviewer ──→ report-writer
  ├─→ spike-analyst
  └─→ passive-analyst

code-reviewer  ← standalone, invoke on any script
```

### Using Agents in VS Code Copilot Chat

In VS Code Copilot Chat, type `@` followed by the agent name:

- `@analysis-planner Plan an analysis for this ABF file`
- `@spike-analyst Detect spikes in the loaded data`
- `@qc-checker Check recording quality`

After an agent finishes, click the handoff button (e.g., "Run Data QC",
"Review Rigor") to pass results to the next agent in the pipeline.

### Using Agents in Claude Code

Run `claude` in the patchAgent directory.  Claude automatically discovers
agents in `.claude/agents/`.  Use `/agent spike-analyst` to invoke a
specific sub-agent.

---

## Shared Instructions

All agents reference a shared set of scientific rigor principles at
`.github/instructions/sciagent-rigor.instructions.md`.  These include:

1. Data integrity (no synthetic data)
2. Objective analysis (no hypothesis confirmation bias)
3. Sanity checks (validate inputs, flag out-of-range values)
4. Transparent reporting (include all results)
5. Uncertainty & error (CI/SEM/SD mandatory)
6. Reproducibility (seeds, versions, parameters)
7. Shell/terminal policy (no analysis via shell)
8. Rigor warnings (never suppress)
9. Patch-clamp specific (IPFX for spikes, physiological bounds, no synthetic traces)

---

## patch-analyst (Main Agent)

**Role**: Primary analysis coordinator

**Description**: The main patch-clamp analysis agent.  Orchestrates
analysis workflows, delegates to specialist sub-agents when appropriate,
and provides comprehensive interpretations.

**Implementation**: Python class `PatchAgent` in `src/patchagent/agent.py`

**Capabilities**:
- Full access to all tools and skills
- Workflow orchestration (e.g., QC → analysis → interpretation)
- Protocol identification
- Result interpretation with biological context

**When to Use**: Default agent for general analysis requests.

---

## analysis-planner

**Role**: Pre-execution planning

**Description**: Creates step-by-step analysis plans before any code runs.
Designs the roadmap, specifies parameters, and anticipates risks.

**Capabilities**:
- Research question clarification
- Data survey and protocol identification
- Pipeline design with parameter recommendations
- Risk assessment and fallback strategies
- Incremental validation planning

**Handoffs**: → `data-qc`, → `spike-analyst`, → `passive-analyst`

**When to Use**:
- "Plan an analysis for this recording"
- "What's the best approach for this dataset?"
- "Design a pipeline for f-I curve analysis"

---

## data-qc

**Role**: General data quality control

**Description**: Checks data quality before analysis — missing values,
outliers, distributions, unit validation, and structural integrity.

**Capabilities**:
- Structural integrity checks (file loading, shape, types)
- Missing data detection and pattern analysis
- Outlier identification against physiological bounds
- Distribution analysis and summary statistics
- Unit and scaling validation

**Handoffs**: → `qc-checker` (deep patch-clamp QC), → user

**When to Use**:
- "Check data quality before analysis"
- "Are there any issues with this file?"
- "Summarize the data structure"

---

## qc-checker

**Role**: Patch-clamp recording quality specialist

**Description**: Assesses recording quality and identifies potential
issues specific to patch-clamp electrophysiology.  Conservative approach.

**Capabilities**:
- Seal resistance assessment (> 1 GΩ)
- Access/series resistance monitoring (< 20 MΩ, < 20% change)
- Baseline stability (drift < 5 mV, noise RMS < 2 mV)
- Cell health indicators (Vm, Rm stability, holding current)
- Signal quality (clipping, 60 Hz noise, bridge balance)
- Sweep-by-sweep QC reports

**Handoffs**: → `spike-analyst`, → `passive-analyst`, → user

**When to Use**:
- "Check the recording quality"
- "Is this cell healthy?"
- "Should I exclude this sweep?"
- "What's the access resistance?"

---

## spike-analyst

**Role**: Action potential specialist

**Description**: Expert in detecting and characterizing action potentials.
Analyzes firing patterns, extracts spike features, and interprets
neuronal excitability.

**Capabilities**:
- Spike detection with IPFX (dV/dt = 20 mV/ms, min peak = −30 mV)
- Individual AP feature extraction (threshold, amplitude, width, kinetics)
- Spike train analysis (adaptation, bursts, ISI statistics)
- Firing pattern classification
- f-I curve construction and rheobase determination

**Handoffs**: → `rigor-reviewer`, → `report-writer`

**When to Use**:
- "Detect spikes in this trace"
- "What's the firing rate?"
- "Analyze the action potential features"
- "Is this cell adapting?"
- "Find the rheobase"

---

## passive-analyst

**Role**: Subthreshold membrane properties specialist

**Description**: Expert in passive membrane properties.  Calculates input
resistance, time constant, sag, and other subthreshold characteristics.

**Capabilities**:
- Input resistance (Rm) from ΔV/ΔI or I-V slope
- Membrane time constant (τ) from single/double exponential fits
- Sag ratio quantification
- Resting membrane potential measurement
- Capacitance estimation (Cm = τ / Rm)

**Handoffs**: → `rigor-reviewer`, → `report-writer`

**When to Use**:
- "What's the input resistance?"
- "Calculate the time constant"
- "How much sag is there?"
- "Measure the resting potential"

---

## rigor-reviewer

**Role**: Scientific rigor auditor

**Description**: Reviews analysis output for scientific rigor violations —
statistical validity, data integrity, reproducibility, and reporting
completeness.

**Capabilities**:
- Statistical test appropriateness review
- Uncertainty and sample size validation
- Data integrity audit (no synthetic data, documented exclusions)
- Reproducibility check (seeds, versions, parameters)
- Physiological bounds validation
- Visualization integrity review

**Handoffs**: → `report-writer`

**When to Use**:
- "Review these results for rigor"
- "Is this analysis statistically valid?"
- "Check if I missed anything"

---

## report-writer

**Role**: Scientific report generator

**Description**: Synthesises analysis results into publication-quality
Markdown reports with figures, tables, uncertainty quantification, and
reproducibility information.

**Capabilities**:
- Structured report generation (Methods, Results, Figures, Tables)
- Patch-clamp-specific sections (recording conditions, QC, passive/active properties)
- Formal terminology and proper units
- Uncertainty reporting (mean ± SD, N, CI)
- Standard figure recommendations

**When to Use**:
- "Write a report for this analysis"
- "Summarize the results"
- "Generate a methods section"

---

## code-reviewer

**Role**: Analysis script reviewer

**Description**: Reviews analysis scripts for correctness, reproducibility,
and adherence to patch-clamp best practices.  Does not modify code.

**Capabilities**:
- Correctness review (computations, edge cases, indexing)
- Reproducibility audit (seeds, versions, paths)
- Anti-pattern detection (find_peaks, Nyquist violations, synthetic data)
- Import and library best practices
- IPFX usage validation

**When to Use**:
- "Review this analysis script"
- "Check this code for issues"
- "Is this IPFX usage correct?"

---

## curve-fitter

**Role**: Curve fitting specialist

**Description**: Expert in fitting mathematical models to
electrophysiology data.  Provides various fitting methods with quality
metrics.

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

### VS Code Copilot Chat

Create a new `.agent.md` file in `.github/agents/`:

```yaml
---
description: >-
  One-line description of the agent's role.
name: my-agent
tools:
  - codebase
  - terminal
  - search
handoffs:
  - label: "Next Step"
    agent: rigor-reviewer
    prompt: "Review the results above."
    send: false
---

## My Agent

Instructions for the agent...

## Domain Customization

Patch-clamp-specific guidance...
```

### Claude Code

Create a `.md` file in `.claude/agents/` with simplified frontmatter:

```yaml
---
name: my-agent
description: >-
  One-line description.
tools: Read, Write, Edit, Bash, Grep, Glob
model: sonnet
---

## My Agent

Instructions with inline rigor principles...
```

### Python (for the main PatchAgent)

1. Define the agent configuration in `src/patchagent/agent.py`
2. Create a system message in `src/patchagent/prompts/system_messages.py`
3. Document the agent in this file
