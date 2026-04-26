"""
Scale Mapper — maps raw pitch contours onto musical scales to produce melodies.

Handles:
- MIDI note quantization
- Multiple scale/mode definitions
- Rhythm generation from speech timing
- Note deduplication and musical cleanup
"""

import numpy as np
from dataclasses import dataclass
from typing import Optional, List, Dict, Tuple
from .pitch_extractor import PitchContour, smooth_pitch_contour

# ─────────────────────────────────────────────
# Scale Definitions (intervals in semitones from root)
# ─────────────────────────────────────────────

SCALES = {
    # Diatonic modes
    "major":              [0, 2, 4, 5, 7, 9, 11],
    "natural_minor":      [0, 2, 3, 5, 7, 8, 10],
    "harmonic_minor":     [0, 2, 3, 5, 7, 8, 11],
    "melodic_minor":      [0, 2, 3, 5, 7, 9, 11],
    "dorian":             [0, 2, 3, 5, 7, 9, 10],
    "phrygian":           [0, 1, 3, 5, 7, 8, 10],
    "lydian":             [0, 2, 4, 6, 7, 9, 11],
    "mixolydian":         [0, 2, 4, 5, 7, 9, 10],
    "locrian":            [0, 1, 3, 5, 6, 8, 10],
    # Pentatonic
    "pentatonic_major":   [0, 2, 4, 7, 9],
    "pentatonic_minor":   [0, 3, 5, 7, 10],
    # Exotic / World
    "blues":              [0, 3, 5, 6, 7, 10],
    "whole_tone":         [0, 2, 4, 6, 8, 10],
    "diminished":         [0, 2, 3, 5, 6, 8, 9, 11],
    "chromatic":          list(range(12)),
    "japanese_in":        [0, 1, 5, 7, 8],
    "arabic":             [0, 2, 3, 6, 7, 8, 11],
    "hungarian_minor":    [0, 2, 3, 6, 7, 8, 11],
    "flamenco":           [0, 1, 4, 5, 7, 8, 11],
    "hirajoshi":          [0, 2, 3, 7, 8],
}

SCALE_DISPLAY_NAMES = {
    "major": "Major (Ionian)",
    "natural_minor": "Natural Minor (Aeolian)",
    "harmonic_minor": "Harmonic Minor",
    "melodic_minor": "Melodic Minor",
    "dorian": "Dorian Mode",
    "phrygian": "Phrygian Mode",
    "lydian": "Lydian Mode",
    "mixolydian": "Mixolydian Mode",
    "locrian": "Locrian Mode",
    "pentatonic_major": "Pentatonic Major",
    "pentatonic_minor": "Pentatonic Minor",
    "blues": "Blues Scale",
    "whole_tone": "Whole Tone",
    "diminished": "Diminished",
    "chromatic": "Chromatic",
    "japanese_in": "Japanese In Scale",
    "arabic": "Arabic Scale",
    "hungarian_minor": "Hungarian Minor",
    "flamenco": "Flamenco",
    "hirajoshi": "Hirajoshi",
}

NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
ROOT_MIDI = {note: i for i, note in enumerate(NOTE_NAMES)}


@dataclass
class MelodyNote:
    """Represents a single melody note."""
    midi: int           # MIDI note number (21-108 for standard piano)
    frequency: float    # Hz
    start_time: float   # seconds
    duration: float     # seconds
    velocity: int       # 0-127 (loudness / emphasis)
    name: str           # e.g. "C4", "G#5"
    original_f0: float  # The raw speech F0 this was mapped from


@dataclass 
class Melody:
    """The complete generated melody."""
    notes: List[MelodyNote]
    scale: str
    root: str
    root_midi: int
    tempo_bpm: float
    total_duration: float
    scale_notes_used: List[int]  # Which MIDI notes appear


def hz_to_midi(freq_hz: float) -> float:
    """Convert frequency in Hz to continuous MIDI note number."""
    return 12 * np.log2(freq_hz / 440.0) + 69


def midi_to_hz(midi: float) -> float:
    """Convert MIDI note number to frequency in Hz."""
    return 440.0 * (2 ** ((midi - 69) / 12))


