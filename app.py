"""
Speech-to-Melody Converter — Flask Web Application
"""
# -*- coding: utf-8 -*-
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')


import os
import uuid
import json
import traceback
from pathlib import Path
from flask import Flask, request, jsonify, send_file, render_template_string

# Add parent to path so 'core' is importable
import sys
sys.path.insert(0, str(Path(__file__).parent))

from core import (
    extract_pitch, get_pitch_statistics,
    map_pitch_to_melody, SCALES, SCALE_DISPLAY_NAMES,
    synthesize_melody, SYNTH_DISPLAY_NAMES,
    write_midi,
    plot_pitch_contour, plot_piano_roll, plot_scale_mapping,
)

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 30 * 1024 * 1024  # 30MB

@app.errorhandler(413)
def too_large(e):
    return jsonify({"error": "File too large. Maximum size is 30 MB."}), 413

@app.errorhandler(400)
def bad_request(e):
    return jsonify({"error": f"Bad request: {e.description}"}), 400

@app.errorhandler(500)
def server_error(e):
    return jsonify({"error": f"Internal server error: {e}"}), 500

_BASE = Path(os.environ.get("STORAGE_DIR", str(Path(__file__).parent)))
UPLOAD_DIR = _BASE / "uploads"
OUTPUT_DIR = _BASE / "outputs"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_EXTENSIONS = {".wav", ".mp3", ".ogg", ".flac", ".m4a", ".webm", ".aac"}


def allowed_file(filename: str) -> bool:
    return Path(filename).suffix.lower() in ALLOWED_EXTENSIONS


# ─────────────────────────────────────────────────────────────────────────────
# HTML Template (single-file UI)
# ─────────────────────────────────────────────────────────────────────────────

HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Speech → Melody</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Space+Mono:ital,wght@0,400;0,700;1,400&family=Outfit:wght@300;400;600;700;900&display=swap" rel="stylesheet">
<style>
  :root {
    --bg:       #0A0F1E;
    --surface:  #111827;
    --surface2: #1A2235;
    --border:   #1E2D45;
    --accent:   #6EE7B7;
    --purple:   #A78BFA;
    --pink:     #F472B6;
    --orange:   #FB923C;
    --text:     #E2E8F0;
    --muted:    #64748B;
    --radius:   14px;
  }

  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

  body {
    background: var(--bg);
    color: var(--text);
    font-family: 'Outfit', sans-serif;
    min-height: 100vh;
    overflow-x: hidden;
  }

  /* ─ Background mesh ─ */
  body::before {
    content: '';
    position: fixed; inset: 0; z-index: 0;
    background:
      radial-gradient(ellipse 80% 50% at 20% 0%, rgba(110,231,183,0.06) 0%, transparent 60%),
      radial-gradient(ellipse 60% 40% at 80% 100%, rgba(167,139,250,0.07) 0%, transparent 60%);
    pointer-events: none;
  }

  .container { max-width: 960px; margin: 0 auto; padding: 0 20px; position: relative; z-index: 1; }

  /* ─ Header ─ */
  header {
    padding: 48px 0 32px;
    text-align: center;
    border-bottom: 1px solid var(--border);
    margin-bottom: 40px;
  }
  .logo {
    display: inline-flex; align-items: center; gap: 12px;
    margin-bottom: 16px;
  }
  .logo-icon {
    width: 48px; height: 48px;
    background: linear-gradient(135deg, var(--accent), var(--purple));
    border-radius: 12px;
    display: flex; align-items: center; justify-content: center;
    font-size: 24px;
  }
  h1 {
    font-size: clamp(1.8rem, 4vw, 2.8rem);
    font-weight: 900;
    letter-spacing: -0.03em;
    background: linear-gradient(135deg, var(--accent) 0%, var(--purple) 60%, var(--pink) 100%);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    background-clip: text;
  }
  .tagline { color: var(--muted); font-size: 1rem; margin-top: 8px; font-weight: 300; }

  /* ─ Cards ─ */
  .card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 28px;
    margin-bottom: 24px;
  }
  .card-title {
    font-size: 0.7rem;
    font-weight: 700;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: var(--accent);
    margin-bottom: 20px;
    font-family: 'Space Mono', monospace;
  }

  /* ─ Upload area ─ */
  .upload-zone {
    border: 2px dashed var(--border);
    border-radius: 10px;
    padding: 40px 24px;
    text-align: center;
    cursor: pointer;
    transition: all 0.25s ease;
    position: relative;
    overflow: hidden;
  }
  .upload-zone:hover, .upload-zone.drag-over {
    border-color: var(--accent);
    background: rgba(110,231,183,0.04);
  }
  .upload-zone input[type=file] {
    position: absolute; inset: 0; opacity: 0; cursor: pointer; width: 100%; height: 100%;
  }
  .upload-icon { font-size: 2.5rem; margin-bottom: 12px; display: block; }
  .upload-text { color: var(--muted); font-size: 0.95rem; }
  .upload-text strong { color: var(--text); }
  #file-name {
    margin-top: 12px; font-size: 0.85rem; color: var(--accent);
    font-family: 'Space Mono', monospace; min-height: 20px;
  }

  /* ─ Record button ─ */
  .record-row {
    display: flex; gap: 10px; margin-top: 16px; align-items: center; flex-wrap: wrap;
  }
  .btn {
    display: inline-flex; align-items: center; gap: 8px;
    padding: 10px 20px; border-radius: 8px; font-size: 0.9rem;
    font-weight: 600; cursor: pointer; border: none; transition: all 0.2s;
    font-family: 'Outfit', sans-serif;
  }
  .btn-accent { background: var(--accent); color: #0A0F1E; }
  .btn-accent:hover { filter: brightness(1.1); transform: translateY(-1px); }
  .btn-outline { background: transparent; color: var(--text); border: 1px solid var(--border); }
  .btn-outline:hover { border-color: var(--accent); color: var(--accent); }
  .btn-record { background: #EF4444; color: white; }
  .btn-record:hover { background: #DC2626; }
  .btn-record.recording { background: #B91C1C; animation: pulse-red 1s infinite; }
  .btn:disabled { opacity: 0.4; cursor: not-allowed; transform: none !important; filter: none !important; }

  @keyframes pulse-red {
    0%, 100% { box-shadow: 0 0 0 0 rgba(239,68,68,0.4); }
    50% { box-shadow: 0 0 0 8px rgba(239,68,68,0); }
  }

  /* ─ Controls grid ─ */
  .controls-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 16px;
    margin-bottom: 20px;
  }
  .form-group label {
    display: block; font-size: 0.75rem; font-weight: 600;
    color: var(--muted); text-transform: uppercase; letter-spacing: 0.08em;
    margin-bottom: 8px; font-family: 'Space Mono', monospace;
  }
  select, input[type=range] {
    width: 100%; background: var(--surface2); border: 1px solid var(--border);
    color: var(--text); border-radius: 8px; padding: 10px 12px;
    font-size: 0.9rem; font-family: 'Outfit', sans-serif;
    appearance: none; cursor: pointer;
    transition: border-color 0.2s;
  }
  select:focus { outline: none; border-color: var(--accent); }
  .slider-value { font-size: 0.8rem; color: var(--accent); font-family: 'Space Mono', monospace; margin-top: 4px; }

  input[type=range] {
    padding: 0; height: 6px; border-radius: 3px;
    background: var(--surface2);
    -webkit-appearance: none;
  }
  input[type=range]::-webkit-slider-thumb {
    -webkit-appearance: none; width: 16px; height: 16px;
    border-radius: 50%; background: var(--accent); cursor: pointer;
  }

  /* ─ Generate button ─ */
  .generate-btn {
    width: 100%; padding: 16px; font-size: 1.05rem; font-weight: 700;
    letter-spacing: 0.04em; border-radius: 10px;
    background: linear-gradient(135deg, var(--accent), var(--purple));
    color: #0A0F1E; border: none; cursor: pointer;
    transition: all 0.25s; font-family: 'Outfit', sans-serif;
  }
  .generate-btn:hover:not(:disabled) { transform: translateY(-2px); filter: brightness(1.08); box-shadow: 0 8px 24px rgba(110,231,183,0.2); }
  .generate-btn:disabled { opacity: 0.4; cursor: not-allowed; transform: none; }

  /* ─ Progress ─ */
  #progress-section { display: none; }
  .progress-bar-outer {
    background: var(--surface2); border-radius: 99px; height: 8px;
    overflow: hidden; margin: 12px 0;
  }
  .progress-bar-inner {
    height: 100%; border-radius: 99px;
    background: linear-gradient(90deg, var(--accent), var(--purple));
    width: 0%; transition: width 0.4s ease;
    animation: shimmer 1.5s infinite;
  }
  @keyframes shimmer {
    0% { filter: brightness(1); }
    50% { filter: brightness(1.2); }
    100% { filter: brightness(1); }
  }
  .step-list { list-style: none; }
  .step-list li {
    padding: 6px 0; font-size: 0.9rem; color: var(--muted);
    display: flex; align-items: center; gap: 8px; transition: color 0.3s;
  }
  .step-list li.active { color: var(--accent); }
  .step-list li.done { color: var(--muted); }
  .step-list li::before { content: '○'; font-size: 0.7rem; }
  .step-list li.active::before { content: '●'; color: var(--accent); }
  .step-list li.done::before { content: '✓'; color: var(--accent); }

  /* ─ Results ─ */
  #results-section { display: none; }
  .stats-grid {
    display: grid; grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
    gap: 12px; margin-bottom: 20px;
  }
  .stat-box {
    background: var(--surface2); border: 1px solid var(--border);
    border-radius: 10px; padding: 14px;
    text-align: center;
  }
  .stat-value { font-size: 1.4rem; font-weight: 700; color: var(--accent); font-family: 'Space Mono', monospace; }
  .stat-label { font-size: 0.72rem; color: var(--muted); margin-top: 4px; text-transform: uppercase; letter-spacing: 0.06em; }

  .viz-tabs { display: flex; gap: 4px; margin-bottom: 16px; flex-wrap: wrap; }
  .tab-btn {
    padding: 8px 16px; font-size: 0.8rem; font-weight: 600;
    border-radius: 6px; border: 1px solid var(--border);
    background: transparent; color: var(--muted); cursor: pointer;
    transition: all 0.2s; font-family: 'Outfit', sans-serif;
  }
  .tab-btn.active { background: var(--accent); color: #0A0F1E; border-color: var(--accent); }

  .viz-pane { display: none; }
  .viz-pane.active { display: block; }
  .viz-pane img { width: 100%; border-radius: 8px; border: 1px solid var(--border); }

  .audio-player {
    background: var(--surface2); border: 1px solid var(--border);
    border-radius: 10px; padding: 16px; margin-bottom: 16px;
    display: flex; align-items: center; gap: 16px; flex-wrap: wrap;
  }
  .audio-player audio { flex: 1; min-width: 200px; }

  .download-row { display: flex; gap: 10px; flex-wrap: wrap; }
  .download-btn {
    flex: 1; min-width: 120px; padding: 12px 16px;
    border-radius: 8px; font-size: 0.88rem; font-weight: 600;
    border: 1px solid var(--border); background: var(--surface2);
    color: var(--text); cursor: pointer; transition: all 0.2s;
    display: flex; align-items: center; justify-content: center; gap: 6px;
    text-decoration: none;
    font-family: 'Outfit', sans-serif;
  }
  .download-btn:hover { border-color: var(--accent); color: var(--accent); }

  /* ─ Error ─ */
  .error-box {
    background: rgba(239,68,68,0.1); border: 1px solid rgba(239,68,68,0.3);
    border-radius: 10px; padding: 14px 18px; color: #FCA5A5;
    font-size: 0.9rem; margin-top: 12px; display: none;
  }

  /* ─ Note list ─ */
  .note-pills { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 12px; }
  .note-pill {
    background: var(--surface2); border: 1px solid var(--border);
    border-radius: 6px; padding: 4px 10px;
    font-size: 0.78rem; font-family: 'Space Mono', monospace; color: var(--purple);
  }

  /* ─ Responsive ─ */
  @media (max-width: 600px) {
    .card { padding: 18px; }
    .controls-grid { grid-template-columns: 1fr 1fr; }
  }
</style>
</head>
<body>
<div class="container">

<header>
  <div class="logo">
    <div class="logo-icon">🎼</div>
  </div>
  <h1>Speech → Melody</h1>
  <p class="tagline">Extract pitch from your voice · Map it onto musical scales · Generate real melodies</p>
</header>

<!-- ─ Upload Card ─ -->
<div class="card">
  <div class="card-title">01 / Audio Input</div>

  <div class="upload-zone" id="upload-zone">
    <input type="file" id="file-input" accept=".wav,.mp3,.ogg,.flac,.m4a,.webm,.aac">
    <span class="upload-icon">🎤</span>
    <div class="upload-text">
      <strong>Drop audio here</strong> or click to browse<br>
      WAV, MP3, OGG, FLAC, M4A supported (max 30 MB)
    </div>
    <div id="file-name"></div>
  </div>

  <div class="record-row">
    <button class="btn btn-record" id="record-btn">⏺ Record Microphone</button>
    <span id="record-status" style="font-size:0.85rem;color:var(--muted);"></span>
  </div>
</div>

<!-- ─ Settings Card ─ -->
<div class="card">
  <div class="card-title">02 / Melody Settings</div>
  <div class="controls-grid">
    <div class="form-group">
      <label>Musical Scale</label>
      <select id="scale-select">
        {% for key, name in scales.items() %}
        <option value="{{ key }}" {% if key == 'pentatonic_minor' %}selected{% endif %}>{{ name }}</option>
        {% endfor %}
      </select>
    </div>
    <div class="form-group">
      <label>Root Key</label>
      <select id="root-select">
        {% for note in notes %}
        <option value="{{ note }}" {% if note == 'C' %}selected{% endif %}>{{ note }}</option>
        {% endfor %}
      </select>
    </div>
    <div class="form-group">
      <label>Instrument</label>
      <select id="instrument-select">
        {% for key, name in instruments.items() %}
        <option value="{{ key }}" {% if key == 'piano' %}selected{% endif %}>{{ name }}</option>
        {% endfor %}
      </select>
    </div>
    <div class="form-group">
      <label>Transpose (semitones)</label>
      <input type="range" id="transpose" min="-12" max="12" value="0" step="1">
      <div class="slider-value" id="transpose-val">0</div>
    </div>
    <div class="form-group">
      <label>Min Note Length (ms)</label>
      <input type="range" id="min-dur" min="40" max="300" value="80" step="10">
      <div class="slider-value" id="min-dur-val">80 ms</div>
    </div>
    <div class="form-group">
      <label>Reverb Amount</label>
      <input type="range" id="reverb" min="0" max="50" value="15" step="5">
      <div class="slider-value" id="reverb-val">15%</div>
    </div>
  </div>

  <button class="generate-btn" id="generate-btn" disabled>
    ✨ Generate Melody
  </button>
  <div class="error-box" id="error-box"></div>
</div>

<!-- ─ Progress Card ─ -->
<div class="card" id="progress-section">
  <div class="card-title">Processing</div>
  <div class="progress-bar-outer">
    <div class="progress-bar-inner" id="progress-bar"></div>
  </div>
  <ul class="step-list" id="step-list">
    <li id="step-load">Loading audio</li>
    <li id="step-pitch">Extracting pitch (pyin)</li>
    <li id="step-map">Mapping to scale</li>
    <li id="step-synth">Synthesizing audio</li>
    <li id="step-viz">Generating visualizations</li>
  </ul>
</div>

<!-- ─ Results Card ─ -->
<div class="card" id="results-section">
  <div class="card-title">03 / Results</div>

  <!-- Stats -->
  <div class="stats-grid" id="stats-grid"></div>

  <!-- Notes used -->
  <div id="note-pills-section" style="margin-bottom:20px;display:none">
    <div style="font-size:0.75rem;color:var(--muted);margin-bottom:6px;text-transform:uppercase;letter-spacing:0.08em;font-family:'Space Mono',monospace;">Scale Notes Used</div>
    <div class="note-pills" id="note-pills"></div>
  </div>

  <!-- Audio Player -->
  <div class="audio-player">
    <span style="font-size:1.4rem">🔊</span>
    <audio id="audio-player" controls style="flex:1;min-width:220px;"></audio>
  </div>

  <!-- Downloads -->
  <div class="download-row" style="margin-bottom:20px;">
    <a class="download-btn" id="dl-wav" href="#">⬇ WAV Audio</a>
    <a class="download-btn" id="dl-midi" href="#">⬇ MIDI File</a>
  </div>

  <!-- Visualizations -->
  <div class="viz-tabs">
    <button class="tab-btn active" data-tab="piano">🎹 Piano Roll</button>
    <button class="tab-btn" data-tab="pitch">📈 Pitch Contour</button>
    <button class="tab-btn" data-tab="mapping">🔗 Scale Mapping</button>
  </div>
  <div class="viz-pane active" id="tab-piano">
    <img id="img-piano" src="" alt="Piano Roll">
  </div>
  <div class="viz-pane" id="tab-pitch">
    <img id="img-pitch" src="" alt="Pitch Contour">
  </div>
  <div class="viz-pane" id="tab-mapping">
    <img id="img-mapping" src="" alt="Scale Mapping">
  </div>
</div>

</div><!-- /container -->

<script>
// ─── State ───────────────────────────────────────────────────────────────────
let selectedFile = null;
let mediaRecorder = null;
let recordedChunks = [];
let isRecording = false;
let sessionId = null;

// ─── Sliders ─────────────────────────────────────────────────────────────────
document.getElementById('transpose').addEventListener('input', e => {
  document.getElementById('transpose-val').textContent = e.target.value;
});
document.getElementById('min-dur').addEventListener('input', e => {
  document.getElementById('min-dur-val').textContent = e.target.value + ' ms';
});
document.getElementById('reverb').addEventListener('input', e => {
  document.getElementById('reverb-val').textContent = e.target.value + '%';
});

// ─── File Upload ──────────────────────────────────────────────────────────────
const fileInput = document.getElementById('file-input');
const uploadZone = document.getElementById('upload-zone');

fileInput.addEventListener('change', e => setFile(e.target.files[0]));
uploadZone.addEventListener('dragover', e => { e.preventDefault(); uploadZone.classList.add('drag-over'); });
uploadZone.addEventListener('dragleave', () => uploadZone.classList.remove('drag-over'));
uploadZone.addEventListener('drop', e => {
  e.preventDefault(); uploadZone.classList.remove('drag-over');
  setFile(e.dataTransfer.files[0]);
});

function setFile(file) {
  if (!file) return;
  selectedFile = file;
  document.getElementById('file-name').textContent = `📎 ${file.name} (${(file.size / 1024).toFixed(0)} KB)`;
  document.getElementById('generate-btn').disabled = false;
  hideError();
}

// ─── Microphone Recording ─────────────────────────────────────────────────────
document.getElementById('record-btn').addEventListener('click', async () => {
  if (!isRecording) {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      recordedChunks = [];
      mediaRecorder = new MediaRecorder(stream, { mimeType: 'audio/webm' });
      mediaRecorder.ondataavailable = e => recordedChunks.push(e.data);
      mediaRecorder.onstop = () => {
        const blob = new Blob(recordedChunks, { type: 'audio/webm' });
        const file = new File([blob], 'recording.webm', { type: 'audio/webm' });
        setFile(file);
        stream.getTracks().forEach(t => t.stop());
        document.getElementById('record-status').textContent = '✅ Recording saved';
      };
      mediaRecorder.start();
      isRecording = true;
      const btn = document.getElementById('record-btn');
      btn.textContent = '⏹ Stop Recording';
      btn.classList.add('recording');
      document.getElementById('record-status').textContent = '🔴 Recording…';
    } catch (err) {
      document.getElementById('record-status').textContent = '❌ Microphone access denied';
    }
  } else {
    mediaRecorder.stop();
    isRecording = false;
    const btn = document.getElementById('record-btn');
    btn.textContent = '⏺ Record Microphone';
    btn.classList.remove('recording');
  }
});

// ─── Generate ─────────────────────────────────────────────────────────────────
document.getElementById('generate-btn').addEventListener('click', async () => {
  if (!selectedFile) return;
  hideError();
  setProgress(0);
  document.getElementById('progress-section').style.display = 'block';
  document.getElementById('results-section').style.display = 'none';
  document.getElementById('generate-btn').disabled = true;
  resetSteps();

  const formData = new FormData();
  formData.append('audio', selectedFile);
  formData.append('scale', document.getElementById('scale-select').value);
  formData.append('root', document.getElementById('root-select').value);
  formData.append('instrument', document.getElementById('instrument-select').value);
  formData.append('transpose', document.getElementById('transpose').value);
  formData.append('min_dur', (parseInt(document.getElementById('min-dur').value) / 1000).toFixed(3));
  formData.append('reverb', (parseInt(document.getElementById('reverb').value) / 100).toFixed(2));

  try {
    animateSteps();
    const resp = await fetch('/process', { method: 'POST', body: formData });

    // Safely parse JSON — if Flask returns an HTML error page (413, 500 etc.)
    // resp.json() throws; we catch that and show the HTTP status instead.
    let data;
    const contentType = resp.headers.get('content-type') || '';
    if (contentType.includes('application/json')) {
      data = await resp.json();
    } else {
      const text = await resp.text();
      const preview = text.replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim().slice(0, 200);
      throw new Error(`Server error ${resp.status}: ${preview}`);
    }

    if (!resp.ok || data.error) {
      throw new Error(data.error || `Server returned ${resp.status}`);
    }

    sessionId = data.session_id;
    setProgress(100);
    await new Promise(r => setTimeout(r, 400));
    showResults(data);
  } catch (err) {
    showError(err.message);
    console.error('Speech-to-Melody error:', err);
  } finally {
    document.getElementById('generate-btn').disabled = false;
  }
});

// ─── Step animation ───────────────────────────────────────────────────────────
let stepTimer = null;
function animateSteps() {
  const steps = ['step-load','step-pitch','step-map','step-synth','step-viz'];
  const progPct = [10, 30, 55, 75, 90];
  let i = 0;
  stepTimer = setInterval(() => {
    if (i > 0) { document.getElementById(steps[i-1]).className = 'done'; }
    if (i < steps.length) {
      document.getElementById(steps[i]).className = 'active';
      setProgress(progPct[i]);
      i++;
    } else {
      clearInterval(stepTimer);
    }
  }, 700);
}

function resetSteps() {
  ['step-load','step-pitch','step-map','step-synth','step-viz'].forEach(id => {
    document.getElementById(id).className = '';
  });
  if (stepTimer) clearInterval(stepTimer);
}

function setProgress(pct) {
  document.getElementById('progress-bar').style.width = pct + '%';
}

// ─── Show Results ─────────────────────────────────────────────────────────────
function showResults(data) {
  // Stats
  const stats = data.stats || {};
  const melody = data.melody || {};
  const statsGrid = document.getElementById('stats-grid');
  statsGrid.innerHTML = '';
  const statItems = [
    { label: 'Notes Generated', value: melody.note_count || 0 },
    { label: 'Duration', value: (melody.total_duration || 0).toFixed(1) + 's' },
    { label: 'Estimated BPM', value: Math.round(melody.tempo_bpm || 120) },
    { label: 'Voiced %', value: stats.voiced_ratio ? (stats.voiced_ratio * 100).toFixed(0) + '%' : 'N/A' },
    { label: 'F0 Range', value: stats.range_semitones ? stats.range_semitones.toFixed(1) + ' st' : 'N/A' },
    { label: 'Avg F0', value: stats.mean_hz ? Math.round(stats.mean_hz) + ' Hz' : 'N/A' },
  ];
  statItems.forEach(s => {
    statsGrid.innerHTML += `<div class="stat-box"><div class="stat-value">${s.value}</div><div class="stat-label">${s.label}</div></div>`;
  });

  // Note pills
  if (melody.notes_used && melody.notes_used.length) {
    document.getElementById('note-pills-section').style.display = 'block';
    document.getElementById('note-pills').innerHTML =
      melody.notes_used.map(n => `<span class="note-pill">${n}</span>`).join('');
  }

  // Audio
  const wavUrl = `/download/${sessionId}/wav`;
  const midiUrl = `/download/${sessionId}/midi`;
  document.getElementById('audio-player').src = wavUrl;
  document.getElementById('dl-wav').href = wavUrl;
  document.getElementById('dl-wav').download = 'melody.wav';
  document.getElementById('dl-midi').href = midiUrl;
  document.getElementById('dl-midi').download = 'melody.mid';

  // Visualizations
  if (data.viz_pitch) document.getElementById('img-pitch').src = 'data:image/png;base64,' + data.viz_pitch;
  if (data.viz_piano) document.getElementById('img-piano').src = 'data:image/png;base64,' + data.viz_piano;
  if (data.viz_mapping) document.getElementById('img-mapping').src = 'data:image/png;base64,' + data.viz_mapping;

  document.getElementById('progress-section').style.display = 'none';
  document.getElementById('results-section').style.display = 'block';
  document.getElementById('results-section').scrollIntoView({ behavior: 'smooth', block: 'start' });
}

// ─── Tabs ─────────────────────────────────────────────────────────────────────
document.querySelectorAll('.tab-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.viz-pane').forEach(p => p.classList.remove('active'));
    btn.classList.add('active');
    document.getElementById('tab-' + btn.dataset.tab).classList.add('active');
  });
});

