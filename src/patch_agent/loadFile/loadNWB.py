"""
loadNWB - Load NWB intracellular electrophysiology files.

Primary backend: pynwb (https://pynwb.readthedocs.io/en/stable/)
Remote/DANDI support: lindi (optional, https://github.com/NeurodataWithoutBorders/lindi)
Legacy fallback: h5py (for non-compliant files)

Vendored from pyAPisolation with major rewrite for patchAgent.
Original: https://github.com/smestern/pyAPisolation/blob/master/pyAPisolation/loadFile/loadNWB.py
"""

from __future__ import annotations

import logging
import warnings
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

import numpy as np

from .loadABF import loadABF

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Unit conversion helpers
# ---------------------------------------------------------------------------

# Standard SI → electrophysiology display-unit scale factors.
# pynwb gives data in SI base units (volts, amperes) after applying
# ``data[:] * conversion + offset``.  We then scale to mV / pA for display.
_VOLTS_TO_MV = 1e3
_AMPS_TO_PA = 1e12


def _series_data_si(series) -> np.ndarray:
    """Read a PatchClampSeries and return data in SI base units (V or A).

    Applies the NWB ``conversion`` and ``offset`` fields:
        value_SI = data[:] * conversion + offset
    """
    raw = np.asarray(series.data[:], dtype=np.float64)
    conversion = getattr(series, "conversion", 1.0)
    offset = getattr(series, "offset", 0.0)
    return raw * conversion + offset


def _series_time(series) -> np.ndarray:
    """Build a time vector (in seconds) for a TimeSeries."""
    n = series.data.shape[0] if hasattr(series.data, "shape") else len(series.data)
    if series.timestamps is not None:
        return np.asarray(series.timestamps[:n], dtype=np.float64)
    else:
        rate = series.rate
        t0 = series.starting_time or 0.0
        return t0 + np.arange(n, dtype=np.float64) / rate


# ---------------------------------------------------------------------------
# Clamp-mode helpers
# ---------------------------------------------------------------------------

_CC_RESPONSE_TYPES = (
    "CurrentClampSeries",
    "IZeroClampSeries",
)
_VC_RESPONSE_TYPES = ("VoltageClampSeries",)
_CC_STIMULUS_TYPES = ("CurrentClampStimulusSeries",)
_VC_STIMULUS_TYPES = ("VoltageClampStimulusSeries",)


def _clamp_mode_of(series) -> str:
    """Return 'CC', 'VC', or 'unknown' based on the neurodata_type."""
    ndt = type(series).__name__
    if ndt in _CC_RESPONSE_TYPES or ndt in _CC_STIMULUS_TYPES:
        return "CC"
    if ndt in _VC_RESPONSE_TYPES or ndt in _VC_STIMULUS_TYPES:
        return "VC"
    return "unknown"


# ---------------------------------------------------------------------------
# NWB file opener – local, remote (lindi), .lindi.json / .lindi.tar
# ---------------------------------------------------------------------------


def _open_nwb(path_or_url: str, local_cache=None):
    """Open an NWB file and return ``(io, nwbfile, closer)``.

    ``closer`` is a callable that closes all resources (call in a finally block).

    Supports:
    - Local ``.nwb`` files via ``pynwb.NWBHDF5IO``
    - Remote ``http(s)://`` URLs via ``lindi`` → ``pynwb.NWBHDF5IO``
    - ``.lindi.json`` / ``.lindi.tar`` files via ``lindi``
    """
    import pynwb

    path_lower = path_or_url.lower()
    is_remote = path_lower.startswith("http://") or path_lower.startswith("https://")
    is_lindi_file = path_lower.endswith(".lindi.json") or path_lower.endswith(".lindi.tar")

    if is_remote or is_lindi_file:
        try:
            import lindi
        except ImportError:
            raise ImportError(
                "The 'lindi' package is required for loading remote NWB files or "
                ".lindi.json/.lindi.tar files.  Install it with:\n"
                "    pip install lindi"
            )

        if is_remote:
            kwargs = {}
            if local_cache is not None:
                kwargs["local_cache"] = local_cache
            lindi_f = lindi.LindiH5pyFile.from_hdf5_file(path_or_url, **kwargs)
        else:
            kwargs = {}
            if local_cache is not None:
                kwargs["local_cache"] = local_cache
            lindi_f = lindi.LindiH5pyFile.from_lindi_file(path_or_url, **kwargs)

        io = pynwb.NWBHDF5IO(file=lindi_f, mode="r")
        nwbfile = io.read()

        def closer():
            io.close()
            lindi_f.close()

        return io, nwbfile, closer

    # Local .nwb file
    io = pynwb.NWBHDF5IO(str(path_or_url), "r", load_namespaces=True)
    nwbfile = io.read()

    return io, nwbfile, io.close


