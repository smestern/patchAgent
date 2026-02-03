"""
Data Resolver - Handles flexible input types and caching for electrophysiology data.

The resolver can accept:
- File paths (str) → loads via loadFile
- Numpy arrays → passes through
- Lists of files → batch loads
- Dict with data arrays → extracts arrays
"""

import logging
from pathlib import Path
from typing import Union, Tuple, Dict, Any, List, Optional
import numpy as np

logger = logging.getLogger(__name__)

# Simple in-memory cache for loaded files
_FILE_CACHE: Dict[str, Tuple[np.ndarray, np.ndarray, np.ndarray, Any]] = {}


class DataResolver:
    """
    Resolves various input formats to standardized (dataX, dataY, dataC) arrays.
    
    Supports caching to avoid re-reading files.
    """

    def __init__(self, use_cache: bool = True, max_cache_size: int = 50):
        """
        Initialize the DataResolver.

        Args:
            use_cache: Whether to cache loaded files
            max_cache_size: Maximum number of files to keep in cache
        """
        self.use_cache = use_cache
        self.max_cache_size = max_cache_size

    def resolve(
        self,
        data: Union[str, Path, np.ndarray, List, Dict[str, Any]],
        return_obj: bool = False,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray, Optional[Any]]:
        """
        Resolve input data to standardized arrays.

        Args:
            data: Input data in various formats:
                - str/Path: File path to load
                - np.ndarray: Assumes this is dataY, generates placeholder dataX/dataC
                - List[str]: List of file paths (returns first, logs warning)
                - Dict: Must contain 'dataX', 'dataY', 'dataC' keys
            return_obj: Whether to return the file object (only for file inputs)

        Returns:
            Tuple of (dataX, dataY, dataC, file_obj or None)
        """
        # Handle file path
        if isinstance(data, (str, Path)):
            return self._load_file(str(data), return_obj)

        # Handle numpy array (assume it's voltage data)
        if isinstance(data, np.ndarray):
            return self._resolve_array(data)

        # Handle list (assume list of file paths)
        if isinstance(data, list):
            if len(data) == 0:
                raise ValueError("Empty list provided")
            
            if isinstance(data[0], str):
                logger.info(f"List of {len(data)} files provided, loading first")
                return self._load_file(data[0], return_obj)
            elif isinstance(data[0], np.ndarray):
                # List of arrays - assume [dataX, dataY, dataC] or [dataY]
                return self._resolve_array_list(data)

        # Handle dict with data arrays
        if isinstance(data, dict):
            return self._resolve_dict(data)

        raise TypeError(f"Unsupported data type: {type(data)}")

    def _load_file(
        self, file_path: str, return_obj: bool = False
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray, Optional[Any]]:
        """Load a file, using cache if available."""
        from ..loadFile import loadFile

        # Check cache
        if self.use_cache and file_path in _FILE_CACHE:
            logger.debug(f"Cache hit: {file_path}")
            cached = _FILE_CACHE[file_path]
            if return_obj:
                return cached
            else:
                return cached[0], cached[1], cached[2], None

        # Load file
        logger.info(f"Loading file: {file_path}")
        result = loadFile(file_path, return_obj=True)
        
        if len(result) == 4:
            dataX, dataY, dataC, obj = result
        else:
            dataX, dataY, dataC = result
            obj = None

        # Cache result
        if self.use_cache:
            self._add_to_cache(file_path, (dataX, dataY, dataC, obj))

        if return_obj:
            return dataX, dataY, dataC, obj
        else:
            return dataX, dataY, dataC, None

    def _resolve_array(
        self, arr: np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray, None]:
        """Resolve a single numpy array (assumed to be voltage data)."""
        dataY = arr
        
        # Generate time array assuming 10 kHz sampling
        if dataY.ndim == 1:
            n_samples = dataY.shape[0]
            dataX = np.arange(n_samples) / 10000.0  # Assume 10 kHz
            dataC = np.zeros_like(dataY)
            # Reshape to (1, n_samples) for consistency
            dataX = dataX.reshape(1, -1)
            dataY = dataY.reshape(1, -1)
            dataC = dataC.reshape(1, -1)
        else:
            n_sweeps, n_samples = dataY.shape
            dataX = np.tile(np.arange(n_samples) / 10000.0, (n_sweeps, 1))
            dataC = np.zeros_like(dataY)

        logger.warning(
            "Numpy array provided without time/stim - assuming 10 kHz, zero stim"
        )
        return dataX, dataY, dataC, None

    def _resolve_array_list(
        self, arrays: List[np.ndarray]
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray, None]:
        """Resolve a list of numpy arrays."""
        if len(arrays) == 1:
            return self._resolve_array(arrays[0])
        elif len(arrays) == 2:
            # Assume [dataX, dataY]
            dataX, dataY = arrays
            dataC = np.zeros_like(dataY)
            return dataX, dataY, dataC, None
        elif len(arrays) >= 3:
            # Assume [dataX, dataY, dataC]
            return arrays[0], arrays[1], arrays[2], None
        else:
            raise ValueError("Invalid array list")

    def _resolve_dict(
        self, data: Dict[str, Any]
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray, None]:
        """Resolve a dictionary with data arrays."""
        if "dataY" not in data:
            raise ValueError("Dict must contain 'dataY' key")

        dataY = np.asarray(data["dataY"])
        
        if "dataX" in data:
            dataX = np.asarray(data["dataX"])
        else:
            # Generate time array
            if dataY.ndim == 1:
                dataX = np.arange(dataY.shape[0]) / 10000.0
            else:
                n_sweeps, n_samples = dataY.shape
                dataX = np.tile(np.arange(n_samples) / 10000.0, (n_sweeps, 1))

        if "dataC" in data:
            dataC = np.asarray(data["dataC"])
        else:
            dataC = np.zeros_like(dataY)

        return dataX, dataY, dataC, None

    def _add_to_cache(
        self, key: str, value: Tuple[np.ndarray, np.ndarray, np.ndarray, Any]
    ):
        """Add item to cache, evicting oldest if necessary."""
        if len(_FILE_CACHE) >= self.max_cache_size:
            # Simple FIFO eviction
            oldest_key = next(iter(_FILE_CACHE))
            del _FILE_CACHE[oldest_key]
            logger.debug(f"Cache eviction: {oldest_key}")

        _FILE_CACHE[key] = value

    def clear_cache(self):
        """Clear the file cache."""
        _FILE_CACHE.clear()
        logger.info("Cache cleared")

    def get_cache_info(self) -> Dict[str, Any]:
        """Get information about the current cache state."""
        return {
            "size": len(_FILE_CACHE),
            "max_size": self.max_cache_size,
            "files": list(_FILE_CACHE.keys()),
        }


# Convenience function
def resolve_data(
    data: Union[str, Path, np.ndarray, List, Dict[str, Any]],
    return_obj: bool = False,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, Optional[Any]]:
    """
    Convenience function to resolve data without creating a DataResolver instance.

    Args:
        data: Input data in various formats
        return_obj: Whether to return the file object

    Returns:
        Tuple of (dataX, dataY, dataC, file_obj or None)
    """
    resolver = DataResolver()
    return resolver.resolve(data, return_obj)
