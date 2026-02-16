"""
patchAgent Web — Browser-based chat UI for patch-clamp analysis.

Delegates to ``sciagent.web.app.create_app`` with the PatchAgent
factory and domain configuration.

Start with:
    patchagent-web          # uses entry point
    python -m patchagent.web.app   # direct
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from sciagent.web.app import create_app as _create_app
from patchagent.agent import create_agent
from patchagent.config import PATCH_CONFIG

logger = logging.getLogger(__name__)


def _sample_dir() -> Path:
    """Return the path to bundled sample data."""
    candidates = [
        Path(__file__).resolve().parents[3] / "data" / "sample_abfs",
        Path.cwd() / "data" / "sample_abfs",
    ]
    for c in candidates:
        if c.exists():
            return c
    return candidates[0]


def create_app():
    """Create the Quart app configured for patch-clamp analysis."""
    return _create_app(
        agent_factory=lambda **kw: create_agent(**kw),
        config=PATCH_CONFIG,
        sample_dir=_sample_dir(),
    )


def main():
    """Run the Quart server (used by ``patchagent-web`` console script)."""
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
