# Guardrails: Keeping AI Honest in Science

## Why This Matters More Than You Think

When an AI helps you write a marketing email and hallucinates something, it's embarrassing. When an AI helps you analyze scientific data and hallucinates something, you might build a paper on fabricated numbers, waste months on follow-up experiments, or — in translational work — mislead drug development.

LLMs are stochastic text generators. They're really, really good at producing plausible output, and that's precisely what makes them dangerous in a scientific context. I've personally seen a generic ChatGPT session do all of the following:

- Generate fake data that looks completely real ("here are the spike features for your cell")
- Use `scipy.signal.find_peaks()` on a voltage trace instead of proper dV/dt-based spike detection
- Report an input resistance of 50,000 MΩ without batting an eye
- Silently skip failed analyses and only report the ones that "worked"

None of these are adversarial attacks. They're just what happens when you point a system optimized for plausibility at a problem that requires correctness.

The approach in patchAgent is layered, structural guardrails — not just prompt instructions that the model might ignore, but hard gates in the execution pipeline that *cannot* be bypassed. There are five layers, and each one catches stuff that slips through the previous one.

## Layer 1: The System Prompt

The foundation is a set of six mandatory principles baked into the agent's system prompt. These are framed as non-negotiable rules, not suggestions:

1. **Data Integrity** — NEVER generate synthetic, fake, or simulated data to fill gaps or pass tests. Real experimental data only. If something is missing or corrupted, say so.
2. **Objective Analysis** — NEVER adjust methods, parameters, or thresholds to confirm a user's hypothesis. Reveal what the data actually shows.
3. **Sanity Checks** — Always validate inputs before analysis. Flag values outside physiological ranges. Question results that seem too perfect.
4. **Transparent Reporting** — Report ALL results, including the inconvenient ones. Never hide failed cells, bad sweeps, or contradictory data.
5. **Uncertainty & Error** — Always report confidence intervals, SEM, or SD where applicable. State N for all measurements.
6. **Reproducibility** — All code must be deterministic and reproducible. Document exact parameters, thresholds, and methods used.

Of course, prompt instructions are only as reliable as the model's adherence to them. Which is exactly why the remaining layers exist.

## Layer 2: Tool Priority

The system prompt also encodes a strict hierarchy for *how* analyses should be performed:

```
Priority 1: Built-in tools    ← Validated, peer-reviewed implementations
Priority 2: IPFX library      ← Allen Institute electrophysiology toolkit
Priority 3: Custom code        ← Last resort, with additional scrutiny
```

And an explicit blocklist of things the agent must never do:
- Reimplement spike detection (eg, custom dV/dt crossings, `find_peaks` on voltage)
- Reimplement spike feature extraction
- Reimplement spike train analysis
- Use `scipy.signal.find_peaks` on voltage traces

This matters because LLMs *love* to write spike detection from scratch — it's a common pattern in training data. Every model I've tested will, at some point, try to reimplement it. By explicitly forbidding that and providing a validated alternative, we prevent one of the most common failure modes in computational neuroscience.

## Layer 3: The Code Sandbox

This is where things go from "instructions the model follows" to "enforcement the model cannot bypass."

Every piece of code the agent generates passes through a pre-execution scanner before it runs. The scanner uses two sets of regex patterns:

### Forbidden Patterns (block execution entirely)

These patterns cause the code to fail immediately — it will not run:

```python
FORBIDDEN_PATTERNS = [
    # Synthetic data generation
    (r"np\.random\.(rand|randn|random|uniform|normal|choice)\s*\(",
     "RIGOR VIOLATION: Random/synthetic data generation detected."),

    (r"fake|dummy|synthetic|simulated",
     "RIGOR VIOLATION: Code references fake/synthetic data."),

    # Result manipulation
    (r"if.*p.?value.*[<>].*0\.05.*:.*=",
     "RIGOR VIOLATION: Conditional result modification based on p-value."),

    (r"result\s*=\s*(expected|hypothesis|target)",
     "RIGOR VIOLATION: Result forced to match expected value."),

    (r"#.*hack|#.*fudge|#.*fake",
     "RIGOR VIOLATION: Suspicious comments suggesting data manipulation."),
]
```

If the LLM generates code containing `np.random.randn(100)` to create fake voltage data, it just won't run. Period. The error message goes back to the model, which has to try a different approach.

### Warning Patterns (flag but allow)

These raise warnings that get surfaced to the user, but don't block execution:

