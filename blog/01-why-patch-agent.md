# What is PatchAgent
*See: [What is Patch-Clamp Electrophysiology?](01-what-is-patch-clamp.md)*  

## The Gap

In a typical electrophysiology lab:

1. **The experimentalist** spends hours at the rig recording patch-clamp data from neurons — a demanding, highly skilled procedure.
2. **The data** comes out as ABF or NWB files, each containing dozens of sweeps of voltage and current traces.
3. **The analysis** — spike detection, passive property extraction, quality control, curve fitting — requires writing Python code using libraries like [pyABF](https://github.com/swharden/pyABF), [IPFX](https://ipfx.readthedocs.io/), NumPy, and SciPy.
4. **The biologist** often has *limited programming experience*.

Step 4 is where everything breaks down.

### It's Not That Biologists Can't Code

Many bench scientists have taken a Python course or two. They can write a for loop and make a scatter plot. But electrophysiology analysis isn't beginner-friendly:

- **Spike detection** needs dV/dt-based threshold crossing — not a simple `find_peaks()` call (which is a [common mistake](https://ipfx.readthedocs.io/) that misidentifies artifacts as spikes).
- **Time constant fitting** requires selecting the right window, choosing single vs. double exponential, and validating the fit quality.
- **f-I curves** require combining data across many sweeps, correctly mapping stimulus amplitudes to firing rates.
- **Quality control** is a judgment call about baseline drift, noise levels, and series resistance — experienced analysts *know* when data looks wrong, but encoding that knowledge in code is nontrivial.

The result? Biologists spend more time fighting Python than thinking about biology. They copy-paste scripts from lab mates (which may contain subtle bugs), use commercial tools (expensive and opaque), or just skip certain analyses entirely.

### Why Not Just Ask ChatGPT?

The LLM revolution has given scientists a powerful new tool: they can describe an analysis in English and get Python code back. And for many tasks, this works well enough.

But for electrophysiology, generic AI assistants fall short in critical ways:

| Problem | What Goes Wrong |
|---|---|
| **No domain guardrails** | An LLM will happily use `scipy.signal.find_peaks()` on a voltage trace to "detect spikes." This is *scientifically wrong* — it misses subthreshold events and catches artefacts. Proper spike detection uses dV/dt threshold criteria. |
| **Hallucinated analysis** | Asked to analyze a file it can't actually read, a generic LLM may generate plausible-looking but completely fabricated numbers. |
| **No data access** | Chat-based LLMs can't load your ABF file, run your analysis, and return real results. They can only generate code for you to run yourself. |
| **No quality control** | A generic assistant won't warn you that your recording's input resistance is drifting, or that the baseline is too noisy for reliable spike detection. |
| **No reproducibility** | Every conversation starts from scratch. There's no standardized workflow, no saved parameters, no audit trail. |

What biologists need isn't a literature-review chatbot or a general-purpose code generator. They need a **specialized coding agent** — one that:

- Actually loads and analyzes their data files
- Uses validated, peer-reviewed analysis methods
- Refuses to cut corners or fabricate results
- Speaks the language of electrophysiology

## The Solution: patchAgent

**patchAgent** is a conversational AI agent purpose-built for patch-clamp electrophysiology. It wraps battle-tested analysis libraries behind a natural-language interface, with scientific guardrails baked in at every layer.

### What It Is

At its core, patchAgent is a [GitHub Copilot SDK](https://github.com/github/copilot-sdk) agent with 20 specialized tools spanning six categories:

| Category | Examples | What They Do |
|---|---|---|
| **I/O** | `load_file`, `list_sweeps` | Load ABF/NWB files, inspect sweep metadata |
| **Spike analysis** | `detect_spikes`, `extract_spike_features` | AP detection via IPFX (dV/dt-based), per-spike and train-level metrics |
| **Passive properties** | `calculate_input_resistance`, `calculate_time_constant` | Rm, τ, sag, resting Vm from subthreshold sweeps |
| **Quality control** | `run_sweep_qc`, `check_baseline_stability` | Baseline drift, noise, clipping detection |
| **Curve fitting** | `fit_iv_curve`, `fit_fi_curve` | Linear/polynomial IV, linear/sqrt f-I |
| **Code execution** | `execute_code`, `validate_code` | Sandboxed Python with rigor enforcement |


### How It Works (30-Second Version)

```
You:     "Load cell_001.abf and measure the input resistance"

Agent:   1. Calls load_file → reads the ABF, returns 20 sweeps at 20 kHz
         2. Identifies hyperpolarizing current steps
         3. Calls calculate_input_resistance → fits V/I slope
         4. Reports: "Rm = 182.4 ± 12.3 MΩ (N=5 sweeps)"
         5. Flags if the value is outside expected physiological range
```

You ask in plain English. The agent translates that into the right sequence of tool calls, executes them against your actual data, and reports results with appropriate units, uncertainty, and quality flags.

## Built-In Guard Rails

This is where patchAgent differs most from a generic AI assistant. We don't just *hope* the LLM does the right thing — we enforce it structurally at multiple layers. Here's a preview (we'll go deeper in a [dedicated post](04-guardrails.md)):

### 🔒 No Fake Data — Ever

The agent's code sandbox scans every snippet before execution. Patterns like `np.random.rand()`, `fake`, `dummy`, or `synthetic` are **blocked outright** — the code won't run. This isn't a prompt instruction the model can ignore; it's a regex-based hard gate in the execution pipeline.

### 🔒 The Right Tools First

The system prompt encodes a strict priority order:

1. **Built-in tools** — validated, peer-reviewed implementations
2. **IPFX** (Allen Institute) — battle-tested electrophysiology library  
3. **Custom code** — only as a last resort, and even then it's scanned

The agent is explicitly forbidden from reimplementing spike detection with `find_peaks`, writing custom dV/dt threshold code, or hand-rolling feature extraction when a validated tool already exists.

### 🔒 Physiological Sanity Checks

Every measurement is checked against hard-coded physiological bounds. An input resistance of 50,000 MΩ? A resting potential of +20 mV? The agent flags it — loudly — before you build a paper on bogus numbers.

### 🔒 Validated Inputs

Before any analysis runs, the agent validates your data: NaN values, Inf values, zero variance, suspiciously smooth traces (possible synthetic data). Problems are reported before they can silently corrupt results.

## Who This Is For

patchAgent was built with a specific user in mind:

> A graduate student or postdoc who runs patch-clamp experiments, has basic Python familiarity (can install packages and run scripts), but doesn't want to spend weeks writing and debugging analysis code.

You know what input resistance *is*. You know why spike half-width matters. You just need help turning that domain knowledge into working, validated analysis — and patchAgent is that help.

## Open Source

patchAgent is [MIT-licensed](https://github.com/smestern/patchAgent) and fully open source. The tools can be used standalone (without the agent framework) as a regular Python library, and the agent is extensible via the [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) for IDE integration.

---

## Key Takeaways

- Electrophysiologists have domain expertise but often limited coding experience — generic AI assistants don't fill this gap safely.
- patchAgent is a **specialized coding agent** that loads real data, runs validated analysis, and enforces scientific rigor.
- Guard rails are structural — not just prompt instructions — preventing fake data, wrong methods, and implausible results.
- It's open source, extensible, and built for the bench scientist who knows *what* to measure but needs help writing the code.

---

*See: [What is Patch-Clamp Electrophysiology?](01-what-is-patch-clamp.md)*  
*Next: [A Walkthrough: Analyzing a Cell with patchAgent →](03-example-walkthrough.ipynb)*
