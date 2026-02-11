"""
Protocol loader — discover and load user-defined protocol YAML files.

Looks for ``protocols/`` directories in two locations (highest priority first):

1. Current working directory (next to the user's data)
2. The patchAgent package/repo root (bundled defaults)

An optional CLI-specified directory is checked with highest priority when provided.
Same-name protocols from higher-priority directories override lower ones.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


# ── Discovery ───────────────────────────────────────────────────────


def discover_protocol_dirs(extra_dir: Optional[str | Path] = None) -> list[Path]:
    """Return a list of ``protocols/`` directories that exist, ordered by priority.

    Priority (highest first):
        1. *extra_dir* (CLI override, if given)
        2. ``./protocols/`` relative to CWD (user's data directory)
        3. ``protocols/`` relative to the patchAgent package root
    """
    dirs: list[Path] = []

    # 1. CLI override
    if extra_dir is not None:
        p = Path(extra_dir)
        if p.is_dir():
            dirs.append(p)
        else:
            logger.debug("CLI protocols dir does not exist: %s", p)

    # 2. CWD / data directory
    cwd_protocols = Path.cwd() / "protocols"
    if cwd_protocols.is_dir():
        dirs.append(cwd_protocols)

    # 3. Bundled protocols (next to the repo root)
    #    Navigate from this file → utils/ → patch_agent/ → src/ → repo root
    package_root = Path(__file__).resolve().parent.parent.parent.parent
    bundled = package_root / "protocols"
    if bundled.is_dir() and bundled not in dirs:
        dirs.append(bundled)

    return dirs


# ── Loading ─────────────────────────────────────────────────────────


def load_protocols(
    dirs: Optional[list[Path]] = None,
    extra_dir: Optional[str | Path] = None,
) -> list[dict[str, Any]]:
    """Load all protocol YAML files from the given directories.

    Parameters
    ----------
    dirs : list[Path], optional
        Directories to scan.  When *None*, :func:`discover_protocol_dirs` is
        called automatically.
    extra_dir : str | Path, optional
        Passed through to :func:`discover_protocol_dirs` when *dirs* is None.

    Returns
    -------
    list[dict]
        Parsed protocol dicts.  Higher-priority directories override
        lower-priority ones when two files define the same ``protocol.name``.
    """
    try:
        import yaml  # noqa: F811
    except ImportError:
        logger.warning(
            "PyYAML is not installed — cannot load protocol files. "
            "Install it with: pip install pyyaml"
        )
        return []

    if dirs is None:
        dirs = discover_protocol_dirs(extra_dir=extra_dir)

    if not dirs:
        return []

    # Collect all YAML files (higher-priority dirs first)
    seen_names: dict[str, dict] = {}  # protocol name → parsed dict
    for d in dirs:
        for path in sorted(d.glob("*.y*ml")):  # .yaml and .yml
            if not path.is_file():
                continue
            try:
                with open(path, "r", encoding="utf-8") as fh:
                    data = yaml.safe_load(fh)
            except Exception as exc:
                logger.warning("Skipping malformed protocol file %s: %s", path.name, exc)
                continue

            if not isinstance(data, dict):
                logger.warning("Skipping %s: expected a YAML mapping, got %s", path.name, type(data).__name__)
                continue

            # Support both top-level ``protocol:`` wrapper and flat format
            proto = data.get("protocol", data)

            name = proto.get("name")
            if not name:
                logger.warning("Skipping %s: missing 'name' field", path.name)
                continue

            # First occurrence wins (higher-priority dir was appended first)
            if name not in seen_names:
                proto["_source"] = str(path)
                seen_names[name] = proto
                logger.debug("Loaded protocol '%s' from %s", name, path)
            else:
                logger.debug(
                    "Protocol '%s' already loaded from higher-priority dir — skipping %s",
                    name,
                    path,
                )

    protocols = list(seen_names.values())
    if protocols:
        logger.info(
            "Loaded %d protocol(s): %s",
            len(protocols),
            ", ".join(p["name"] for p in protocols),
        )
    return protocols


# ── Prompt formatting ───────────────────────────────────────────────


def format_protocols_for_prompt(protocols: list[dict[str, Any]]) -> str:
    """Render loaded protocols as a plain-text section for the system message.

    Returns an empty string when there are no protocols.
    """
    if not protocols:
        return ""

    lines = [
        "## Known Recording Protocols",
        "",
        "The following recording protocols are available.  When the user loads a file, "
        "check if the file's protocol name matches one of these.  If it does, use the "
        "analysis_recommendations to guide your analysis.",
        "",
    ]

    for proto in protocols:
        lines.append(f"### {proto['name']}")
        if proto.get("type"):
            lines.append(f"- **Type:** {proto['type']}")
        if proto.get("description"):
            lines.append(f"- **Description:** {proto['description']}")

        timing = proto.get("timing")
        if timing and isinstance(timing, dict):
            parts = [f"{k}: {v}" for k, v in timing.items()]
            lines.append(f"- **Timing:** {', '.join(parts)}")

        stimulus = proto.get("stimulus")
        if stimulus and isinstance(stimulus, dict):
            parts = [f"{k}: {v}" for k, v in stimulus.items()]
            lines.append(f"- **Stimulus:** {', '.join(parts)}")

        expected = proto.get("expected_responses")
        if expected and isinstance(expected, list):
            lines.append(f"- **Expected responses:** {', '.join(expected)}")

        recs = proto.get("analysis_recommendations")
        if recs and isinstance(recs, list):
            lines.append(f"- **Recommended analyses:** {', '.join(recs)}")

        notes = proto.get("notes")
        if notes:
            lines.append(f"- **Notes:** {notes}")

        lines.append("")

    return "\n".join(lines)


# ── Auto-matching ───────────────────────────────────────────────────


def find_matching_protocol(
    protocols: list[dict[str, Any]],
    name: str,
) -> Optional[dict[str, Any]]:
    """Find a loaded protocol whose name matches *name* (case-insensitive substring).

    Parameters
    ----------
    protocols : list[dict]
        Loaded protocol dicts (from :func:`load_protocols`).
    name : str
        Protocol name string from the data file (e.g. ``abf.protocol``).

    Returns
    -------
    dict or None
        The matching protocol dict, or *None* if no match is found.
    """
    if not protocols or not name:
        return None

    name_lower = name.lower().replace("_", " ").replace("-", " ")
    name_compact = name_lower.replace(" ", "")

    # Pass 1: exact match (case-insensitive, normalised)
    for proto in protocols:
        proto_name = proto["name"].lower().replace("_", " ").replace("-", " ")
        if proto_name == name_lower:
            return proto

    # Pass 2: substring match (either direction)
    for proto in protocols:
        proto_name = proto["name"].lower().replace("_", " ").replace("-", " ")
        proto_compact = proto_name.replace(" ", "")
        if (proto_name in name_lower or name_lower in proto_name
                or proto_compact in name_compact or name_compact in proto_compact):
            return proto

    return None