# ---------------------------------------------------------------------------
# Sweep discovery
# ---------------------------------------------------------------------------


def _discover_sweeps(nwbfile) -> List[Dict[str, Any]]:
    """Discover all intracellular sweeps in an NWBFile.

    Returns a list of dicts, each containing:
        sweep_number  : int or None
        response      : PatchClampSeries (response / acquisition)
        stimulus      : PatchClampSeries (stimulus / presentation) or None
        clamp_mode    : 'CC' | 'VC' | 'unknown'
        protocol      : str  (stimulus_description)
    """
    from pynwb.icephys import PatchClampSeries

    # ── Strategy 1: Use the sweep table if available ──────────────────────
    sweep_table = getattr(nwbfile, "sweep_table", None)
    if sweep_table is not None and len(sweep_table) > 0:
        sweep_numbers = sorted(set(int(x) for x in sweep_table["sweep_number"][:]))
        sweeps = []
        for sn in sweep_numbers:
            series_list = sweep_table.get_series(sn)
            resp, stim = None, None
            for s in series_list:
                ndt = type(s).__name__
                if ndt in _CC_RESPONSE_TYPES or ndt in _VC_RESPONSE_TYPES:
                    resp = s
                elif ndt in _CC_STIMULUS_TYPES or ndt in _VC_STIMULUS_TYPES:
                    stim = s
                else:
                    # Generic PatchClampSeries – check if it's in acquisition
                    if s.name in (nwbfile.acquisition or {}):
                        resp = s
                    else:
                        stim = s
            if resp is not None:
                sweeps.append({
                    "sweep_number": sn,
                    "response": resp,
                    "stimulus": stim,
                    "clamp_mode": _clamp_mode_of(resp),
                    "protocol": getattr(resp, "stimulus_description", "N/A") or "N/A",
                })
        if sweeps:
            return sweeps

    # ── Strategy 2: Match acquisition ↔ stimulus by sweep_number attr ─────
    acq_series = {}  # sweep_number → series
    for name, series in (nwbfile.acquisition or {}).items():
        if isinstance(series, PatchClampSeries):
            sn = getattr(series, "sweep_number", None)
            acq_series[sn if sn is not None else name] = series

    stim_series = {}
    stim_container = getattr(nwbfile, "stimulus", None) or {}
    # nwbfile.stimulus can be a dict-like or have items() directly
    if hasattr(stim_container, "items"):
        for name, series in stim_container.items():
            if isinstance(series, PatchClampSeries):
                sn = getattr(series, "sweep_number", None)
                stim_series[sn if sn is not None else name] = series

    # Also check stimulus templates (some files put stimulus there)
    stim_templates = getattr(nwbfile, "stimulus_template", None) or {}
    if hasattr(stim_templates, "items"):
        for name, series in stim_templates.items():
            if isinstance(series, PatchClampSeries):
                sn = getattr(series, "sweep_number", None)
                key = sn if sn is not None else name
                if key not in stim_series:
                    stim_series[key] = series

    sweeps = []
    for key in sorted(acq_series.keys(), key=lambda k: (isinstance(k, str), k)):
        resp = acq_series[key]
        stim = stim_series.get(key, None)
        sweeps.append({
            "sweep_number": key if isinstance(key, (int, np.integer)) else None,
            "response": resp,
            "stimulus": stim,
            "clamp_mode": _clamp_mode_of(resp),
            "protocol": getattr(resp, "stimulus_description", "N/A") or "N/A",
        })

    return sweeps


# ---------------------------------------------------------------------------
# Filtering helpers
# ---------------------------------------------------------------------------


