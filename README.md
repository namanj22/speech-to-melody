# 🎼 Speech-to-Melody Converter

Extract pitch contours from speech audio and map them onto musical scales to generate real melodies.

---

## What It Does

1. **Loads** your speech audio (WAV, MP3, OGG, FLAC, M4A, WebM)
2. **Extracts** the fundamental frequency (F0) pitch contour using the **pYIN algorithm** — the same technique used in professional pitch detection tools
3. **Smooths** the contour, detects voiced segments, and segments them into note events
4. **Quantizes** each note to the nearest pitch in your chosen musical scale
5. **Synthesizes** the result into real audio using 5 different instruments
6. **Exports** both a WAV audio file and a standard MIDI file
7. **Visualizes** the pitch contour, piano roll, and scale mapping charts

---

## Features

| Feature | Details |
|---------|---------|
| **Pitch extraction** | pYIN (librosa) — robust, handles noise and unvoiced regions |
| **20 musical scales** | Major, Minor, Blues, Pentatonic, Dorian, Hirajoshi, Flamenco, and more |
| **12 root keys** | C through B |
| **5 synthesis engines** | Piano, Flute, Plucked String (Karplus-Strong), Marimba, Sine |
| **MIDI export** | Standard .mid file — load in any DAW |
| **3 visualizations** | Waveform + F0, Piano roll, Scale quantization scatter plot |
| **Web UI** | Full browser interface with mic recording |
| **CLI** | Command-line interface for batch processing |

---

## Quick Start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Run the demo (no microphone needed)
```bash
python demo.py
```
Generates synthetic speech and processes it through all 5 scales and all 5 instruments.
Output WAV, MIDI, and PNG chart files go to `/tmp/demo_*`.

### 3. Launch the web app
```bash
python app.py
```
Open `http://localhost:5050` in your browser.

- Upload an audio file, or click **Record Microphone**
- Choose your scale, root key, instrument, and settings
- Click **Generate Melody**
- Download WAV + MIDI, view charts

### 4. Use the CLI
```bash
python cli.py my_speech.wav
python cli.py my_speech.wav --scale blues --root A --instrument pluck
python cli.py my_speech.wav --scale major --root G --transpose 3 --reverb 0.3
```

---

## Project Structure

```
speech_to_melody/
├── app.py                  ← Flask web application (run this for the UI)
├── cli.py                  ← Command-line interface
├── demo.py                 ← Self-contained demo / test script
├── requirements.txt
└── core/
    ├── pitch_extractor.py  ← pYIN pitch extraction, smoothing
    ├── scale_mapper.py     ← Scale definitions, F0 → MIDI quantization
    ├── synthesizer.py      ← 5 synthesis engines + reverb
    ├── midi_exporter.py    ← Pure-Python MIDI writer (no mido needed)
    └── visualizer.py       ← Matplotlib charts (base64 PNG)
```

---

## How It Works (Technical)

### Pitch Extraction (pYIN)
The **probabilistic YIN** algorithm computes the difference function of the audio signal, finds periodic repetitions (the fundamental period), and assigns a probability to each F0 candidate. Unlike plain autocorrelation, pYIN explicitly models the probability of a frame being voiced, reducing octave errors and false detections in noisy speech.

### Scale Quantization
Each voiced frame's F0 is converted to a continuous MIDI note number via:
```
midi = 12 × log₂(f / 440) + 69
```
Then snapped to the nearest MIDI pitch that belongs to the chosen scale + root key combination, across octaves 2–6.

### Note Segmentation
Consecutive voiced frames with similar F0 (within ±40 Hz by default) are merged into a single note. Short unvoiced gaps (< 3 frames ≈ 70ms) are bridged. Notes shorter than `min_note_duration` are discarded.

### Synthesis Engines
- **Piano** — additive (7 harmonics) + exponential decay
- **Flute** — few harmonics + breathy attack noise
- **Pluck** — Karplus-Strong algorithm (physical modelling of a string)
- **Marimba** — slightly inharmonic partials + fast mallet decay
- **Sine** — pure sine with ADSR envelope

---

## Tips for Best Results

- **Speak clearly and slowly** — sustained vowels produce the clearest pitch
- **Record in a quiet room** — background noise confuses pitch detection
- **Hum or sing rather than speak** — pitch continuity is much higher
- **5–15 seconds** is a good audio length
- **Pentatonic scales** tend to sound most musical with speech (fewer "wrong" notes)
- Use **Transpose** if the melody sounds too high or low
- **Blues + Pluck** gives a surprisingly expressive result
- Export the MIDI and load it into a DAW to add drums, bass, and your own instrumentation

---

## Extending the Project

Some ideas to take this further:

- **Polyphony**: Add chord harmonization below the melody
- **Rhythm quantization**: Snap note durations to nearest beat grid
- **Multiple speakers**: Separate speakers → separate melody voices
- **Real-time mode**: Use PyAudio for live mic input streaming
- **Music21 integration**: Generate sheet music PDF from the MIDI
- **CREPE integration**: Replace pYIN with the CREPE neural pitch detector for higher accuracy
- **Style transfer**: Map the melody rhythm pattern to a different genre's groove

---

## Dependencies

| Package | Purpose |
|---------|---------|
| `librosa` | Audio loading, pYIN pitch detection |
| `soundfile` | WAV reading/writing |
| `numpy` | Signal processing arrays |
| `scipy` | Median filter, label components |
| `matplotlib` | Visualization charts |
| `flask` | Web server |

try it here: https://speech-to-melody-production-3a81.up.railway.app/