// ─── Helpers ──────────────────────────────────────────────────────────────────
function showError(msg) {
  const box = document.getElementById('error-box');
  box.textContent = '⚠ ' + msg;
  box.style.display = 'block';
  document.getElementById('progress-section').style.display = 'none';
}
function hideError() {
  document.getElementById('error-box').style.display = 'none';
}
</script>
</body>
</html>
"""


# ─────────────────────────────────────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    from core.scale_mapper import NOTE_NAMES
    return render_template_string(
        HTML,
        scales=SCALE_DISPLAY_NAMES,
        notes=NOTE_NAMES,
        instruments=SYNTH_DISPLAY_NAMES,
    )


@app.route("/process", methods=["POST"])
def process():
    # ── Validate file ──
    if "audio" not in request.files:
        return jsonify({"error": "No audio file uploaded."}), 400
    file = request.files["audio"]
    if not file.filename:
        return jsonify({"error": "Empty filename."}), 400
    if not allowed_file(file.filename):
        return jsonify({"error": f"Unsupported file type. Use: {', '.join(ALLOWED_EXTENSIONS)}"}), 400

    # ── Parse params ──
    scale      = request.form.get("scale", "pentatonic_minor")
    root       = request.form.get("root", "C")
    instrument = request.form.get("instrument", "piano")
    transpose  = int(request.form.get("transpose", 0))
    min_dur    = float(request.form.get("min_dur", 0.08))
    reverb     = float(request.form.get("reverb", 0.15))

    # ── Save upload ──
    session_id = uuid.uuid4().hex[:12]
    suffix = Path(file.filename).suffix.lower()
    upload_path = UPLOAD_DIR / f"{session_id}{suffix}"
    file.save(upload_path)

    try:
        # ── Extract pitch ──
        contour = extract_pitch(str(upload_path))
        stats = get_pitch_statistics(contour)
        if "error" in stats:
            return jsonify({"error": stats["error"]}), 422

        # ── Map to melody ──
        melody = map_pitch_to_melody(
            contour,
            scale=scale,
            root=root,
            min_note_duration=min_dur,
            transpose_semitones=transpose,
        )

        # ── Synthesize ──
        wav_path  = str(OUTPUT_DIR / f"{session_id}.wav")
        midi_path = str(OUTPUT_DIR / f"{session_id}.mid")
        synthesize_melody(melody, instrument=instrument, output_path=wav_path, reverb_amount=reverb)
        write_midi(melody, output_path=midi_path)

        # ── Visualize ──
        from core.scale_mapper import midi_to_name
        viz_pitch   = plot_pitch_contour(contour)
        viz_piano   = plot_piano_roll(melody)
        viz_mapping = plot_scale_mapping(melody, contour)

        # ── Build response ──
        notes_used = [midi_to_name(m) for m in melody.scale_notes_used]
        return jsonify({
            "session_id": session_id,
            "stats": stats,
            "melody": {
                "note_count":     len(melody.notes),
                "total_duration": melody.total_duration,
                "tempo_bpm":      melody.tempo_bpm,
                "scale":          melody.scale,
                "root":           melody.root,
                "notes_used":     notes_used,
            },
            "viz_pitch":   viz_pitch,
            "viz_piano":   viz_piano,
            "viz_mapping": viz_mapping,
        })

    except ValueError as e:
        return jsonify({"error": str(e)}), 422
    except Exception as e:
        tb = traceback.format_exc()
        print(f"[ERROR] /process exception:\n{tb}", flush=True)
        # Return the actual exception message so the UI shows something useful
        return jsonify({"error": f"{type(e).__name__}: {str(e)}"}), 500
    finally:
        try:
            upload_path.unlink(missing_ok=True)
        except Exception:
            pass


@app.route("/download/<session_id>/<fmt>")
def download(session_id: str, fmt: str):
    # Basic path safety
    if not session_id.isalnum() or len(session_id) > 32:
        return "Invalid session", 400

    if fmt == "wav":
        path = OUTPUT_DIR / f"{session_id}.wav"
        mime = "audio/wav"
        name = "melody.wav"
    elif fmt == "midi":
        path = OUTPUT_DIR / f"{session_id}.mid"
        mime = "audio/midi"
        name = "melody.mid"
    else:
        return "Unknown format", 400

    if not path.exists():
        return "File not found", 404

    return send_file(str(path), mimetype=mime, as_attachment=True, download_name=name)


if __name__ == "__main__":
    print("\nSpeech-to-Melody Converter")
    print("------------------------------")
    print("   http://localhost:5050\n")
    app.run(host="0.0.0.0", port=5050, debug=False)
