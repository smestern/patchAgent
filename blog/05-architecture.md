# Architecture: Building a Domain-Specific Agent with the Copilot SDK

*How patchAgent is structured — and how you could build something similar for your own domain.*

---

## High-Level Overview

patchAgent is a relatively small codebase (~2,500 lines of Python) with a clear layered architecture:

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

Let's walk through each layer.

---

## The Agent Core: `PatchAgent`

The central class wraps the GitHub Copilot SDK's `CopilotClient`:

```python
from copilot import CopilotClient
from copilot.types import Tool, SessionConfig, CustomAgentConfig

class PatchAgent:
    def __init__(self, model="claude-sonnet-4.5", output_dir=None):
        self._client = CopilotClient({"log_level": "info"})
        self._tools: List[Tool] = []
        self._load_tools()         # Register all 20 tools
        self._output_dir = Path(output_dir or tempfile.mkdtemp())
```

### Key Design Decisions

**1. Tools as the API surface.** The agent doesn't have "abilities" — it has *tools*. Each tool is a Python function with a JSON schema describing its parameters. The LLM sees the schema, decides which tool to call based on the user's question, and the SDK handles the invocation. This means:

- Adding a new capability = writing one function + one schema
- Testing a tool = calling the function directly (no LLM needed)
- The LLM doesn't write analysis code from scratch — it *selects and parameterizes* existing, validated functions

**2. Output directory, not `os.chdir()`.** The agent never changes the working directory. Instead, it creates a dedicated output directory (`OUTPUT_DIR`) and passes it into the code sandbox. All figures, scripts, and CSVs save there. This avoids the chaos of files ending up in random locations.

**3. Streaming-first.** The agent uses the Copilot SDK's event-based streaming rather than `send_and_wait()`:

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

This lets the CLI show real-time thinking ("💭 I'm loading the file..."), tool execution progress ("⚙ Running detect_spikes..."), and streaming text output. Since electrophysiology analyses can take seconds per tool call, this feedback is critical for user experience.

---

## The Tool System: 20 Tools in 6 Categories

### Tool Registration

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

The LLM sees the schema and decides which tools to call. It doesn't need to know the implementation details — just what each tool does and what parameters it accepts.

### Tool Categories

| Category | File | Tools | Key Library |
|---|---|---|---|
| **I/O** | `io_tools.py` | `load_file`, `get_file_metadata`, `get_sweep_data`, `list_sweeps` | pyABF, h5py, pynwb |
| **Spike** | `spike_tools.py` | `detect_spikes`, `extract_spike_features`, `extract_spike_train_features` | IPFX |
| **Passive** | `passive_tools.py` | `calculate_input_resistance`, `calculate_time_constant`, `calculate_sag`, `calculate_resting_potential` | NumPy, SciPy |
| **QC** | `qc_tools.py` | `run_sweep_qc`, `check_baseline_stability`, `measure_noise` | NumPy |
| **Fitting** | `fitting_tools.py` | `fit_exponential`, `fit_iv_curve`, `fit_fi_curve` | SciPy |
| **Code** | `code_tools.py` | `execute_code`, `run_custom_analysis`, `validate_code`, `check_scientific_rigor`, `validate_data_integrity`, `check_physiological_bounds` | — |

### Adding a New Tool

To add a new analysis capability:

1. **Write the function** in the appropriate `*_tools.py` file:
   ```python
   def calculate_rheobase(file_path: str) -> Dict[str, Any]:
       """Find the minimum current that elicits at least one spike."""
       # ... implementation ...
       return {"rheobase_pA": rheobase, "sweep_index": sweep_idx}
   ```

2. **Import it** in `tools/__init__.py`

3. **Register it** in `agent.py`'s `_load_tools()`:
   ```python
   _create_tool(
       "calculate_rheobase",
       "Find the minimum current that elicits spiking (rheobase)",
       calculate_rheobase,
       {"type": "object", "properties": {"file_path": {"type": "string"}}, "required": ["file_path"]},
   )
   ```

That's it. The LLM will automatically discover the new tool via its schema and start using it when appropriate.

---

## The Data Layer: `DataResolver`

File I/O is abstracted through a `DataResolver` that provides a unified interface across formats:

```python
# All of these return the same (dataX, dataY, dataC) tuple:
dataX, dataY, dataC = load_file("cell.abf")      # ABF via pyABF
dataX, dataY, dataC = load_file("cell.nwb")       # NWB via pynwb/h5py
dataX, dataY, dataC = load_file(numpy_array)       # Raw arrays
```

Where:
- `dataX` — time arrays (one per sweep), shape `(n_sweeps, n_samples)`
- `dataY` — voltage arrays (same shape)
- `dataC` — command/stimulus arrays (same shape)

### Caching

The `DataResolver` maintains an in-memory LRU cache (up to 50 files). This matters because the LLM typically makes multiple tool calls against the same file in a single conversation — without caching, each tool call would re-read and re-parse the file from disk.

### NWB Protocol Filtering

NWB files can contain dozens of different stimulus protocols (long square, short square, ramp, voltage clamp, etc.) in a single file. By default, patchAgent loads all sweeps, but provides filter options:

```python
# Only long-square current-step sweeps
dataX, dataY, dataC = load_file("cell.nwb", protocol_filter=["Long Square"])

# Only current-clamp recordings
dataX, dataY, dataC = load_file("cell.nwb", clamp_mode_filter="CC")

# Specific sweep numbers
dataX, dataY, dataC = load_file("cell.nwb", sweep_numbers=[0, 1, 5])
```

