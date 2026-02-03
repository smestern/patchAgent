"""
loadNWB - Load NWB files using h5py

Vendored from pyAPisolation with modifications for patchAgent.
Original: https://github.com/smestern/pyAPisolation/blob/master/pyAPisolation/loadFile/loadNWB.py
"""

import numpy as np
from .loadABF import loadABF

try:
    import h5py
except ImportError:
    print("h5py import fail - NWB loading will not work")

import pandas as pd


def loadFile(file_path, return_obj=False, old=False):
    """
    Loads electrophysiology files and returns standardized arrays.
    Unified interface for ABF and NWB files.

    Args:
        file_path (str): Path to the file (.abf or .nwb)
        return_obj (bool, optional): Return the file object. Defaults to False.
        old (bool, optional): Use old NWB indexing method. Defaults to False.

    Returns:
        dataX: time (seconds)
        dataY: voltage (mV)
        dataC: current (pA)
        obj: file object (optional)
    """
    if file_path.endswith(".nwb"):
        return loadNWB(file_path, return_obj, old)
    elif file_path.endswith(".abf"):
        return loadABF(file_path, return_obj)
    else:
        raise Exception(f"File type not supported: {file_path}")


def loadNWB(file_path, return_obj=False, old=False, load_into_mem=True):
    """
    Loads the NWB object and returns three arrays dataX, dataY, dataC.
    Same input/output as loadABF for easy pipeline inclusion.

    Args:
        file_path (str): Path to NWB file
        return_obj (bool, optional): Return the NWB object. Defaults to False.
        old (bool, optional): Use old indexing method. Defaults to False.
        load_into_mem (bool, optional): Load data into memory. Defaults to True.

    Returns:
        dataX: time (seconds)
        dataY: voltage (mV)
        dataC: current (pA)
        obj: nwbFile object (optional)
    """
    if old:
        nwb = old_nwbFile(file_path)
    else:
        nwb = nwbFile(file_path, load_into_mem=load_into_mem)

    fs_dict = nwb.rate
    fs = fs_dict["rate"]
    dt = np.reciprocal(fs)

    if isinstance(nwb.dataX, np.ndarray) == False and load_into_mem == True:
        dataX = np.asarray(nwb.dataX, dtype=np.dtype("O"))
        dataY = np.asarray(nwb.dataY, dtype=np.dtype("O"))
        dataC = np.asarray(nwb.dataC, dtype=np.dtype("O"))
    elif load_into_mem == True:
        dataX = nwb.dataX
        dataY = nwb.dataY
        dataC = nwb.dataC
    else:
        dataX = []
        dataY = []
        dataC = []

    if return_obj:
        return dataX, dataY, dataC, nwb
    else:
        return dataX, dataY, dataC


class nwbFile(object):
    """
    A simple class to load NWB data quickly and easily.
    Sweep data located at nwb.dataX, nwb.dataY, nwb.dataC (for stim)
    """

    def __init__(self, file_path, load_into_mem=True):
        with h5py.File(file_path, "r") as f:
            acq_keys = list(f["acquisition"].keys())
            stim_keys = list(f["stimulus"]["presentation"].keys())
            sweeps = zip(acq_keys, stim_keys)

            # Find the indices with long square
            index_to_use = []
            for key_resp, key_stim in sweeps:
                sweep_dict = dict(f["acquisition"][key_resp].attrs.items())
                if check_stimulus(sweep_dict, key_resp):
                    index_to_use.append((key_resp, key_stim))

            self.sweepCount = len(index_to_use)
            
            if len(index_to_use) == 0:
                self.rate = {"rate": np.nan}
                self.sweepYVars = np.nan
                self.sweepCVars = np.nan
            else:
                if "starting_time" in f["acquisition"][index_to_use[-1][0]]:
                    self.rate = dict(
                        f["acquisition"][index_to_use[-1][0]]["starting_time"].attrs.items()
                    )
                elif "starting_time" in f["stimulus"]["presentation"][stim_keys[-1]]:
                    self.rate = dict(
                        f["stimulus"]["presentation"][stim_keys[-1]]["starting_time"].attrs.items()
                    )
                else:
                    self.rate = {"rate": np.nan}

                self.sweepYVars = dict(
                    f["acquisition"][index_to_use[0][0]]["data"].attrs.items()
                )
                self.sweepCVars = dict(
                    f["stimulus"]["presentation"][stim_keys[-1]]["data"].attrs.items()
                )

            dataY = []
            dataX = []
            dataC = []
            self.sweepMetadata = []
            
            for sweep_resp, sweep_stim in index_to_use:
                data_space_s = 1 / (
                    dict(f["acquisition"][sweep_resp]["starting_time"].attrs.items())["rate"]
                )
                try:
                    bias_current = f["acquisition"][sweep_resp]["bias_current"][()]
                    if np.isnan(bias_current):
                        bias_current = 0
                except:
                    bias_current = 0

                if load_into_mem:
                    temp_dataY = (
                        np.asarray(f["acquisition"][sweep_resp]["data"][()])
                        * dict(f["acquisition"][sweep_resp]["data"].attrs.items())["conversion"]
                    )
                    temp_dataX = np.cumsum(
                        np.hstack((0, np.full(temp_dataY.shape[0] - 1, data_space_s)))
                    )
                    temp_dataC = (
                        np.asarray(f["stimulus"]["presentation"][sweep_stim]["data"][()])
                        * dict(f["stimulus"]["presentation"][sweep_stim]["data"].attrs.items())[
                            "conversion"
                        ]
                    )
                    dataY.append(temp_dataY)
                    dataX.append(temp_dataX)
                    dataC.append(temp_dataC)
                else:
                    dataY.append(f["acquisition"][sweep_resp]["data"])
                    dataX.append(f["acquisition"][sweep_resp]["starting_time"])
                    dataC.append(f["stimulus"]["presentation"][sweep_stim]["data"])

                sweep_dict_resp = dict(f["acquisition"][sweep_resp].attrs.items())
                sweep_dict_resp.update(
                    dict(f["acquisition"][sweep_resp]["data"].attrs.items())
                )
                sweep_dict_stim = dict(
                    f["stimulus"]["presentation"][sweep_stim].attrs.items()
                )
                sweep_dict_stim.update(
                    dict(f["stimulus"]["presentation"][sweep_stim]["data"].attrs.items())
                )
                self.sweepMetadata.append(
                    dict(resp_dict=sweep_dict_resp, stim_dict=sweep_dict_stim)
                )

            try:
                self.dataX = np.vstack(dataX)
                self.dataC = np.vstack(dataC)
                self.dataY = np.vstack(dataY)
            except:
                self.dataX = dataX
                self.dataC = dataC
                self.dataY = dataY


