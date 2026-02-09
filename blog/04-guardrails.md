# Guardrails: Keeping AI Honest in Science

*How patchAgent prevents an LLM from fabricating data, using wrong methods, or reporting implausible results.*

---

## The Stakes

When an AI assistant helps you write a marketing email, a hallucination is embarrassing. When an AI assistant helps you analyze scientific data, a hallucination can invalidate a paper, waste months of follow-up experiments, or — in translational research — mislead drug development.

Large language models are stochastic text generators. They are *phenomenally* good at producing plausible output, and that's exactly what makes them dangerous in scientific contexts. A generic ChatGPT session can:

- Generate fake data that looks real ("here are the spike features for your cell")
- Use `scipy.signal.find_peaks()` on a voltage trace instead of proper dV/dt-based spike detection
- Report an input resistance of 50,000 MΩ without blinking
- Silently skip failed analyses and only report the ones that "worked"

None of these are adversarial attacks. They're the natural failure mode of a system optimized for plausibility rather than correctness.

**patchAgent addresses this with layered, structural guardrails** — not just prompt instructions that the model might ignore, but hard gates in the execution pipeline that *cannot* be bypassed.

---

## Layer 1: The System Prompt — Scientific Principles

The foundation is a set of six mandatory principles encoded in the agent's system prompt. These aren't suggestions — they're framed as non-negotiable rules:

### 1. Data Integrity
> *NEVER generate synthetic, fake, or simulated data to fill gaps or pass tests. Real experimental data ONLY — if data is missing or corrupted, report honestly.*

### 2. Objective Analysis
> *NEVER adjust methods, parameters, or thresholds to confirm a user's hypothesis. Your job is to reveal what the data ACTUALLY shows, not what anyone wants it to show.*

### 3. Sanity Checks
> *Always validate inputs before analysis. Flag values outside physiological ranges. Question results that seem too perfect or too convenient.*

### 4. Transparent Reporting
> *Report ALL results, including inconvenient ones. Acknowledge when analysis is uncertain or inconclusive. Never hide failed cells, bad sweeps, or contradictory data.*

### 5. Uncertainty & Error
> *Always report confidence intervals, SEM, or SD where applicable. State N for all measurements.*

### 6. Reproducibility
> *All code must be deterministic and reproducible. Document exact parameters, thresholds, and methods used.*

Of course, prompt instructions are only as reliable as the model's adherence to them. That's why the remaining layers exist — they enforce these principles in code.

---

## Layer 2: Tool Priority — The Right Method First

The system prompt also encodes a strict hierarchy for *how* analyses should be performed:

```
Priority 1: Built-in tools    ← Validated, peer-reviewed implementations
Priority 2: IPFX library      ← Allen Institute electrophysiology toolkit
Priority 3: Custom code        ← Last resort, with additional scrutiny
```

And an explicit **blocklist** of things the agent must never do:

- ❌ Reimplement spike detection (e.g., custom dV/dt crossings, `find_peaks` on voltage)
- ❌ Reimplement spike feature extraction
- ❌ Reimplement spike train analysis
- ❌ Use `scipy.signal.find_peaks` on voltage traces

This matters because LLMs *love* to write spike detection from scratch — it's a common pattern in training data. By explicitly forbidding it and providing a validated alternative, we prevent one of the most common failure modes in computational neuroscience.

---

## Layer 3: Code Sandbox — Hard Gates

This is where guardrails go from "instructions the model follows" to "enforcement the model cannot bypass."

Every piece of code the agent generates passes through a **pre-execution scanner** before it runs. The scanner uses two sets of regex patterns:

### Forbidden Patterns (Block Execution)

These patterns cause the code to **fail immediately** — it will not execute:

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

If the LLM generates code containing `np.random.randn(100)` to create fake voltage data, it won't run. Period. The error message is returned to the model, which must then try a different approach.

### Warning Patterns (Flag but Allow)

These patterns raise warnings that are surfaced to the user, but don't block execution:

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

The distinction is intentional: we don't want to block *all* random number usage (you might need it for bootstrap confidence intervals), but we *do* want to flag it. We block outright only the patterns that are unambiguously wrong in a scientific context.

---

## Layer 4: Data Validation — Trust but Verify

Before any analysis function processes data, the agent runs automated validation:

### Input Validation

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

