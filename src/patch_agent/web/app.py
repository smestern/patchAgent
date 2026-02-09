"""
patchAgent Web — Quart backend serving a browser-based chat demo.

Provides:
    GET  /             → Single-page chat UI
    WS   /ws/chat      → Streaming agent conversation over WebSocket
    POST /upload       → File upload (ABF / NWB)
    GET  /api/samples  → List bundled sample files
    POST /api/load-sample → Copy a sample into the session workspace

Start with:
    patchagent-web          # uses entry point
    python -m patch_agent.web.app   # direct
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import tempfile
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

from quart import Quart, websocket, request, jsonify, send_from_directory
from quart_cors import cors

from patch_agent.web.figure_queue import (
    register_session,
    unregister_session,
    set_current_session,
    get_figures,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

def create_app() -> Quart:
    """Create and configure the Quart application."""
    app = Quart(
        __name__,
        static_folder=str(Path(__file__).parent / "static"),
        template_folder=str(Path(__file__).parent / "templates"),
    )
    app = cors(app, allow_origin="*")

    # Store active sessions: ws_id -> { agent, session, output_dir }
    app.ws_sessions = {}

    # ---------------------------------------------------------------------------
    # Routes
    # ---------------------------------------------------------------------------

    @app.route("/")
    async def index():
        """Serve the single-page chat UI."""
        return await send_from_directory(app.template_folder, "index.html")

    @app.route("/api/samples")
    async def list_samples():
        """Return a list of bundled sample ABF/NWB files."""
        sample_dir = _sample_dir()
        if not sample_dir.exists():
            return jsonify({"samples": []})
        samples = []
        for f in sorted(sample_dir.iterdir()):
            if f.suffix.lower() in (".abf", ".nwb") and f.is_file():
                samples.append({
                    "name": f.name,
                    "size_kb": round(f.stat().st_size / 1024, 1),
                })
        return jsonify({"samples": samples})

    @app.route("/api/load-sample", methods=["POST"])
    async def load_sample():
        """Copy a sample file into a per-session temp directory."""
        data = await request.get_json()
        sample_name = data.get("name", "")
        session_id = data.get("session_id", "")

        src = _sample_dir() / sample_name
        if not src.exists() or src.suffix.lower() not in (".abf", ".nwb"):
            return jsonify({"error": "Sample not found"}), 404

        # Create or reuse session output dir
        dest_dir = _session_dir(session_id)
        dest = dest_dir / sample_name
        shutil.copy2(src, dest)

        return jsonify({"file_id": sample_name, "path": str(dest)})

    @app.route("/upload", methods=["POST"])
    async def upload_file():
        """Accept an ABF or NWB file upload."""
        files = await request.files
        uploaded = files.get("file")
        if uploaded is None:
            return jsonify({"error": "No file provided"}), 400

        fname = uploaded.filename or "upload.abf"
        if not fname.lower().endswith((".abf", ".nwb")):
            return jsonify({"error": "Only .abf and .nwb files are supported"}), 400

        session_id = (await request.form).get("session_id", str(uuid.uuid4()))
        dest_dir = _session_dir(session_id)
        dest = dest_dir / fname
        await uploaded.save(str(dest))

        return jsonify({"file_id": fname, "path": str(dest), "session_id": session_id})

    # ---------------------------------------------------------------------------
    # WebSocket chat endpoint
    # ---------------------------------------------------------------------------

    @app.websocket("/ws/chat")
    async def ws_chat():
        """Main chat endpoint — one WebSocket per conversation."""
        ws_id = str(uuid.uuid4())
        agent = None
        session = None
        output_dir = _session_dir(ws_id)

        # Register this session for figure queue
        register_session(ws_id)

        # Queue bridges sync SDK callbacks → async WebSocket sends.
        # The SDK event handler is synchronous and runs outside Quart's
        # websocket context, so we can't call websocket.send() directly
        # from it.  Instead, callbacks push messages onto this queue and
        # a dedicated consumer task drains it.
        send_queue: asyncio.Queue = asyncio.Queue()

        async def _drain_queue():
            """Forward queued messages to the WebSocket client."""
            while True:
                msg = await send_queue.get()
                if msg is None:
                    break  # sentinel — stop draining
                try:
                    await websocket.send(json.dumps(msg))
                except Exception:
                    break

        async def _drain_figure_queue():
            """Periodically check for figures from tool execution."""
            while True:
                await asyncio.sleep(0.1)  # Check every 100ms
                figures = get_figures(ws_id)
                for fig in figures:
                    if isinstance(fig, dict) and "image_base64" in fig:
                        try:
                            await websocket.send(json.dumps({
                                "type": "figure",
                                "data": fig["image_base64"],
                                "figure_number": fig.get("figure_number", 0),
                            }))
                        except Exception:
                            break

        drain_task = asyncio.ensure_future(_drain_queue())
        figure_drain_task = asyncio.ensure_future(_drain_figure_queue())

        try:
            from patch_agent.agent import create_agent
            from patch_agent.tools.code_tools import set_output_dir

            agent = create_agent(output_dir=output_dir)
            set_output_dir(output_dir)

            send_queue.put_nowait({
                "type": "status", "text": "Starting agent…"
            })
            await agent.start()

            session = await agent.create_session()
            send_queue.put_nowait({
                "type": "connected",
                "session_id": ws_id,
                "text": (
                    "Agent ready. Ask me anything about "
                    "your patch-clamp data!"
                ),
            })

            # Message loop
            while True:
                raw = await websocket.receive()
                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    msg = {"text": raw}

                user_text = msg.get("text", "").strip()
                if not user_text:
                    continue

                # If user references a file_id, rewrite to full path
                file_id = msg.get("file_id")
                if file_id:
                    full_path = output_dir / file_id
                    if full_path.exists():
                        user_text = (
                            f"Load the file at {full_path} "
                            f"and then: {user_text}"
                        )

                # Set current session for figure queue before streaming
                set_current_session(ws_id)
                await _stream_response(
                    session, user_text, output_dir, send_queue
                )
                set_current_session(None)

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.exception("WebSocket error")
            try:
                send_queue.put_nowait({
                    "type": "error", "text": str(e)
                })
            except Exception:
                pass
        finally:
            # Clean up
            set_current_session(None)
            unregister_session(ws_id)
            # Stop the drain tasks
            send_queue.put_nowait(None)
            drain_task.cancel()
            figure_drain_task.cancel()
            if agent:
                try:
                    await agent.stop()
                except Exception:
                    pass

    return app


# ---------------------------------------------------------------------------
# Streaming helper (mirrors cli._send_streaming but over WebSocket)
# ---------------------------------------------------------------------------

async def _stream_response(
    session, prompt: str, output_dir: Path,
    send_queue: asyncio.Queue, timeout: float = 600
):
    """Send a prompt and stream events back via the queue."""
    from copilot.generated.session_events import SessionEventType

    idle_event = asyncio.Event()
    response_text_parts: list[str] = []

    def _enqueue(msg: dict):
        """Thread/callback-safe: put a message on the queue."""
        try:
            send_queue.put_nowait(msg)
        except Exception:
            pass

    def _handler(event):
        etype = event.type

        if etype == SessionEventType.ASSISTANT_REASONING_DELTA:
            delta = (
                getattr(event.data, "delta_content", None) or ""
            )
            if delta:
                _enqueue({"type": "thinking", "text": delta})

        elif etype == SessionEventType.ASSISTANT_REASONING:
            text = (
                getattr(event.data, "reasoning_text", None) or ""
            )
            if text:
                _enqueue({"type": "thinking", "text": text})

        elif etype == SessionEventType.ASSISTANT_MESSAGE_DELTA:
            delta = (
                getattr(event.data, "delta_content", None) or ""
            )
            if delta:
                response_text_parts.append(delta)
                _enqueue({
                    "type": "text_delta", "text": delta
                })

        elif etype == SessionEventType.ASSISTANT_MESSAGE:
            _enqueue_figures(event, output_dir, _enqueue)
            if not response_text_parts:
                content = _extract_content(event)
                if content:
                    _enqueue({
                        "type": "text_delta", "text": content
                    })

        elif etype == SessionEventType.TOOL_EXECUTION_START:
            name = getattr(event.data, "tool_name", "tool")
            _enqueue({"type": "tool_start", "name": name})

        elif etype == SessionEventType.TOOL_EXECUTION_COMPLETE:
            name = getattr(event.data, "tool_name", "tool")
            _enqueue({"type": "tool_complete", "name": name})
            # Extract figures from tool result
            _extract_figures_from_tool_event(event, _enqueue)

        elif etype == SessionEventType.SESSION_ERROR:
            err = getattr(event.data, "message", str(event.data))
            _enqueue({"type": "error", "text": err})
            idle_event.set()

        elif etype == SessionEventType.SESSION_IDLE:
            idle_event.set()

    unsub = session.on(_handler)
    try:
        await session.send({"prompt": prompt})
        try:
            await asyncio.wait_for(
                idle_event.wait(), timeout=timeout
            )
        except asyncio.TimeoutError:
            _enqueue({
                "type": "error", "text": "Response timed out."
            })
    finally:
        unsub()

    _enqueue({"type": "done"})
    # Give the drain task a moment to flush
    await asyncio.sleep(0.05)


def _enqueue_figures(event, output_dir: Path, enqueue_fn):
    """Extract figures from a completed message and enqueue them."""
    # Debug: log all available attributes
    if hasattr(event, "data"):
        attrs = [a for a in dir(event.data) if not a.startswith("_")]
        logger.debug(
            "ASSISTANT_MESSAGE event.data attrs: %s", attrs
        )
    
    tool_results = getattr(event, "tool_results", None)
    if not tool_results:
        if hasattr(event, "data"):
            tool_results = getattr(
                event.data, "tool_results", None
            )
    
    logger.debug(
        "tool_results from event: %s",
        type(tool_results).__name__ if tool_results else "None"
    )
    
    if not tool_results:
        return

    items = (
        tool_results if isinstance(tool_results, list)
        else [tool_results]
    )
    for tr in items:
        if not isinstance(tr, dict):
            continue
        figures = tr.get("figures", [])
        logger.debug("Found %d figures in tool result", len(figures))
        for fig in figures:
            if isinstance(fig, dict) and "image_base64" in fig:
                enqueue_fn({
                    "type": "figure",
                    "data": fig["image_base64"],
                    "figure_number": fig.get(
                        "figure_number", 0
                    ),
                })


def _extract_figures_from_tool_event(event, enqueue_fn):
    """Extract figures from a tool execution complete event."""
    # Debug: log all available attributes on event.data
    if hasattr(event, "data"):
        attrs = [a for a in dir(event.data) if not a.startswith("_")]
        logger.debug(
            "TOOL_EXECUTION_COMPLETE event.data attrs: %s",
            attrs
        )
    
    # Try multiple ways to get the tool result
    result = None
    
    # Check event.data.result
    if hasattr(event, "data"):
        result = getattr(event.data, "result", None)
        if result is None:
            result = getattr(event.data, "tool_result", None)
        if result is None:
            result = getattr(event.data, "output", None)
        # Also check for nested result in content
        if result is None:
            content = getattr(event.data, "content", None)
            if content:
                result = content
    
    # If result is a string, try to parse as JSON
    if isinstance(result, str):
        try:
            result = json.loads(result)
        except (json.JSONDecodeError, TypeError):
            pass
    
    if not isinstance(result, dict):
        logger.debug(
            "Tool event result is not a dict: type=%s",
            type(result).__name__ if result else "None"
        )
        return
    
    # Check for figures in the result
    figures = result.get("figures", [])
    if not figures:
        logger.debug("No figures in tool result")
        return
    
    logger.debug("Found %d figure(s) in tool result", len(figures))
    for fig in figures:
        if isinstance(fig, dict) and "image_base64" in fig:
            enqueue_fn({
                "type": "figure",
                "data": fig["image_base64"],
                "figure_number": fig.get("figure_number", 0),
            })


def _extract_content(event) -> Optional[str]:
    """Pull text content from a SessionEvent."""
    if hasattr(event, "data") and hasattr(event.data, "content"):
        return event.data.content
    if isinstance(event, dict):
        return event.get("content") or event.get("message")
    return None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sample_dir() -> Path:
    """Return the path to bundled sample data."""
    # Look relative to project root (data/sample_abfs/)
    candidates = [
        Path(__file__).resolve().parents[3] / "data" / "sample_abfs",
        Path.cwd() / "data" / "sample_abfs",
    ]
    for c in candidates:
        if c.exists():
            return c
    return candidates[0]


def _session_dir(session_id: str) -> Path:
    """Return (and create) a temp directory for a WebSocket session."""
    d = Path(tempfile.gettempdir()) / "patchagent_web" / session_id
    d.mkdir(parents=True, exist_ok=True)
    return d


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    """Run the Quart server (used by `patchagent-web` console script)."""
    port = int(os.environ.get("PORT", "8080"))
    host = os.environ.get("HOST", "0.0.0.0")
    debug = os.environ.get("PATCHAGENT_DEBUG", "").lower() in ("1", "true", "yes")

    logging.basicConfig(
        level=logging.DEBUG if debug else logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    app = create_app()
    app.run(host=host, port=port, debug=debug)


if __name__ == "__main__":
    main()
