"""
Code Tools - Custom Python code generation and execution.

Enables the agent to design and run custom analysis code for tasks
beyond the built-in tools.

=== SCIENTIFIC RIGOR POLICY ===
All code generated and executed through this module MUST:

1. NEVER generate synthetic data to fill gaps or pass tests
2. NEVER adjust analysis to confirm user hypotheses  
3. ALWAYS include sanity checks for physiological plausibility
4. ALWAYS report all results transparently, including negative findings
5. ALWAYS be reproducible and deterministic

Violations of these principles will cause code execution to fail.
"""

import sys
import re
import io
import traceback
import logging
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
from contextlib import redirect_stdout, redirect_stderr

logger = logging.getLogger(__name__)

# Sandboxed execution namespace with common scientific libraries
SAFE_GLOBALS = {
    "__builtins__": __builtins__,
}

# Libraries to make available in the execution environment
AVAILABLE_LIBRARIES = [
    "numpy",
    "pandas", 
    "scipy",
    "matplotlib",
    "matplotlib.pyplot",
]


# =============================================================================
# SCIENTIFIC RIGOR: Constants and Validation
# =============================================================================

# Physiological bounds for sanity checking (can be customized per preparation)
PHYSIOLOGICAL_BOUNDS = {
    "resting_potential_mV": (-100, -40),       # Typical neuron Vm
    "input_resistance_MOhm": (10, 2000),       # Typical Rm range
    "membrane_tau_ms": (1, 100),                # Membrane time constant
    "spike_threshold_mV": (-60, -20),           # AP threshold
    "spike_amplitude_mV": (40, 140),            # AP amplitude
    "spike_width_ms": (0.1, 5.0),               # AP width at half-max
    "firing_rate_Hz": (0, 500),                 # Max physiological rate
    "series_resistance_MOhm": (1, 100),         # Rs
    "capacitance_pF": (1, 500),                 # Cell capacitance
    "holding_current_pA": (-500, 500),          # Holding current
}

# Patterns that violate scientific rigor - these will BLOCK execution
FORBIDDEN_PATTERNS = [
    # Synthetic data generation
    (r"np\.random\.(rand|randn|random|uniform|normal|choice)\s*\(", 
     "RIGOR VIOLATION: Random/synthetic data generation detected. Use real experimental data only."),
    (r"random\.(random|uniform|gauss|choice)\s*\(",
     "RIGOR VIOLATION: Random data generation detected. Use real experimental data only."),
    (r"fake|dummy|synthetic|simulated",
     "RIGOR VIOLATION: Code references fake/synthetic data. Use real experimental data only."),
    # Result manipulation 
    (r"if.*p.?value.*[<>].*0\.05.*:.*=",
     "RIGOR VIOLATION: Conditional result modification based on p-value detected."),
    (r"result\s*=\s*(expected|hypothesis|target)",
     "RIGOR VIOLATION: Result forced to match expected/hypothesis value."),
    (r"#.*hack|#.*fudge|#.*fake",
     "RIGOR VIOLATION: Code contains suspicious comments suggesting data manipulation."),
]

