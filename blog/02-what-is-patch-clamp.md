# What is Patch-Clamp Electrophysiology?


## Tapping the Phone Line on a Single Cell

If you're not from a neuroscience background, patch-clamp can sound intimidating, but the core idea is actually pretty intuitive:

You take a tiny glass pipette (we're talking ~1 µm tip diameter), press it against a single cell's membrane, form a tight seal, and then either *listen in* on the electrical signals or *inject* current to see how the cell responds.

<!-- SCREENSHOT: diagram of a patch pipette approaching a neuron, forming a gigaohm seal -->
![Patch-clamp setup diagram](assets/patch-clamp-diagram.png)
*A glass micropipette pressed against a neuron's membrane. Suction forms a high-resistance seal (a "gigaseal," >1 GΩ), which lets you measure currents as small as a few picoamperes.*

The technique was developed by Erwin Neher and Bert Sakmann (1991 Nobel Prize), and despite being decades old, it's still the gold standard for single-cell electrophysiology. Nothing else gives you that level of precision.

### Whole-Cell Configuration

The variant I use (and the one patchAgent focuses on) is **whole-cell patch-clamp**. After forming the seal, you apply a brief pulse of suction to rupture the membrane patch under the pipette tip, which gives you electrical access to the entire cell interior. From there you can:

- **Record** the cell's membrane potential while injecting current (*current-clamp* mode)
- **Clamp** the membrane at a fixed voltage and measure the currents that flow (*voltage-clamp* mode)

## What Does the Data Actually Look Like?

A typical experiment produces many **sweeps** — individual trials where you apply a stimulus (usually a current step) and record the response.

### Current-Clamp Recordings

In current-clamp mode, you inject a series of current steps (eg, −100 pA to +400 pA) and record the resulting voltage. Small negative currents produce little downward dips (hyperpolarization). Larger positive currents push the cell past threshold and trigger action potentials — the big voltage spikes you see in the traces.

<!-- SCREENSHOT: example voltage traces from a current-step protocol — subthreshold responses and spiking -->
![Current-clamp traces](assets/current-clamp-traces.png)
*Voltage responses to a family of current steps. Each colored line is one sweep. The ones with the big deflections are action potentials.*

From these traces you can extract a lot of information. Some of the main ones:

- **Resting membrane potential (Vm)** — the cell's baseline voltage, typically −80 to −55 mV
- **Input resistance (Rm)** — how easily current changes the voltage (basically Ohm's law: V = IR), usually 50–500 MΩ
- **Membrane time constant (τ)** — how quickly the cell charges/discharges, reflects membrane capacitance, 5–30 ms range
- **Sag ratio** — a voltage "sag" during hyperpolarization caused by the HCN/Ih channel, 0–0.3
- **Action potential threshold** — the voltage at which the cell fires, −55 to −35 mV
- **Spike amplitude** — peak height of the AP, 60–120 mV
- **Spike half-width** — duration at half max amplitude. Narrow in fast-spiking interneurons, broad in pyramidal cells (0.3–2.0 ms)
- **Firing rate / f-I curve** — how firing frequency increases with injected current
- **Spike adaptation** — whether firing slows down during a sustained step

### Why Do These Numbers Matter?

These measurements aren't just academic bookkeeping — they're basically the fingerprints of cell identity and health:

**Cell-type classification.** Fast-spiking interneurons have narrow spikes and little adaptation. Pyramidal neurons have broader spikes and strong adaptation. You can often tell *what kind* of neuron you recorded just from these features.

**Drug screening.** If a compound shifts the AP threshold or changes input resistance, it's directly affecting ion channels — which is exactly what pharmacologists want to know.

**Disease models.** In mouse models of epilepsy (for example), neuronal excitability is often altered. Patch-clamp can detect these changes at the single-cell level, long before network-level symptoms show up.

**Quality control.** If input resistance drifts during a recording, or baseline voltage is unusually depolarized, the cell might be dying or the seal might be degrading. You'd want to flag that data or exclude it entirely.

## The Analysis Bottleneck

Here's the thing: collecting patch-clamp data is already labor-intensive (a skilled experimentalist might record from 5–10 cells in a full day), but the analysis can be even more time-consuming. A single cell might produce 20–50 sweeps, each needing spike detection, feature extraction, quality checks, and curve fitting.

Most electrophysiologists analyze their data with some combination of:

- **Commercial software** (Clampfit, Igor Pro) — powerful but expensive and proprietary
- **Python libraries** ([pyABF](https://github.com/swharden/pyABF), [IPFX](https://ipfx.readthedocs.io/), [Neo](https://neo.readthedocs.io/)) — free and flexible, but you need to actually know how to code
- **Custom scripts** — often ad-hoc, poorly documented, passed around the lab like folklore

A lot of biologists have deep domain expertise but limited programming experience. They know *what* they want to measure — they just need help writing the code to measure it correctly. That's the gap patchAgent was built to fill, which I get into in [the next post](01-why-patch-agent.md).


