"""
loadABF - Load ABF files using pyABF

Vendored from pyAPisolation with modifications for patchAgent.
Original: https://github.com/smestern/pyAPisolation/blob/master/pyAPisolation/loadFile/loadABF.py
"""

import numpy as np
import pyabf


def loadABF(file_path, return_obj=False):
    """
    Employs pyABF to generate numpy arrays of the ABF data. Optionally returns abf object.
    Same I/O as loadNWB for easy pipeline inclusion.

    Args:
        file_path (str): Path to the ABF file
        return_obj (bool, optional): Return the pyABF object to access various properties. 
            Defaults to False.

    Returns:
        dataX: time array (seconds), shape (n_sweeps, n_samples)
        dataY: voltage/response array (mV or pA), shape (n_sweeps, n_samples)
        dataC: current/command array (pA or mV), shape (n_sweeps, n_samples)
        abf: pyabf.ABF object (optional, if return_obj=True)
    """
    abf = pyabf.ABF(file_path)
    dataX = []
    dataY = []
    dataC = []
    
    for sweep in abf.sweepList:
        abf.setSweep(sweep)
        tempX = abf.sweepX
        tempY = abf.sweepY
        tempC = abf.sweepC
        dataX.append(tempX)
        dataY.append(tempY)
        dataC.append(tempC)
    
    npdataX = np.vstack(dataX)
    npdataY = np.vstack(dataY)
    npdataC = np.vstack(dataC)

    if return_obj:
        return npdataX, npdataY, npdataC, abf
    else:
        return npdataX, npdataY, npdataC
