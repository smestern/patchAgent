"""
I/O Tools - File loading and data access tools.

These tools wrap the vendored loadFile module and provide flexible data access.
"""

from typing import Union, Dict, Any, List, Optional
from pathlib import Path
import numpy as np


def load_file(
    file_path: str,
    return_metadata: bool = False,
) -> Dict[str, Any]:
    """
    Load an electrophysiology file (ABF or NWB).

    Args:
        file_path: Path to the file (.abf or .nwb)
        return_metadata: Whether to include file metadata in response

    Returns:
        Dict containing:
            - dataX: Time array (seconds), shape (n_sweeps, n_samples)
            - dataY: Response array (mV or pA), shape (n_sweeps, n_samples)
            - dataC: Command array (pA or mV), shape (n_sweeps, n_samples)
            - metadata: File metadata (if return_metadata=True)
    """
    from ..utils.data_resolver import resolve_data

    dataX, dataY, dataC, obj = resolve_data(file_path, return_obj=True)

    result = {
        "dataX": dataX,
        "dataY": dataY,
        "dataC": dataC,
        "n_sweeps": dataY.shape[0] if dataY.ndim > 1 else 1,
        "n_samples": dataY.shape[-1],
    }

    if return_metadata and obj is not None:
        result["metadata"] = get_file_metadata(file_path)

    return result


def get_file_metadata(file_path: str) -> Dict[str, Any]:
    """
    Get metadata from an electrophysiology file.

    Args:
        file_path: Path to the file (.abf or .nwb)

    Returns:
        Dict containing file metadata:
            - file_type: 'abf' or 'nwb'
            - sweep_count: Number of sweeps
            - sample_rate: Sampling rate in Hz
            - protocol: Protocol name (if available)
            - sweep_length_sec: Length of each sweep in seconds
            - channel_count: Number of channels
            - units: Dict with response and command units
    """
    import pyabf

    if file_path.endswith(".abf"):
        abf = pyabf.ABF(file_path, loadData=False)
        return {
            "file_type": "abf",
            "file_id": abf.abfID,
            "sweep_count": abf.sweepCount,
            "sample_rate": abf.dataRate,
            "protocol": abf.protocol,
            "sweep_length_sec": abf.sweepLengthSec,
            "channel_count": abf.channelCount,
            "units": {
                "response": abf.sweepLabelY,
                "command": abf.sweepLabelC,
                "time": abf.sweepLabelX,
            },
            "clamp_mode": _infer_clamp_mode(abf.sweepLabelY),
        }
    elif file_path.endswith(".nwb"):
        # NWB metadata extraction
        from ..loadFile import loadNWB

        _, _, _, nwb = loadNWB(file_path, return_obj=True)
        return {
            "file_type": "nwb",
            "sweep_count": nwb.sweepCount,
            "sample_rate": nwb.rate.get("rate", None),
            "protocol": getattr(nwb, "protocol", "unknown"),
            "clamp_mode": getattr(nwb, "clamp_mode", "unknown"),
            "sweep_length_sec": (
                float(nwb.dataX[0, -1]) if nwb.dataX.size > 0 else None
            ),
            "protocols": getattr(nwb, "protocols", []),
            "units": {
                "response": nwb.sweepYVars if isinstance(nwb.sweepYVars, dict) else {},
                "command": nwb.sweepCVars if isinstance(nwb.sweepCVars, dict) else {},
            },
            "session_description": getattr(nwb, "session_description", ""),
            "electrode_info": getattr(nwb, "electrode_info", {}),
        }
    else:
        raise ValueError(f"Unsupported file type: {file_path}")


