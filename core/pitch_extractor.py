"""
Pitch Extractor — extracts fundamental frequency (F0) contours from speech audio.
Uses librosa's pyin algorithm which is robust for speech signals.
"""

import numpy as np
import librosa
import soundfile as sf
from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass
class PitchContour:
    """Holds the raw pitch extraction results."""
    times: np.ndarray          # Time stamps (seconds)
    frequencies: np.ndarray    # F0 in Hz (NaN where unvoiced)
    voiced_flags: np.ndarray   # Boolean mask for voiced frames
    voiced_probs: np.ndarray   # Confidence probabilities
    sr: int                    # Sample rate
    duration: float            # Total audio duration
    audio: np.ndarray          # Raw audio signal


def load_audio(file_path: str, target_sr: int = 22050) -> Tuple[np.ndarray, int]:
    """Load audio file and resample to target sample rate."""
    audio, sr = librosa.load(file_path, sr=target_sr, mono=True)
    return audio, sr


def extract_pitch(
    file_path: str,
    sr: int = 22050,
    frame_length: int = 2048,
    hop_length: int = 512,
    fmin: float = 50.0,    # Hz — lower bound for speech F0
    fmax: float = 800.0,   # Hz — upper bound for speech F0
) -> PitchContour:
    """
    Extract pitch contour from a speech audio file using the pyin algorithm.
    
    pyin (Probabilistic YIN) is significantly better than basic autocorrelation
    for speech — it handles noise, octave errors, and unvoiced regions well.
    """
    audio, sr = load_audio(file_path, sr)
    duration = len(audio) / sr

    # pyin returns F0 estimates, voiced flags, and voiced probabilities
    f0, voiced_flag, voiced_probs = librosa.pyin(
        audio,
        fmin=fmin,
        fmax=fmax,
        sr=sr,
        frame_length=frame_length,
        hop_length=hop_length,
        fill_na=np.nan,
    )

    times = librosa.times_like(f0, sr=sr, hop_length=hop_length)

    return PitchContour(
        times=times,
        frequencies=f0,
        voiced_flags=voiced_flag,
        voiced_probs=voiced_probs,
        sr=sr,
        duration=duration,
        audio=audio,
    )


def smooth_pitch_contour(
    contour: PitchContour,
    smoothing_window: int = 5
) -> np.ndarray:
    """
    Smooth the pitch contour using a median filter on voiced regions.
    Fills short gaps by interpolation to produce a continuous melodic line.
    """
    f0 = contour.frequencies.copy()

    # Interpolate over short unvoiced gaps (up to ~100ms)
    voiced_idx = np.where(contour.voiced_flags)[0]
    if len(voiced_idx) == 0:
        return f0

    # Linear interpolation over NaN gaps
    nan_mask = np.isnan(f0)
    x_valid = np.where(~nan_mask)[0]
    if len(x_valid) >= 2:
        x_all = np.arange(len(f0))
        f0_interp = np.interp(x_all, x_valid, f0[x_valid])
        # Only fill gaps that are short (< 10 frames ~ 100ms at hop=512, sr=22050)
        gap_mask = nan_mask.copy()
        from scipy.ndimage import label
        labeled, n_gaps = label(gap_mask)
        for gap_id in range(1, n_gaps + 1):
            gap_region = labeled == gap_id
            if gap_region.sum() <= 10:
                f0[gap_region] = f0_interp[gap_region]

    # Apply median smoothing on voiced+interpolated sections
    from scipy.signal import medfilt
    voiced_or_interp = ~np.isnan(f0)
    if voiced_or_interp.sum() > smoothing_window:
        f0_smooth = f0.copy()
        valid = voiced_or_interp
        f0_smooth[valid] = medfilt(f0[valid], kernel_size=smoothing_window)
        return f0_smooth

    return f0


def get_pitch_statistics(contour: PitchContour) -> dict:
    """Compute useful statistics about the extracted pitch contour."""
    voiced_freqs = contour.frequencies[contour.voiced_flags]

    if len(voiced_freqs) == 0:
        return {"error": "No voiced segments detected"}

    return {
        "mean_hz": float(np.nanmean(voiced_freqs)),
        "median_hz": float(np.nanmedian(voiced_freqs)),
        "min_hz": float(np.nanmin(voiced_freqs)),
        "max_hz": float(np.nanmax(voiced_freqs)),
        "range_semitones": float(
            12 * np.log2(np.nanmax(voiced_freqs) / np.nanmin(voiced_freqs))
        ),
        "voiced_ratio": float(contour.voiced_flags.sum() / len(contour.voiced_flags)),
        "duration": contour.duration,
        "total_frames": len(contour.frequencies),
        "voiced_frames": int(contour.voiced_flags.sum()),
    }
