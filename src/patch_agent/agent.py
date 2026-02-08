"""
patchAgent - Main agent entry point

This module provides the main Copilot SDK client and agent configuration
for patch-clamp electrophysiology analysis.
"""

import logging
import tempfile
from pathlib import Path
from typing import Optional, Dict, Any, List, Callable

# Import Copilot SDK
from copilot import CopilotClient
from copilot.types import Tool, SessionConfig, CustomAgentConfig

logger = logging.getLogger(__name__)


# Agent configuration
AGENT_CONFIG: CustomAgentConfig = {
    "name": "patch-analyst",
    "display_name": "Patch-Clamp Analysis Agent",
    "description": "Expert agent for analyzing patch-clamp electrophysiology recordings",
    "prompt": "",  # Will be set from system messages
    "infer": True,
}


def _create_tool(
    name: str,
    description: str,
    handler: Callable,
    parameters: Optional[Dict[str, Any]] = None
) -> Tool:
    """
    Create a Tool object for the Copilot SDK.
    
    Args:
        name: Tool name (function name)
        description: What the tool does
        handler: The function to call
        parameters: JSON schema for parameters
        
    Returns:
        Tool object
    """
    return Tool(
        name=name,
        description=description,
        handler=handler,
        parameters=parameters or {"type": "object", "properties": {}},
    )


