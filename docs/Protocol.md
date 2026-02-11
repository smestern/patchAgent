# Recording Protocols

patchAgent can use protocol definitions to guide analysis — matching your recording protocol to recommended analyses automatically.

---

## Quick Start

patchAgent ships with templates for common protocols in the `protocols/` folder. To add your own:

1. **Copy a template** from patchAgent's `protocols/` folder
2. **Edit the fields** to match your recording setup
3. **Save it** as a `.yaml` file in a `protocols/` folder next to your data

```
my_experiment/
├── protocols/             ← put your .yaml files here
│   └── my_custom_step.yaml
├── cell_001.abf
├── cell_002.abf
└── ...
```

That's it. When you start patchAgent from your experiment folder, it automatically loads your protocols and uses them to guide analysis.

### Example: customising a template

Copy `protocols/long_square.yaml` and edit it:

```yaml
protocol:
  name: "My Long Step"
  type: "current_clamp"
  description: "800ms current steps, -200 to +400 pA in 25 pA increments"

  timing:
    sweep_duration: 1.5
    baseline_duration: 0.3
    stimulus_duration: 0.8
    post_stimulus: 0.4
    inter_sweep_interval: 8

  stimulus:
    type: "step"
    start_amplitude: -200    # pA
    end_amplitude: 400       # pA
    step_size: 25            # pA

  expected_responses:
    - "passive_response"
    - "action_potentials"

  analysis_recommendations:
    - "input_resistance"
    - "time_constant"
    - "fi_curve"
    - "spike_features"

  notes: "Room temperature, ACSF with 2mM Ca2+"
```

Save this as `protocols/my_long_step.yaml` in your data folder. The agent will pick it up automatically next time you start a session.

---

## One-Off Use (no file needed)

If you don't want to save a file, paste protocol details directly into the chat:

```
Analyze my Long Square data:
- 15 sweeps, -100 to +180 pA in 20 pA steps
- 1 second steps with 500ms baseline
- Current clamp, 10 kHz sampling

Please calculate input resistance, time constant, and build an f-I curve.
```

Or reference a known protocol:

```
This is a standard Long Square protocol. Please run the full analysis.
```

---

## How It Works

When patchAgent starts, it looks for protocol `.yaml` files in two places:

| Location | Purpose |
|----------|---------|
| `protocols/` next to your data (CWD) | Your custom protocols |
| `protocols/` in the patchAgent install | Bundled defaults |

If the same protocol name appears in both, your version takes priority.

When you load a file, patchAgent checks its protocol metadata (e.g. the ABF protocol name) against the loaded protocols. If it finds a match, it automatically suggests the appropriate analyses.

If no protocol is provided or matched, the agent will infer the protocol from the data — it just may take an extra step.

---

## Template Reference

Each protocol YAML file has these fields (all optional except `name`):

| Field | Description |
|-------|-------------|
| `name` | Protocol name (used for matching against file metadata) |
| `type` | `"current_clamp"` or `"voltage_clamp"` |
| `description` | Brief description of what this protocol measures |
| `timing` | Sweep timing parameters (durations in seconds) |
| `stimulus` | Stimulus parameters (type, amplitudes, step size) |
| `expected_responses` | What responses to expect (e.g. `"action_potentials"`, `"sag"`) |
| `analysis_recommendations` | Which analyses to run (e.g. `"fi_curve"`, `"input_resistance"`) |
| `notes` | Any additional context (temperature, solutions, etc.) |

### Bundled templates

patchAgent includes these ready-to-use templates:

| File | Protocol |
|------|----------|
| `long_square.yaml` | 1s current steps (-100 to +300 pA) |
| `short_square.yaml` | 3ms pulses for rheobase |
| `ramp.yaml` | Linear current ramp |
| `hyperpolarizing_steps.yaml` | Hyperpolarizing steps for passive properties |
| `voltage_clamp_step.yaml` | Voltage steps for IV curves |
| `gap_free.yaml` | Continuous recording |

---

## Notes

- Protocol information helps the agent choose appropriate analysis methods
- If protocol is unknown, the agent will attempt to infer it from the data
- Always mention the clamp mode (current_clamp vs voltage_clamp)
- You can use `--protocols-dir` on the CLI to load protocols from a custom location
