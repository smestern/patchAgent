"""
Data Resolver — Electrophysiology-specific data resolution.

Subclass of ``sciagent.data.resolver.BaseDataResolver`` that registers
ABF and NWB file loaders and provides ephys-specific shape conventions
(``dataX``, ``dataY``, ``dataC``).

The resolver can accept:
- File paths (str) → loads via loadFile
- Numpy arrays → passes through (assumed voltage, 10 kHz)
- Lists of files → batch loads
- Dict with data arrays → extracts arrays
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np

from sciagent.data.resolver import BaseDataResolver  # noqa: F401 — also re-export

from ..constants import DEFAULT_SAMPLE_RATE_HZ

logger = logging.getLogger(__name__)


class DataResolver(BaseDataResolver):
    """Resolve various input formats to (dataX, dataY, dataC) arrays.

    Inherits caching and dispatch infrastructure from ``BaseDataResolver``
    and adds electrophysiology-specific loaders and shape conventions.
    """

    def __init__(
        self,
        use_cache: bool = True,
        max_cache_size: int = 50,
    ):
        super().__init__(
            use_cache=use_cache,
            max_cache_size=max_cache_size,
            default_sample_rate=DEFAULT_SAMPLE_RATE_HZ,
        )
        # Register ABF and NWB formats
        self.register_format(".abf", self._load_ephys_file)
        self.register_format(".nwb", self._load_ephys_file)

    # ── Format loaders ──────────────────────────────────────────────

    def _load_ephys_file(
        self,
        file_path: str,
        return_obj: bool = False,
        **kwargs,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray, Optional[Any]]:
        """Load an ABF or NWB file via ``patchagent.loadFile``."""
        from ..loadFile import loadFile

        result = loadFile(file_path, return_obj=True, **kwargs)

        if len(result) == 4:
            dataX, dataY, dataC, obj = result
        else:
            dataX, dataY, dataC = result
            obj = None

        if return_obj:
            return dataX, dataY, dataC, obj
        return dataX, dataY, dataC, None

    # ── Override: array resolution with ephys assumptions ───────────

    def _resolve_array(
        self,
        arr: np.ndarray,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray, None]:
        """Resolve a single numpy array (assumed voltage data)."""
        dataY = arr

        # Generate time array assuming default sample rate (10 kHz)
        if dataY.ndim == 1:
            n_samples = dataY.shape[0]
            dataX = np.arange(n_samples) / self.default_sample_rate
            dataC = np.zeros_like(dataY)
            # Reshape to (1, n_samples) for consistency
            dataX = dataX.reshape(1, -1)
            dataY = dataY.reshape(1, -1)
            dataC = dataC.reshape(1, -1)
        else:
            n_sweeps, n_samples = dataY.shape
            dataX = np.tile(
                np.arange(n_samples) / self.default_sample_rate,
                (n_sweeps, 1),
            )
            dataC = np.zeros_like(dataY)

        logger.warning(
            "Numpy array provided without time/stim — assuming %g Hz, zero stim",
            self.default_sample_rate,
        )
        return dataX, dataY, dataC, None

    def _resolve_array_list(
        self,
        arrays: List[np.ndarray],
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray, None]:
        """Resolve a list of numpy arrays."""
        if len(arrays) == 1:
            return self._resolve_array(arrays[0])
        elif len(arrays) == 2:
            # Assume [dataX, dataY]
            dataX, dataY = arrays[0], arrays[1]
            dataC = np.zeros_like(dataY)
            return dataX, dataY, dataC, None
        elif len(arrays) >= 3:
            return arrays[0], arrays[1], arrays[2], None
        else:
            raise ValueError("Invalid array list")

    def _resolve_dict(
        self,
        data: Dict[str, Any],
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray, None]:
        """Resolve a dictionary with data arrays."""
        if "dataY" not in data:
            raise ValueError("Dict must contain 'dataY' key")

        dataY = np.asarray(data["dataY"])

        if "dataX" in data:
            dataX = np.asarray(data["dataX"])
        else:
            if dataY.ndim == 1:
                dataX = np.arange(dataY.shape[0]) / self.default_sample_rate
            else:
                n_sweeps, n_samples = dataY.shape
                dataX = np.tile(
                    np.arange(n_samples) / self.default_sample_rate,
                    (n_sweeps, 1),
                )

        if "dataC" in data:
            dataC = np.asarray(data["dataC"])
        else:
            dataC = np.zeros_like(dataY)

        return dataX, dataY, dataC, None


# ── Convenience function ────────────────────────────────────────────────

def resolve_data(
    data: Union[str, Path, np.ndarray, List, Dict[str, Any]],
    return_obj: bool = False,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, Optional[Any]]:
    """Convenience function to resolve data without creating a DataResolver instance.

    Args:
        data: Input data in various formats.
        return_obj: Whether to return the file object.

    Returns:
        Tuple of (dataX, dataY, dataC, file_obj or None).
    """
    resolver = DataResolver()
    return resolver.resolve(data, return_obj=return_obj)