---

## The CLI: Rich + prompt-toolkit

The interactive terminal is built with:

- **[Typer](https://typer.tiangolo.com/)** for CLI commands and argument parsing
- **[prompt-toolkit](https://python-prompt-toolkit.readthedocs.io/)** for input with history, auto-suggest, and key bindings
- **[Rich](https://rich.readthedocs.io/)** for Markdown rendering, progress indicators, and styled output

### Slash Commands

The CLI intercepts lines starting with `/` before they reach the LLM:

| Command | Action |
|---|---|
| `/load <path>` | Load a file (calls `load_file` tool directly) |
| `/sweeps` | List sweeps (calls `list_sweeps` tool directly) |
| `/save [path]` | Export conversation as Markdown |
| `/clear` | Clear terminal |
| `/help` | Show available commands and example prompts |
| `/quit` | Exit |

### Figure Handling

When the agent generates a matplotlib plot (via the code sandbox), the figure is:

1. Rendered to a PNG using the `Agg` backend (no GUI window pops up)
2. Saved to `OUTPUT_DIR/figure_N.png`
3. Encoded as base64 and included in the response
4. Automatically opened with the OS image viewer for immediate inspection

The `Agg` backend is forced and `plt.show()` is overridden to a no-op — this prevents the agent from accidentally blocking on a GUI window.

---

## Sub-Agent Architecture

patchAgent defines five specialized sub-agents, each with its own system prompt and expertise:

| Agent | Role | Specialization |
|---|---|---|
| `patch-analyst` | Main coordinator | All tools, workflow orchestration |
| `spike-analyst` | AP specialist | Spike detection, feature extraction, firing patterns |
| `passive-analyst` | Membrane properties | Rm, τ, sag, capacitance |
| `qc-checker` | Quality control | Baseline stability, noise, seal quality |
| `curve-fitter` | Fitting specialist | Exponential, IV, f-I curve fitting |

Currently, the `patch-analyst` serves as the primary agent and handles routing internally — the system prompt instructs it to apply specialized analysis strategies based on the type of question. The sub-agent definitions provide a roadmap for future explicit delegation.

---

## MCP Server: IDE Integration

patchAgent also exposes its tools via the [Model Context Protocol (MCP)](https://modelcontextprotocol.io/), allowing IDE extensions and other MCP clients to use the analysis capabilities:

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

The MCP server wraps a subset of tools (8 of 20) with JSON-safe serialization (converting numpy arrays to lists, etc.). This enables workflows like:

- Analyzing data from within VS Code via Copilot
- Chaining patchAgent with other MCP tools
- Building custom UIs that call patchAgent's analysis functions

---

## Key Patterns Worth Stealing

If you're building a domain-specific agent, here are the patterns from patchAgent that are most transferable:

### 1. Tools Over Free-Form Code

Don't let the LLM write analysis code from scratch. Wrap your validated methods as tools with JSON schemas. The LLM *selects and parameterizes* — it doesn't *implement*.

### 2. Layered Guardrails

Prompt instructions → tool priority → code scanning → data validation → output bounds. Each layer catches failures that slip through the previous one.

### 3. Output Directory Pattern

Give the agent a dedicated output directory. Don't change the working directory. Inject the path into code sandboxes as a variable. This keeps all outputs organized and prevents file system pollution.

### 4. Streaming with Narration

For agents that run slow operations (file I/O, numerical fitting), streaming with live narration ("💭 Detecting spikes...") is essential. Users need to know the agent is working, not frozen.

### 5. Escape Hatches

The code sandbox (`execute_code`) exists because no predefined tool set covers every possible analysis. But it's the *last resort*, not the default path — and it carries extra scrutiny (rigor scanning, warning patterns).

### 6. Format Abstraction

Users shouldn't need to care whether their file is ABF, NWB, or a numpy array. The `DataResolver` provides a unified `(time, voltage, current)` interface across all formats, with caching.

---

## What's Next

patchAgent is in alpha (v0.1.0). Areas of active development include:

- **Batch analysis** — processing multiple cells from a directory
- **DANDI integration** — loading NWB files directly from the DANDI archive
- **Web interface** — a browser-based UI (Quart backend, already scaffolded)
- **Explicit sub-agent delegation** — routing questions to specialist agents
- **Community tools** — a plugin system for lab-specific analysis protocols

Contributions welcome — it's [MIT-licensed on GitHub](https://github.com/smestern/patchAgent).

---

## Key Takeaways

- patchAgent is a ~2,500 line Python project with a clear layered architecture: CLI → Agent → Tools → Data Layer.
- Built on the **GitHub Copilot SDK**, using tools-as-functions with JSON schemas — no custom orchestration needed.
- **20 tools** across 6 categories cover the full electrophysiology analysis workflow.
- The **DataResolver** abstracts file formats behind a unified `(time, voltage, current)` interface with LRU caching.
- **MCP server** enables IDE integration and composability with other tools.
- The architecture is intentionally simple and extensible — adding a new analysis = one function + one schema.

---

*Previous: [← Guardrails: Keeping AI Honest in Science](04-guardrails.md)*  

---

*This is the final post in the patchAgent blog series. Thanks for reading!*  
*Start from the beginning: [What is Patch-Clamp Electrophysiology? →](01-what-is-patch-clamp.md)*
