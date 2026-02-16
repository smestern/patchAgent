"""
MCP Server for Patch-Clamp Analysis Tools

Subclasses ``sciagent.mcp.BaseMCPServer`` to expose patch-clamp
analysis tools via the Model Context Protocol.
"""

import asyncio
import json
import logging
from typing import Any, Dict

import numpy as np

from sciagent.mcp import BaseMCPServer

logger = logging.getLogger(__name__)


class PatchAgentMCPServer(BaseMCPServer):
    """
    MCP Server exposing patch-clamp analysis tools.

    Inherits JSON-RPC dispatch and tool registration from
    ``BaseMCPServer``; adds electrophysiology-specific tools.
    """

    def __init__(self):
        super().__init__(name="patch-agent-mcp", version="0.1.0")
        self._register_patch_tools()

    def _register_patch_tools(self):
        """Register all patch-clamp-specific tools."""
        from patchagent.tools import (
            load_file,
            get_file_metadata,
            detect_spikes,
            extract_spike_features,
            calculate_input_resistance,
            calculate_time_constant,
            run_sweep_qc,
            fit_exponential,
        )
        from patchagent.tools.io_tools import get_sweep_data

        # -- Direct tools (take simple params) --------------------------------
        self.register_tool("load_file", self._wrap(load_file), {
            "description": "Load an ABF or NWB electrophysiology file",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Path to the file"},
                },
                "required": ["file_path"],
            },
        })
        self.register_tool("get_file_metadata", self._wrap(get_file_metadata), {
            "description": "Get metadata from an electrophysiology file",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Path to the file"},
                },
                "required": ["file_path"],
            },
        })

        # -- Tools that need sweep data loaded first --------------------------
        def _sweep_schema(extra_props=None):
            props = {
                "file_path": {"type": "string", "description": "Path to the file"},
                "sweep_number": {"type": "integer", "description": "Sweep number (0-indexed)", "default": 0},
            }
            if extra_props:
                props.update(extra_props)
            return {"type": "object", "properties": props, "required": ["file_path"]}

        async def _with_sweep(func, arguments):
            file_path = arguments.pop("file_path")
            sweep_number = arguments.pop("sweep_number", 0)
            sweep_data = get_sweep_data(file_path, sweep_number)
            result = func(
                voltage=sweep_data["voltage"],
                time=sweep_data["time"],
                current=sweep_data.get("current"),
                **arguments,
            )
            return self._serialize(result)

        self.register_tool("detect_spikes",
            lambda args: _with_sweep(detect_spikes, dict(args)),
            {"description": "Detect action potentials using dV/dt threshold",
             "inputSchema": _sweep_schema()})

        self.register_tool("extract_spike_features",
            lambda args: _with_sweep(extract_spike_features, dict(args)),
            {"description": "Extract spike features (threshold, amplitude, width)",
             "inputSchema": _sweep_schema()})

        self.register_tool("calculate_input_resistance",
            lambda args: _with_sweep(calculate_input_resistance, dict(args)),
            {"description": "Calculate input resistance from hyperpolarizing step",
             "inputSchema": _sweep_schema()})

        self.register_tool("calculate_time_constant",
            lambda args: _with_sweep(calculate_time_constant, dict(args)),
            {"description": "Fit membrane time constant (tau)",
             "inputSchema": _sweep_schema()})

        self.register_tool("run_sweep_qc",
            lambda args: _with_sweep(run_sweep_qc, dict(args)),
            {"description": "Run quality control checks on a sweep",
             "inputSchema": _sweep_schema()})

        self.register_tool("fit_exponential",
            lambda args: _with_sweep(fit_exponential, dict(args)),
            {"description": "Fit single exponential to data",
             "inputSchema": _sweep_schema()})

    # -- Helpers --------------------------------------------------------------

    def _wrap(self, func):
        """Wrap a sync tool for async dispatch."""
        async def _handler(arguments: dict):
            result = func(**arguments)
            return self._serialize(result)
        return _handler

    def _serialize(self, value: Any) -> Any:
        """Recursively convert numpy types to JSON-safe Python types."""
        if isinstance(value, np.ndarray):
            return value.tolist()
        if isinstance(value, (np.integer,)):
            return int(value)
        if isinstance(value, (np.floating,)):
            return float(value)
        if isinstance(value, dict):
            return {k: self._serialize(v) for k, v in value.items()}
        if isinstance(value, list):
            return [self._serialize(v) for v in value]
        return value


def main():
    """Run the MCP server over stdio."""
    logging.basicConfig(level=logging.INFO)
    PatchAgentMCPServer().run()


if __name__ == "__main__":
    main()
