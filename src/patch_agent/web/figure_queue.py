"""
Figure Queue - Thread-safe queue for passing figures from tools to websocket.

This allows synchronous tool executions to communicate figure data back
to the async websocket handlers for inline display.
"""

import threading
from queue import Queue
from typing import Dict, Any, Optional, Callable
import logging

logger = logging.getLogger(__name__)

# Global registry of session queues: session_id -> Queue
_session_queues: Dict[str, Queue] = {}
_lock = threading.Lock()


def register_session(session_id: str) -> Queue:
    """
    Register a new session and create its figure queue.
    
    Args:
        session_id: Unique session identifier
        
    Returns:
        Queue for this session's figures
    """
    with _lock:
        if session_id not in _session_queues:
            _session_queues[session_id] = Queue()
            logger.debug("Registered figure queue for session %s", session_id)
        return _session_queues[session_id]


def unregister_session(session_id: str) -> None:
    """Remove a session's figure queue."""
    with _lock:
        if session_id in _session_queues:
            del _session_queues[session_id]
            logger.debug("Unregistered figure queue for session %s", session_id)


def push_figure(session_id: str, figure_data: Dict[str, Any]) -> bool:
    """
    Push a figure to a session's queue.
    
    Args:
        session_id: Target session
        figure_data: Dict with 'image_base64', 'figure_number', etc.
        
    Returns:
        True if successfully queued, False if session not found
    """
    with _lock:
        queue = _session_queues.get(session_id)
        if queue is None:
            logger.warning(
                "No queue for session %s, figure dropped", session_id
            )
            return False
    
    queue.put_nowait(figure_data)
    logger.debug(
        "Pushed figure %s to session %s",
        figure_data.get("figure_number", "?"),
        session_id
    )
    return True


def get_figures(session_id: str) -> list:
    """
    Get all pending figures for a session (non-blocking).
    
    Returns:
        List of figure data dicts
    """
    with _lock:
        queue = _session_queues.get(session_id)
        if queue is None:
            return []
    
    figures = []
    while not queue.empty():
        try:
            figures.append(queue.get_nowait())
        except Exception:
            break
    
    return figures


# Global current session ID for tool execution context
_current_session_id: Optional[str] = None
_session_lock = threading.Lock()


def set_current_session(session_id: Optional[str]) -> None:
    """Set the current session ID for tool execution context."""
    global _current_session_id
    with _session_lock:
        _current_session_id = session_id
        logger.debug("Current session set to %s", session_id)


def get_current_session() -> Optional[str]:
    """Get the current session ID."""
    with _session_lock:
        return _current_session_id


def push_figure_to_current_session(figure_data: Dict[str, Any]) -> bool:
    """Push a figure to the current session's queue."""
    session_id = get_current_session()
    if session_id is None:
        logger.debug("No current session, figure not queued")
        return False
    return push_figure(session_id, figure_data)
