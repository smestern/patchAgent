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
│   ├── prompts/              # System prompts
│   └── web/                  # Browser-based chat demo (Quart)
│       ├── app.py            # Backend: WebSocket + REST API
│       ├── templates/        # HTML template
│       └── static/           # CSS + JS (vanilla, no build)
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
pip install -e ".[cli]"
```

(Omit `[cli]` if you only need the library without the interactive chat.)

## Quick Start — Interactive Chat

```bash
# Start a chat session
patchagent chat

# Pre-load a recording at startup
patchagent chat --file data/sample_abfs/cell_001.abf

# Use a specific model
patchagent chat --model claude-sonnet-4

# Save figures to a custom directory (default: temp dir)
patchagent chat --output-dir ./figures

# Also works via python -m
python -m patch_agent chat --file cell_001.abf
```

### Chat Commands

| Command | Description |
|---------|-------------|
| `/help` | Show commands and example prompts |
| `/load <path>` | Load an ABF / NWB file |
| `/sweeps` | List sweeps in the loaded file |
| `/save [path]` | Save conversation to markdown |
| `/clear` | Clear terminal |
| `/quit` | Exit (also Ctrl-D) |

### Example Session

```
🧪 You ❯ /load data/sample_abfs/cell_001.abf
  Loading…
  Loaded cell_001.abf — 20 sweeps, 20 kHz, current-clamp protocol

🧪 You ❯ Detect spikes in sweep 5
  Found 12 action potentials.
  Mean amplitude: 82.3 mV | Mean half-width: 1.1 ms

🧪 You ❯ Plot the voltage trace of sweep 5
  📊 Saved figure → /tmp/patchagent_.../figure_1.png
```

## Programmatic Usage

```python
import asyncio
from patch_agent import PatchAgent, create_agent

async def main():
    # Create and start the agent
    agent = create_agent(model="claude-sonnet-4.5")
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

## Web Demo

patchAgent includes a browser-based chat interface for demos and quick exploration.

### Local Setup

```bash
# Install with web extras
pip install -e ".[web,cli]"

# Launch the web server
patchagent web

# Or with options:
patchagent web --port 3000 --debug
```

Then open [http://127.0.0.1:8080](http://127.0.0.1:8080) in your browser.

### Features

- Streaming chat with real-time thinking indicators and tool status
- Markdown rendering with syntax-highlighted code blocks
- Inline figure display (spike plots, IV curves, etc.)
- File upload (ABF / NWB) or use bundled sample files
- Dark / light theme toggle
- Mobile-responsive layout

### Docker Deployment

```bash
# Build the image
docker build -t patchagent-web .

# Run it (set your Copilot auth token)
docker run -p 8080:8080 -e COPILOT_API_KEY=your-key patchagent-web
```

Deploy the container to any hosting service (Railway, Fly.io, Azure App Service, etc.).
Copy `.env.example` to `.env` and fill in your credentials before deploying.

## License

MIT