def get_sweep_data(
    data: Union[str, Dict[str, Any]],
    sweep_number: int,
    channel: int = 0,
) -> Dict[str, np.ndarray]:
    """
    Get data for a specific sweep.

    Args:
        data: File path or pre-loaded data dict
        sweep_number: Sweep index (0-based)
        channel: Channel number (default 0)

    Returns:
        Dict containing:
            - time: Time array for this sweep
            - voltage: Voltage/response array
            - current: Current/command array
    """
    from ..utils.data_resolver import resolve_data

    # Resolve data if needed
    if isinstance(data, str):
        dataX, dataY, dataC, _ = resolve_data(data)
    elif isinstance(data, dict):
        dataX = data["dataX"]
        dataY = data["dataY"]
        dataC = data["dataC"]
    else:
        raise TypeError(f"Unsupported data type: {type(data)}")

    # Handle single sweep case
    if dataY.ndim == 1:
        if sweep_number != 0:
            raise IndexError(f"Only sweep 0 available, requested {sweep_number}")
        return {
            "time": dataX,
            "voltage": dataY,
            "current": dataC,
            "sweep_number": 0,
        }

    # Multi-sweep case
    n_sweeps = dataY.shape[0]
    if sweep_number < 0 or sweep_number >= n_sweeps:
        raise IndexError(f"Sweep {sweep_number} out of range [0, {n_sweeps})")

    return {
        "time": dataX[sweep_number],
        "voltage": dataY[sweep_number],
        "current": dataC[sweep_number],
        "sweep_number": sweep_number,
    }


def list_sweeps(
    data: Union[str, Dict[str, Any]],
) -> Dict[str, Any]:
    """
    List available sweeps and their basic properties.

    Args:
        data: File path or pre-loaded data dict

    Returns:
        Dict containing:
            - sweep_count: Number of sweeps
            - sweep_indices: List of sweep indices
            - sweep_info: List of dicts with per-sweep info
    """
    from ..utils.data_resolver import resolve_data

    # Resolve data if needed
    if isinstance(data, str):
        dataX, dataY, dataC, _ = resolve_data(data)
    elif isinstance(data, dict):
        dataX = data["dataX"]
        dataY = data["dataY"]
        dataC = data["dataC"]
    else:
        raise TypeError(f"Unsupported data type: {type(data)}")

    # Handle single sweep
    if dataY.ndim == 1:
        return {
            "sweep_count": 1,
            "sweep_indices": [0],
            "sweep_info": [
                {
                    "index": 0,
                    "duration_sec": dataX[-1] - dataX[0],
                    "stim_amplitude": float(np.max(np.abs(dataC))),
                }
            ],
        }

    # Multi-sweep
    n_sweeps = dataY.shape[0]
    sweep_info = []
    
    for i in range(n_sweeps):
        info = {
            "index": i,
            "duration_sec": float(dataX[i, -1] - dataX[i, 0]),
            "stim_amplitude": float(np.max(np.abs(dataC[i]))),
        }
        sweep_info.append(info)

    return {
        "sweep_count": n_sweeps,
        "sweep_indices": list(range(n_sweeps)),
        "sweep_info": sweep_info,
    }


def list_ephys_files(
    directory: Optional[str] = None,
    recursive: bool = False,
    file_type: Optional[str] = None,
) -> Dict[str, Any]:
    """
    List electrophysiology files (.abf, .nwb) in a directory.

    Args:
        directory: Directory to search. Defaults to the current working directory.
        recursive: If True, search subdirectories recursively.
        file_type: Filter by file type: 'abf', 'nwb', or None for both.

    Returns:
        Dict containing:
            - directory: The directory that was searched
            - files: List of dicts with 'name', 'path', and 'type' for each file
            - total: Total number of files found
    """
    target = Path(directory).expanduser().resolve() if directory else Path.cwd()

    if not target.is_dir():
        raise FileNotFoundError(f"Directory not found: {target}")

    extensions = []
    if file_type is None or file_type.lower() == "abf":
        extensions.append("*.abf")
    if file_type is None or file_type.lower() == "nwb":
        extensions.append("*.nwb")

    files = []
    for ext in extensions:
        pattern = f"**/{ext}" if recursive else ext
        for p in sorted(target.glob(pattern)):
            files.append({
                "name": p.name,
                "path": str(p),
                "type": p.suffix.lstrip("."),
            })

    return {
        "directory": str(target),
        "files": files,
        "total": len(files),
    }


def _infer_clamp_mode(sweep_label_y: str) -> str:
    """Infer clamp mode from sweep label."""
    label_lower = sweep_label_y.lower()
    if "mv" in label_lower or "voltage" in label_lower:
        return "current_clamp"
    elif "pa" in label_lower or "current" in label_lower:
        return "voltage_clamp"
    else:
        return "unknown"
