from patchagent.loadFile import loadFile
import numpy as np
from scipy.signal import find_peaks
from scipy.optimize import curve_fit
import matplotlib.pyplot as plt

file = r'M:\Users\SMest\source\repos\dataclub_2\data\EPSP_NOISE_2_NEW_2\repeating_EPSP_NOISE\2022_03_24_0003.abf'
dataX, dataY, dataC = loadFile(file)

t = dataX[0]
v = dataY[0]
dt = np.mean(np.diff(t))

# Detect EPSPs
dv_dt = np.gradient(v, t)
peaks, _ = find_peaks(dv_dt, height=3, distance=int(0.008/dt))
good_peaks = [p for p in peaks if np.max(v[p:min(p+int(0.01/dt), len(v))]) < -10]
good_peaks = np.array(good_peaks)

def single_exp(t, A, tau, C):
    return A * np.exp(-t / tau) + C

# Collect fitting data
fit_data = []

for i, onset_idx in enumerate(good_peaks):
    search_window = int(0.003 / dt)
    peak_idx = onset_idx + np.argmax(v[onset_idx:onset_idx+search_window])
    
    decay_duration = int(0.005 / dt)
    decay_start = peak_idx
    decay_end = min(decay_start + decay_duration, len(v))
    
    if i < len(good_peaks) - 1:
        next_onset = good_peaks[i+1]
        if next_onset < decay_end:
            decay_end = next_onset - int(0.001/dt)
    
    if decay_end - decay_start < 50:
        continue
    
    t_decay = t[decay_start:decay_end] - t[decay_start]
    v_decay = v[decay_start:decay_end]
    
    try:
        p0 = [v_decay[0] - v_decay[-1], 0.003, v_decay[-1]]
        bounds = ([0, 0.0005, -70], [15, 0.015, -30])
        popt, _ = curve_fit(single_exp, t_decay, v_decay, p0=p0, bounds=bounds, maxfev=5000)
        
        A, tau, C = popt
        v_fit = single_exp(t_decay, *popt)
        
        ss_res = np.sum((v_decay - v_fit)**2)
        ss_tot = np.sum((v_decay - np.mean(v_decay))**2)
        r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0
        
        if r_squared > 0.3 and 0.5 < tau*1000 < 15 and A > 0.05:
            fit_data.append({
                'time': t[onset_idx],
                'tau_ms': tau * 1000,
                'amp': A,
                'baseline': C,
                'r2': r_squared,
                't_decay': t_decay,
                'v_decay': v_decay,
                'v_fit': v_fit
            })
    except:
        pass

taus = np.array([d['tau_ms'] for d in fit_data])
times = np.array([d['time'] for d in fit_data])
amps = np.array([d['amp'] for d in fit_data])
r2s = np.array([d['r2'] for d in fit_data])

# Create plot
fig = plt.figure(figsize=(16, 12))
gs = fig.add_gridspec(4, 4, hspace=0.3, wspace=0.3)

# Tau over time
ax1 = fig.add_subplot(gs[0, :])
scatter = ax1.scatter(times, taus, c=r2s, cmap='viridis', s=30, alpha=0.7)
ax1.axhline(np.mean(taus), color='r', linestyle='--', linewidth=2, label=f'Mean={np.mean(taus):.2f} ms')
ax1.axhline(np.median(taus), color='orange', linestyle='--', linewidth=2, label=f'Median={np.median(taus):.2f} ms')
ax1.set_xlabel('Time (s)', fontsize=12)
ax1.set_ylabel('Decay τ (ms)', fontsize=12)
ax1.set_title(f'EPSP Decay Time Constants (N={len(taus)})', fontsize=14, fontweight='bold')
ax1.legend(fontsize=10)
ax1.grid(True, alpha=0.3)
cbar = plt.colorbar(scatter, ax=ax1)
cbar.set_label('Fit R²', fontsize=10)

# Histogram
ax2 = fig.add_subplot(gs[1, 0])
ax2.hist(taus, bins=20, edgecolor='black', alpha=0.7)
ax2.axvline(np.mean(taus), color='r', linestyle='--', linewidth=2)
ax2.set_xlabel('Decay τ (ms)', fontsize=11)
ax2.set_ylabel('Count', fontsize=11)
ax2.set_title('Distribution', fontsize=12)
ax2.grid(True, alpha=0.3)

# Amp vs tau
ax3 = fig.add_subplot(gs[1, 1])
ax3.scatter(amps, taus, c=r2s, cmap='viridis', s=30, alpha=0.7)
ax3.set_xlabel('Amplitude (mV)', fontsize=11)
ax3.set_ylabel('Decay τ (ms)', fontsize=11)
ax3.set_title('Amplitude vs Tau', fontsize=12)
ax3.grid(True, alpha=0.3)

# R² dist
ax4 = fig.add_subplot(gs[1, 2])
ax4.hist(r2s, bins=20, edgecolor='black', alpha=0.7, color='green')
ax4.set_xlabel('R²', fontsize=11)
ax4.set_ylabel('Count', fontsize=11)
ax4.set_title('Fit Quality', fontsize=12)
ax4.grid(True, alpha=0.3)

# Amplitude dist
ax5 = fig.add_subplot(gs[1, 3])
ax5.hist(amps, bins=20, edgecolor='black', alpha=0.7, color='coral')
ax5.set_xlabel('Amplitude (mV)', fontsize=11)
ax5.set_ylabel('Count', fontsize=11)
ax5.set_title('Amplitude Dist', fontsize=12)
ax5.grid(True, alpha=0.3)

# Example fits
sorted_idx = np.argsort(r2s)[::-1]
for plot_i in range(6):
    ax = fig.add_subplot(gs[2 + plot_i//3, plot_i%3])
    if plot_i < len(sorted_idx):
        idx = sorted_idx[plot_i]
        d = fit_data[idx]
        ax.plot(d['t_decay']*1000, d['v_decay'], 'k.', markersize=4, label='Data')
        ax.plot(d['t_decay']*1000, d['v_fit'], 'r-', linewidth=2, label='Fit')
        ax.set_title(f"τ={d['tau_ms']:.2f} ms, R²={d['r2']:.3f}", fontsize=10)
        ax.set_xlabel('Time (ms)', fontsize=9)
        ax.set_ylabel('V (mV)', fontsize=9)
        ax.legend(fontsize=8)
        ax.grid(True, alpha=0.3)

plt.suptitle('EPSP Decay Analysis', fontsize=16, fontweight='bold', y=0.995)
plt.savefig(r'C:\Users\SMest\Dropbox\patchAgent\output\epsp_decay_summary.png', dpi=150, bbox_inches='tight')
print('✓ Summary plot saved')
