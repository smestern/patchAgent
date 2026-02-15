"""Passive membrane property extraction using patchAgent tools.

Selects hyperpolarizing sweeps and calculates input resistance,
membrane time constant, sag ratio, and resting potential.

Usage:
    python passive_properties.py <path_to_file>
"""
import sys
from patch_agent.tools import (
    load_file,
    list_sweeps,
    calculate_input_resistance,
    calculate_time_constant,
    calculate_sag,
    calculate_resting_potential,
)


def main(file_path: str):
    # 1. Load file
    data = load_file(file_path)
    sweeps = list_sweeps(data)
    print(f"Loaded {sweeps['sweep_count']} sweeps from {file_path}")

    # 2. Find hyperpolarizing sweeps (negative current)
    hyper_sweeps = [
        s for s in sweeps["sweep_info"]
        if s["stim_amplitude"] < -10  # at least -10 pA
    ]

    if not hyper_sweeps:
        print("No hyperpolarizing sweeps found — cannot extract passive properties.")
        return

    print(f"Found {len(hyper_sweeps)} hyperpolarizing sweeps")

    # 3. Use the largest hyperpolarizing sweep for best SNR
    best = min(hyper_sweeps, key=lambda s: s["stim_amplitude"])
    idx = best["index"]
    t = data["dataX"][idx]
    v = data["dataY"][idx]
    c = data["dataC"][idx]
    print(f"Using sweep {idx} ({best['stim_amplitude']:.0f} pA)")

    # 4. Calculate passive properties
    rm = calculate_input_resistance(v, t, c)
    tau = calculate_time_constant(v, t)
    sag = calculate_sag(v, t, c)
    vrest = calculate_resting_potential(v, t)

    print(f"\n=== Passive Properties ===")
    print(f"  Input resistance: {rm.get('input_resistance_MOhm', 'N/A')} MOhm")
    print(f"  Time constant:    {tau.get('tau_ms', 'N/A')} ms")
    print(f"  Sag ratio:        {sag.get('sag_ratio', 'N/A')}")
    print(f"  Resting Vm:       {vrest.get('resting_potential_mV', 'N/A')} mV")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python passive_properties.py <path_to_file>")
        sys.exit(1)
    main(sys.argv[1])