def _match_filter(value: str, substrings: Sequence[str]) -> bool:
    """Return True if *any* substring appears in *value* (case-insensitive)."""
    v = value.upper()
    return any(s.upper() in v for s in substrings)


def _filter_sweeps(
    sweeps: List[Dict[str, Any]],
    *,
    protocol_filter: Optional[Sequence[str]] = None,
    clamp_mode_filter: Optional[str] = None,
    sweep_numbers: Optional[Sequence[int]] = None,
) -> List[Dict[str, Any]]:
    """Filter a sweep list by protocol name, clamp mode, or sweep number."""
    out = sweeps

    if sweep_numbers is not None:
        sn_set = set(sweep_numbers)
        out = [s for s in out if s["sweep_number"] in sn_set]

    if clamp_mode_filter is not None:
        cm = clamp_mode_filter.upper()
        out = [s for s in out if s["clamp_mode"] == cm]

    if protocol_filter is not None and len(protocol_filter) > 0:
        out = [s for s in out if _match_filter(s["protocol"], protocol_filter)]

    return out


# ---------------------------------------------------------------------------
# NWBRecording wrapper
# ---------------------------------------------------------------------------


class NWBRecording:
    """Modern wrapper around a pynwb NWBFile for intracellular ephys data.

    Provides the standard ``(dataX, dataY, dataC)`` arrays plus rich
    metadata about sweeps, protocol, clamp mode, and electrode info.

    Properties
    ----------
    sweepCount : int
    rate : dict  (``{"rate": <Hz>}``) — kept for backward compat
    sample_rate : float  — Hz
    sweepYVars : dict  — response conversion attributes
    sweepCVars : dict  — stimulus conversion attributes
    sweepMetadata : list[dict]
    clamp_mode : str  — dominant clamp mode across sweeps
    clamp_modes : list[str]  — per-sweep
    protocols : list[str]  — per-sweep protocol / stimulus_description
    electrode_info : dict
    dataX, dataY, dataC : np.ndarray  — (n_sweeps, n_samples)
    """

    def __init__(self, nwbfile, sweeps: List[Dict[str, Any]]):
        """
        Args:
            nwbfile: pynwb.NWBFile (kept as reference for metadata)
            sweeps: Pre-filtered list of sweep dicts from ``_discover_sweeps``
        """
        self._nwbfile = nwbfile
        self._sweeps = sweeps
        self._build_arrays()
        self._build_metadata()

    # -- Array construction -------------------------------------------------

    def _build_arrays(self):
        if len(self._sweeps) == 0:
            self.dataX = np.empty((0, 0))
            self.dataY = np.empty((0, 0))
            self.dataC = np.empty((0, 0))
            return

        ys, xs, cs = [], [], []
        for sd in self._sweeps:
            resp = sd["response"]
            stim = sd.get("stimulus")

            # Response → display units
            resp_si = _series_data_si(resp)
            cm = sd["clamp_mode"]
            if cm == "CC":
                y = resp_si * _VOLTS_TO_MV  # V → mV
            elif cm == "VC":
                y = resp_si * _AMPS_TO_PA   # A → pA
            else:
                # Best guess: if unit string says "volt" → mV, else pA
                unit_str = getattr(resp, "unit", "") or ""
                if "volt" in unit_str.lower():
                    y = resp_si * _VOLTS_TO_MV
                else:
                    y = resp_si * _AMPS_TO_PA

            # Time
            x = _series_time(resp)

            # Stimulus → display units
            if stim is not None:
                stim_si = _series_data_si(stim)
                stim_cm = _clamp_mode_of(stim)
                # Stimulus is inverse: CC stim → pA, VC stim → mV
                if stim_cm in ("CurrentClampStimulusSeries",) or cm == "CC":
                    c = stim_si * _AMPS_TO_PA
                else:
                    c = stim_si * _VOLTS_TO_MV
            else:
                c = np.zeros_like(y)

            ys.append(y)
            xs.append(x)
            cs.append(c)

        # Attempt to vstack; handle variable-length sweeps by padding
        try:
            self.dataY = np.vstack(ys)
            self.dataX = np.vstack(xs)
            self.dataC = np.vstack(cs)
        except ValueError:
            # Variable-length sweeps — pad to longest with NaN
            max_len = max(a.shape[0] for a in ys)

            def _pad(arr, length):
                if arr.shape[0] == length:
                    return arr
                padded = np.full(length, np.nan, dtype=np.float64)
                padded[: arr.shape[0]] = arr
                return padded

            self.dataY = np.vstack([_pad(a, max_len) for a in ys])
            self.dataX = np.vstack([_pad(a, max_len) for a in xs])
            self.dataC = np.vstack([_pad(a, max_len) for a in cs])

    # -- Metadata -----------------------------------------------------------

    def _build_metadata(self):
        nwbfile = self._nwbfile

        # Per-sweep metadata
        self.clamp_modes: List[str] = [s["clamp_mode"] for s in self._sweeps]
        self.protocols: List[str] = [s["protocol"] for s in self._sweeps]
        self.sweep_numbers: List[Optional[int]] = [s["sweep_number"] for s in self._sweeps]

        # Dominant clamp mode
        if self.clamp_modes:
            from collections import Counter

            self.clamp_mode = Counter(self.clamp_modes).most_common(1)[0][0]
        else:
            self.clamp_mode = "unknown"

        # Dominant protocol
        if self.protocols:
            unique_protos = sorted(set(self.protocols))
            self.protocol = (
                unique_protos[0]
                if len(unique_protos) == 1
                else ", ".join(unique_protos)
            )
        else:
            self.protocol = "unknown"

        # Sample rate
        if self._sweeps:
            resp = self._sweeps[0]["response"]
            self._sample_rate = float(resp.rate) if resp.rate else np.nan
        else:
            self._sample_rate = np.nan

        # Sweep-level metadata dicts (backward compat)
        self.sweepMetadata = []
        for sd in self._sweeps:
            resp = sd["response"]
            stim = sd.get("stimulus")
            resp_dict = {
                "neurodata_type": type(resp).__name__,
                "description": getattr(resp, "description", ""),
                "stimulus_description": sd["protocol"],
                "conversion": getattr(resp, "conversion", 1.0),
                "unit": getattr(resp, "unit", ""),
                "sweep_number": sd["sweep_number"],
            }
            stim_dict = {}
            if stim is not None:
                stim_dict = {
                    "neurodata_type": type(stim).__name__,
                    "description": getattr(stim, "description", ""),
                    "stimulus_description": getattr(
                        stim, "stimulus_description", "N/A"
                    ),
                    "conversion": getattr(stim, "conversion", 1.0),
                    "unit": getattr(stim, "unit", ""),
                    "sweep_number": sd["sweep_number"],
                }
            self.sweepMetadata.append(
                {"resp_dict": resp_dict, "stim_dict": stim_dict}
            )

        # Electrode info
        self.electrode_info = {}
        icephys_electrodes = getattr(nwbfile, "icephys_electrodes", None) or {}
        if hasattr(icephys_electrodes, "items"):
            for name, elec in icephys_electrodes.items():
                self.electrode_info[name] = {
                    "description": getattr(elec, "description", ""),
                    "device": (
                        getattr(elec.device, "name", "")
                        if getattr(elec, "device", None)
                        else ""
                    ),
                    "location": getattr(elec, "location", ""),
                    "resistance": getattr(elec, "resistance", ""),
                    "cell_id": getattr(elec, "cell_id", ""),
                }

        # Session-level metadata
        self.session_description = getattr(nwbfile, "session_description", "")
        self.identifier = getattr(nwbfile, "identifier", "")
        self.session_start_time = getattr(nwbfile, "session_start_time", None)

    # -- Backward-compatible properties ------------------------------------

    @property
    def sweepCount(self) -> int:
        return len(self._sweeps)

    @property
    def rate(self) -> Dict[str, float]:
        """Backward-compatible rate dict ``{"rate": Hz}``."""
        return {"rate": self._sample_rate}

    @property
    def sample_rate(self) -> float:
        return self._sample_rate

    @property
    def sweepYVars(self) -> Dict[str, Any]:
        """Response conversion attrs from the first sweep (backward compat)."""
        if self._sweeps:
            resp = self._sweeps[0]["response"]
            return {
                "conversion": getattr(resp, "conversion", 1.0),
                "unit": getattr(resp, "unit", ""),
                "resolution": getattr(resp, "resolution", -1.0),
            }
        return {}

    @property
    def sweepCVars(self) -> Dict[str, Any]:
        """Stimulus conversion attrs from the first sweep (backward compat)."""
        if self._sweeps:
            stim = self._sweeps[0].get("stimulus")
            if stim is not None:
                return {
                    "conversion": getattr(stim, "conversion", 1.0),
                    "unit": getattr(stim, "unit", ""),
                    "resolution": getattr(stim, "resolution", -1.0),
                }
        return {}

    def __repr__(self) -> str:
        return (
            f"NWBRecording(sweeps={self.sweepCount}, rate={self._sample_rate:.0f} Hz, "
            f"clamp={self.clamp_mode}, protocol={self.protocol!r})"
        )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def loadFile(
    file_path: str,
    return_obj: bool = False,
    old: bool = False,
    *,
    protocol_filter: Optional[Sequence[str]] = None,
    clamp_mode_filter: Optional[str] = None,
    sweep_numbers: Optional[Sequence[int]] = None,
    local_cache=None,
) -> Union[
    Tuple[np.ndarray, np.ndarray, np.ndarray],
    Tuple[np.ndarray, np.ndarray, np.ndarray, Any],
]:
    """Load an electrophysiology file (.abf, .nwb, or remote URL).

    Unified dispatcher — routes to :func:`loadNWB` or :func:`loadABF`.

    Args:
        file_path: Path to local file, DANDI URL, or .lindi.json/.lindi.tar
        return_obj: Return the file object as a fourth element.
        old: (Deprecated) Use the legacy h5py NWB loader.
        protocol_filter: List of substrings to match against
            ``stimulus_description``.  Only sweeps matching at least one
            substring are loaded.  ``None`` means load all.
        clamp_mode_filter: ``"CC"`` or ``"VC"`` — only load sweeps of that
            clamp mode.  ``None`` means load all.
        sweep_numbers: Explicit list of sweep numbers to load.  ``None``
            means load all.
        local_cache: Optional ``lindi.LocalCache`` for remote file caching.

    Returns:
        ``(dataX, dataY, dataC)`` or ``(dataX, dataY, dataC, obj)``
    """
    path_lower = file_path.lower()
    is_remote = path_lower.startswith("http://") or path_lower.startswith("https://")
    is_lindi = path_lower.endswith(".lindi.json") or path_lower.endswith(".lindi.tar")

    if path_lower.endswith(".abf") and not is_remote:
        return loadABF(file_path, return_obj)
    elif path_lower.endswith(".nwb") or is_remote or is_lindi:
        return loadNWB(
            file_path,
            return_obj=return_obj,
            old=old,
            protocol_filter=protocol_filter,
            clamp_mode_filter=clamp_mode_filter,
            sweep_numbers=sweep_numbers,
            local_cache=local_cache,
        )
    else:
        raise ValueError(f"Unsupported file type: {file_path}")


