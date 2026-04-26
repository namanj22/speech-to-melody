#!/usr/bin/env python3
"""
Demo / Test script — generates a synthetic "speech-like" signal
and runs the full Speech-to-Melody pipeline on it.

This lets you verify everything works without needing a real microphone.
"""

import sys
import numpy as np
import soundfile as sf
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))


def generate_synthetic_speech(output_path: str, sr: int = 22050, duration: float = 4.0) -> str:
    """
    Generate a synthetic pitched signal that mimics speech prosody.
    Uses a voiced source model: glottal pulses + formant-like bandpass filters.
    
    The F0 follows a sentence-like intonation contour (rises then falls).
    """
    print("  Generating synthetic speech signal...")
    t = np.arange(int(duration * sr)) / sr

    # F0 contour — mimics sentence intonation
    # Rises in first half, falls at end (like a spoken question)
    f0_contour = (
        180  +
        40  * np.sin(2 * np.pi * 0.5 * t) +
        25  * np.sin(2 * np.pi * 1.1 * t) +
        15  * np.cos(2 * np.pi * 0.3 * t)
    )

    # Generate sawtooth-like glottal source (voiced speech)
    phase = np.cumsum(f0_contour / sr) * 2 * np.pi
    source = np.sin(phase) + 0.3 * np.sin(2 * phase) + 0.1 * np.sin(3 * phase)

    # Add unvoiced (silence) gaps between "syllables"
    # Modulate amplitude with syllable rhythm
    syllable_rate = 4.5  # syllables per second
    amplitude_env = np.abs(np.sin(np.pi * syllable_rate * t)) ** 0.5
    # Hard-gate low amplitude regions (simulate consonant stops)
    gate = (amplitude_env > 0.25).astype(float)
    # Smooth the gate
    from scipy.signal import medfilt
    gate = medfilt(gate, 11)

    signal = source * amplitude_env * gate

    # Add a bit of noise (breathiness)
    signal += np.random.randn(len(signal)) * 0.03

    # Normalize
    signal = signal / np.max(np.abs(signal)) * 0.8

    sf.write(output_path, signal, sr)
    return output_path


def run_demo():
    from core import (
        extract_pitch, get_pitch_statistics,
        map_pitch_to_melody, SCALES,
        synthesize_melody, SYNTHESIZERS,
        write_midi,
        plot_pitch_contour, plot_piano_roll, plot_scale_mapping,
    )

    print("\n" + "═" * 55)
    print("  🎼  Speech → Melody  |  Full Pipeline Demo")
    print("═" * 55)

    # ── 1. Generate synthetic speech ──────────────────────────
    speech_path = "/tmp/demo_speech.wav"
    generate_synthetic_speech(speech_path)
    print(f"  ✓ Synthetic speech: {speech_path}")

    # ── 2. Extract pitch ───────────────────────────────────────
    print("\n  [1/5] Extracting pitch contour (pyin)...")
    contour = extract_pitch(speech_path)
    stats = get_pitch_statistics(contour)
    if "error" in stats:
        print(f"  ✗ {stats['error']}")
        return
    print(f"       Duration     : {stats['duration']:.2f}s")
    print(f"       Voiced ratio : {stats['voiced_ratio']*100:.1f}%")
    print(f"       Mean F0      : {stats['mean_hz']:.1f} Hz")
    print(f"       F0 range     : {stats['range_semitones']:.1f} semitones")

    # ── 3. Test multiple scales ────────────────────────────────
    test_cases = [
        ("pentatonic_minor", "C", "piano"),
        ("major",            "G", "flute"),
        ("blues",            "A", "pluck"),
        ("dorian",           "D", "marimba"),
        ("hirajoshi",        "E", "sine"),
    ]

    for scale, root, instrument in test_cases:
        print(f"\n  [Scale] {root} {scale} / {instrument}")

        melody = map_pitch_to_melody(contour, scale=scale, root=root)
        print(f"         {len(melody.notes)} notes  |  BPM ≈ {melody.tempo_bpm:.0f}")

        out_wav  = f"/tmp/demo_{scale}_{root}_{instrument}.wav"
        out_mid  = f"/tmp/demo_{scale}_{root}_{instrument}.mid"

        synthesize_melody(melody, instrument=instrument, output_path=out_wav)
        write_midi(melody, out_mid)

        print(f"         WAV  → {out_wav}")
        print(f"         MIDI → {out_mid}")

    # ── 4. Generate visualizations for the first scale ─────────
    print("\n  [5/5] Generating visualizations...")
    melody = map_pitch_to_melody(contour, scale="pentatonic_minor", root="C")

    viz_pitch   = plot_pitch_contour(contour)
    viz_piano   = plot_piano_roll(melody)
    viz_mapping = plot_scale_mapping(melody, contour)

    # Save as PNG files
    import base64
    for name, b64 in [("pitch_contour", viz_pitch), ("piano_roll", viz_piano), ("scale_mapping", viz_mapping)]:
        png_path = f"/tmp/demo_{name}.png"
        with open(png_path, "wb") as f:
            f.write(base64.b64decode(b64))
        print(f"         Chart → {png_path}")

    print("\n" + "═" * 55)
    print("  ✅  All tests passed!")
    print("  Output files in /tmp/demo_*.wav  /tmp/demo_*.mid  /tmp/demo_*.png")
    print("═" * 55)
    print("\n  🚀  To start the web app, run:  python app.py")
    print()


if __name__ == "__main__":
    run_demo()
