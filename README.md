# patchAgent

A scientific analysis agent for patch-clamp electrophysiology, built on the [**sciagent**](https://github.com/smestern/sciagent) framework and powered by the GitHub Copilot SDK.

The Idea here is to build more human in the loop scientific coding tools. Landing somewhere in between the basic LLM chat interface, and the end-to-end AI for science tools. The goal of this project is not to do the science for you, but you help you write strong, rigorous, and reproducible research code. 
Essentially an LLM wrapper but with a few extra tools to make sure the LLM doesn't go off the rails.

![alt text](image.png)

## Overview

patchAgent helps design and run Python code for analyzing patch-clamp electrophysiology recordings. It leverages:

- **[sciagent](https://github.com/smestern/sciagent)** — Generic scientific coding agent framework (base agent, guardrails, sandbox, web UI, CLI)
- **[pyABF](https://github.com/swharden/pyABF)** — ABF file I/O
- **[IPFX](https://ipfx.readthedocs.io/)** — Electrophysiology feature extraction
- **[GitHub Copilot SDK](https://github.com/github/copilot-sdk)** — LLM agent framework

## Features

- **Flexible I/O**: Load ABF, NWB files, or pass numpy arrays directly
- **Spike Analysis**: Detection, feature extraction, train analysis
- **Passive Properties**: Input resistance, time constant, sag, capacitance
- **Quality Control**: Seal resistance, access resistance, stability checks
- **Curve Fitting**: Exponential fits, IV curves, f-I relationships
- **Guardrails**: Physiological bounds checking, code scanning for synthetic data / result manipulation, data integrity validation
- **Web UI**: Branded chat interface with WebSocket streaming, file upload, inline figures
- **CLI**: Rich terminal REPL with slash commands, history, markdown rendering
- **Protocol Matching**: Drop protocol YAML files into `protocols/` and the agent auto-matches them to your recordings (see [Protocol docs](docs/Protocol.md))
- **MCP Server**: Expose tools via Model Context Protocol for use from any MCP-compatible client

## Architecture

patchAgent is a domain-specific implementation of the **sciagent** framework.
All generic infrastructure (agent lifecycle, code sandbox, guardrails, web UI, CLI, MCP transport) lives in sciagent.
patchAgent adds electrophysiology-specific tools, prompts, bounds, and file loaders.

```
sciagent (framework)            patchAgent (domain layer)
├── BaseScientificAgent    ←──  PatchAgent(BaseScientificAgent)
├── AgentConfig            ←──  PATCH_CONFIG
├── ScientificCLI          ←──  PatchCLI(ScientificCLI)
├── create_app()           ←──  web/app.py delegates here
├── BaseMCPServer          ←──  PatchAgentMCPServer(BaseMCPServer)
├── CodeScanner            ←──  + patch-clamp forbidden patterns
├── BoundsChecker          ←──  + physiological bounds (Vm, Ri, tau, …)
└── build_system_message() ←──  PATCH_ANALYST_SYSTEM_MESSAGE
```

## Project Structure

```
patchAgent/
├── protocols/                # Protocol YAML templates (bundled defaults)
├── mcp/                      # MCP server (subclasses BaseMCPServer)
├── src/patchagent/          # Main Python package
│   ├── config.py             # PATCH_CONFIG — branding, bounds, patterns
│   ├── agent.py              # PatchAgent(BaseScientificAgent)
│   ├── cli.py                # PatchCLI(ScientificCLI) + Typer commands
│   ├── loadFile/             # ABF / NWB file loaders
│   ├── tools/                # Domain-specific analysis tools
│   │   ├── io_tools.py       # File loading & sweep access
│   │   ├── spike_tools.py    # Spike detection & features
│   │   ├── passive_tools.py  # Rin, tau, sag, Vrest
│   │   ├── qc_tools.py       # Sweep quality control
│   │   ├── fitting_tools.py  # IV, f-I, exponential fits
│   │   └── code_tools.py     # Code sandbox + rigor checks
│   ├── prompts/              # Patch-clamp system prompts
│   ├── utils/                # Data resolver
│   └── web/                  # Thin wrapper around sciagent web UI
├── docs/                     # Documentation
├── data/sample_abfs/         # Sample recordings for testing
└── blog/                     # Blog posts & walkthroughs
```

## Installation

### Prerequisites

Install **sciagent** first (from local source or PyPI when published):

```bash
# From local source (editable)
cd path/to/sciagent
pip install -e ".[cli,web]"
```

### Install patchAgent

```bash
# CLI mode (terminal chat)
pip install -e ".[cli]"

# Web mode (browser chat UI)
pip install -e ".[web,cli]"

# Everything
pip install -e ".[cli,web,dev,remote]"
```

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
python -m patchagent chat --file cell_001.abf
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
from patchagent import PatchAgent, create_agent

async def main():
    # Create and start the agent
    agent = create_agent(model="GPT-5.3-Codex")
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
from patchagent import loadFile
from patchagent.tools import detect_spikes, extract_spike_features

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
The UI is provided by sciagent and automatically branded with patchAgent's config (name, logo, accent colour, suggestion chips).

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

## MCP Server

Expose patch-clamp tools to any MCP-compatible client (VS Code, other agents):

```bash
python mcp/mcp_server.py
```

The server runs over stdio and exposes tools like `load_file`, `detect_spikes`,
`calculate_input_resistance`, etc. See [mcp/mcp_config.json](mcp/mcp_config.json) for the full tool list.

## Building Your Own Agent

patchAgent is built on **sciagent**. To create your own domain-specific agent, subclass the base classes:

```python
from sciagent import BaseScientificAgent, AgentConfig

MY_CONFIG = AgentConfig(
    name="my-agent",
    display_name="My Agent",
    description="Analyses my domain data",
    instructions="You are a helpful domain expert.",
)

class MyAgent(BaseScientificAgent):
    def __init__(self):
        super().__init__(MY_CONFIG)

    def _load_tools(self):
        return [self._create_tool(name="my_tool", ...)]
```

See the [sciagent README](https://github.com/smestern/sciagent) and `sciagent/examples/csv_analyst/` for a complete walkthrough.

## License

MIT
