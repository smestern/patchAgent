"""
patchAgent — Domain agent for patch-clamp electrophysiology.

Thin subclass of ``sciagent.BaseScientificAgent`` that registers
electrophysiology-specific tools and system prompts.
"""

import logging
from pathlib import Path
from typing import Optional, List

from sciagent import BaseScientificAgent
from sciagent.config import AgentConfig

from patch_agent.config import PATCH_CONFIG

logger = logging.getLogger(__name__)


class PatchAgent(BaseScientificAgent):
    """
    Patch-clamp analysis agent.

    Inherits all generic infrastructure (session lifecycle, code sandbox,
    guardrails) from ``BaseScientificAgent`` and adds electrophysiology-
    specific tools, loaders, and expertise.

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
        config: Optional[AgentConfig] = None,
        model: str = "claude-sonnet-4.5",
        log_level: str = "info",
        output_dir: Optional[str | Path] = None,
    ):
        cfg = config or PATCH_CONFIG
        super().__init__(config=cfg, model=model, log_level=log_level, output_dir=output_dir)

    # ── Tools ───────────────────────────────────────────────────────

    def _load_tools(self) -> list:
        """Load base tools + electrophysiology-specific tools."""
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
            # Code tools (from sciagent, re-exported by patch_agent.tools)
            execute_code,
            run_custom_analysis,
            validate_code,
            # Rigor tools
            check_scientific_rigor,
            validate_data_integrity,
            check_physiological_bounds,
        )

        tools = [
            # === I/O Tools ===
            self._create_tool(
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
            self._create_tool(
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
            self._create_tool(
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
            self._create_tool(
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
            self._create_tool(
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
            self._create_tool(
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
            self._create_tool(
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
            self._create_tool(
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
            self._create_tool(
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
            self._create_tool(
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
            self._create_tool(
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
            self._create_tool(
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
            self._create_tool(
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
            self._create_tool(
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
            self._create_tool(
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
            self._create_tool(
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
            self._create_tool(
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
            self._create_tool(
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
            self._create_tool(
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
            self._create_tool(
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
            self._create_tool(
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
            self._create_tool(
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
            self._create_tool(
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

        logger.info("Loaded %d tools", len(tools))
        return tools

    # ── System message ──────────────────────────────────────────────

    def _get_system_message(self) -> str:
        """Get the patch-clamp-specific system message."""
        from .prompts.system_messages import PATCH_ANALYST_SYSTEM_MESSAGE
        return PATCH_ANALYST_SYSTEM_MESSAGE

    # ── Execution environment ───────────────────────────────────────

    def _get_execution_environment(self) -> dict:
        """Provide patch-clamp libraries to the code sandbox."""
        env = {}
        try:
            from patch_agent.loadFile import loadFile
            env["loadFile"] = loadFile
        except ImportError:
            pass
        try:
            import ipfx
            env["ipfx"] = ipfx
        except ImportError:
            pass
        try:
            import pyabf
            env["pyabf"] = pyabf
        except ImportError:
            pass
        return env

    def _get_script_imports(self) -> list[str]:
        """Return domain-specific imports for the reproducible script."""
        return ["pyabf", "ipfx", "numpy", "scipy", "matplotlib", "pandas"]


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

    Returns:
        Configured PatchAgent instance
    """
    return PatchAgent(model=model, log_level=log_level, output_dir=output_dir)
