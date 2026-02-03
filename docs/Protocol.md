# Protocol Metadata

This document provides a template for describing recording protocols. The agent uses this information to understand how to analyze your data appropriately.

---

## How to Use This Document

1. Copy the relevant protocol template section below
2. Fill in your specific parameters
3. Provide this information when asking the agent to analyze data
4. The agent will use this context to select appropriate analysis methods

---

## Protocol Template

```yaml
protocol:
  name: "Your Protocol Name"
  type: "current_clamp" | "voltage_clamp"
  description: "Brief description of what this protocol measures"
  
  timing:
    sweep_duration: 2.0        # seconds
    baseline_duration: 0.5     # seconds before stimulus
    stimulus_duration: 1.0     # seconds
    post_stimulus: 0.5         # seconds after stimulus
    inter_sweep_interval: 10   # seconds between sweeps
  
  stimulus:
    type: "step" | "ramp" | "sine" | "custom"
    start_amplitude: -100      # pA or mV
    end_amplitude: 300         # pA or mV
    step_size: 20              # pA or mV per sweep
    
  expected_responses:
    - "action_potentials"      # for suprathreshold steps
    - "passive_response"       # for hyperpolarizing steps
    - "sag"                    # for large hyperpolarizing steps
    
  analysis_recommendations:
    - "spike_detection"
    - "input_resistance"
    - "fi_curve"
    
  notes: "Any additional information about the protocol"
```

---

## Common Protocol Templates

### Long Square (Current Step)

Standard protocol for characterizing neuronal excitability.

```yaml
protocol:
  name: "Long Square"
  type: "current_clamp"
  description: "1 second current steps from -100 to +300 pA"
  
  timing:
    sweep_duration: 2.0
    baseline_duration: 0.5
    stimulus_duration: 1.0
    post_stimulus: 0.5
    inter_sweep_interval: 10
  
  stimulus:
    type: "step"
    start_amplitude: -100  # pA
    end_amplitude: 300     # pA
    step_size: 20          # pA
    
  expected_responses:
    - "passive_response"     # sweeps with negative current
    - "subthreshold"         # small positive current
    - "action_potentials"    # larger positive current
    
  analysis_recommendations:
    - "input_resistance"     # from hyperpolarizing sweeps
    - "time_constant"        # from hyperpolarizing sweeps
    - "sag_ratio"            # from large hyperpolarizing sweeps
    - "rheobase"             # first sweep with spikes
    - "fi_curve"             # all suprathreshold sweeps
    - "spike_features"       # representative spiking sweep
```

### Short Square (Rheobase)

Quick steps for finding rheobase.

```yaml
protocol:
  name: "Short Square"
  type: "current_clamp"
  description: "3ms current pulses for rheobase determination"
  
  timing:
    sweep_duration: 0.5
    baseline_duration: 0.1
    stimulus_duration: 0.003
    post_stimulus: 0.4
  
  stimulus:
    type: "step"
    start_amplitude: 0
    end_amplitude: 1000
    step_size: 10
    
  analysis_recommendations:
    - "rheobase"
    - "latency"
```

### Ramp

Current ramp for dynamic threshold measurement.

```yaml
protocol:
  name: "Ramp"
  type: "current_clamp"
  description: "Linear current ramp from 0 to peak"
  
  timing:
    sweep_duration: 3.0
    baseline_duration: 0.5
    stimulus_duration: 2.0
    post_stimulus: 0.5
  
  stimulus:
    type: "ramp"
    start_amplitude: 0
    end_amplitude: 500
    ramp_rate: 250  # pA/s
    
  analysis_recommendations:
    - "threshold_voltage"
    - "rheobase"
```

### Hyperpolarizing Steps (Passive Properties)

Protocol optimized for passive property measurement.

```yaml
protocol:
  name: "Hyperpol Steps"
  type: "current_clamp"
  description: "Hyperpolarizing steps for Rm, tau, sag"
  
  timing:
    sweep_duration: 1.5
    baseline_duration: 0.3
    stimulus_duration: 1.0
    post_stimulus: 0.2
  
  stimulus:
    type: "step"
    start_amplitude: -150
    end_amplitude: -20
    step_size: 10
    
  expected_responses:
    - "passive_response"
    - "sag"
    - "rebound"
    
  analysis_recommendations:
    - "input_resistance"
    - "time_constant"
    - "sag_ratio"
    - "rebound_spikes"
```

### Voltage Clamp Step

Standard voltage clamp protocol.

```yaml
protocol:
  name: "VC Steps"
  type: "voltage_clamp"
  description: "Voltage steps for IV curve"
  
  timing:
    sweep_duration: 0.5
    baseline_duration: 0.1
    stimulus_duration: 0.3
    post_stimulus: 0.1
  
  stimulus:
    type: "step"
    holding: -70       # mV
    start_amplitude: -120
    end_amplitude: 40
    step_size: 10
    
  analysis_recommendations:
    - "iv_curve"
    - "conductance"
    - "reversal_potential"
```

### Gap-Free (Continuous Recording)

Continuous recording without sweeps.

```yaml
protocol:
  name: "Gap Free"
  type: "current_clamp"
  description: "Continuous recording for spontaneous activity"
  
  timing:
    total_duration: 300  # 5 minutes
    
  stimulus:
    type: "none"  # No stimulus, holding only
    holding_current: 0
    
  expected_responses:
    - "spontaneous_spikes"
    - "synaptic_events"
    
  analysis_recommendations:
    - "spike_detection"
    - "firing_rate"
    - "resting_potential"
```

---

## Providing Protocol Information

When asking the agent to analyze data, you can provide protocol info like:

```
Analyze my Long Square data:
- 15 sweeps, -100 to +180 pA in 20 pA steps
- 1 second steps with 500ms baseline
- Current clamp, 10 kHz sampling

Please calculate input resistance, time constant, and build an f-I curve.
```

Or simply reference a known protocol:

```
This is a standard Long Square protocol. Please run the full analysis.
```

---

## Notes

- Protocol information helps the agent choose appropriate analysis methods
- If protocol is unknown, the agent will attempt to infer it from the data
- Always mention the clamp mode (current_clamp vs voltage_clamp)
- Include any non-standard settings or modifications
