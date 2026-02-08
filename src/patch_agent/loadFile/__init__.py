"""
loadFile - Vendored I/O module from pyAPisolation

Provides unified loading interface for ABF and NWB electrophysiology files.
Original source: https://github.com/smestern/pyAPisolation/tree/master/pyAPisolation/loadFile
"""

from .loadNWB import loadNWB, loadFile, NWBRecording
from .loadABF import loadABF

__all__ = ["loadFile", "loadABF", "loadNWB", "NWBRecording"]