def loadNWB(
    file_path: str,
    return_obj: bool = False,
    old: bool = False,
    load_into_mem: bool = True,
    *,
    protocol_filter: Optional[Sequence[str]] = None,
    clamp_mode_filter: Optional[str] = None,
    sweep_numbers: Optional[Sequence[int]] = None,
    local_cache=None,
) -> Union[
    Tuple[np.ndarray, np.ndarray, np.ndarray],
    Tuple[np.ndarray, np.ndarray, np.ndarray, "NWBRecording"],
]:
    """Load an NWB file and return ``(dataX, dataY, dataC[, obj])``.

    Uses **pynwb** as the primary backend, with optional **lindi** for remote
    files.  Falls back to the legacy h5py-based loader on failure.

    Args:
        file_path: Local path, DANDI URL, or .lindi file path.
        return_obj: Return the :class:`NWBRecording` wrapper as fourth element.
        old: (Deprecated) Force the legacy h5py loader.
        load_into_mem: Ignored (kept for backward API compat).
        protocol_filter: Substring(s) to match in ``stimulus_description``.
        clamp_mode_filter: ``"CC"`` or ``"VC"``.
        sweep_numbers: Explicit sweep number list.
        local_cache: ``lindi.LocalCache`` instance for remote caching.

    Returns:
        ``(dataX, dataY, dataC)`` or ``(dataX, dataY, dataC, NWBRecording)``
    """
    if old:
        warnings.warn(
            "old=True is deprecated. Using legacy h5py loader.",
            DeprecationWarning,
            stacklevel=2,
        )
        return _legacy_load_nwb(file_path, return_obj=return_obj, old=True)

    # ── Primary path: pynwb ──────────────────────────────────────────────
    try:
        io, nwbfile, closer = _open_nwb(file_path, local_cache=local_cache)
        try:
            sweeps = _discover_sweeps(nwbfile)
            sweeps = _filter_sweeps(
                sweeps,
                protocol_filter=protocol_filter,
                clamp_mode_filter=clamp_mode_filter,
                sweep_numbers=sweep_numbers,
            )

            if len(sweeps) == 0:
                available = _discover_sweeps(nwbfile)
                avail_protos = sorted(set(s["protocol"] for s in available))
                avail_modes = sorted(set(s["clamp_mode"] for s in available))
                logger.warning(
                    "No sweeps matched filters (protocol_filter=%s, "
                    "clamp_mode_filter=%s, sweep_numbers=%s). "
                    "Available protocols: %s, modes: %s, "
                    "total sweeps: %d",
                    protocol_filter,
                    clamp_mode_filter,
                    sweep_numbers,
                    avail_protos,
                    avail_modes,
                    len(available),
                )

            recording = NWBRecording(nwbfile, sweeps)
        finally:
            # Close the file — data is already in numpy arrays
            try:
                closer()
            except Exception:
                pass

        if return_obj:
            return recording.dataX, recording.dataY, recording.dataC, recording
        return recording.dataX, recording.dataY, recording.dataC

    except ImportError:
        # pynwb not installed — fall through to legacy
        logger.warning("pynwb not installed, falling back to legacy h5py NWB loader.")
    except Exception as exc:
        logger.warning(
            "pynwb loading failed (%s: %s), falling back to legacy h5py NWB loader.",
            type(exc).__name__,
            exc,
        )

    # ── Fallback: legacy h5py loader ─────────────────────────────────────
    return _legacy_load_nwb(file_path, return_obj=return_obj)


