"""
Visualizer — generates charts for the speech pitch contour and melody piano roll.
Returns base64-encoded PNG strings for embedding in the web UI.
"""

import io
import base64
import numpy as np
import matplotlib
matplotlib.use("Agg")  # Non-interactive backend
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.colors import LinearSegmentedColormap

from .pitch_extractor import PitchContour
from .scale_mapper import Melody, midi_to_name


# ─── Color palette ────────────────────────────────────────────────────────────
ACCENT   = "#6EE7B7"   # Mint green
ACCENT2  = "#A78BFA"   # Purple
ACCENT3  = "#F472B6"   # Pink
BG       = "#0F172A"   # Dark navy
GRID     = "#1E293B"
TEXT     = "#CBD5E1"
ORANGE   = "#FB923C"


def fig_to_base64(fig) -> str:
    """Render a matplotlib figure to a base64 PNG string."""
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=130, bbox_inches="tight",
                facecolor=BG, edgecolor="none")
    buf.seek(0)
    img_b64 = base64.b64encode(buf.read()).decode("utf-8")
    plt.close(fig)
    return img_b64


def plot_pitch_contour(contour: PitchContour) -> str:
    """
    Plot the raw pitch contour extracted from speech:
    - Waveform (top)
    - F0 contour with voiced/unvoiced coloring (bottom)
    """
    fig, axes = plt.subplots(2, 1, figsize=(10, 5.5), facecolor=BG)
    fig.subplots_adjust(hspace=0.4)

    # ── Waveform ────────────────────────────────────────────────────────────
    ax1 = axes[0]
    ax1.set_facecolor(BG)
    t_audio = np.linspace(0, contour.duration, len(contour.audio))
    ax1.plot(t_audio, contour.audio, color=ACCENT2, linewidth=0.6, alpha=0.8)
    ax1.fill_between(t_audio, contour.audio, alpha=0.15, color=ACCENT2)
    ax1.set_xlim(0, contour.duration)
    ax1.set_ylabel("Amplitude", color=TEXT, fontsize=9)
    ax1.set_title("Speech Waveform", color=TEXT, fontsize=10, pad=6)
    ax1.tick_params(colors=TEXT, labelsize=8)
    for spine in ax1.spines.values():
        spine.set_edgecolor(GRID)
    ax1.set_xlabel("")

    # ── F0 Contour ──────────────────────────────────────────────────────────
    ax2 = axes[1]
    ax2.set_facecolor(BG)

    times = contour.times
    f0 = contour.frequencies.copy()

    # Plot voiced and unvoiced separately
    voiced_mask = contour.voiced_flags & ~np.isnan(f0)
    unvoiced_mask = ~contour.voiced_flags

    # Voiced segments
    voiced_times = np.where(voiced_mask, times, np.nan)
    voiced_f0    = np.where(voiced_mask, f0, np.nan)
    ax2.plot(voiced_times, voiced_f0, color=ACCENT, linewidth=2.0, label="Voiced", zorder=3)

    # Dots at voiced frames
    ax2.scatter(
        times[voiced_mask], f0[voiced_mask],
        s=12, color=ACCENT, zorder=4, alpha=0.6
    )

    # Shade unvoiced regions
    for i in range(len(times) - 1):
        if unvoiced_mask[i]:
            ax2.axvspan(times[i], times[i+1], color=GRID, alpha=0.4, linewidth=0)

    ax2.set_xlim(0, contour.duration)
    valid_f0 = f0[voiced_mask]
    if len(valid_f0) > 0:
        ax2.set_ylim(max(0, np.nanmin(valid_f0) * 0.85), np.nanmax(valid_f0) * 1.15)
    ax2.set_xlabel("Time (s)", color=TEXT, fontsize=9)
    ax2.set_ylabel("Frequency (Hz)", color=TEXT, fontsize=9)
    ax2.set_title("Pitch Contour (F0)", color=TEXT, fontsize=10, pad=6)
    ax2.tick_params(colors=TEXT, labelsize=8)
    ax2.grid(True, color=GRID, linestyle="--", linewidth=0.5, alpha=0.7)
    for spine in ax2.spines.values():
        spine.set_edgecolor(GRID)

    voiced_patch = mpatches.Patch(color=ACCENT, label="Voiced")
    ax2.legend(handles=[voiced_patch], facecolor=BG, edgecolor=GRID,
               labelcolor=TEXT, fontsize=8, loc="upper right")

    return fig_to_base64(fig)