# Patterns that trigger warnings but don't block execution
WARNING_PATTERNS = [
    (r"np\.random\.seed", "Random seed set - ensure this is for reproducibility, not cherry-picking."),
    (r"outlier.*remove|remove.*outlier", "Outlier removal detected - document criteria and report how many removed."),
    (r"exclude|skip|ignore", "Data exclusion detected - document criteria and report what was excluded."),
    # Reimplementation warnings — prefer built-in tools and IPFX
    (r"find_peaks\s*\(\s*voltage|find_peaks\s*\(\s*v[^a]",
     "WARNING: Using scipy find_peaks on voltage traces. Use the detect_spikes tool or ipfx.spike_detector instead — dV/dt-based detection is more scientifically appropriate."),
    (r"dvdt.*threshold|dv_dt.*threshold|dv\/dt",
     "WARNING: Custom dV/dt threshold code detected. Use the detect_spikes tool or ipfx.spike_detector.detect_putative_spikes instead."),
    (r"def\s+detect.*spike|def\s+find.*spike|def\s+spike.*detect",
     "WARNING: Custom spike detection function detected. Use the detect_spikes tool or ipfx.spike_detector instead."),
    (r"def\s+extract.*spike.*feature|def\s+spike.*feature|def\s+ap_feature",
     "WARNING: Custom spike feature extraction detected. Use extract_spike_features tool or ipfx.feature_extractor.SpikeFeatureExtractor instead."),
    (r"def\s+calc.*input.*resist|def\s+measure.*resist|def\s+compute.*rm",
     "NOTE: Custom input resistance calculation detected. Consider using calculate_input_resistance tool or ipfx.subthresh_features first unless custom fitting is needed."),
    (r"def\s+calc.*tau|def\s+fit.*tau|def\s+membrane.*tau",
     "NOTE: Custom time constant calculation detected. Consider using calculate_time_constant tool or ipfx.subthresh_features first unless a specialized fit (e.g., bi-exponential decay) is needed."),
]


def check_scientific_rigor(code: str) -> Dict[str, Any]:
    """
    Check code for violations of scientific rigor principles.
    
    Args:
        code: Python code to check
        
    Returns:
        Dict with 'passed', 'violations' (blocking), 'warnings' (non-blocking)
    """
    violations = []
    warnings = []
    
    # Check for forbidden patterns (block execution)
    for pattern, message in FORBIDDEN_PATTERNS:
        if re.search(pattern, code, re.IGNORECASE):
            violations.append(message)
    
    # Check for warning patterns (allow but flag)
    for pattern, message in WARNING_PATTERNS:
        if re.search(pattern, code, re.IGNORECASE):
            warnings.append(message)
    
    return {
        "passed": len(violations) == 0,
        "violations": violations,
        "warnings": warnings,
    }


def validate_data_integrity(data, name: str = "data") -> Dict[str, Any]:
    """
    Validate that input data is suitable for analysis.
    
    Checks for:
    - NaN/Inf values
    - Constant values (no variation)
    - Suspicious patterns suggesting synthetic data
    - Reasonable array sizes
    
    Args:
        data: NumPy array or array-like to validate
        name: Name for error messages
        
    Returns:
        Dict with 'valid', 'issues', 'warnings', 'stats'
    """
    import numpy as np
    
    arr = np.asarray(data)
    issues = []
    warnings = []
    
    # Check for NaN
    nan_count = np.sum(np.isnan(arr))
    nan_pct = 100 * nan_count / arr.size if arr.size > 0 else 0
    if nan_count > 0:
        if nan_pct > 50:
            issues.append(f"{name}: {nan_pct:.1f}% NaN values - data may be corrupted")
        else:
            warnings.append(f"{name}: {nan_pct:.1f}% NaN values detected")
    
    # Check for Inf
    inf_count = np.sum(np.isinf(arr))
    if inf_count > 0:
        issues.append(f"{name}: {inf_count} Inf values detected - check amplifier saturation")
    
    # Check for constant data (recording failure)
    clean = arr[np.isfinite(arr)]
    if len(clean) > 0 and np.std(clean) == 0:
        issues.append(f"{name}: Zero variance - possible recording failure or disconnection")
    
    # Check for all zeros
    if np.all(arr == 0):
        issues.append(f"{name}: All zeros - check amplifier connection")
    
    # Check for suspiciously perfect data (possible synthetic)
    if len(clean) > 1000:
        noise_ratio = np.std(np.diff(clean)) / (np.std(clean) + 1e-10)
        if noise_ratio < 0.0001:
            warnings.append(f"{name}: Suspiciously smooth - real recordings typically have noise")
    
    # Compute stats for reporting
    stats = {}
    if len(clean) > 0:
        stats = {
            "min": float(np.min(clean)),
            "max": float(np.max(clean)),
            "mean": float(np.mean(clean)),
            "std": float(np.std(clean)),
            "n_valid": int(len(clean)),
            "n_total": int(arr.size),
        }
    
    return {
        "valid": len(issues) == 0,
        "issues": issues,
        "warnings": warnings,
        "stats": stats,
        "name": name,
    }