```python
WARNING_PATTERNS = [
    (r"np\.random\.seed",
     "Random seed set — ensure for reproducibility, not cherry-picking."),

    (r"outlier.*remove|remove.*outlier",
     "Outlier removal detected — document criteria and report how many removed."),

    (r"find_peaks\s*\(\s*voltage",
     "WARNING: Using scipy find_peaks on voltage traces. Use detect_spikes tool instead."),

    (r"def\s+detect.*spike|def\s+find.*spike",
     "WARNING: Custom spike detection function detected. Use detect_spikes tool instead."),
]
```

The distinction is intentional. I don't want to block *all* random number usage (you might need it for bootstrap confidence intervals), but I do want to flag it. The only things that get blocked outright are patterns that are unambiguously wrong in a scientific context.

## Layer 4: Data Validation

Before any analysis function processes data, the agent runs automated validation checks:

```python
def validate_data_integrity(data, name="data"):
    """
    Checks:
    - NaN percentage (>50% → likely corrupted)
    - Inf values (amplifier saturation?)
    - Zero variance (recording failure or disconnection)
    - All zeros (check amplifier connection)
    - Suspiciously smooth data (possible synthetic)
    """
```

That last check is kind of neat — real electrophysiology data *always* has noise. If a trace is too smooth, it might be fabricated. The scanner computes the noise ratio (`std(diff(data)) / std(data)`) and flags traces below a threshold. It's a simple heuristic but it catches a surprising number of cases.

On top of that, every code execution automatically prepends helper functions that the LLM's code can use: `_validate_input(arr, name)` for checking NaN/Inf/empty arrays, and `_check_range(value, name, low, high)` for physiological bounds. These are injected by the sandbox, not by the LLM, so they're always available even if the model doesn't think to add them.

## Layer 5: Physiological Bounds

The final layer is a set of hard-coded physiological plausibility ranges. When a measurement falls outside these bounds, the agent flags it in its response. It doesn't *hide* the value (transparency is a core principle), but it makes sure you know something looks off.

Some examples:
- **Resting potential**: −100 to −40 mV (outside this, cell may be dead or dying)
- **Input resistance**: 10–2,000 MΩ (way outside this suggests a seal leak or calculation error)
- **Time constant**: 1–100 ms (outside this usually means a fitting error or wrong sweep window)
- **Spike threshold**: −60 to −20 mV
- **Spike amplitude**: 40–140 mV
- **Spike half-width**: 0.1–5.0 ms
- **Firing rate**: 0–500 Hz (above 500 Hz isn't physiological for most neurons)

These ranges are intentionally broad. They're not meant to catch subtle errors — they're meant to catch *catastrophic* ones. The kind where a sign error turns −70 mV into +70 mV, or a units mismatch reports resistance in Ω instead of MΩ. Those happen more often than you'd think.

## A Concrete Example

To make this more tangible, here's what happens when the LLM tries to take a shortcut:

**User**: "Generate some example spike data and analyze it"

The system prompt tells the model to refuse ("NEVER generate synthetic data"). If it complies, great — it responds saying it can only analyze real data. But if the model ignores the prompt and generates code with `np.random.randn()`... the code scanner catches the forbidden pattern, blocks execution, and returns the error: "RIGOR VIOLATION: Random/synthetic data generation detected." The model has to try again without synthetic data. The user's request simply *cannot* be fulfilled — and that's the correct outcome.

**User**: "Detect spikes using `find_peaks` on the voltage"

Again, the system prompt says don't do that. If the model complies, it uses the `detect_spikes` tool instead. If it generates code with `find_peaks(voltage)` anyway, the warning pattern triggers and the user sees the warning. The code still runs (it's a warning, not a block), but the user knows something might be off and can decide whether to re-run with the proper method.

## Beyond Electrophysiology

The guardrail architecture here is domain-specific, but the general pattern works for any scientific AI agent:

1. **Principle-level** — encode scientific integrity in the system prompt
2. **Method-level** — enforce tool priority so the model doesn't reinvent the wheel badly
3. **Code-level** — scan generated code for known antipatterns before execution
4. **Data-level** — validate inputs for integrity and outputs for plausibility
5. **Bounds-level** — hard-code domain-specific sanity checks

If you're building something similar for genomics, imaging, proteomics, or whatever — think about what your equivalent of "don't use `find_peaks` on voltage" would be. Every domain has its version of that. And build it into the pipeline, not just the prompt.

*Previous: [A Walkthrough: Analyzing a Cell](03-example-walkthrough.ipynb)*  
*Next: [Architecture: Building an Agent with the Copilot SDK](05-architecture.md)*