class PatchAgent:
    """
    Main patch-clamp analysis agent.
    
    Wraps the GitHub Copilot SDK client and provides electrophysiology-specific
    tools and system prompts.
    
    Example:
        >>> agent = PatchAgent()
        >>> await agent.start()
        >>> session = await agent.create_session()
        >>> result = await session.send_and_wait({"prompt": "Load my file.abf"})
        >>> await session.destroy()
        >>> await agent.stop()
    """

    def __init__(
        self,
        model: str = "claude-sonnet-4.5",
        log_level: str = "info",
        output_dir: Optional[str | Path] = None,
    ):
        """
        Initialize the PatchAgent.

        Args:
            model: The model to use for the agent (gpt-4.1, claude-sonnet-4, etc.)
            log_level: Logging level for the SDK
            output_dir: Directory where the agent saves scripts, plots, and
                analysis outputs.  Does NOT change the process working directory.
                Defaults to a temp directory if not set.
        """
        self.model = model

        # Resolve and create the output directory
        if output_dir is not None:
            self._output_dir = Path(output_dir).resolve()
        else:
            self._output_dir = Path(tempfile.mkdtemp(prefix="patchagent_"))
        self._output_dir.mkdir(parents=True, exist_ok=True)

        self._client = CopilotClient({
                    "log_level": log_level,
                })
        self._tools: List[Tool] = []
        self._sessions: Dict[str, Any] = {}
        self._load_tools()

    # -- output_dir property --------------------------------------------------

    @property
    def output_dir(self) -> Path:
        """The directory where the agent saves scripts, plots, and outputs."""
        return self._output_dir

    @output_dir.setter
    def output_dir(self, value: str | Path) -> None:
        """Change the output directory at runtime (creates it if needed)."""
        self._output_dir = Path(value).resolve()
        self._output_dir.mkdir(parents=True, exist_ok=True)
        logger.info("Agent output_dir set to %s", self._output_dir)

    def _load_tools(self):
        """Load all available tools from the tools module."""
        from .tools import (
            # I/O tools
            load_file,
            get_file_metadata,
            get_sweep_data,
            list_sweeps,
            # Spike tools
            detect_spikes,
            extract_spike_features,
            extract_spike_train_features,
            # Passive tools
            calculate_input_resistance,
            calculate_time_constant,
            calculate_sag,
            calculate_resting_potential,
            # QC tools
            run_sweep_qc,
            check_baseline_stability,
            measure_noise,
            # Fitting tools
            fit_exponential,
            fit_iv_curve,
            fit_fi_curve,
            # Code tools
            execute_code,
            run_custom_analysis,
            validate_code,
            # Rigor tools
            check_scientific_rigor,
            validate_data_integrity,
            check_physiological_bounds,
        )

        # Define tool schemas for the SDK
        self._tools = [
            # === I/O Tools ===
            _create_tool(
                "load_file",
                "Load an ABF or NWB electrophysiology file. Returns time, voltage, and current arrays.",
                load_file,
                {
                    "type": "object",
                    "properties": {
                        "file_path": {"type": "string", "description": "Path to the ABF or NWB file"},
                    },
                    "required": ["file_path"],
                },
            ),
            _create_tool(
                "get_file_metadata",
                "Get metadata from an electrophysiology file (sweep count, sample rate, protocol, etc.)",
                get_file_metadata,
                {
                    "type": "object",
                    "properties": {
                        "file_path": {"type": "string", "description": "Path to the file"},
                    },
                    "required": ["file_path"],
                },
            ),
            _create_tool(
                "get_sweep_data",
                "Get voltage/current data for a specific sweep",
                get_sweep_data,
                {
                    "type": "object",
                    "properties": {
                        "file_path": {"type": "string", "description": "Path to the file"},
                        "sweep_index": {"type": "integer", "description": "Sweep number (0-indexed)"},
                    },
                    "required": ["file_path", "sweep_index"],
                },
            ),
            _create_tool(
                "list_sweeps",
                "List all sweeps in a file with their stimulus amplitudes",
                list_sweeps,
                {
                    "type": "object",
                    "properties": {
                        "file_path": {"type": "string", "description": "Path to the file"},
                    },
                    "required": ["file_path"],
                },
            ),
            
            # === Spike Analysis Tools ===
            _create_tool(
                "detect_spikes",
                "Detect action potentials in a voltage trace using dV/dt threshold",
                detect_spikes,
                {
                    "type": "object",
                    "properties": {
                        "voltage": {"type": "array", "items": {"type": "number"}, "description": "Voltage trace in mV"},
                        "time": {"type": "array", "items": {"type": "number"}, "description": "Time array in seconds"},
                        "dv_cutoff": {"type": "number", "description": "dV/dt threshold in mV/ms (default: 20)"},
                        "min_peak": {"type": "number", "description": "Minimum peak voltage in mV (default: -30)"},
                    },
                    "required": ["voltage", "time"],
                },
            ),
            _create_tool(
                "extract_spike_features",
                "Extract features from detected spikes (threshold, amplitude, width, kinetics)",
                extract_spike_features,
                {
                    "type": "object",
                    "properties": {
                        "voltage": {"type": "array", "items": {"type": "number"}, "description": "Voltage trace in mV"},
                        "time": {"type": "array", "items": {"type": "number"}, "description": "Time array in seconds"},
                    },
                    "required": ["voltage", "time"],
                },
            ),
            _create_tool(
                "extract_spike_train_features",
                "Extract spike train features (firing rate, adaptation, ISI statistics)",
                extract_spike_train_features,
                {
                    "type": "object",
                    "properties": {
                        "voltage": {"type": "array", "items": {"type": "number"}, "description": "Voltage trace in mV"},
                        "time": {"type": "array", "items": {"type": "number"}, "description": "Time array in seconds"},
                    },
                    "required": ["voltage", "time"],
                },
            ),
            
            # === Passive Property Tools ===
            _create_tool(
                "calculate_input_resistance",
                "Calculate input resistance from a hyperpolarizing current step (Rm = ΔV/ΔI)",
                calculate_input_resistance,
                {
                    "type": "object",
                    "properties": {
                        "voltage": {"type": "array", "items": {"type": "number"}, "description": "Voltage trace in mV"},
                        "time": {"type": "array", "items": {"type": "number"}, "description": "Time array in seconds"},
                        "current": {"type": "array", "items": {"type": "number"}, "description": "Current command in pA"},
                    },
                    "required": ["voltage", "time", "current"],
                },
            ),
            _create_tool(
                "calculate_time_constant",
                "Fit membrane time constant (tau) from voltage response to current step",
                calculate_time_constant,
                {
                    "type": "object",
                    "properties": {
                        "voltage": {"type": "array", "items": {"type": "number"}, "description": "Voltage trace in mV"},
                        "time": {"type": "array", "items": {"type": "number"}, "description": "Time array in seconds"},
                    },
                    "required": ["voltage", "time"],
                },
            ),
            _create_tool(
                "calculate_sag",
                "Calculate sag ratio from hyperpolarizing step (Ih indicator)",
                calculate_sag,
                {
                    "type": "object",
                    "properties": {
                        "voltage": {"type": "array", "items": {"type": "number"}, "description": "Voltage trace in mV"},
                        "time": {"type": "array", "items": {"type": "number"}, "description": "Time array in seconds"},
                        "current": {"type": "array", "items": {"type": "number"}, "description": "Current command in pA"},
                    },
                    "required": ["voltage", "time", "current"],
                },
            ),
            _create_tool(
                "calculate_resting_potential",
                "Calculate resting membrane potential from baseline period",
                calculate_resting_potential,
                {
                    "type": "object",
                    "properties": {
                        "voltage": {"type": "array", "items": {"type": "number"}, "description": "Voltage trace in mV"},
                        "time": {"type": "array", "items": {"type": "number"}, "description": "Time array in seconds"},
                    },
                    "required": ["voltage", "time"],
                },
            ),
            
            # === QC Tools ===
            _create_tool(
                "run_sweep_qc",
                "Run quality control checks on a sweep (baseline stability, noise, integrity)",
                run_sweep_qc,
                {
                    "type": "object",
                    "properties": {
                        "voltage": {"type": "array", "items": {"type": "number"}, "description": "Voltage trace in mV"},
                        "time": {"type": "array", "items": {"type": "number"}, "description": "Time array in seconds"},
                        "current": {"type": "array", "items": {"type": "number"}, "description": "Current command in pA"},
                    },
                    "required": ["voltage", "time"],
                },
            ),
            _create_tool(
                "check_baseline_stability",
                "Check if baseline period is stable (low drift and noise)",
                check_baseline_stability,
                {
                    "type": "object",
                    "properties": {
                        "voltage": {"type": "array", "items": {"type": "number"}, "description": "Voltage trace in mV"},
                        "time": {"type": "array", "items": {"type": "number"}, "description": "Time array in seconds"},
                    },
                    "required": ["voltage", "time"],
                },
            ),
            _create_tool(
                "measure_noise",
                "Measure RMS noise level in a trace",
                measure_noise,
                {
                    "type": "object",
                    "properties": {
                        "voltage": {"type": "array", "items": {"type": "number"}, "description": "Voltage trace in mV"},
                    },
                    "required": ["voltage"],
                },
            ),
            
            # === Fitting Tools ===
            _create_tool(
                "fit_exponential",
                "Fit single exponential decay to data",
                fit_exponential,
                {
                    "type": "object",
                    "properties": {
                        "y": {"type": "array", "items": {"type": "number"}, "description": "Y values to fit"},
                        "x": {"type": "array", "items": {"type": "number"}, "description": "X values"},
                    },
                    "required": ["y", "x"],
                },
            ),
            _create_tool(
                "fit_iv_curve",
                "Fit IV curve to extract conductance and reversal potential",
                fit_iv_curve,
                {
                    "type": "object",
                    "properties": {
                        "currents": {"type": "array", "items": {"type": "number"}, "description": "Current values in pA"},
                        "voltages": {"type": "array", "items": {"type": "number"}, "description": "Voltage values in mV"},
                    },
                    "required": ["currents", "voltages"],
                },
            ),
            _create_tool(
                "fit_fi_curve",
                "Fit f-I curve to extract gain and rheobase",
                fit_fi_curve,
                {
                    "type": "object",
                    "properties": {
                        "currents": {"type": "array", "items": {"type": "number"}, "description": "Current steps in pA"},
                        "firing_rates": {"type": "array", "items": {"type": "number"}, "description": "Firing rates in Hz"},
                    },
                    "required": ["currents", "firing_rates"],
                },
            ),
            
            # === Code Execution Tools ===
            _create_tool(
                "execute_code",
                "Execute custom Python code for analysis. Code is validated for scientific rigor.",
                execute_code,
                {
                    "type": "object",
                    "properties": {
                        "code": {"type": "string", "description": "Python code to execute"},
                        "context": {"type": "object", "description": "Variables to make available"},
                    },
                    "required": ["code"],
                },
            ),
            _create_tool(
                "run_custom_analysis",
                "Run custom analysis code on a loaded file",
                run_custom_analysis,
                {
                    "type": "object",
                    "properties": {
                        "code": {"type": "string", "description": "Python analysis code"},
                        "file_path": {"type": "string", "description": "Path to data file"},
                    },
                    "required": ["code"],
                },
            ),
            _create_tool(
                "validate_code",
                "Validate Python code syntax and check for dangerous operations",
                validate_code,
                {
                    "type": "object",
                    "properties": {
                        "code": {"type": "string", "description": "Python code to validate"},
                    },
                    "required": ["code"],
                },
            ),
            
            # === Scientific Rigor Tools ===
            _create_tool(
                "check_scientific_rigor",
                "Check code for violations of scientific rigor (synthetic data, result manipulation)",
                check_scientific_rigor,
                {
                    "type": "object",
                    "properties": {
                        "code": {"type": "string", "description": "Python code to check"},
                    },
                    "required": ["code"],
                },
            ),
            _create_tool(
                "validate_data_integrity",
                "Validate data array for integrity issues (NaN, Inf, zero variance)",
                validate_data_integrity,
                {
                    "type": "object",
                    "properties": {
                        "data": {"type": "array", "items": {"type": "number"}, "description": "Data array to validate"},
                        "name": {"type": "string", "description": "Name for error messages"},
                    },
                    "required": ["data"],
                },
            ),
            _create_tool(
                "check_physiological_bounds",
                "Check if a measured value is within physiologically plausible bounds",
                check_physiological_bounds,
                {
                    "type": "object",
                    "properties": {
                        "value": {"type": "number", "description": "Measured value"},
                        "parameter": {"type": "string", "description": "Parameter name (e.g., 'input_resistance_MOhm')"},
                    },
                    "required": ["value", "parameter"],
                },
            ),
        ]
        
        logger.info(f"Loaded {len(self._tools)} tools")

    def _get_system_message(self) -> str:
        """Get the system message for the agent."""
        from .prompts.system_messages import PATCH_ANALYST_SYSTEM_MESSAGE
        return PATCH_ANALYST_SYSTEM_MESSAGE

    async def start(self):
        """Start the Copilot SDK client."""
        await self._client.start()
        logger.info("PatchAgent started")

    async def stop(self):
        """Stop the Copilot SDK client and clean up sessions."""
        for session_id in list(self._sessions.keys()):
            try:
                await self._sessions[session_id].destroy()
            except Exception as e:
                logger.warning(f"Error destroying session {session_id}: {e}")
        self._sessions.clear()
        await self._client.stop()
        logger.info("PatchAgent stopped")

    async def create_session(
        self,
        custom_system_message: Optional[str] = None,
        model: Optional[str] = None,
        additional_tools: Optional[List[Tool]] = None,
    ):
        """
        Create a new agent session with the Copilot SDK.

        Args:
            custom_system_message: Optional custom system message (appended to default)
            model: Optional model override
            additional_tools: Optional additional tools to include

        Returns:
            The created CopilotSession object
        """
        # Build system message
        base_system = self._get_system_message()
        if custom_system_message:
            system_message = {"mode": "append", "content": custom_system_message}
        else:
            system_message = {"mode": "append", "content": base_system}

        # Combine tools
        all_tools = self._tools.copy()
        if additional_tools:
            all_tools.extend(additional_tools)

        # Build custom agent config with our system prompt
        agent_config = AGENT_CONFIG.copy()
        agent_config["prompt"] = base_system

        # Create session config
        config: SessionConfig = {
            "model": model or self.model,
            "tools": all_tools,
            "system_message": system_message,
            "custom_agents": [agent_config],
            "streaming": True,
        }

        session = await self._client.create_session(config)
        self._sessions[session.session_id] = session
        logger.info(f"Created session: {session.session_id}")
        
        return session

    async def resume_session(self, session_id: str):
        """
        Resume an existing session.

        Args:
            session_id: ID of the session to resume

        Returns:
            The resumed CopilotSession
        """
        session = await self._client.resume_session(session_id)
        self._sessions[session_id] = session
        logger.info(f"Resumed session: {session_id}")
        return session

    @property
    def tools(self) -> List[Tool]:
        """Get the list of available tools."""
        return self._tools

    @property
    def client(self) -> CopilotClient:
        """Get the underlying Copilot client."""
        return self._client


def create_agent(
    model: str = "claude-sonnet-4.5",
    log_level: str = "info",
    output_dir: Optional[str | Path] = None,
) -> PatchAgent:
    """
    Factory function to create a PatchAgent.

    Args:
        model: The model to use
        log_level: Logging level for the SDK
        output_dir: Directory for saving scripts, plots, and analysis outputs.
            Does NOT change the process working directory.

    Returns:
        Configured PatchAgent instance
    """
    return PatchAgent(model=model, log_level=log_level, output_dir=output_dir)