That last check is particularly clever — real electrophysiology data *always* has noise. If a trace is too smooth, it may be fabricated. The scanner computes the noise ratio (`std(diff(data)) / std(data)`) and flags traces below a threshold.

### Auto-Injected Validation

Every code execution automatically prepends helper functions that the LLM's code can use:

- `_validate_input(arr, name)` — checks for NaN, Inf, empty arrays
- `_check_range(value, name, low, high)` — checks against physiological bounds

These are injected *by the sandbox*, not by the LLM — so they're always available even if the model doesn't think to add them.

---

## Layer 5: Physiological Bounds — Does This Number Make Sense?

The final layer is a set of hard-coded physiological plausibility ranges:

| Measurement | Expected Range | What It Means If Out of Range |
|---|---|---|
| Resting potential | −100 to −40 mV | Cell may be dead or dying |
| Input resistance | 10–2,000 MΩ | Possible seal leak or calculation error |
| Time constant | 1–100 ms | Fitting error or wrong sweep window |
| Spike threshold | −60 to −20 mV | Unusual, worth investigating |
| Spike amplitude | 40–140 mV | Possible recording artefact |
| Spike half-width | 0.1–5.0 ms | Very unusual cell type or error |
| Firing rate | 0–500 Hz | Above 500 Hz is not physiological for most neurons |

When a measurement falls outside these bounds, the agent raises a flag in its response. It doesn't *hide* the value — transparency is a core principle — but it makes sure you know something looks unusual.

These ranges are intentionally broad. They're not meant to catch subtle errors; they're meant to catch *catastrophic* ones — the kind where a sign error turns −70 mV into +70 mV, or a units mismatch reports resistance in Ω instead of MΩ.

---

## Putting It Together: A Concrete Example

What happens when the LLM tries to take a shortcut? Let's trace through a scenario:

**User**: "Generate some example spike data and analyze it"

1. **System prompt** instructs the model to refuse ("NEVER generate synthetic data").
2. If the model complies → it responds saying it can only analyze real data. ✅
3. If the model ignores the prompt and generates code with `np.random.randn()`:
   - **Code scanner** catches `FORBIDDEN_PATTERNS` match → execution blocked ❌
   - Error message returned: "RIGOR VIOLATION: Random/synthetic data generation detected."
   - Model must try again without synthetic data.
4. The user's request *cannot* be fulfilled — and that's the correct outcome.

**User**: "Detect spikes using `find_peaks` on the voltage"

1. **System prompt** says: don't use `find_peaks` on voltage traces.
2. If the model complies → it uses the `detect_spikes` tool instead. ✅
3. If the model generates code with `find_peaks(voltage)`:
   - **Warning pattern** triggers → warning surfaced to user.
   - Code still executes (it's a warning, not a block), but the user sees:
     *"WARNING: Using scipy find_peaks on voltage traces. Use the detect_spikes tool or ipfx.spike_detector instead — dV/dt-based detection is more scientifically appropriate."*
4. The user can then decide whether to re-run with the proper method.

---

## Beyond Electrophysiology

The guardrail architecture in patchAgent is domain-specific, but the *pattern* is generalizable to any scientific AI agent:

1. **Principle-level** — encode scientific integrity in the system prompt
2. **Method-level** — enforce tool priority to prevent reinventing the wheel badly
3. **Code-level** — scan generated code for known antipatterns before execution
4. **Data-level** — validate inputs for integrity and outputs for plausibility
5. **Bounds-level** — hard-code domain-specific sanity checks

If you're building an AI agent for genomics, proteomics, imaging, or any other data-intensive science, consider what your equivalent of "don't use `find_peaks` on voltage" would be — and build it into the pipeline, not just the prompt.

---

## Key Takeaways

- Prompt instructions alone are insufficient for scientific rigor — LLMs can and do ignore them.
- patchAgent uses **five layers of guardrails**: system prompt, tool priority, code scanning, data validation, and physiological bounds.
- The code scanner uses regex-based **forbidden patterns** that hard-block execution of code that fabricates data or manipulates results.
- Physiological bounds catch catastrophic errors (sign flips, unit mismatches) that would otherwise silently corrupt results.
- The pattern — principle → method → code → data → bounds — is generalizable to any scientific domain.

---

*Previous: [← A Walkthrough: Analyzing a Cell](03-example-walkthrough.ipynb)*  
*Next: [Architecture: Building an Agent with the Copilot SDK →](05-architecture.md)*
