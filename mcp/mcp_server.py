"""
MCP Server for Patch-Clamp Analysis Tools

Exposes patch-clamp analysis tools via Model Context Protocol (MCP).
"""

import asyncio
import json
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)



class PatchAgentMCPServer:
    """
    MCP Server that exposes patch-clamp analysis tools.
    
    This allows the tools to be used from any MCP-compatible client,
    including VS Code extensions and other AI assistants.
    """

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize the MCP server.

        Args:
            config_path: Path to mcp_config.json, defaults to same directory
        """
        self.config_path = config_path or "mcp_config.json"
        self.config = self._load_config()
        self.tools = self._register_tools()

    def _load_config(self) -> Dict[str, Any]:
        """Load MCP configuration from JSON file."""
        import os
        
        config_file = os.path.join(os.path.dirname(__file__), self.config_path)
        try:
            with open(config_file, "r") as f:
                return json.load(f)
        except FileNotFoundError:
            logger.warning(f"Config file not found: {config_file}")
            return {"name": "patch-agent-mcp", "tools": {}}

    def _register_tools(self) -> Dict[str, callable]:
        """Register tool handlers."""
        from patch_agent.tools import (
            load_file,
            get_file_metadata,
            detect_spikes,
            extract_spike_features,
            calculate_input_resistance,
            calculate_time_constant,
            run_sweep_qc,
            fit_exponential,
        )
        from patch_agent.tools.io_tools import get_sweep_data

        return {
            "load_file": self._wrap_tool(load_file),
            "get_file_metadata": self._wrap_tool(get_file_metadata),
            "detect_spikes": self._wrap_spike_tool(detect_spikes),
            "extract_spike_features": self._wrap_spike_tool(extract_spike_features),
            "calculate_input_resistance": self._wrap_passive_tool(calculate_input_resistance),
            "calculate_time_constant": self._wrap_passive_tool(calculate_time_constant),
            "run_sweep_qc": self._wrap_qc_tool(run_sweep_qc),
            "fit_exponential": self._wrap_fit_tool(fit_exponential),
        }

    def _wrap_tool(self, func):
        """Wrap a simple tool function for MCP."""
        async def wrapper(params: Dict[str, Any]) -> Dict[str, Any]:
            try:
                result = func(**params)
                # Convert numpy arrays to lists for JSON serialization
                return self._serialize_result(result)
            except Exception as e:
                logger.error(f"Tool error: {e}")
                return {"error": str(e)}
        return wrapper

    def _wrap_spike_tool(self, func):
        """Wrap spike analysis tools that need data loading."""
        async def wrapper(params: Dict[str, Any]) -> Dict[str, Any]:
            try:
                from patch_agent.tools.io_tools import get_sweep_data
                
                file_path = params.pop("file_path")
                sweep_number = params.pop("sweep_number", 0)
                
                sweep_data = get_sweep_data(file_path, sweep_number)
                result = func(
                    voltage=sweep_data["voltage"],
                    time=sweep_data["time"],
                    current=sweep_data["current"],
                    **params
                )
                return self._serialize_result(result)
            except Exception as e:
                logger.error(f"Spike tool error: {e}")
                return {"error": str(e)}
        return wrapper

    def _wrap_passive_tool(self, func):
        """Wrap passive property tools."""
        async def wrapper(params: Dict[str, Any]) -> Dict[str, Any]:
            try:
                from patch_agent.tools.io_tools import get_sweep_data
                
                file_path = params.pop("file_path")
                sweep_number = params.pop("sweep_number", 0)
                
                sweep_data = get_sweep_data(file_path, sweep_number)
                result = func(
                    voltage=sweep_data["voltage"],
                    current=sweep_data["current"],
                    time=sweep_data["time"],
                    **params
                )
                return self._serialize_result(result)
            except Exception as e:
                logger.error(f"Passive tool error: {e}")
                return {"error": str(e)}
        return wrapper

    def _wrap_qc_tool(self, func):
        """Wrap QC tools."""
        async def wrapper(params: Dict[str, Any]) -> Dict[str, Any]:
            try:
                from patch_agent.tools.io_tools import get_sweep_data
                
                file_path = params.pop("file_path")
                sweep_number = params.pop("sweep_number", 0)
                
                sweep_data = get_sweep_data(file_path, sweep_number)
                result = func(
                    voltage=sweep_data["voltage"],
                    current=sweep_data["current"],
                    time=sweep_data["time"],
                    **params
                )
                return self._serialize_result(result)
            except Exception as e:
                logger.error(f"QC tool error: {e}")
                return {"error": str(e)}
        return wrapper

    def _wrap_fit_tool(self, func):
        """Wrap fitting tools."""
        async def wrapper(params: Dict[str, Any]) -> Dict[str, Any]:
            try:
                from patch_agent.tools.io_tools import get_sweep_data
                import numpy as np
                
                file_path = params.pop("file_path")
                sweep_number = params.pop("sweep_number", 0)
                
                sweep_data = get_sweep_data(file_path, sweep_number)
                result = func(
                    y=sweep_data["voltage"],
                    x=sweep_data["time"],
                    **params
                )
                return self._serialize_result(result)
            except Exception as e:
                logger.error(f"Fit tool error: {e}")
                return {"error": str(e)}
        return wrapper

    def _serialize_result(self, result: Any) -> Dict[str, Any]:
        """Serialize result for JSON, converting numpy arrays to lists."""
        import numpy as np
        
        if isinstance(result, dict):
            return {k: self._serialize_value(v) for k, v in result.items()}
        return self._serialize_value(result)

    def _serialize_value(self, value: Any) -> Any:
        """Serialize a single value."""
        import numpy as np
        
        if isinstance(value, np.ndarray):
            return value.tolist()
        elif isinstance(value, (np.integer, np.floating)):
            return float(value)
        elif isinstance(value, dict):
            return {k: self._serialize_value(v) for k, v in value.items()}
        elif isinstance(value, list):
            return [self._serialize_value(v) for v in value]
        return value

    async def handle_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle an incoming MCP request.

        Args:
            request: MCP request with 'method' and 'params'

        Returns:
            MCP response
        """
        method = request.get("method")
        params = request.get("params", {})

        if method == "tools/list":
            return {"tools": list(self.config.get("tools", {}).keys())}
        
        elif method == "tools/call":
            tool_name = params.get("name")
            tool_params = params.get("arguments", {})
            
            if tool_name in self.tools:
                result = await self.tools[tool_name](tool_params)
                return {"content": [{"type": "text", "text": json.dumps(result)}]}
            else:
                return {"error": f"Unknown tool: {tool_name}"}
        
        elif method == "resources/list":
            return {"resources": list(self.config.get("resources", {}).keys())}
        
        else:
            return {"error": f"Unknown method: {method}"}

    async def run(self, host: str = "localhost", port: int = 8080):
        """
        Run the MCP server.

        Args:
            host: Host to bind to
            port: Port to listen on
        """
        # Placeholder for actual MCP server implementation
        # This would use the MCP library when available
        logger.info(f"MCP Server would start on {host}:{port}")
        logger.info(f"Available tools: {list(self.tools.keys())}")
        
        # Keep running
        while True:
            await asyncio.sleep(1)


def main():
    """Main entry point for running the MCP server."""
    logging.basicConfig(level=logging.INFO)
    
    server = PatchAgentMCPServer()
    
    try:
        asyncio.run(server.run())
    except KeyboardInterrupt:
        logger.info("Server stopped")


if __name__ == "__main__":
    main()
