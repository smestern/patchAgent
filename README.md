# patchAgent

A scientific analysis agent for patch-clamp electrophysiology, powered by the GitHub Copilot SDK.

## Overview

patchAgent helps design and run Python code for analyzing patch-clamp electrophysiology recordings. It leverages:

- **[pyABF](https://github.com/swharden/pyABF)** — ABF file I/O
- **[IPFX](https://ipfx.readthedocs.io/)** — Electrophysiology feature extraction
- **[GitHub Copilot SDK](https://github.com/github/copilot-sdk)** — Agent framework

## Features

- **Flexible I/O**: Load ABF, NWB files, or pass numpy arrays directly
- **Spike Analysis**: Detection, feature extraction, train analysis
- **Passive Properties**: Input resistance, time constant, sag, capacitance
- **Quality Control**: Seal resistance, access resistance, stability checks
- **Curve Fitting**: Exponential fits, IV curves, f-I relationships

## Project Structure

```
patchAgent/
├── .copilot/skills/          # Skill definitions for the agent
├── mcp/                      # MCP server configuration
├── src/patch_agent/          # Main Python package
│   ├── loadFile/             # Vendored I/O module
│   ├── tools/                # Agent tools
│   ├── utils/                # Utilities (data resolver, etc.)
│   └── prompts/              # System prompts
├── docs/                     # Documentation
│   ├── Agents.md             # Sub-agent definitions
│   ├── Skills.md             # Skill overview
│   ├── Tools.md              # Tool reference
│   ├── Protocol.md           # Recording protocol metadata
│   └── Operations.md         # Operating procedures
└── data/sample_abfs/         # Sample data for testing
```

## Installation

```bash
pip install -e .
```

## Quick Start

```python
import asyncio
from patch_agent import PatchAgent, create_agent

async def main():
    # Create and start the agent
    agent = create_agent(model="gpt-4.1")
    await agent.start()
    
    try:
        # Create a session
        session = await agent.create_session()
        
        # Send analysis request
        result = await session.send_and_wait({
            "prompt": "Load cell_001.abf and analyze spike properties"
        })
        print(result.message)
        
        # Clean up
        await session.destroy()
    finally:
        await agent.stop()

asyncio.run(main())
```

### Direct Tool Usage

You can also use the tools directly without the agent:

```python
from patch_agent import loadFile
from patch_agent.tools import detect_spikes, extract_spike_features

# Load data
dataX, dataY, dataC = loadFile("cell_001.abf")

# Detect spikes
spikes = detect_spikes(voltage=dataY[0], time=dataX[0])
print(f"Found {spikes['count']} spikes")

# Extract features
features = extract_spike_features(voltage=dataY[0], time=dataX[0])
print(f"Mean spike amplitude: {features['mean_amplitude']:.1f} mV")
```

## Documentation

- [Agents](docs/Agents.md) — Sub-agent definitions
- [Skills](docs/Skills.md) — Model capabilities
- [Tools](docs/Tools.md) — Available tools and schemas
- [Protocol](docs/Protocol.md) — Recording protocol metadata template
- [Operations](docs/Operations.md) — Agent operating procedures

## License

MIT
