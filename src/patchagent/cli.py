"""
patchAgent CLI — Interactive chat interface for patch-clamp analysis.

Subclasses ``sciagent.cli.ScientificCLI`` and adds patch-clamp-specific
slash commands (``/sweeps``, ``/load``).

Usage:
    patchagent chat                          # start interactive session
    patchagent chat --file cell_001.abf      # pre-load a recording
    patchagent chat --model claude-sonnet-4  # use a specific model
"""

from __future__ import annotations

import asyncio
import logging
import tempfile
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel

from sciagent.cli import ScientificCLI, run_cli
from patchagent.agent import create_agent
from patchagent.config import PATCH_CONFIG

logger = logging.getLogger(__name__)

console = Console()

app = typer.Typer(
    name="patchagent",
    help="patchAgent – conversational analysis for patch-clamp electrophysiology.",
    no_args_is_help=True,
    add_completion=False,
)


class PatchCLI(ScientificCLI):
    """PatchAgent-specific CLI with electrophysiology slash commands."""

    def __init__(self, protocols_dir: Optional[str] = None, **kwargs):
        super().__init__(
            agent_factory=lambda **kw: create_agent(protocols_dir=protocols_dir, **kw),
            config=PATCH_CONFIG,
            **kwargs,
        )
        self._preload_file: Optional[str] = None

    def banner(self) -> str:
        return (
            "[bold green]patchAgent[/bold green] — Patch-clamp analysis assistant\n"
            f"[dim]{PATCH_CONFIG.description}[/dim]\n\n"
            "Type a question or /help for commands."
        )

    def get_example_prompts(self) -> list[str]:
        return [
            "Load cell_001.abf and summarize",
            "Detect spikes in sweep 3",
            "Calculate input resistance from the -100 pA step",
            "Plot the voltage trace of sweep 0",
            "Fit an exponential to the membrane time constant",
            "Run QC on all sweeps and flag failures",
        ]

    def get_slash_commands(self):
        return [
            ("load", "Load an ABF/NWB file into the session", self._cmd_load),
            ("sweeps", "List sweeps in the currently loaded file", self._cmd_sweeps),
        ]

    async def _cmd_load(self):
        console.print("Usage: /load <path>", style="yellow")

    async def _cmd_sweeps(self):
        if self._session:
            await self._stream_and_print("List all sweeps in the currently loaded file")

    async def run(self):
        """Override to handle /load and pre-load file."""
        # Patch the REPL to intercept /load <path>
        _orig_all_commands = self._all_commands

        def _patched_all_commands():
            return _orig_all_commands()

        self._all_commands = _patched_all_commands
        await super().run()


# ---------------------------------------------------------------------------
# Typer commands
# ---------------------------------------------------------------------------

@app.command()
def chat(
    file: Optional[str] = typer.Option(
        None, "--file", "-f",
        help="Path to an ABF or NWB file to load at startup.",
    ),
    model: str = typer.Option(
        "GPT-5.3-Codex", "--model", "-m",
        help="LLM model name (e.g. gpt-4.1, claude-sonnet-4).",
    ),
    output_dir: Optional[str] = typer.Option(
        None, "--output-dir", "-o",
        help="Directory for saving generated figures (default: temp dir).",
    ),
    protocols_dir: Optional[str] = typer.Option(
        None, "--protocols-dir",
        help="Extra directory containing protocol YAML files.",
    ),
    timeout: float = typer.Option(
        600, "--timeout", "-t",
        help="Max seconds to wait for agent response (default: 600).",
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v",
        help="Enable debug logging.",
    ),
) -> None:
    """Start an interactive chat session with patchAgent."""
    if verbose:
        logging.basicConfig(level=logging.DEBUG, format="%(name)s %(levelname)s %(message)s")

    if file and not Path(file).exists():
        console.print(f"File not found: {file}", style="bold red")
        raise typer.Exit(code=1)

    if output_dir:
        out = Path(output_dir)
    elif file:
        # Place working dir near the file being analysed
        from sciagent.data.resolver import resolve_working_dir
        out = resolve_working_dir(file, "patchagent")
    else:
        out = Path(tempfile.mkdtemp(prefix="patchagent_"))
    out.mkdir(parents=True, exist_ok=True)

    cli = PatchCLI(output_dir=out, protocols_dir=protocols_dir)
    asyncio.run(cli.run())


@app.command()
def web(
    port: int = typer.Option(8080, "--port", "-p", help="Port to listen on."),
    host: str = typer.Option("127.0.0.1", "--host", help="Host to bind to."),
    debug: bool = typer.Option(False, "--debug", help="Enable debug mode with auto-reload."),
) -> None:
    """Launch the browser-based chat demo."""
    try:
        from patchagent.web.app import create_app
    except ImportError as exc:
        console.print(
            Panel(
                f"Could not import the web module.\n\n{exc}\n\n"
                "Install the web extras:\n  pip install -e '.[web]'",
                title="Missing dependency",
                border_style="red",
            )
        )
        raise typer.Exit(code=1)

    console.print(
        Panel(
            f"[bold green]patchAgent web demo[/bold green]\n"
            f"Open [bold cyan]http://{host}:{port}[/bold cyan] in your browser.",
            border_style="green",
        )
    )
    web_app = create_app()
    web_app.run(host=host, port=port, debug=debug)


@app.command()
def version() -> None:
    """Show patchAgent version."""
    from patchagent import __version__
    console.print(f"patchAgent v{__version__}")


if __name__ == "__main__":
    app()