# ---------------------------------------------------------------------------
# Legacy h5py-based loader (preserved as fallback)
# ---------------------------------------------------------------------------


def _legacy_load_nwb(
    file_path: str,
    return_obj: bool = False,
    old: bool = False,
):
    """Legacy h5py-based NWB loader.

    Kept as a fallback for non-standard NWB files that pynwb cannot read.
    """
    warnings.warn(
        "Using legacy h5py NWB loader. Consider converting the file to a "
        "standard NWB format for best results.",
        DeprecationWarning,
        stacklevel=3,
    )

    try:
        import h5py  # noqa: F401
    except ImportError:
        raise ImportError(
            "Neither pynwb nor h5py is available. Install at least one:\n"
            "    pip install pynwb    (recommended)\n"
            "    pip install h5py     (legacy fallback)"
        )

    if old:
        nwb = _LegacyOldNWBFile(file_path)
    else:
        nwb = _LegacyNWBFile(file_path)

    dataX = (
        nwb.dataX
        if isinstance(nwb.dataX, np.ndarray)
        else np.asarray(nwb.dataX, dtype=object)
    )
    dataY = (
        nwb.dataY
        if isinstance(nwb.dataY, np.ndarray)
        else np.asarray(nwb.dataY, dtype=object)
    )
    dataC = (
        nwb.dataC
        if isinstance(nwb.dataC, np.ndarray)
        else np.asarray(nwb.dataC, dtype=object)
    )

    if return_obj:
        return dataX, dataY, dataC, nwb
    return dataX, dataY, dataC