def check_physiological_bounds(
    value: float,
    parameter: str,
    custom_bounds: Optional[Tuple[float, float]] = None
) -> Dict[str, Any]:
    """
    Check if a measured value is within physiologically plausible bounds.
    
    Args:
        value: The measured value
        parameter: Name of parameter (key in PHYSIOLOGICAL_BOUNDS)
        custom_bounds: Optional (min, max) to override defaults
        
    Returns:
        Dict with 'valid', 'value', 'bounds', 'warning'
    """
    if custom_bounds:
        bounds = custom_bounds
    elif parameter in PHYSIOLOGICAL_BOUNDS:
        bounds = PHYSIOLOGICAL_BOUNDS[parameter]
    else:
        return {
            "valid": None,
            "value": value,
            "bounds": None,
            "note": f"No bounds defined for '{parameter}'",
        }
    
    is_valid = bounds[0] <= value <= bounds[1]
    result = {
        "valid": is_valid,
        "value": value,
        "bounds": bounds,
    }
    
    if not is_valid:
        result["warning"] = (
            f"Value {value} for '{parameter}' is outside physiological range "
            f"[{bounds[0]}, {bounds[1]}]. This may indicate a recording issue, "
            f"analysis error, or genuinely unusual cell. Investigate before proceeding."
        )
    
    return result


# Sanity check code to inject into user code
SANITY_CHECK_HEADER = '''
# === AUTO-INJECTED SANITY CHECKS (Scientific Rigor) ===
import numpy as np

def _validate_input(arr, name="data"):
    """Validate input array before analysis. Raises on critical issues."""
    if arr is None:
        raise ValueError(f"RIGOR: {name} is None - cannot analyze missing data")
    arr = np.asarray(arr)
    if arr.size == 0:
        raise ValueError(f"RIGOR: {name} is empty - no data to analyze")
    nan_pct = 100 * np.sum(np.isnan(arr)) / arr.size
    if nan_pct > 50:
        raise ValueError(f"RIGOR: {name} is {nan_pct:.0f}% NaN - data is corrupted")
    elif nan_pct > 0:
        print(f"WARNING: {name} contains {nan_pct:.1f}% NaN values")
    if np.all(arr == 0):
        raise ValueError(f"RIGOR: {name} is all zeros - check recording")
    if np.std(arr[np.isfinite(arr)]) == 0:
        raise ValueError(f"RIGOR: {name} has zero variance - recording failure?")
    return arr

def _check_range(value, name, lo, hi):
    """Warn if value is outside expected physiological range."""
    if not (lo <= value <= hi):
        print(f"WARNING: {name}={value:.4g} outside expected range [{lo}, {hi}]")
    return value

# === END SANITY CHECKS ===
'''


# ---------------------------------------------------------------------------
# Module-level output directory (set by the agent / CLI at startup)
# ---------------------------------------------------------------------------
_output_dir: Optional[Path] = None


def set_output_dir(path: "str | Path") -> Path:
    """Set the module-level output directory for code execution.

    This is called by PatchAgent / CLI so that ``execute_code`` can
    inject an ``OUTPUT_DIR`` variable into the sandbox without touching
    ``os.chdir()``.

    Returns the resolved Path.
    """
    global _output_dir
    _output_dir = Path(path).resolve()
    _output_dir.mkdir(parents=True, exist_ok=True)
    return _output_dir


