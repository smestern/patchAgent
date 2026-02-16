"""
Tools module for patchAgent.

Provides electrophysiology analysis tools that can be used with the Copilot SDK.
"""

from .io_tools import (
    load_file,
    get_file_metadata,
    get_sweep_data,
    list_sweeps,
    list_ephys_files,
    list_protocols,
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
    validate_nwb,
)
from .fitting_tools import (
    fit_exponential,
    fit_double_exponential,
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
    set_output_dir,
    get_output_dir,
    # Scientific rigor functions
    check_scientific_rigor,
    validate_data_integrity,
    check_physiological_bounds,
    PHYSIOLOGICAL_BOUNDS,
)


__all__ = [
    # I/O
    "load_file",
    "get_file_metadata",
    "get_sweep_data",
    "list_sweeps",
    "list_ephys_files",
    "list_protocols",
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
    "validate_nwb",
    # Fitting
    "fit_exponential",
    "fit_double_exponential",
    "fit_iv_curve",
    "fit_fi_curve",
    # Code
    "execute_code",
    "run_custom_analysis",
    "generate_analysis_code",
    "validate_code",
    "get_code_snippet",
    "list_code_snippets",
    "set_output_dir",
    "get_output_dir",
    # Scientific rigor
    "check_scientific_rigor",
    "validate_data_integrity",
    "check_physiological_bounds",
    "PHYSIOLOGICAL_BOUNDS",
]
