# Architecture: How patchAgent is Put Together

*The internals of patchAgent — and some patterns that might be useful if you're building something similar.*

## The Big Picture

patchAgent is pretty small — about ~2,500 lines of Python. The overall structure is layered, which I'll walk through below, but at a high level it looks like this:

```
┌─────────────────────────────────────────────┐
│                   User                       │
│        (natural language questions)           │
└──────────────────┬──────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────┐
│               CLI (cli.py)                   │
│  Rich rendering · prompt-toolkit REPL        │
│  Slash commands · Streaming response handler │
└──────────────────┬──────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────┐
│          PatchAgent (agent.py)               │
│  Copilot SDK client · Tool registration      │
│  Session management · System prompt          │
└──────────────────┬──────────────────────────┘
                   │
          ┌────────┼────────┐
          ▼        ▼        ▼
┌──────────┐ ┌──────────┐ ┌──────────┐
│ I/O      │ │ Analysis │ │ Code     │
│ Tools    │ │ Tools    │ │ Sandbox  │
│          │ │          │ │          │
│ loadABF  │ │ spikes   │ │ execute  │
│ loadNWB  │ │ passive  │ │ validate │
│ sweeps   │ │ QC       │ │ rigor    │
│ metadata │ │ fitting  │ │ bounds   │
└──────────┘ └──────────┘ └──────────┘
       │            │
       ▼            ▼
┌─────────────────────────────────────────────┐
│            Data Layer                        │
│  DataResolver (caching, format abstraction)  │
│  pyABF · h5py/pynwb · numpy arrays          │
└─────────────────────────────────────────────┘
```

## The Agent Core

The central class wraps the GitHub Copilot SDK's `CopilotClient`:

```python
from copilot import CopilotClient
from copilot.types import Tool, SessionConfig, CustomAgentConfig

class PatchAgent:
    def __init__(self, model="claude-opus-4.5", output_dir=None):
        self._client = CopilotClient({"log_level": "info"})
        self._tools: List[Tool] = []
        self._load_tools()         # Register all 20 tools
        self._output_dir = Path(output_dir or tempfile.mkdtemp())
```

A few design decisions worth mentioning:

**Tools as the API surface.** The agent doesn't have "abilities" — it has *tools*. Each tool is a Python function with a JSON schema for its parameters. The LLM sees the schema, decides which tool to call, and the SDK handles invocation. This means adding a new capability is just writing one function + one schema, and you can test any tool by calling the function directly without needing the LLM at all. Importantly, the LLM doesn't write analysis code from scratch — it *selects and parameterizes* existing validated functions.

**Dedicated output directory.** The agent never touches `os.chdir()`. Instead it creates a dedicated output directory and passes it into the code sandbox. All figures, scripts, and CSVs end up there. Avoids the chaos of files showing up in random locations (I learned this one the hard way).

**Streaming-first.** The agent uses the Copilot SDK's event-based streaming rather than `send_and_wait()`:

```python
async for event in session.send(message):
    match event.type:
        case SessionEventType.THINKING:
            render_thinking(event.text)
        case SessionEventType.TOOL_CALL:
            render_tool_execution(event.tool, event.args)
        case SessionEventType.TEXT_DELTA:
            render_text(event.text)
```

Since electrophysiology analyses can take a few seconds per tool call, showing real-time progress ("loading the file...", "running spike detection...") makes a big difference. Without it, the user just stares at a blank terminal wondering if something broke.

## Tools: 20 of Them, 6 Categories

Each tool is registered as a `Tool` object with a name, description, handler function, and JSON schema:

```python
Tool(
    name="detect_spikes",
    description="Detect action potentials in a voltage trace using dV/dt threshold",
    handler=detect_spikes,
    parameters={
        "type": "object",
        "properties": {
            "file_path": {"type": "string"},
            "sweep_index": {"type": "integer"},
            "dvdt_cutoff": {"type": "number", "default": 20},
        },
        "required": ["file_path", "sweep_index"],
    },
)
```

The LLM sees the schema and decides which tools to call. It doesn't need to know the implementation details — just what each tool does and what parameters it takes.

The tools break down across six files:
- **I/O** (`io_tools.py`) — `load_file`, `get_file_metadata`, `get_sweep_data`, `list_sweeps` (pyABF, h5py, pynwb)
- **Spike** (`spike_tools.py`) — `detect_spikes`, `extract_spike_features`, `extract_spike_train_features` (IPFX)
- **Passive** (`passive_tools.py`) — `calculate_input_resistance`, `calculate_time_constant`, `calculate_sag`, `calculate_resting_potential` (NumPy, SciPy)
- **QC** (`qc_tools.py`) — `run_sweep_qc`, `check_baseline_stability`, `measure_noise` (NumPy)
- **Fitting** (`fitting_tools.py`) — `fit_exponential`, `fit_iv_curve`, `fit_fi_curve` (SciPy)
- **Code** (`code_tools.py`) — `execute_code`, `run_custom_analysis`, `validate_code`, `check_scientific_rigor`, `validate_data_integrity`, `check_physiological_bounds`

### Adding a New Tool

If you want to add a new analysis, the process is pretty straightforward:

1. Write the function in the appropriate `*_tools.py` file
2. Import it in `tools/__init__.py`
3. Register it in `agent.py`'s `_load_tools()`

