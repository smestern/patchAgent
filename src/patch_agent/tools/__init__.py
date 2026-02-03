"""
Tools module for patchAgent.

Provides electrophysiology analysis tools that can be used with the Copilot SDK.
"""

from .io_tools import (
    load_file,
    get_file_metadata,
    get_sweep_data,
    list_sweeps,
)
from .spike_tools import (
    detect_spikes,
    extract_spike_features,
    extract_spike_train_features,
)
from .passive_tools import (
    calculate_input_resistance,
    calculate_time_constant,
    calculate_sag,
    calculate_resting_potential,
)
from .qc_tools import (
    run_sweep_qc,
    check_baseline_stability,
    measure_noise,
)
from .fitting_tools import (
    fit_exponential,
    fit_iv_curve,
    fit_fi_curve,
)
from .code_tools import (
    execute_code,
    run_custom_analysis,
    generate_analysis_code,
    validate_code,
    get_code_snippet,
    list_code_snippets,
    # Scientific rigor functions
    check_scientific_rigor,
    validate_data_integrity,
    check_physiological_bounds,
    PHYSIOLOGICAL_BOUNDS,
)


def get_all_tools():
    """
    Get all available tools as a list of tool definitions.
    
    Returns:
        List of tool definition dicts for use with Copilot SDK
    """
    # TODO: Convert to proper Copilot SDK tool definitions
    # For now, return a list of function references
    return [
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
        generate_analysis_code,
        validate_code,
        get_code_snippet,
        list_code_snippets,
        # Scientific rigor tools
        check_scientific_rigor,
        validate_data_integrity,
        check_physiological_bounds,
    ]


__all__ = [
    # I/O
    "load_file",
    "get_file_metadata",
    "get_sweep_data",
    "list_sweeps",
    # Spike
    "detect_spikes",
    "extract_spike_features",
    "extract_spike_train_features",
    # Passive
    "calculate_input_resistance",
    "calculate_time_constant",
    "calculate_sag",
    "calculate_resting_potential",
    # QC
    "run_sweep_qc",
    "check_baseline_stability",
    "measure_noise",
    # Fitting
    "fit_exponential",
    "fit_iv_curve",
    "fit_fi_curve",
    # Code
    "execute_code",
    "run_custom_analysis",
    "generate_analysis_code",
    "validate_code",
    "get_code_snippet",
    "list_code_snippets",
    # Scientific rigor
    "check_scientific_rigor",
    "validate_data_integrity",
    "check_physiological_bounds",
    "PHYSIOLOGICAL_BOUNDS",
    # Meta
    "get_all_tools",
]
    "list_code_snippets",
    # Meta
    "get_all_tools",
]
