"""
Audio Synthesizer — converts a Melody object into actual audio.

Supports multiple synthesis modes:
- Sine: Pure sine wave (clean, simple)
- Piano: Additive synthesis approximating piano timbre  
- Flute: Breathy, smooth timbre
- Pluck: Karplus-Strong string pluck algorithm
- Marimba: Percussive mallet/marimba sound
"""

import numpy as np
import soundfile as sf
from .scale_mapper import Melody, MelodyNote


SR = 44100  # Output sample rate


# ─────────────────────────────────────────────
# Envelope Generators
# ─────────────────────────────────────────────

def adsr_envelope(
    n_samples: int,
    sr: int,
    attack: float = 0.02,
    decay: float = 0.05,
    sustain: float = 0.7,
    release: float = 0.1,
) -> np.ndarray:
    """Generate an ADSR amplitude envelope."""
    attack_s = int(attack * sr)
    decay_s = int(decay * sr)
    release_s = int(release * sr)
    sustain_s = max(0, n_samples - attack_s - decay_s - release_s)

    env = np.concatenate([
        np.linspace(0, 1, attack_s),
        np.linspace(1, sustain, decay_s),
        np.full(sustain_s, sustain),
        np.linspace(sustain, 0, release_s),
    ])
    # Trim or pad to exact length
    if len(env) > n_samples:
        env = env[:n_samples]
    elif len(env) < n_samples:
        env = np.pad(env, (0, n_samples - len(env)))
    return env


# ─────────────────────────────────────────────
# Synthesis Engines
# ─────────────────────────────────────────────

def synth_sine(freq: float, n_samples: int, sr: int, velocity: int) -> np.ndarray:
    """Pure sine wave with ADSR envelope."""
    t = np.linspace(0, n_samples / sr, n_samples, endpoint=False)
    wave = np.sin(2 * np.pi * freq * t)
    env = adsr_envelope(n_samples, sr, attack=0.01, decay=0.05, sustain=0.8, release=0.15)
    return wave * env * (velocity / 127)


def synth_piano(freq: float, n_samples: int, sr: int, velocity: int) -> np.ndarray:
    """
    Piano-like additive synthesis.
    Combines fundamental + overtones with piano-like decay profile.
    """
    t = np.linspace(0, n_samples / sr, n_samples, endpoint=False)
    # Overtone series with amplitude falloff
    harmonics = [
        (1.0,  1.00),   # fundamental
        (2.0,  0.50),   # 2nd harmonic
        (3.0,  0.25),   # 3rd harmonic
        (4.0,  0.15),   # 4th harmonic
        (5.0,  0.08),   # 5th harmonic
        (6.0,  0.05),   # 6th harmonic
        (7.0,  0.02),   # 7th harmonic
    ]
    wave = np.zeros(n_samples)
    for harmonic, amp in harmonics:
        h_freq = freq * harmonic
        if h_freq < sr / 2:  # Nyquist check
            wave += amp * np.sin(2 * np.pi * h_freq * t)

    # Percussive envelope — fast attack, exponential decay
    attack_s = int(0.005 * sr)
    decay_t = np.linspace(0, n_samples / sr, n_samples)
    decay_tau = 1.5  # decay time constant (seconds)
    env = np.exp(-decay_t / decay_tau)
    env[:attack_s] = np.linspace(0, 1, attack_s)

    wave = wave * env * (velocity / 127)
    return wave / (np.max(np.abs(wave)) + 1e-9) * (velocity / 127)


def synth_flute(freq: float, n_samples: int, sr: int, velocity: int) -> np.ndarray:
    """
    Flute-like synthesis: few harmonics, breathy attack noise, smooth envelope.
    """
    t = np.linspace(0, n_samples / sr, n_samples, endpoint=False)
    wave = (
        np.sin(2 * np.pi * freq * t) +
        0.1 * np.sin(2 * np.pi * freq * 2 * t) +
        0.02 * np.sin(2 * np.pi * freq * 3 * t)
    )
    # Add breathy noise at attack
    noise = np.random.randn(n_samples) * 0.05
    attack_s = int(0.05 * sr)
    noise_env = np.zeros(n_samples)
    noise_env[:attack_s] = np.linspace(1, 0, attack_s)
    wave += noise * noise_env

    env = adsr_envelope(n_samples, sr, attack=0.05, decay=0.02, sustain=0.9, release=0.2)
    return wave * env * (velocity / 127) * 0.8