def get_output_dir() -> Optional[Path]:
    """Return the current output directory (may be ``None``)."""
    return _output_dir


def get_execution_environment(output_dir: Optional["str | Path"] = None) -> Dict[str, Any]:
    """
    Build a safe execution environment with scientific libraries.

    Args:
        output_dir: Optional directory path to expose as ``OUTPUT_DIR``
            inside the sandbox.  Falls back to the module-level default
            set via :func:`set_output_dir`.

    Returns:
        Dict of global variables for code execution
    """
    env = SAFE_GLOBALS.copy()

    # Resolve which output directory to expose
    resolved_dir = None
    if output_dir is not None:
        resolved_dir = Path(output_dir).resolve()
    elif _output_dir is not None:
        resolved_dir = _output_dir

    if resolved_dir is not None:
        resolved_dir.mkdir(parents=True, exist_ok=True)
        env["OUTPUT_DIR"] = resolved_dir
        # Also add a convenience Path import
        env["Path"] = Path
    
    # Import common libraries
    try:
        import numpy as np
        env["np"] = np
        env["numpy"] = np
    except ImportError:
        pass
    
    try:
        import pandas as pd
        env["pd"] = pd
        env["pandas"] = pd
    except ImportError:
        pass
    
    try:
        import scipy
        from scipy import signal, stats, optimize
        env["scipy"] = scipy
        env["signal"] = signal
        env["stats"] = stats
        env["optimize"] = optimize
    except ImportError:
        pass
    
    try:
        import matplotlib
        matplotlib.use('Agg')  # Non-interactive backend — no GUI windows
        import matplotlib.pyplot as plt
        # Override plt.show() so agent-generated code never opens a GUI window.
        # Figures are captured as base64 PNGs after execution instead.
        plt.show = lambda *args, **kwargs: None
        plt.ion = lambda *args, **kwargs: None  # prevent interactive mode
        env["plt"] = plt
        env["matplotlib"] = matplotlib
    except ImportError:
        pass
    
    # Import IPFX electrophysiology analysis library
    try:
        import ipfx
        env["ipfx"] = ipfx
    except ImportError:
        pass

    try:
        from ipfx.spike_detector import detect_putative_spikes, find_peak_indexes
        env["detect_putative_spikes"] = detect_putative_spikes
        env["find_peak_indexes"] = find_peak_indexes
    except ImportError:
        pass

    try:
        from ipfx.feature_extractor import (
            SpikeFeatureExtractor,
            SpikeTrainFeatureExtractor,
        )
        env["SpikeFeatureExtractor"] = SpikeFeatureExtractor
        env["SpikeTrainFeatureExtractor"] = SpikeTrainFeatureExtractor
    except ImportError:
        pass

    try:
        from ipfx import subthresh_features as ipfx_subthresh
        env["ipfx_subthresh"] = ipfx_subthresh
    except ImportError:
        pass

    try:
        from ipfx import stimulus_protocol_analysis as ipfx_protocol
        env["ipfx_protocol"] = ipfx_protocol
    except ImportError:
        pass

    try:
        from ipfx import sweep_props as ipfx_sweep_props
        env["ipfx_sweep_props"] = ipfx_sweep_props
    except ImportError:
        pass

    # Import patch_agent tools and utilities
    try:
        from ..loadFile import loadFile, loadABF, loadNWB, NWBRecording
        env["loadFile"] = loadFile
        env["loadABF"] = loadABF
        env["loadNWB"] = loadNWB
        env["NWBRecording"] = NWBRecording
    except ImportError:
        pass
    
    try:
        from ..utils.data_resolver import resolve_data, DataResolver
        env["resolve_data"] = resolve_data
        env["DataResolver"] = DataResolver
    except ImportError:
        pass
    
    return env


