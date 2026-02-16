"""Detailed spike feature analysis using patchAgent tools.

Detects spikes, extracts single-spike features (threshold, amplitude,
width, rise/fall kinetics), and spike train features (adaptation, ISI).

Usage:
    python spike_analysis.py <path_to_file>
"""
import sys
from patchagent.tools import (
    load_file,
    list_sweeps,
    detect_spikes,
    extract_spike_features,
    extract_spike_train_features,
)


def main(file_path: str):
    # 1. Load file
    data = load_file(file_path)
    sweeps = list_sweeps(data)
    print(f"Loaded {sweeps['sweep_count']} sweeps from {file_path}")

    # 2. Find a sweep with spikes (suprathreshold)
    spiking_sweep = None
    for s in sweeps["sweep_info"]:
        idx = s["index"]
        v = data["dataY"][idx]
        t = data["dataX"][idx]
        result = detect_spikes(v, t)
        if result.get("spike_count", 0) > 0:
            spiking_sweep = idx
            n = result["spike_count"]
            print(f"  Sweep {idx}: {n} spikes detected")
            break

    if spiking_sweep is None:
        print("No spiking sweeps found in this file.")
        return

    t = data["dataX"][spiking_sweep]
    v = data["dataY"][spiking_sweep]

    # 3. Extract single-spike features
    features = extract_spike_features(v, t)
    print(f"\n=== Single-spike features (sweep {spiking_sweep}) ===")
    for key in [
        "threshold_mV",
        "amplitude_mV",
        "width_ms",
        "rise_rate_mV_per_ms",
        "fall_rate_mV_per_ms",
    ]:
        val = features.get(key, "N/A")
        print(f"  {key}: {val}")

    # 4. Extract spike train features
    train = extract_spike_train_features(v, t)
    print(f"\n=== Spike train features (sweep {spiking_sweep}) ===")
    for key in [
        "spike_count",
        "mean_firing_rate_Hz",
        "adaptation_index",
        "mean_isi_ms",
        "cv_isi",
    ]:
        val = train.get(key, "N/A")
        print(f"  {key}: {val}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python spike_analysis.py <path_to_file>")
        sys.exit(1)
    main(sys.argv[1])