class old_nwbFile(object):
    """
    Handles older NWB files that do not have the same structure as newer ones.
    """

    def __init__(self, file_path):
        with h5py.File(file_path, "r") as f:
            sweeps = list(f["acquisition"].keys())
            self.sweepCount = len(sweeps)
            self.rate = dict(f["acquisition"][sweeps[0]]["starting_time"].attrs.items())
            self.sweepYVars = dict(f["acquisition"][sweeps[0]]["data"].attrs.items())
            self.sweepCVars = dict(
                f["stimulus"]["presentation"][sweeps[0]]["data"].attrs.items()
            )
            
            data_space_s = 1 / self.rate["rate"]
            dataY = []
            dataX = []
            dataC = []
            
            for sweep in sweeps:
                temp_dataY = np.asarray(f["acquisition"][sweep]["data"][()])
                temp_dataX = np.cumsum(
                    np.hstack((0, np.full(temp_dataY.shape[0] - 1, data_space_s)))
                )
                temp_dataC = np.asarray(f["stimulus"]["presentation"][sweep]["data"][()])
                dataY.append(temp_dataY)
                dataX.append(temp_dataX)
                dataC.append(temp_dataC)

            try:
                self.dataX = np.vstack(dataX)
                self.dataC = np.vstack(dataC)
                self.dataY = np.vstack(dataY)
            except:
                self.dataX = dataX
                self.dataC = dataC
                self.dataY = dataY


class stim_names:
    """Global stimulus name filters for NWB file loading."""
    stim_inc = ["long", "1000"]
    stim_exc = ["rheo", "Rf50_", "stimulus_apwaveform", "extracellular"]
    stim_type = [""]

    def __init__(self):
        self.stim_inc = stim_names.stim_inc
        self.stim_exc = stim_names.stim_exc


GLOBAL_STIM_NAMES = stim_names()


def check_stimulus(sweep_dict, name):
    """Check if a sweep matches the stimulus criteria."""
    if "description" in sweep_dict.keys():
        desc_check1 = check_stimulus_desc(sweep_dict["description"])
    else:
        desc_check1 = False
    if "stimulus_description" in sweep_dict.keys():
        desc_check2 = check_stimulus_desc(sweep_dict["stimulus_description"])
    else:
        desc_check2 = False
    desc_check = np.logical_or(desc_check1, desc_check2)
    type_check = check_stimulus_type(sweep_dict.get("neurodata_type", "")) or check_stimulus_type(
        name
    )
    return np.logical_and(desc_check, type_check)


def check_stimulus_type(sweep_type):
    """Check if sweep type matches expected types."""
    try:
        sweep_type_str = sweep_type.decode()
    except:
        sweep_type_str = sweep_type
    return np.any(
        [x.upper() in sweep_type_str.upper() for x in GLOBAL_STIM_NAMES.stim_type]
    )


def check_stimulus_desc(stim_desc):
    """Check if stimulus description matches inclusion/exclusion criteria."""
    try:
        stim_desc_str = stim_desc.decode()
    except:
        stim_desc_str = stim_desc
    include_s = np.any(
        [x.upper() in stim_desc_str.upper() for x in GLOBAL_STIM_NAMES.stim_inc]
    )
    exclude_s = np.invert(
        np.any([x.upper() in stim_desc_str.upper() for x in GLOBAL_STIM_NAMES.stim_exc])
    )
    return np.logical_and(include_s, exclude_s)