def plot_piano_roll(melody: Melody) -> str:
    """
    Piano roll visualization — shows the generated melody as colored note bars,
    like a DAW/sequencer view.
    """
    if not melody.notes:
        fig, ax = plt.subplots(figsize=(10, 4), facecolor=BG)
        ax.text(0.5, 0.5, "No notes to display", color=TEXT,
                ha="center", va="center", transform=ax.transAxes)
        return fig_to_base64(fig)

    fig, ax = plt.subplots(figsize=(10, 5.5), facecolor=BG)
    ax.set_facecolor(BG)

    # Color gradient based on velocity
    cmap = LinearSegmentedColormap.from_list(
        "melody", [ACCENT2, ACCENT, ACCENT3], N=128
    )

    midi_values = [n.midi for n in melody.notes]
    min_midi = min(midi_values) - 2
    max_midi = max(midi_values) + 2

    # Draw octave lines
    for midi in range(min_midi, max_midi + 1):
        if midi % 12 == 0:  # C notes
            ax.axhline(midi, color=GRID, linewidth=0.8, alpha=0.6, linestyle="--")

    # Draw note rectangles
    for note in melody.notes:
        color = cmap(note.velocity / 127)
        rect = mpatches.FancyBboxPatch(
            (note.start_time, note.midi - 0.38),
            width=note.duration * 0.92,
            height=0.76,
            boxstyle="round,pad=0.02",
            facecolor=color,
            edgecolor="none",
            alpha=0.9,
            zorder=3,
        )
        ax.add_patch(rect)

        # Note label if note is long enough
        if note.duration > 0.15:
            ax.text(
                note.start_time + note.duration * 0.05,
                note.midi,
                note.name,
                color=BG,
                fontsize=6.5,
                va="center",
                fontweight="bold",
                zorder=4,
            )

    # Y-axis: note names
    y_ticks = list(range(min_midi, max_midi + 1))
    y_labels = [midi_to_name(m) for m in y_ticks]
    ax.set_yticks(y_ticks)
    ax.set_yticklabels(y_labels, fontsize=7.5, color=TEXT)
    ax.set_ylim(min_midi - 0.5, max_midi + 0.5)

    ax.set_xlim(-0.1, melody.total_duration + 0.5)
    ax.set_xlabel("Time (s)", color=TEXT, fontsize=9)
    ax.set_title(
        f"Piano Roll — {melody.root} {melody.scale.replace('_', ' ').title()}  "
        f"({len(melody.notes)} notes)",
        color=TEXT, fontsize=10, pad=8,
    )
    ax.tick_params(colors=TEXT, labelsize=8, axis="x")
    ax.grid(True, axis="x", color=GRID, linestyle="--", linewidth=0.4, alpha=0.6)
    for spine in ax.spines.values():
        spine.set_edgecolor(GRID)

    # Colorbar for velocity
    sm = plt.cm.ScalarMappable(cmap=cmap, norm=plt.Normalize(0, 127))
    sm.set_array([])
    cb = fig.colorbar(sm, ax=ax, orientation="vertical", pad=0.01, fraction=0.015)
    cb.set_label("Velocity", color=TEXT, fontsize=8)
    cb.ax.yaxis.set_tick_params(color=TEXT, labelsize=7)
    plt.setp(cb.ax.yaxis.get_ticklabels(), color=TEXT)
    cb.outline.set_edgecolor(GRID)

    return fig_to_base64(fig)


def plot_scale_mapping(melody: Melody, contour: PitchContour) -> str:
    """
    Scatter plot showing how each raw speech F0 was mapped to a scale note.
    Shows the 'quantization' process visually.
    """
    if not melody.notes:
        return ""

    fig, ax = plt.subplots(figsize=(10, 4.5), facecolor=BG)
    ax.set_facecolor(BG)

    raw_f0s = [n.original_f0 for n in melody.notes]
    mapped_freqs = [n.frequency for n in melody.notes]
    times = [n.start_time for n in melody.notes]

    # Raw pitch
    ax.scatter(times, raw_f0s, color=ORANGE, s=25, zorder=4,
               label="Raw Speech F0", alpha=0.85)

    # Mapped notes
    ax.scatter(times, mapped_freqs, color=ACCENT, s=35, zorder=5,
               marker="D", label="Quantized to Scale", alpha=0.9)

    # Lines connecting raw → mapped
    for t, r, m in zip(times, raw_f0s, mapped_freqs):
        ax.plot([t, t], [r, m], color=ACCENT2, linewidth=0.8, alpha=0.5, zorder=2)

    ax.set_xlabel("Time (s)", color=TEXT, fontsize=9)
    ax.set_ylabel("Frequency (Hz)", color=TEXT, fontsize=9)
    ax.set_title(
        f"Scale Quantization — Speech F0 → {melody.root} {melody.scale.replace('_', ' ').title()}",
        color=TEXT, fontsize=10, pad=8,
    )
    ax.tick_params(colors=TEXT, labelsize=8)
    ax.grid(True, color=GRID, linestyle="--", linewidth=0.4, alpha=0.6)
    for spine in ax.spines.values():
        spine.set_edgecolor(GRID)
    ax.legend(facecolor=BG, edgecolor=GRID, labelcolor=TEXT, fontsize=8)

    return fig_to_base64(fig)
