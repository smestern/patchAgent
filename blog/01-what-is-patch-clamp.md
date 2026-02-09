# What is Patch-Clamp Electrophysiology?

*A gentle introduction for the curious — no neuroscience degree required.*

---

## The Brain Runs on Electricity

Your brain is made of roughly 86 billion neurons. Each one is a tiny, living battery — it maintains a voltage difference across its membrane, typically around −70 millivolts. When a neuron "fires," that voltage briefly spikes upward in a stereotyped, all-or-nothing pulse called an **action potential** (AP). Chains of these electrical impulses are the brain's signaling language: they encode everything from sensory input to motor commands to thought itself.

Understanding *how* individual neurons generate, shape, and propagate these signals is foundational to neuroscience. It tells us how drugs affect the brain, what goes wrong in diseases like epilepsy or ALS, and how different cell types contribute to neural circuits.

## Tapping the Phone Line on a Single Cell

To study a neuron's electrical behavior, scientists use a technique called **patch-clamp electrophysiology**. The core idea is disarmingly simple:

> Press the polished tip of a tiny glass pipette against a single cell's membrane, form a tight seal, and *listen in* on the electrical signals — or *inject* current to see how the cell responds.

<!-- SCREENSHOT: diagram of a patch pipette approaching a neuron, forming a gigaohm seal -->
![Patch-clamp setup diagram](assets/patch-clamp-diagram.png)
*A simplified view of a patch-clamp recording. A glass micropipette with a tip diameter of ~1 µm is pressed against a neuron's membrane. Suction forms a high-resistance seal (a "gigaseal," >1 GΩ), allowing measurement of currents as small as a few picoamperes.*

The technique was pioneered by Erwin Neher and Bert Sakmann, who received the 1991 Nobel Prize in Physiology or Medicine for their work. Decades later, it remains the gold standard for measuring neuronal electrophysiology at the single-cell level.

### Whole-Cell Configuration

The most common variant — and the one patchAgent focuses on — is **whole-cell patch-clamp**. After forming the seal, a brief pulse of suction ruptures the small patch of membrane under the pipette tip, giving electrical access to the entire cell interior. The researcher can now:

- **Record** the cell's membrane potential as it responds to injected current (*current-clamp* mode)
- **Clamp** the membrane at a fixed voltage and measure the currents that flow (*voltage-clamp* mode)

## What Does the Data Look Like?

A typical patch-clamp experiment consists of many **sweeps** — individual trials where a stimulus (usually a step of current) is applied and the cell's response is recorded.

### Current-Clamp Recordings

In current-clamp mode, the experimenter injects a series of current steps (e.g., −100 pA to +400 pA) and records the resulting voltage trace. Here's what you might see:

<!-- SCREENSHOT: example voltage traces from a current-step protocol — subthreshold responses and spiking -->
![Current-clamp traces](assets/current-clamp-traces.png)
*Voltage responses to a family of current steps. Small negative currents produce hyperpolarizing deflections (downward dips). Larger positive currents depolarize the cell past threshold, triggering action potentials. Each colored line is one sweep.*

From these traces, electrophysiologists extract a rich set of measurements:

| Measurement | What It Tells You | Typical Range |
|---|---|---|
| **Resting membrane potential (Vm)** | The cell's baseline voltage | −80 to −55 mV |
| **Input resistance (Rm)** | How easily current changes the voltage (Ohm's law: V = IR) | 50–500 MΩ |
| **Membrane time constant (τ)** | How quickly the cell charges/discharges — reflects membrane capacitance | 5–30 ms |
| **Sag ratio** | A voltage "sag" during hyperpolarization, caused by the HCN/Ih ion channel | 0–0.3 |
| **Action potential threshold** | The voltage at which the cell fires | −55 to −35 mV |
| **Spike amplitude** | The peak height of the action potential | 60–120 mV |
| **Spike half-width** | Duration at half max amplitude — narrow in fast-spiking interneurons, broad in pyramidal cells | 0.3–2.0 ms |
| **Firing rate / f-I curve** | How firing frequency increases with injected current | Varies by cell type |
| **Spike adaptation** | Whether firing slows down during a sustained step | Varies by cell type |

### Why These Measurements Matter

These numbers aren't just academic bookkeeping. They are the fingerprints of cell identity and health:

- **Cell-type classification**: Fast-spiking interneurons have narrow spikes and little adaptation. Pyramidal neurons have broader spikes and strong adaptation. These features help identify *what kind* of neuron you've recorded.

- **Drug screening**: A compound that shifts the AP threshold or changes input resistance is directly affecting ion channels — exactly what pharmacologists want to know.

- **Disease models**: In mouse models of epilepsy, neuronal excitability is often altered. Patch-clamp can detect these changes at the single-cell level, long before network-level symptoms appear.

- **Quality control**: If input resistance drifts during a recording, or baseline voltage is unusually depolarized, it may signal that the cell is unhealthy or the seal is degrading — and the data should be interpreted cautiously or excluded.

## The Analysis Bottleneck

Here's the catch: collecting patch-clamp data is labor-intensive (a skilled experimentalist might record from 5–10 cells in a full day), but **analyzing** it can be even more time-consuming. A single cell might produce 20–50 sweeps of data, each requiring spike detection, feature extraction, quality checks, and curve fitting.

Electrophysiologists typically analyze their data with a patchwork of tools:

- **Commercial software** (Clampfit, Igor Pro) — powerful but expensive and proprietary
- **Python libraries** ([pyABF](https://github.com/swharden/pyABF), [IPFX](https://ipfx.readthedocs.io/), [Neo](https://neo.readthedocs.io/)) — free and flexible, but require coding proficiency
- **Custom scripts** — often ad-hoc, poorly documented, and hard to reproduce

Many biologists have deep domain expertise but limited programming experience. They know *what* they want to measure — they just need help writing the code to measure it correctly.

That's the gap patchAgent was built to fill. But we'll get to that in [the next post](02-why-patch-agent.md).

---

## Key Takeaways

- **Patch-clamp** records electrical signals from individual neurons by forming a tight seal with a glass pipette.
- **Current-clamp** experiments inject current and record voltage responses; the resulting traces encode a rich set of measurable features.
- These features — input resistance, spike shape, firing pattern — identify cell types, reveal drug effects, and flag disease states.
- **Analysis** of this data requires spike detection, feature extraction, and curve fitting — tasks that are tractable in code but daunting for many bench scientists.

---

*Next: [Why We Built patchAgent →](02-why-patch-agent.md)*