def synth_pluck(freq: float, n_samples: int, sr: int, velocity: int) -> np.ndarray:
    """
    Karplus-Strong string pluck synthesis.
    Creates a realistic plucked string sound.
    """
    period = int(sr / freq)
    if period < 2:
        period = 2

    # Initialize with noise burst
    buf = np.random.uniform(-1, 1, period)
    output = np.zeros(n_samples)

    for i in range(n_samples):
        output[i] = buf[i % period]
        # Low-pass filter (averaging) creates the string decay
        next_idx = (i + 1) % period
        buf[next_idx % period] = 0.996 * 0.5 * (buf[i % period] + buf[next_idx % period])

    # Apply short fade-out at end
    fade_s = min(int(0.05 * sr), n_samples // 4)
    output[-fade_s:] *= np.linspace(1, 0, fade_s)
    return output * (velocity / 127)


def synth_marimba(freq: float, n_samples: int, sr: int, velocity: int) -> np.ndarray:
    """
    Marimba-like mallet synthesis: strong fundamental, fast decay, inharmonic partials.
    """
    t = np.linspace(0, n_samples / sr, n_samples, endpoint=False)
    # Marimba has prominent fundamental and a few slightly inharmonic partials
    wave = (
        1.0  * np.sin(2 * np.pi * freq       * t) +
        0.4  * np.sin(2 * np.pi * freq * 3.9 * t) +  # slightly flat 4th harmonic
        0.1  * np.sin(2 * np.pi * freq * 10.0 * t)
    )
    decay_tau = 0.8
    env = np.exp(-t / decay_tau)
    attack_s = int(0.003 * sr)
    env[:attack_s] = np.linspace(0, 1, attack_s)
    return wave * env * (velocity / 127)


SYNTHESIZERS = {
    "sine":    synth_sine,
    "piano":   synth_piano,
    "flute":   synth_flute,
    "pluck":   synth_pluck,
    "marimba": synth_marimba,
}

SYNTH_DISPLAY_NAMES = {
    "sine":    "Sine Wave",
    "piano":   "Piano",
    "flute":   "Flute",
    "pluck":   "Plucked String",
    "marimba": "Marimba",
}


def synthesize_melody(
    melody: Melody,
    instrument: str = "piano",
    output_path: str = "melody.wav",
    reverb_amount: float = 0.15,
    sr: int = SR,
) -> str:
    """
    Render a Melody to a WAV file.
    
    Args:
        melody: The Melody object from scale_mapper
        instrument: One of 'sine', 'piano', 'flute', 'pluck', 'marimba'
        output_path: Where to save the WAV
        reverb_amount: Simple reverb mix [0-1]
        sr: Sample rate
    
    Returns:
        Path to the saved WAV file
    """
    if instrument not in SYNTHESIZERS:
        raise ValueError(f"Unknown instrument: {instrument}. Choose from {list(SYNTHESIZERS.keys())}")

    synth_fn = SYNTHESIZERS[instrument]

    if not melody.notes:
        raise ValueError("Melody has no notes to synthesize.")

    # Calculate total buffer length
    total_samples = int((melody.total_duration + 2.0) * sr)  # +2s tail
    buffer = np.zeros(total_samples)

    for note in melody.notes:
        start_sample = int(note.start_time * sr)
        n_samples = int(note.duration * sr)
        n_samples = max(n_samples, int(0.05 * sr))  # minimum 50ms

        # Don't exceed buffer
        if start_sample >= total_samples:
            continue
        available = total_samples - start_sample
        n_samples = min(n_samples, available)

        note_audio = synth_fn(note.frequency, n_samples, sr, note.velocity)
        buffer[start_sample:start_sample + n_samples] += note_audio[:n_samples]

    # Normalize
    peak = np.max(np.abs(buffer))
    if peak > 0:
        buffer = buffer / peak * 0.85

    # Simple algorithmic reverb (comb filter approximation)
    if reverb_amount > 0:
        buffer = apply_simple_reverb(buffer, sr, amount=reverb_amount)

    # Final normalization
    peak = np.max(np.abs(buffer))
    if peak > 0:
        buffer = buffer / peak * 0.9

    sf.write(output_path, buffer, sr, subtype="PCM_16")
    return output_path


def apply_simple_reverb(audio: np.ndarray, sr: int, amount: float = 0.2) -> np.ndarray:
    """
    Simple comb-filter reverb using multiple delay lines.
    Not studio-quality but adds nice warmth and space.
    """
    output = audio.copy()
    delays_ms = [37, 52, 61, 89]  # Prime-ish delay times in ms
    gains = [0.6, 0.5, 0.45, 0.4]

    for delay_ms, gain in zip(delays_ms, gains):
        delay_samples = int(delay_ms / 1000 * sr)
        delayed = np.zeros_like(audio)
        delayed[delay_samples:] = audio[:-delay_samples] * gain * amount
        output += delayed

    return output
