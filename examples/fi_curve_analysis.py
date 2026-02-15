"""F-I curve analysis using patchAgent tools.

Loads an electrophysiology file, detects spikes in each sweep, builds a
frequency-current (f-I) curve, and fits it to extract gain and rheobase.

Usage:
    python fi_curve_analysis.py <path_to_file>
"""
import sys
from patch_agent.tools import load_file, list_sweeps, detect_spikes, fit_fi_curve


def main(file_path: str):
    # 1. Load file
    data = load_file(file_path)
    sweeps = list_sweeps(data)
    print(f"Loaded {sweeps['sweep_count']} sweeps from {file_path}")

    # 2. Detect spikes in each sweep and build f-I data
    currents = []
    firing_rates = []
    for sweep_info in sweeps["sweep_info"]:
        idx = sweep_info["index"]
        t = data["dataX"][idx]
        v = data["dataY"][idx]
        c = data["dataC"][idx]

        spikes = detect_spikes(v, t)
        n_spikes = spikes.get("spike_count", 0)

        # Estimate stimulus duration from command waveform
        stim_mask = abs(c) > 0.5  # pA threshold
        if stim_mask.any():
            stim_dur = float(t[stim_mask][-1] - t[stim_mask][0])
        else:
            stim_dur = 1.0

        rate = n_spikes / stim_dur if stim_dur > 0 else 0.0
        currents.append(sweep_info["stim_amplitude"])
        firing_rates.append(rate)

        if n_spikes > 0:
            print(f"  Sweep {idx}: {n_spikes} spikes, {rate:.1f} Hz @ {sweep_info['stim_amplitude']:.0f} pA")

    # 3. Fit f-I curve
    fi_result = fit_fi_curve(currents, firing_rates)
    print(f"\n=== F-I Curve Fit ===")
    print(f"  Gain:     {fi_result.get('gain', 'N/A')} Hz/pA")
    print(f"  Rheobase: {fi_result.get('rheobase', 'N/A')} pA")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python fi_curve_analysis.py <path_to_file>")
        sys.exit(1)
    main(sys.argv[1])
