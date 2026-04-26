"""
MIDI Exporter — converts a Melody to a standard MIDI file.
Uses only stdlib + struct (no mido dependency needed).
"""

import struct
from .scale_mapper import Melody


def int_to_varlen(value: int) -> bytes:
    """Encode integer as MIDI variable-length quantity."""
    result = []
    result.append(value & 0x7F)
    value >>= 7
    while value:
        result.append((value & 0x7F) | 0x80)
        value >>= 7
    return bytes(reversed(result))


def write_midi(melody: Melody, output_path: str, tempo_bpm: float = None) -> str:
    """
    Write a Melody to a MIDI file (.mid).
    
    Creates a Type 0 (single-track) MIDI file.
    Tempo is inferred from melody unless overridden.
    """
    tempo_bpm = tempo_bpm or melody.tempo_bpm
    tempo_bpm = max(40, min(200, tempo_bpm))

    # MIDI tempo in microseconds per beat
    us_per_beat = int(60_000_000 / tempo_bpm)
    ticks_per_beat = 480

    def seconds_to_ticks(seconds: float) -> int:
        beats = seconds * tempo_bpm / 60.0
        return int(beats * ticks_per_beat)

    track_events = []

    # Tempo event at tick 0
    track_events.append((0, bytes([0xFF, 0x51, 0x03]) + struct.pack(">I", us_per_beat)[1:]))

    # Program change (piano = 0)
    track_events.append((0, bytes([0xC0, 0x00])))

    # Build note-on/note-off events
    note_events = []
    for note in melody.notes:
        on_tick = seconds_to_ticks(note.start_time)
        off_tick = seconds_to_ticks(note.start_time + note.duration * 0.95)
        midi_note = max(0, min(127, note.midi))
        vel = max(1, min(127, note.velocity))

        note_events.append((on_tick,  bytes([0x90, midi_note, vel])))
        note_events.append((off_tick, bytes([0x80, midi_note, 0])))

    note_events.sort(key=lambda x: x[0])
    track_events.extend(note_events)

    # End of track
    track_events.sort(key=lambda x: x[0])
    track_events.append((track_events[-1][0] if track_events else 0, bytes([0xFF, 0x2F, 0x00])))

    # Convert to delta times
    track_bytes = bytearray()
    prev_tick = 0
    for tick, event_bytes in track_events:
        delta = tick - prev_tick
        prev_tick = tick
        track_bytes += int_to_varlen(delta)
        track_bytes += event_bytes

    # MIDI header chunk
    header = struct.pack(">4sIHHH", b"MThd", 6, 0, 1, ticks_per_beat)

    # Track chunk
    track_chunk = struct.pack(">4sI", b"MTrk", len(track_bytes)) + bytes(track_bytes)

    with open(output_path, "wb") as f:
        f.write(header)
        f.write(track_chunk)

    return output_path