def midi_to_name(midi: int) -> str:
    """Convert MIDI number to note name e.g. 60 -> 'C4'."""
    note = NOTE_NAMES[midi % 12]
    octave = (midi // 12) - 1
    return f"{note}{octave}"


def quantize_to_scale(
    midi_float: float,
    scale_intervals: List[int],
    root_midi: int = 60,
    octave_range: Tuple = (2, 6),
) -> int:
    """
    Snap a continuous MIDI value to the nearest note in a given scale.
    Searches across multiple octaves to find the absolute closest scale note.
    """
    best_midi = None
    best_dist = float("inf")

    for octave in range(octave_range[0], octave_range[1] + 1):
        for interval in scale_intervals:
            candidate = root_midi + interval + (octave - 4) * 12
            # Clamp to piano range
            if candidate < 21 or candidate > 108:
                continue
            dist = abs(midi_float - candidate)
            if dist < best_dist:
                best_dist = dist
                best_midi = candidate

    return best_midi if best_midi is not None else int(round(midi_float))


def extract_note_segments(
    f0_smooth: np.ndarray,
    times: np.ndarray,
    voiced_flags: np.ndarray,
    min_note_duration: float = 0.08,   # seconds — shorter than this gets dropped
    pitch_stability_threshold: float = 50.0,  # Hz — merge similar adjacent pitches
) -> List[Dict]:
    """
    Segment the pitch contour into discrete note events.
    Groups consecutive voiced frames with similar pitch into single notes.
    """
    segments = []
    if len(times) < 2:
        return segments

    hop_duration = times[1] - times[0]

    i = 0
    while i < len(f0_smooth):
        if not voiced_flags[i] or np.isnan(f0_smooth[i]):
            i += 1
            continue

        # Start of a voiced segment
        seg_start = i
        seg_freqs = [f0_smooth[i]]

        j = i + 1
        while j < len(f0_smooth):
            if not voiced_flags[j] or np.isnan(f0_smooth[j]):
                # Allow short unvoiced gaps (up to 3 frames)
                gap_end = min(j + 3, len(f0_smooth))
                has_voice_after = any(
                    voiced_flags[k] and not np.isnan(f0_smooth[k])
                    for k in range(j, gap_end)
                )
                if has_voice_after and (gap_end - j) <= 3:
                    j = gap_end
                    continue
                break

            # Check if pitch has drifted significantly (new note territory)
            curr_freq = f0_smooth[j]
            median_so_far = np.median(seg_freqs)
            if abs(curr_freq - median_so_far) > pitch_stability_threshold:
                break

            seg_freqs.append(curr_freq)
            j += 1

        duration = (j - seg_start) * hop_duration
        if duration >= min_note_duration:
            segments.append({
                "start_time": times[seg_start],
                "duration": duration,
                "mean_freq": float(np.median(seg_freqs)),
                "freq_std": float(np.std(seg_freqs)),
                "frame_count": j - seg_start,
            })

        i = j if j > i else i + 1

    return segments


def compute_velocity(freq_std: float, duration: float) -> int:
    """
    Estimate note velocity (dynamics) from pitch stability and duration.
    More stable, longer notes get higher velocity (more prominent).
    """
    stability = max(0, 1 - freq_std / 100)
    duration_factor = min(1.0, duration / 0.5)
    velocity = int(40 + stability * 50 + duration_factor * 37)
    return max(1, min(127, velocity))


def map_pitch_to_melody(
    contour: PitchContour,
    scale: str = "pentatonic_minor",
    root: str = "C",
    min_note_duration: float = 0.08,
    transpose_semitones: int = 0,
    pitch_stability_threshold: float = 40.0,
) -> Melody:
    """
    Full pipeline: pitch contour → quantized melody.
    
    1. Smooth the raw F0
    2. Segment into note events
    3. Quantize each note to the chosen scale
    4. Build Melody object
    """
    if scale not in SCALES:
        raise ValueError(f"Unknown scale: {scale}. Available: {list(SCALES.keys())}")

    scale_intervals = SCALES[scale]
    root_semitone = ROOT_MIDI.get(root, 0)
    root_midi_val = 60 + root_semitone  # Middle C octave as anchor

    # Step 1: Smooth
    f0_smooth = smooth_pitch_contour(contour)

    # Step 2: Segment
    segments = extract_note_segments(
        f0_smooth,
        contour.times,
        contour.voiced_flags,
        min_note_duration=min_note_duration,
        pitch_stability_threshold=pitch_stability_threshold,
    )

    if not segments:
        raise ValueError(
            "No voiced speech segments detected. "
            "Please check your audio — it may be too quiet, too noisy, or entirely unvoiced."
        )

    # Step 3: Quantize and build notes
    notes = []
    scale_notes_set = set()

    for seg in segments:
        raw_midi = hz_to_midi(seg["mean_freq"])
        raw_midi += transpose_semitones

        quantized_midi = quantize_to_scale(raw_midi, scale_intervals, root_midi_val)
        freq_hz = midi_to_hz(quantized_midi)
        velocity = compute_velocity(seg["freq_std"], seg["duration"])

        note = MelodyNote(
            midi=quantized_midi,
            frequency=freq_hz,
            start_time=seg["start_time"],
            duration=seg["duration"],
            velocity=velocity,
            name=midi_to_name(quantized_midi),
            original_f0=seg["mean_freq"],
        )
        notes.append(note)
        scale_notes_set.add(quantized_midi)

    # Estimate tempo from note spacing
    if len(notes) > 1:
        gaps = [notes[i+1].start_time - notes[i].start_time for i in range(len(notes)-1)]
        median_gap = np.median(gaps)
        tempo_bpm = 60.0 / median_gap if median_gap > 0 else 120.0
        tempo_bpm = float(np.clip(tempo_bpm, 40, 200))
    else:
        tempo_bpm = 120.0

    total_duration = (
        notes[-1].start_time + notes[-1].duration if notes else 0.0
    )

    return Melody(
        notes=notes,
        scale=scale,
        root=root,
        root_midi=root_midi_val,
        tempo_bpm=tempo_bpm,
        total_duration=total_duration,
        scale_notes_used=sorted(scale_notes_set),
    )
