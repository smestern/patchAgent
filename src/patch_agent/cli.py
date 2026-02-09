"""
patchAgent CLI — Interactive chat interface for patch-clamp analysis.

Provides a REPL-style conversational interface backed by the PatchAgent
and GitHub Copilot SDK.  Designed for neuroscientists comfortable with
Python/notebooks who prefer CLI tools.

Usage:
    patchagent chat                          # start interactive session
    patchagent chat --file cell_001.abf      # pre-load a recording
    patchagent chat --model claude-sonnet-4  # use a specific model
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
import platform
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.theme import Theme

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Typer app
# ---------------------------------------------------------------------------

_CUSTOM_THEME = Theme(
    {
        "info": "dim cyan",
        "warning": "bold yellow",
        "error": "bold red",
        "agent": "green",
        "user_prompt": "bold cyan",
    }
)

console = Console(theme=_CUSTOM_THEME)

app = typer.Typer(
    name="patchagent",
    help="patchAgent – conversational analysis for patch-clamp electrophysiology.",
    no_args_is_help=True,
    add_completion=False,
)


# ---------------------------------------------------------------------------
# Slash-command registry (client-side, never sent to LLM)
# ---------------------------------------------------------------------------

SLASH_COMMANDS = {
    "/help": "Show available commands and example prompts",
    "/load <path>": "Load an ABF / NWB file into the session",
    "/sweeps": "List sweeps in the currently loaded file",
    "/clear": "Clear the terminal screen",
    "/save [path]": "Save conversation to a markdown file",
    "/quit": "Exit the chat (also: /exit, Ctrl-D)",
    "/exit": "Exit the chat",
}


def _print_help() -> None:
    """Display slash-commands and example prompts."""
    table = Table(title="Commands", show_header=True, header_style="bold cyan")
    table.add_column("Command", style="bold")
    table.add_column("Description")
    for cmd, desc in SLASH_COMMANDS.items():
        if cmd == "/exit":
            continue  # already shown under /quit
        table.add_row(cmd, desc)
    console.print(table)
    console.print()
    console.print(
        Panel(
            "\n".join(
                [
                    "[bold]Example prompts:[/bold]",
                    "",
                    "  Load cell_001.abf and summarize",
                    "  Detect spikes in sweep 3",
                    "  Calculate input resistance from the -100 pA step",
                    "  Plot the voltage trace of sweep 0",
                    "  Fit an exponential to the membrane time constant",
                    "  Run QC on all sweeps and flag failures",
                ]
            ),
            title="Tips",
            border_style="dim",
        )
    )


# ---------------------------------------------------------------------------
# Figure handling
# ---------------------------------------------------------------------------

def _save_and_open_figures(
    figures: list,
    output_dir: Path,
    auto_open: bool = True,
) -> list[Path]:
    """Decode base64 figures, save as PNGs, and optionally open them."""
    saved: list[Path] = []
    for fig in figures:
        if not isinstance(fig, dict) or "image_base64" not in fig:
            continue
        fig_num = fig.get("figure_number", len(saved) + 1)
        dest = output_dir / f"figure_{fig_num}.png"
        # Avoid overwriting — increment suffix
        counter = 1
        while dest.exists():
            dest = output_dir / f"figure_{fig_num}_{counter}.png"
            counter += 1
        dest.write_bytes(base64.b64decode(fig["image_base64"]))
        saved.append(dest)
        console.print(f"  📊 Saved figure → [link=file://{dest}]{dest}[/link]", style="info")
        if auto_open:
            _open_file(dest)
    return saved


def _open_file(path: Path) -> None:
    """Open a file with the OS default viewer (cross-platform)."""
    try:
        system = platform.system()
        if system == "Windows":
            os.startfile(str(path))  # type: ignore[attr-defined]
        elif system == "Darwin":
            subprocess.Popen(["open", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)])
    except Exception:
        pass  # non-fatal — user can open manually


# ---------------------------------------------------------------------------
# Response rendering
# ---------------------------------------------------------------------------

def _extract_message(response) -> str | None:
    """Pull the assistant text out of whatever shape *response* has.

    The Copilot SDK ``send_and_wait()`` returns an ``Optional[SessionEvent]``
    whose payload is at ``response.data.content``.  We also handle plain
    dicts and raw strings defensively.
    """
    if response is None:
        return None

    # SessionEvent → .data.content
    if hasattr(response, "data") and hasattr(response.data, "content"):
        c = response.data.content
        if c:
            return c

    # Fallback: plain dict
    if isinstance(response, dict):
        return response.get("content") or response.get("message") or None

    # Fallback: raw string
    if isinstance(response, str):
        return response

    # Last resort — check common attrs
    for attr in ("message", "content", "text"):
        val = getattr(response, attr, None)
        if val and isinstance(val, str):
            return val

    return None


def _render_response(response, output_dir: Path, auto_open: bool) -> None:
    """Render an agent response to the terminal with rich formatting."""
    if response is None:
        console.print("[dim](no response)[/dim]")
        return

    message = _extract_message(response)
    tool_results: list | None = None

    # Try to find tool results in the response
    if hasattr(response, "tool_results"):
        tool_results = response.tool_results
    elif isinstance(response, dict):
        tool_results = response.get("tool_results")

    # -- Render main text as markdown ----------------------------------------
    if message:
        console.print()
        console.print(Markdown(message))
    else:
        # Debug: show what we actually received so the user can report it
        logger.debug("Response object type=%s, attrs=%s", type(response).__name__,
                     [a for a in dir(response) if not a.startswith("_")])
        console.print("[dim](empty response)[/dim]")

    # -- Render tool results -------------------------------------------------
    if tool_results:
        for tr in tool_results:
            _render_tool_result(tr, output_dir, auto_open)

    console.print()


def _render_tool_result(result: dict, output_dir: Path, auto_open: bool) -> None:
    """Render a single tool result dict, including tables and figures."""
    if not isinstance(result, dict):
        return

    # Handle figures produced by execute_code
    figures = result.get("figures")
    if figures and isinstance(figures, list) and len(figures) > 0:
        # Only process dicts with image data (not bare figure-number ints)
        if isinstance(figures[0], dict):
            _save_and_open_figures(figures, output_dir, auto_open)

    # If the result has an error, show it prominently
    error = result.get("error")
    if error:
        console.print(Panel(str(error), title="⚠ Tool Error", border_style="red"))

    # Try to render dict-of-lists / list-of-dicts as a table
    data = result.get("result") or result.get("variables")
    if isinstance(data, dict):
        _try_render_table(data)


def _try_render_table(data: dict) -> None:
    """Attempt to render a dict as a Rich table if it looks tabular."""
    # dict of equal-length lists → table (like a DataFrame)
    if all(isinstance(v, list) for v in data.values()):
        lengths = {len(v) for v in data.values()}
        if len(lengths) == 1 and lengths.pop() > 0:
            table = Table(show_header=True, header_style="bold magenta")
            for col in data:
                table.add_column(str(col))
            for row_vals in zip(*data.values()):
                table.add_row(*(str(v) for v in row_vals))
            console.print(table)
            return

    # Simple key-value dict → two-column table
    if all(isinstance(v, (int, float, str, bool)) for v in data.values()):
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Parameter")
        table.add_column("Value", justify="right")
        for k, v in data.items():
            table.add_row(str(k), str(v))
        console.print(table)


# ---------------------------------------------------------------------------
# Conversation saver
# ---------------------------------------------------------------------------

def _save_conversation(history: list[dict], dest: Path | None = None) -> Path:
    """Save conversation history to a markdown file."""
    if dest is None:
        dest = Path.cwd() / "patchagent_conversation.md"
    lines = ["# patchAgent Conversation\n"]
    for entry in history:
        role = entry.get("role", "unknown")
        text = entry.get("text", "")
        if role == "user":
            lines.append(f"## 🧑 User\n\n{text}\n")
        else:
            lines.append(f"## 🤖 Agent\n\n{text}\n")
    dest.write_text("\n".join(lines), encoding="utf-8")
    return dest


# ---------------------------------------------------------------------------
# Welcome banner
# ---------------------------------------------------------------------------

def _print_banner(model: str, file_path: str | None = None, output_dir: Path | None = None) -> None:
    banner_lines = [
        "[bold green]patchAgent[/bold green] — Patch-clamp analysis assistant",
        f"Model: [cyan]{model}[/cyan]",
    ]
    if file_path:
        banner_lines.append(f"File:  [cyan]{file_path}[/cyan]")
    if output_dir:
        banner_lines.append(f"Output dir: [cyan]{output_dir}[/cyan]")
    banner_lines.extend(
        [
            "",
            "Type a question or command.  [dim]/help[/dim] for options, "
            "[dim]/quit[/dim] or [dim]Ctrl-D[/dim] to exit.",
        ]
    )
    console.print(
        Panel(
            "\n".join(banner_lines),
            border_style="green",
            padding=(1, 2),
        )
    )


# ---------------------------------------------------------------------------
# Core chat loop (async)
# ---------------------------------------------------------------------------

async def _send_streaming(
    session,
    prompt: str,
    output_dir: Path,
    auto_open: bool,
    timeout: float = 600,
):
    """Send a message using streaming events for live thinking/tool feedback.

    Instead of ``send_and_wait()`` (which blocks silently), this uses the
    event-based ``send()`` + ``session.on()`` pattern so the user sees
    reasoning, tool invocations, and streamed response text in real time.
    """
    from copilot.generated.session_events import SessionEventType

    collected_response = None
    idle_event = asyncio.Event()
    response_text_parts: list[str] = []
    showed_thinking_header = False
    showed_tool_header = False

    def _handler(event):
        nonlocal collected_response, showed_thinking_header, showed_tool_header

        etype = event.type

        # ── Reasoning / thinking deltas ────────────────────────────
        if etype == SessionEventType.ASSISTANT_REASONING_DELTA:
            delta = getattr(event.data, "delta_content", None) or ""
            if delta:
                if not showed_thinking_header:
                    console.print()
                    console.print("[dim italic]💭 Thinking…[/dim italic]")
                    showed_thinking_header = True
                console.print(f"[dim]{delta}[/dim]", end="", highlight=False)

        elif etype == SessionEventType.ASSISTANT_REASONING:
            text = getattr(event.data, "reasoning_text", None) or ""
            if text:
                if not showed_thinking_header:
                    console.print()
                    console.print("[dim italic]💭 Thinking…[/dim italic]")
                    showed_thinking_header = True
                console.print(f"[dim]{text}[/dim]", highlight=False)

        # ── Streamed response text ─────────────────────────────────
        elif etype == SessionEventType.ASSISTANT_MESSAGE_DELTA:
            delta = getattr(event.data, "delta_content", None) or ""
            if delta:
                response_text_parts.append(delta)
                console.print(delta, end="", highlight=False)

        # ── Completed assistant message ────────────────────────────
        elif etype == SessionEventType.ASSISTANT_MESSAGE:
            collected_response = event
            # If streaming was active we already printed text;
            # otherwise fall back to full render later.
            if response_text_parts:
                console.print()  # newline after streamed text

        # ── Tool execution feedback ────────────────────────────────
        elif etype == SessionEventType.TOOL_EXECUTION_START:
            tool_name = getattr(event.data, "tool_name", "tool")
            if showed_thinking_header:
                console.print()  # newline after thinking block
                showed_thinking_header = False
            console.print(f"  [bold cyan]⚙ Running:[/bold cyan] [cyan]{tool_name}[/cyan]")
            showed_tool_header = True

        elif etype == SessionEventType.TOOL_EXECUTION_COMPLETE:
            tool_name = getattr(event.data, "tool_name", "tool")
            console.print(f"  [dim green]✓ {tool_name} done[/dim green]")
            showed_tool_header = False

        elif etype == SessionEventType.TOOL_EXECUTION_PROGRESS:
            msg = getattr(event.data, "progress_message", None) or ""
            if msg:
                console.print(f"  [dim]  ↳ {msg}[/dim]")

        # ── Session idle — we're done ──────────────────────────────
        elif etype == SessionEventType.SESSION_IDLE:
            idle_event.set()

        # ── Errors ─────────────────────────────────────────────────
        elif etype == SessionEventType.SESSION_ERROR:
            err_msg = getattr(event.data, "message", str(event.data))
            console.print(Panel(err_msg, title="⚠ Session Error", border_style="red"))
            idle_event.set()

    # Subscribe, send, wait
    unsubscribe = session.on(_handler)
    try:
        await session.send({"prompt": prompt})
        try:
            await asyncio.wait_for(idle_event.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            console.print(
                "\n[bold yellow]⏱ Response timed out.[/bold yellow] "
                f"The agent did not finish within {int(timeout)}s. "
                "Use [bold]--timeout[/bold] to increase the limit."
            )
    finally:
        unsubscribe()

    return collected_response


async def _chat_loop(
    model: str,
    file_path: str | None,
    output_dir: Path,
    auto_open: bool,
    timeout: float = 600,
) -> None:
    """Run the interactive REPL."""
    # Lazy-import prompt_toolkit (only needed here)
    from prompt_toolkit import PromptSession
    from prompt_toolkit.history import FileHistory
    from prompt_toolkit.auto_suggest import AutoSuggestFromHistory

    # Local import of agent factory — fails fast with a clear message
    # if the Copilot SDK is not properly installed.
    try:
        from patch_agent.agent import create_agent
    except ImportError as exc:
        console.print(
            Panel(
                f"Could not import the agent.\n\n{exc}\n\n"
                "Make sure the GitHub Copilot SDK is installed:\n"
                "  pip install copilot",
                title="⚠ Missing dependency",
                border_style="red",
            )
        )
        return

    history_file = Path.home() / ".patchagent_history"
    prompt_session: PromptSession = PromptSession(
        history=FileHistory(str(history_file)),
        auto_suggest=AutoSuggestFromHistory(),
    )

    _print_banner(model, file_path, output_dir)

    # ── Start the agent ────────────────────────────────────────────────
    agent = create_agent(model=model, output_dir=output_dir)

    # Also tell the code_tools module where to save scripts / expose OUTPUT_DIR
    from patch_agent.tools.code_tools import set_output_dir
    set_output_dir(output_dir)

    try:
        with console.status("[bold green]Starting patchAgent…[/bold green]"):
            await agent.start()
            session = await agent.create_session()

        # Pre-load file if requested
        if file_path:
            response = await _send_streaming(
                session,
                f"Load and summarize the file at {file_path}",
                output_dir,
                auto_open,
                timeout,
            )
            _render_response(response, output_dir, auto_open)

        # Conversation log (for /save)
        conversation: list[dict] = []

        # ── REPL ──────────────────────────────────────────────────────
        while True:
            try:
                user_input: str = await prompt_session.prompt_async(
                    "🧪 You ❯ ",
                )
            except (EOFError, KeyboardInterrupt):
                # Ctrl-D or Ctrl-C at the prompt → exit
                break

            user_input = user_input.strip()
            if not user_input:
                continue

            # ── Slash commands ────────────────────────────────────────
            if user_input.startswith("/"):
                cmd_parts = user_input.split(maxsplit=1)
                cmd = cmd_parts[0].lower()
                arg = cmd_parts[1] if len(cmd_parts) > 1 else ""

                if cmd in ("/quit", "/exit"):
                    break
                elif cmd == "/help":
                    _print_help()
                    continue
                elif cmd == "/clear":
                    console.clear()
                    continue
                elif cmd == "/save":
                    dest = Path(arg) if arg else None
                    saved = _save_conversation(conversation, dest)
                    console.print(f"Conversation saved to [link=file://{saved}]{saved}[/link]", style="info")
                    continue
                elif cmd == "/load":
                    if not arg:
                        console.print("Usage: /load <path>", style="warning")
                        continue
                    user_input = f"Load and summarize the file at {arg}"
                    # fall through to send to agent
                elif cmd == "/sweeps":
                    user_input = "List all sweeps in the currently loaded file"
                    # fall through to send to agent
                else:
                    console.print(f"Unknown command: {cmd}. Type /help for options.", style="warning")
                    continue

            # ── Send to agent ─────────────────────────────────────────
            conversation.append({"role": "user", "text": user_input})

            try:
                response = await _send_streaming(
                    session, user_input, output_dir, auto_open, timeout,
                )

                # Log the response text
                resp_text = _extract_message(response) or ""
                conversation.append({"role": "agent", "text": resp_text})

            except KeyboardInterrupt:
                console.print("\n[dim]Request cancelled.[/dim]")
                continue
            except Exception as exc:
                console.print(
                    Panel(str(exc), title="⚠ Error", border_style="red")
                )
                logger.exception("Error during agent request")
                continue

    finally:
        with console.status("[bold green]Shutting down…[/bold green]"):
            await agent.stop()
        console.print("[dim]Goodbye![/dim]")


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
        "claude-sonnet-4.5", "--model", "-m",
        help="LLM model name (e.g. gpt-4.1, claude-sonnet-4).",
    ),
    output_dir: Optional[str] = typer.Option(
        None, "--output-dir", "-o",
        help="Directory for saving generated figures (default: temp dir).",
    ),
    timeout: float = typer.Option(
        600, "--timeout", "-t",
        help="Max seconds to wait for agent response (default: 600).",
    ),
    no_open: bool = typer.Option(
        False, "--no-open",
        help="Don't auto-open generated figures in the OS viewer.",
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v",
        help="Enable debug logging.",
    ),
) -> None:
    """Start an interactive chat session with patchAgent."""

    if verbose:
        logging.basicConfig(level=logging.DEBUG, format="%(name)s %(levelname)s %(message)s")

    # Validate --file if given
    if file and not Path(file).exists():
        console.print(f"File not found: {file}", style="error")
        raise typer.Exit(code=1)

    # Resolve output directory
    out = Path(output_dir) if output_dir else Path(tempfile.mkdtemp(prefix="patchagent_"))
    out.mkdir(parents=True, exist_ok=True)

    asyncio.run(
        _chat_loop(
            model=model,
            file_path=file,
            output_dir=out,
            auto_open=not no_open,
            timeout=timeout,
        )
    )


@app.command()
def web(
    port: int = typer.Option(8080, "--port", "-p", help="Port to listen on."),
    host: str = typer.Option("127.0.0.1", "--host", help="Host to bind to."),
    debug: bool = typer.Option(False, "--debug", help="Enable debug mode with auto-reload."),
) -> None:
    """Launch the browser-based chat demo."""
    try:
        from patch_agent.web.app import create_app
    except ImportError as exc:
        console.print(
            Panel(
                f"Could not import the web module.\n\n{exc}\n\n"
                "Install the web extras:\n  pip install -e '.[web]'",
                title="⚠ Missing dependency",
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
    from patch_agent import __version__

    console.print(f"patchAgent v{__version__}")


# Allow `python -m patch_agent chat` via __main__.py
if __name__ == "__main__":
    app()