class _LegacyNWBFile:
    """Legacy h5py-based NWB loader (internal, kept as fallback)."""

    def __init__(self, file_path):
        import h5py

        with h5py.File(file_path, "r") as f:
            acq_keys = list(f["acquisition"].keys())
            stim_keys = list(f["stimulus"]["presentation"].keys())
            sweeps = list(zip(acq_keys, stim_keys))

            self.sweepCount = len(sweeps)

            if len(sweeps) == 0:
                self.rate = {"rate": np.nan}
                self.sweepYVars = {}
                self.sweepCVars = {}
                self.dataX = np.empty((0, 0))
                self.dataY = np.empty((0, 0))
                self.dataC = np.empty((0, 0))
                self.sweepMetadata = []
                return

            # Rate
            first_resp = sweeps[0][0]
            if "starting_time" in f["acquisition"][first_resp]:
                self.rate = dict(
                    f["acquisition"][first_resp]["starting_time"].attrs.items()
                )
            else:
                self.rate = {"rate": np.nan}

            self.sweepYVars = dict(
                f["acquisition"][first_resp]["data"].attrs.items()
            )
            self.sweepCVars = dict(
                f["stimulus"]["presentation"][sweeps[0][1]]["data"].attrs.items()
            )

            dataY, dataX, dataC = [], [], []
            self.sweepMetadata = []

            for sweep_resp, sweep_stim in sweeps:
                try:
                    rate_attrs = dict(
                        f["acquisition"][sweep_resp]["starting_time"].attrs.items()
                    )
                    data_space_s = 1.0 / rate_attrs.get(
                        "rate", self.rate.get("rate", 1.0)
                    )
                except Exception:
                    data_space_s = 1.0 / self.rate.get("rate", 1.0)

                try:
                    conv_y = dict(
                        f["acquisition"][sweep_resp]["data"].attrs.items()
                    ).get("conversion", 1.0)
                except Exception:
                    conv_y = 1.0

                try:
                    conv_c = dict(
                        f["stimulus"]["presentation"][sweep_stim][
                            "data"
                        ].attrs.items()
                    ).get("conversion", 1.0)
                except Exception:
                    conv_c = 1.0

                temp_dataY = (
                    np.asarray(f["acquisition"][sweep_resp]["data"][()]) * conv_y
                )
                temp_dataX = np.cumsum(
                    np.hstack(
                        (0, np.full(temp_dataY.shape[0] - 1, data_space_s))
                    )
                )
                temp_dataC = (
                    np.asarray(
                        f["stimulus"]["presentation"][sweep_stim]["data"][()]
                    )
                    * conv_c
                )

                dataY.append(temp_dataY)
                dataX.append(temp_dataX)
                dataC.append(temp_dataC)

                sweep_dict_resp = dict(
                    f["acquisition"][sweep_resp].attrs.items()
                )
                sweep_dict_stim = dict(
                    f["stimulus"]["presentation"][sweep_stim].attrs.items()
                )
                self.sweepMetadata.append(
                    {"resp_dict": sweep_dict_resp, "stim_dict": sweep_dict_stim}
                )

            try:
                self.dataX = np.vstack(dataX)
                self.dataC = np.vstack(dataC)
                self.dataY = np.vstack(dataY)
            except ValueError:
                self.dataX = dataX
                self.dataC = dataC
                self.dataY = dataY