```python
_create_tool(
    "calculate_rheobase",
    "Find the minimum current that elicits spiking (rheobase)",
    calculate_rheobase,
    {"type": "object", "properties": {"file_path": {"type": "string"}}, "required": ["file_path"]},
)
```

The LLM will automatically discover the new tool via its schema and start using it when appropriate. No other wiring needed.

## The Data Layer

File I/O is abstracted through a `DataResolver` that provides a unified interface regardless of format:

```python
# All of these return the same (dataX, dataY, dataC) tuple:
dataX, dataY, dataC = load_file("cell.abf")      # ABF via pyABF
dataX, dataY, dataC = load_file("cell.nwb")       # NWB via pynwb/h5py
dataX, dataY, dataC = load_file(numpy_array)       # Raw arrays
```

Where `dataX` is time arrays, `dataY` is voltage, and `dataC` is command/stimulus — all shaped `(n_sweeps, n_samples)`.

The resolver also has an in-memory LRU cache (up to 50 files). This actually matters a lot in practice because the LLM typically makes multiple tool calls against the same file in a single conversation — without caching, each call re-reads and re-parses from disk, which gets slow fast.

For NWB files (which can contain dozens of different stimulus protocols in a single file), there are filter options:

```python
# Only long-square current-step sweeps
dataX, dataY, dataC = load_file("cell.nwb", protocol_filter=["Long Square"])

# Only current-clamp recordings
dataX, dataY, dataC = load_file("cell.nwb", clamp_mode_filter="CC")
```

Users shouldn't need to care whether their file is ABF, NWB, or a numpy array. The resolver handles it.

## The CLI

The interactive terminal uses [Typer](https://typer.tiangolo.com/) for argument parsing, [prompt-toolkit](https://python-prompt-toolkit.readthedocs.io/) for input with history and auto-suggest, and [Rich](https://rich.readthedocs.io/) for Markdown rendering and styled output.

There are a few slash commands that bypass the LLM and call tools directly: `/load <path>`, `/sweeps`, `/save`, `/clear`, `/help`, `/quit`. These are handy for quick operations where you don't need the model to interpret your request.

For figures: when the agent generates a matplotlib plot, it renders to PNG using the `Agg` backend (no GUI window), saves it to the output directory, encodes it as base64 for the response, and auto-opens it with the OS image viewer. I also override `plt.show()` to a no-op so the agent can't accidentally block on a GUI window. That was a fun bug to track down.

## Sub-Agents

patchAgent defines five specialized sub-agents, each with its own system prompt:

- `patch-analyst` — main coordinator, has all tools
- `spike-analyst` — AP detection, feature extraction, firing patterns
- `passive-analyst` — Rm, τ, sag, capacitance
- `qc-checker` — baseline stability, noise, seal quality
- `curve-fitter` — exponential, IV, f-I curve fitting

Currently, `patch-analyst` handles everything and routes internally based on the question type. The sub-agent definitions are mostly a roadmap for future explicit delegation — but the structure is already there when I want to flip that switch.

## MCP Server

patchAgent also exposes its tools via the [Model Context Protocol (MCP)](https://modelcontextprotocol.io/), so IDE extensions and other MCP clients can use the analysis capabilities:

```json
{
  "mcpServers": {
    "patchAgent": {
      "command": "python",
      "args": ["mcp/mcp_server.py"],
      "env": {}
    }
  }
}
```

The MCP server wraps a subset of tools (8 of the 20) with JSON-safe serialization (converting numpy arrays to lists, etc.). This is what enables analyzing data from within VS Code via Copilot, chaining patchAgent with other MCP tools, or building custom UIs on top of the analysis functions.

## Patterns That Might Be Useful

If you're building your own domain-specific agent, a few things I found really helpful:

**Tools over free-form code.** Don't let the LLM write analysis code from scratch. Wrap validated methods as tools with JSON schemas. The LLM selects and parameterizes — it doesn't implement. This is probably the single most important design decision.

**Layered guardrails.** Prompt instructions → tool priority → code scanning → data validation → output bounds. Each layer catches stuff that slips through the previous one. I talk about this a lot more in the [guardrails post](04-guardrails.md).

**Escape hatches.** The code sandbox exists because no predefined tool set will cover every possible analysis. But it's the last resort, not the default — and it gets extra scrutiny (rigor scanning, warning patterns).

**Format abstraction.** Users shouldn't need to know or care what file format their data is in. Build a unified interface early and save yourself a lot of headaches.

## What's Next

patchAgent is in alpha (v0.1.0). Things I'm actively working on:

- **Batch analysis** — processing multiple cells from a directory
- **DANDI integration** — loading NWB files directly from the DANDI archive
- **Web interface** — a browser-based UI (Quart backend, already scaffolded)
- **Explicit sub-agent delegation** — routing questions to specialist agents
- **Community tools** — a plugin system for lab-specific analysis protocols

It's all [MIT-licensed on GitHub](https://github.com/smestern/patchAgent) — contributions welcome.

*Previous: [Guardrails: Keeping AI Honest in Science](04-guardrails.md)*  
*Start from the beginning: [What is Patch-Clamp Electrophysiology?](02-what-is-patch-clamp.md)*
