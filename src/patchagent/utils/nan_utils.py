"""
NaN utilities — clean NaN-padded arrays from variable-length sweep loading.

When NWB files contain sweeps of different lengths, :func:`loadNWB` pads
shorter sweeps with ``np.nan`` so they can be stacked into a uniform 2-D
matrix.  The functions here strip that padding.
"""

from __future__ import annotations

from typing import List, Tuple, Union

import numpy as np


def clean_nans(
    dataX: np.ndarray,
    dataY: np.ndarray,
    dataC: np.ndarray,
) -> Tuple[
    Union[np.ndarray, List[np.ndarray]],
    Union[np.ndarray, List[np.ndarray]],
    Union[np.ndarray, List[np.ndarray]],
]:
    """Remove trailing NaN padding from variable-length sweep arrays.

    For each sweep the function finds the first index at which *any* of
    the three arrays is ``NaN`` and truncates all three to that length.

    If all sweeps end up the same length the result is a regular 2-D
    ``np.ndarray`` (same shape convention as the original).  When sweep
    lengths differ after trimming a **list of 1-D arrays** is returned
    instead — this preserves data fidelity at the cost of uniform shape.

    1-D inputs (single-sweep) are returned unchanged.

    Parameters
    ----------
    dataX, dataY, dataC : np.ndarray
        Time, response, and command arrays as returned by ``loadFile``.

    Returns
    -------
    (dataX, dataY, dataC)
        Cleaned arrays (2-D ``ndarray`` when uniform, else list of 1-D arrays).
    """
    # Single-sweep: nothing to do
    if dataX.ndim == 1:
        mask = ~(np.isnan(dataX) | np.isnan(dataY) | np.isnan(dataC))
        return dataX[mask], dataY[mask], dataC[mask]

    trimmed_x: List[np.ndarray] = []
    trimmed_y: List[np.ndarray] = []
    trimmed_c: List[np.ndarray] = []

    for i in range(dataX.shape[0]):
        # Find first NaN in any of the three arrays
        nan_mask = np.isnan(dataX[i]) | np.isnan(dataY[i]) | np.isnan(dataC[i])
        nan_indices = np.where(nan_mask)[0]

        if len(nan_indices) > 0:
            end = nan_indices[0]
        else:
            end = dataX.shape[1]

        trimmed_x.append(dataX[i, :end])
        trimmed_y.append(dataY[i, :end])
        trimmed_c.append(dataC[i, :end])

    # If all sweeps are the same length, return a uniform 2-D array
    lengths = [len(a) for a in trimmed_x]
    if len(set(lengths)) == 1:
        return (
            np.vstack(trimmed_x),
            np.vstack(trimmed_y),
            np.vstack(trimmed_c),
        )

    # Otherwise return list-of-arrays
    return trimmed_x, trimmed_y, trimmed_c