class _LegacyOldNWBFile:
    """Legacy h5py-based loader for older NWB files (internal fallback)."""

    def __init__(self, file_path):
        import h5py

        with h5py.File(file_path, "r") as f:
            sweeps = list(f["acquisition"].keys())
            self.sweepCount = len(sweeps)
            self.rate = dict(
                f["acquisition"][sweeps[0]]["starting_time"].attrs.items()
            )
            self.sweepYVars = dict(
                f["acquisition"][sweeps[0]]["data"].attrs.items()
            )
            self.sweepCVars = dict(
                f["stimulus"]["presentation"][sweeps[0]]["data"].attrs.items()
            )

            data_space_s = 1.0 / self.rate["rate"]
            dataY, dataX, dataC = [], [], []

            for sweep in sweeps:
                temp_dataY = np.asarray(f["acquisition"][sweep]["data"][()])
                temp_dataX = np.cumsum(
                    np.hstack(
                        (0, np.full(temp_dataY.shape[0] - 1, data_space_s))
                    )
                )
                temp_dataC = np.asarray(
                    f["stimulus"]["presentation"][sweep]["data"][()]
                )
                dataY.append(temp_dataY)
                dataX.append(temp_dataX)
                dataC.append(temp_dataC)

            try:
                self.dataX = np.vstack(dataX)
                self.dataC = np.vstack(dataC)
                self.dataY = np.vstack(dataY)
            except ValueError:
                self.dataX = dataX
                self.dataC = dataC
                self.dataY = dataY
