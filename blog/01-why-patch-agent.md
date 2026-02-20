# What is PatchAgent
*See: [What is Patch-Clamp Electrophysiology?](02-what-is-patch-clamp.md)*  

## The Gap

If you've spent any time in an electrophysiology lab, you know the workflow. You spend hours at the rig, carefully patching neurons, collecting beautiful data across dozens of sweeps. The data comes out as ABF or NWB files. And then... you have to actually analyze it.

This is where things tend to fall apart for a lot of people.

The analysis side — spike detection, passive property extraction, QC, curve fitting — lives firmly in Python-land. You need [pyABF](https://github.com/swharden/pyABF), [IPFX](https://ipfx.readthedocs.io/), NumPy, SciPy, and a decent amount of coding experience to string it all together. But a huge number of electrophysiologists come from biology backgrounds. They've taken a Python course or two, can write a for loop and make a scatter plot, but the analysis side is a real bottleneck.

It's not that biologists *can't* code — it's that electrophysiology analysis is genuinely tricky, even for people who are comfortable with Python:

- Spike detection needs dV/dt-based threshold crossing — not a simple `find_peaks()` call (which is a [common mistake](https://ipfx.readthedocs.io/) that misidentifies artifacts as spikes)
- Time constant fitting requires picking the right window, choosing single vs. double exponential, and making sure the fit is actually good
- f-I curves require combining data across many sweeps, correctly mapping stimulus amplitudes to firing rates
- Quality control is a judgment call — experienced analysts just *know* when data looks wrong, but encoding that in code is nontrivial

So what actually happens? People spend more time fighting Python than thinking about biology. They copy-paste scripts from lab mates (which may contain subtle bugs), use commercial tools (expensive, opaque), or just skip certain analyses entirely. It's not great.

### Why Not Just Ask ChatGPT?

Fair question. The LLM revolution has been legitimately helpful — you can describe what you want in English and get Python code back. For a lot of tasks, that works well enough.

But for electrophysiology specifically, I've found that generic AI assistants fall short in ways that really matter:

- **No domain guardrails.** An LLM will happily use `scipy.signal.find_peaks()` on a voltage trace to "detect spikes." This is scientifically wrong — it misses subthreshold events and catches artefacts. Proper spike detection uses dV/dt threshold criteria.
- **Hallucinated analysis.** Ask it to analyze a file it can't actually read, and it'll generate plausible-looking but completely fabricated numbers. I've seen this happen more times than I'd like.
- **No data access.** Chat-based LLMs can't load your ABF file, run your analysis, and return real results. They can only generate code for *you* to run.
- **No quality control.** A generic assistant won't warn you that your recording's input resistance is drifting, or that the baseline is too noisy for reliable spike detection.
- **No reproducibility.** Every conversation starts from scratch. No standardized workflow, no saved parameters, no audit trail.

What researchers actually need isn't a literature-review chatbot or a general-purpose code generator — it's a specialized coding agent that loads and analyzes their actual data, uses validated methods, and refuses to cut corners.

## So... PatchAgent

patchAgent is basically that. It's a conversational AI agent purpose-built for patch-clamp electrophysiology. Under the hood, it wraps well-tested analysis libraries (pyABF, IPFX, NumPy, SciPy) behind a natural-language interface, with scientific guardrails baked in at multiple levels.

It's built on the [GitHub Copilot SDK](https://github.com/github/copilot-sdk) and has about 20 specialized tools spanning I/O, spike analysis, passive properties, QC, curve fitting, and sandboxed code execution. Think of it like this:

```
You:     "Load cell_001.abf and measure the input resistance"

Agent:   1. Calls load_file → reads the ABF, returns 20 sweeps at 20 kHz
         2. Identifies hyperpolarizing current steps
         3. Calls calculate_input_resistance → fits V/I slope
         4. Reports: "Rm = 182.4 ± 12.3 MΩ (N=5 sweeps)"
         5. Flags if the value is outside expected physiological range
```

You ask a question in plain English. The agent figures out which tools to call, runs them against your actual data, and gives you results with appropriate units, uncertainty, and quality flags. No copying code into a notebook and debugging import errors.

## Guard Rails (the important part)

This is honestly where patchAgent differs most from a generic AI assistant. Rather than just *hoping* the LLM does the right thing, we actually enforce it structurally. I go into a lot more detail in a [dedicated post](04-guardrails.md), but the highlights:

**No fake data, ever.** The code sandbox scans every snippet before execution. Patterns like `np.random.rand()`, `fake`, `dummy`, or `synthetic` get blocked outright — the code simply won't run. This isn't a prompt instruction the model can choose to ignore; it's a regex-based hard gate in the execution pipeline.

**The right tools first.** The system prompt encodes a strict priority: built-in validated tools first, then IPFX (Allen Institute's library), then custom code only as a last resort. The agent is explicitly forbidden from reimplementing spike detection with `find_peaks` or hand-rolling feature extraction when a validated tool already exists.

**Physiological sanity checks.** Every measurement gets checked against hard-coded physiological bounds. Input resistance of 50,000 MΩ? Resting potential of +20 mV? The agent flags it before you build a paper on bogus numbers.

**Input validation.** Before any analysis runs, the data itself gets checked: NaN values, Inf values, zero variance, suspiciously smooth traces (which might be synthetic). Problems get flagged before they can silently corrupt results.

## Who is this for?

I built this with a pretty specific person in mind: a grad student or postdoc who runs patch-clamp experiments, knows enough Python to install packages and run scripts, but doesn't want to spend weeks writing and debugging analysis code. You know what input resistance *is*. You know why spike half-width matters. You just need help turning that domain knowledge into working, validated code.

patchAgent is [MIT-licensed](https://github.com/smestern/patchAgent) and fully open source. The tools can be used standalone (without the agent framework) as a regular Python library, and the whole thing is extensible via [MCP](https://modelcontextprotocol.io/) for IDE integration.

*See: [What is Patch-Clamp Electrophysiology?](02-what-is-patch-clamp.md)*  
*Next: [A Walkthrough: Analyzing a Cell with patchAgent →](03-example-walkthrough.ipynb)*