def _save_script(code: str, output_dir: Optional["str | Path"] = None) -> Optional[Path]:
    """Save executed code to ``OUTPUT_DIR/scripts/`` for reproducibility.

    The filename is ``script_<YYYYMMDD_HHMMSS>_<hash>.py`` so multiple
    executions within the same second don't collide.  Returns the saved
    path, or ``None`` if there is nowhere to save.
    """
    target_dir: Optional[Path] = None
    if output_dir is not None:
        target_dir = Path(output_dir).resolve()
    elif _output_dir is not None:
        target_dir = _output_dir

    if target_dir is None:
        return None

    scripts_dir = target_dir / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    short_hash = hashlib.md5(code.encode()).hexdigest()[:6]
    dest = scripts_dir / f"script_{stamp}_{short_hash}.py"
    dest.write_text(code, encoding="utf-8")
    logger.debug("Saved script to %s", dest)
    return dest


def execute_code(
    code: str,
    context: Optional[Dict[str, Any]] = None,
    timeout: Optional[float] = 30.0,
    enforce_rigor: bool = True,
    inject_sanity_checks: bool = True,
    output_dir: Optional["str | Path"] = None,
) -> Dict[str, Any]:
    """
    Execute custom Python code in a controlled environment.

    The sandbox exposes an ``OUTPUT_DIR`` (:class:`~pathlib.Path`) variable
    pointing to the agent's output directory.  Generated code should save
    plots and files there (e.g. ``fig.savefig(OUTPUT_DIR / "plot.png")``).
    The executed script is also auto-saved to ``OUTPUT_DIR/scripts/``.

    SCIENTIFIC RIGOR: This function enforces research integrity by:
    - Blocking code with forbidden patterns (synthetic data, result manipulation)
    - Validating input data integrity  
    - Optionally injecting sanity check functions

    Args:
        code: Python code to execute
        context: Optional dict of variables to inject into namespace
        timeout: Maximum execution time in seconds (not enforced in basic impl)
        enforce_rigor: If True, check for scientific rigor violations (recommended)
        inject_sanity_checks: If True, prepend validation functions to code

    Returns:
        Dict containing:
            - success: Whether execution completed without error
            - output: Captured stdout
            - error: Error message if failed
            - result: Last expression value (if any)
            - variables: Dict of variables created/modified
            - rigor_warnings: Any scientific rigor warnings
    """
    rigor_warnings = []
    
    # RIGOR CHECK: Scan for forbidden patterns
    if enforce_rigor:
        rigor_check = check_scientific_rigor(code)
        if not rigor_check["passed"]:
            return {
                "success": False,
                "output": "",
                "error": "SCIENTIFIC RIGOR VIOLATION - Code blocked:\n" + "\n".join(rigor_check["violations"]),
                "result": None,
                "variables": {},
                "figures": [],
                "rigor_warnings": rigor_check["violations"],
            }
        rigor_warnings.extend(rigor_check["warnings"])
    
    # RIGOR CHECK: Validate input data
    if context:
        import numpy as np
        for key, value in context.items():
            if isinstance(value, np.ndarray):
                integrity = validate_data_integrity(value, key)
                if not integrity["valid"]:
                    return {
                        "success": False,
                        "output": "",
                        "error": "DATA INTEGRITY ISSUE - Analysis blocked:\n" + "\n".join(integrity["issues"]),
                        "result": None,
                        "variables": {},
                        "figures": [],
                        "rigor_warnings": integrity["issues"],
                    }
                rigor_warnings.extend(integrity["warnings"])
    
    # Inject sanity check functions
    if inject_sanity_checks:
        code = SANITY_CHECK_HEADER + code
    
    # Build execution environment (with OUTPUT_DIR injected)
    exec_globals = get_execution_environment(output_dir=output_dir)
    exec_locals = {}

    # Auto-save the script for reproducibility
    _save_script(code, output_dir)
    
    # Inject context variables
    if context:
        exec_locals.update(context)
    
    # Capture output
    stdout_capture = io.StringIO()
    stderr_capture = io.StringIO()
    
    result = {
        "success": False,
        "output": "",
        "error": None,
        "result": None,
        "variables": {},
        "figures": [],
        "rigor_warnings": rigor_warnings if rigor_warnings else None,
    }
    
    try:
        with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
            # Execute the code
            exec(code, exec_globals, exec_locals)
        
        result["success"] = True
        result["output"] = stdout_capture.getvalue()
        
        # Capture any stderr (warnings, etc.)
        stderr_output = stderr_capture.getvalue()
        if stderr_output:
            result["output"] += f"\n[stderr]: {stderr_output}"
        
        # Extract user-defined variables (exclude modules and builtins)
        import types
        import numpy as np
        
        for name, value in exec_locals.items():
            if name.startswith("_"):
                continue
            if isinstance(value, types.ModuleType):
                continue
            
            # Serialize the value appropriately
            if isinstance(value, np.ndarray):
                if value.size <= 100:
                    result["variables"][name] = value.tolist()
                else:
                    result["variables"][name] = f"<ndarray shape={value.shape} dtype={value.dtype}>"
            elif isinstance(value, (int, float, str, bool, list, dict)):
                result["variables"][name] = value
            else:
                result["variables"][name] = str(type(value))
        
        # Check for matplotlib figures and capture as base64 PNGs
        try:
            import matplotlib
            matplotlib.use('Agg')  # ensure non-interactive
            import matplotlib.pyplot as plt
            open_figs = plt.get_fignums()
            if open_figs:
                import base64
                logger.debug("Capturing %d matplotlib figure(s)", len(open_figs))
                figures_data = []
                for fig_num in open_figs:
                    fig = plt.figure(fig_num)
                    buf = io.BytesIO()
                    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
                    buf.seek(0)
                    fig_data = {
                        "figure_number": fig_num,
                        "image_base64": base64.b64encode(buf.read()).decode("utf-8"),
                        "format": "png",
                    }
                    figures_data.append(fig_data)
                    buf.close()
                    
                    # Push figure to websocket queue for real-time display
                    try:
                        from patch_agent.web.figure_queue import (
                            push_figure_to_current_session
                        )
                        push_figure_to_current_session(fig_data)
                    except ImportError:
                        pass  # Web module not available (CLI mode)
                    except Exception as q_err:
                        logger.debug("Failed to push figure to queue: %s", q_err)
                
                plt.close("all")
                result["figures"] = figures_data
                logger.debug("Captured %d figure(s) as base64 PNG", len(figures_data))
        except Exception as fig_err:
            logger.warning("Failed to capture matplotlib figures: %s", fig_err)
            
    except Exception as e:
        result["error"] = f"{type(e).__name__}: {str(e)}\n{traceback.format_exc()}"
        result["output"] = stdout_capture.getvalue()
    
    return result


