#!/usr/bin/env python3
"""
Speech-to-Melody CLI
Usage: python cli.py <audio_file> [options]
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from core import (
    extract_pitch, get_pitch_statistics,
    map_pitch_to_melody, SCALES,
    synthesize_melody, SYNTHESIZERS,
    write_midi,
)


def main():
    parser = argparse.ArgumentParser(
        description="Convert speech audio to melody",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python cli.py speech.wav
  python cli.py speech.wav --scale major --root A --instrument flute
  python cli.py speech.wav --scale blues --transpose -2 --no-midi
        """
    )
    parser.add_argument("audio", help="Input audio file (WAV/MP3/OGG/FLAC etc.)")
    parser.add_argument("--scale", default="pentatonic_minor",
                        choices=list(SCALES.keys()), help="Musical scale")
    parser.add_argument("--root", default="C",
                        choices=["C","C#","D","D#","E","F","F#","G","G#","A","A#","B"],
                        help="Root key")
    parser.add_argument("--instrument", default="piano",
                        choices=list(SYNTHESIZERS.keys()), help="Synthesis instrument")
    parser.add_argument("--transpose", type=int, default=0, metavar="N",
                        help="Transpose by N semitones")
    parser.add_argument("--min-dur", type=float, default=0.08, metavar="SEC",
                        help="Minimum note duration in seconds")
    parser.add_argument("--reverb", type=float, default=0.15, metavar="0-1",
                        help="Reverb amount")
    parser.add_argument("--output", default=None, help="Output WAV path (auto if not set)")
    parser.add_argument("--no-midi", action="store_true", help="Skip MIDI export")
    parser.add_argument("--verbose", action="store_true")

    args = parser.parse_args()

    audio_path = Path(args.audio)
    if not audio_path.exists():
        print(f"❌ File not found: {audio_path}")
        sys.exit(1)

    output_wav = args.output or str(audio_path.stem + "_melody.wav")
    output_mid = str(audio_path.stem + "_melody.mid")

    print(f"\n🎤 Speech-to-Melody Converter")
    print(f"   Input  : {audio_path}")
    print(f"   Scale  : {args.root} {args.scale}")
    print(f"   Instr  : {args.instrument}")
    print()

    try:
        print("  [1/4] Extracting pitch contour...")
        contour = extract_pitch(str(audio_path))
        stats = get_pitch_statistics(contour)

        if "error" in stats:
            print(f"❌ {stats['error']}")
            sys.exit(1)

        if args.verbose:
            print(f"       Duration      : {stats['duration']:.2f}s")
            print(f"       Voiced ratio  : {stats['voiced_ratio']*100:.1f}%")
            print(f"       Mean F0       : {stats['mean_hz']:.1f} Hz")
            print(f"       F0 range      : {stats['range_semitones']:.1f} semitones")

        print("  [2/4] Mapping to scale...")
        melody = map_pitch_to_melody(
            contour,
            scale=args.scale,
            root=args.root,
            min_note_duration=args.min_dur,
            transpose_semitones=args.transpose,
        )
        print(f"       {len(melody.notes)} notes generated  |  BPM ≈ {melody.tempo_bpm:.0f}")

        print("  [3/4] Synthesizing audio...")
        synthesize_melody(
            melody,
            instrument=args.instrument,
            output_path=output_wav,
            reverb_amount=args.reverb,
        )
        print(f"       → {output_wav}")

        if not args.no_midi:
            print("  [4/4] Exporting MIDI...")
            write_midi(melody, output_mid)
            print(f"       → {output_mid}")
        else:
            print("  [4/4] Skipping MIDI export.")

        print(f"\n✅ Done! Melody saved to: {output_wav}")

    except ValueError as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        if args.verbose:
            import traceback; traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