def generate_analysis_code(
    task_description: str,
    data_info: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Generate Python code for a custom analysis task.
    
    This is a template/helper - the actual code generation is done by the LLM.
    This function provides structure and examples.

    Args:
        task_description: Description of the analysis to perform
        data_info: Information about available data (shapes, types, etc.)

    Returns:
        Dict containing:
            - template: Code template/skeleton
            - available_functions: List of available helper functions
            - examples: Relevant code examples
    """
    template = '''"""
Custom Analysis: {task}
Generated for patch-clamp data analysis
"""

import numpy as np
from scipy import signal, stats

# Data is available as:
# - dataX: time array (n_sweeps, n_samples) in seconds
# - dataY: voltage array (mV) or current array (pA)
# - dataC: command/stimulus array

# Your analysis code here:

# Example: Calculate something for each sweep
results = []
for sweep_idx in range(dataY.shape[0]):
    voltage = dataY[sweep_idx]
    time = dataX[sweep_idx]
    current = dataC[sweep_idx]
    
    # Your per-sweep analysis...
    result = np.mean(voltage)  # Example
    results.append(result)

# Store final results
analysis_result = {{
    "per_sweep": results,
    "mean": np.mean(results),
    "std": np.std(results),
}}

print(f"Analysis complete: {{analysis_result}}")
'''.format(task=task_description)

    available_functions = [
        "loadFile(path) - Load ABF/NWB file, returns (dataX, dataY, dataC)",
        "loadFile(path, return_obj=True) - Also returns NWBRecording/pyabf obj",
        "loadFile(path, protocol_filter=['Long Square']) - Filter NWB sweeps by protocol",
        "loadFile(path, clamp_mode_filter='CC') - Filter NWB sweeps by clamp mode",
        "resolve_data(data) - Flexible data loading with caching",
        "np.* - Full NumPy library",
        "scipy.signal.* - Signal processing (filters, peaks, etc.)",
        "scipy.stats.* - Statistical functions",
        "scipy.optimize.* - Curve fitting and optimization",
        "pd.DataFrame() - Pandas for tabular data",
        "plt.* - Matplotlib for plotting",
    ]
    
    examples = {
        "filter_data": '''
# Apply a lowpass Bessel filter
from scipy.signal import bessel, filtfilt
b, a = bessel(4, 1000, btype='low', fs=sample_rate)
filtered = filtfilt(b, a, voltage)
''',
        "find_peaks": '''
# Find peaks in a trace
from scipy.signal import find_peaks
peaks, properties = find_peaks(voltage, height=-20, prominence=10)
peak_times = time[peaks]
peak_heights = voltage[peaks]
''',
        "exponential_fit": '''
# Fit exponential decay
from scipy.optimize import curve_fit

def exp_decay(t, amp, tau, offset):
    return amp * np.exp(-t / tau) + offset

popt, pcov = curve_fit(exp_decay, time, voltage, p0=[10, 0.02, -70])
amplitude, tau, offset = popt
''',
        "baseline_subtraction": '''
# Baseline subtraction
baseline_idx = time < 0.1  # First 100ms
baseline = np.mean(voltage[baseline_idx])
voltage_subtracted = voltage - baseline
''',
        "area_under_curve": '''
# Calculate area under curve (e.g., for charge transfer)
from scipy.integrate import trapezoid
area = trapezoid(current, time)  # pA * s = pC
''',
        "cross_correlation": '''
# Cross-correlation between two signals
from scipy.signal import correlate
correlation = correlate(signal1, signal2, mode='full')
lags = np.arange(-len(signal1)+1, len(signal2))
''',
    }
    
    return {
        "template": template,
        "available_functions": available_functions,
        "examples": examples,
        "data_info": data_info,
    }


def validate_code(code: str) -> Dict[str, Any]:
    """
    Validate Python code without executing it.
    
    Checks for syntax errors and potentially dangerous operations.

    Args:
        code: Python code to validate

    Returns:
        Dict containing:
            - valid: Whether code is syntactically valid
            - errors: List of syntax errors
            - warnings: List of potential issues
    """
    import ast
    
    result = {
        "valid": False,
        "errors": [],
        "warnings": [],
    }
    
    # Check syntax
    try:
        tree = ast.parse(code)
        result["valid"] = True
    except SyntaxError as e:
        result["errors"].append(f"Syntax error at line {e.lineno}: {e.msg}")
        return result
    
    # Check for potentially problematic operations
    dangerous_calls = ["eval", "exec", "compile", "__import__", "open", "os.system"]
    dangerous_attrs = ["__class__", "__bases__", "__subclasses__"]
    
    for node in ast.walk(tree):
        # Check function calls
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                if node.func.id in dangerous_calls:
                    result["warnings"].append(
                        f"Potentially dangerous call: {node.func.id}()"
                    )
        
        # Check attribute access
        if isinstance(node, ast.Attribute):
            if node.attr in dangerous_attrs:
                result["warnings"].append(
                    f"Accessing special attribute: {node.attr}"
                )
    
    return result


def run_custom_analysis(
    code: str,
    file_path: Optional[str] = None,
    data: Optional[Dict[str, Any]] = None,
    validate_first: bool = True,
) -> Dict[str, Any]:
    """
    Run custom analysis code with data loading.

    This is the main entry point for custom code execution.

    Args:
        code: Python code to execute
        file_path: Optional path to data file to load
        data: Optional pre-loaded data dict
        validate_first: Whether to validate code before running

    Returns:
        Dict containing execution results
    """
    # Validate first if requested
    if validate_first:
        validation = validate_code(code)
        if not validation["valid"]:
            return {
                "success": False,
                "error": f"Code validation failed: {validation['errors']}",
                "validation": validation,
            }
        if validation["warnings"]:
            logger.warning(f"Code warnings: {validation['warnings']}")
    
    # Prepare context with data
    context = {}
    
    if file_path:
        try:
            from ..loadFile import loadFile
            dataX, dataY, dataC = loadFile(file_path)
            context["dataX"] = dataX
            context["dataY"] = dataY
            context["dataC"] = dataC
            context["file_path"] = file_path
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to load data: {e}",
            }
    
    if data:
        context.update(data)
    
    # Execute the code
    result = execute_code(code, context=context)
    
    return result


# Code snippets library for common operations
CODE_SNIPPETS = {
    "detect_events": '''
def detect_events(trace, threshold, min_distance=10):
    """Detect threshold crossings in a trace."""
    above = trace > threshold
    crossings = np.where(np.diff(above.astype(int)) == 1)[0]
    
    # Filter by minimum distance
    if len(crossings) > 1:
        keep = [crossings[0]]
        for c in crossings[1:]:
            if c - keep[-1] >= min_distance:
                keep.append(c)
        crossings = np.array(keep)
    
    return crossings
''',
    
    "calculate_derivative": '''
def calculate_derivative(voltage, time):
    """Calculate dV/dt from voltage trace."""
    dt = np.mean(np.diff(time))
    dvdt = np.gradient(voltage, dt)
    return dvdt  # mV/s, divide by 1000 for mV/ms
''',
    
    "align_to_event": '''
def align_to_event(traces, event_indices, window_before=100, window_after=200):
    """Align traces to detected events."""
    aligned = []
    for trace, events in zip(traces, event_indices):
        for ev in events:
            start = ev - window_before
            end = ev + window_after
            if start >= 0 and end < len(trace):
                aligned.append(trace[start:end])
    return np.array(aligned)
''',
    
    "measure_rise_time": '''
def measure_rise_time(trace, time, baseline_end, peak_time, pct_low=10, pct_high=90):
    """Measure 10-90% rise time."""
    baseline = np.mean(trace[time < baseline_end])
    peak_idx = np.argmin(np.abs(time - peak_time))
    peak_val = trace[peak_idx]
    
    amplitude = peak_val - baseline
    thresh_low = baseline + amplitude * (pct_low / 100)
    thresh_high = baseline + amplitude * (pct_high / 100)
    
    # Find crossing times
    rising = trace[:peak_idx]
    t_low = time[np.where(rising > thresh_low)[0][0]]
    t_high = time[np.where(rising > thresh_high)[0][0]]
    
    return t_high - t_low
''',

    "spectral_analysis": '''
def spectral_analysis(trace, sample_rate):
    """Compute power spectral density."""
    from scipy.signal import welch
    freqs, psd = welch(trace, fs=sample_rate, nperseg=1024)
    return freqs, psd
''',
}


def get_code_snippet(name: str) -> Optional[str]:
    """Get a code snippet by name."""
    return CODE_SNIPPETS.get(name)


def list_code_snippets() -> List[str]:
    """List available code snippets."""
    return list(CODE_SNIPPETS.keys())
