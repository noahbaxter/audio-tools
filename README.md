# mastering-tools

CLI tools for music mastering workflow.

## Tools

**`stems`** — Separate audio into stems (vocals, drums, bass, guitar, piano, other) using BS-Rofo-SW-Fixed 6-stem RoFormer model. Auto-downloads model on first run. Supports batch processing and FLAC/WAV/MP3 output.

**`normalize`** — Audio normalization by peak or LUFS. Supports individual and group modes for batch processing, with peak ceiling clamping.

**`loudness`** — Audio loudness analysis. Wraps ffmpeg's ebur128 filter to extract peak, LUFS, and loudness change timestamps. Supports single file analysis, batch comparison, reference matching, and segment-by-segment gain suggestions.

**`declick`** — Detect and remove single-sample digital clicks and zero-sample dropouts from audio files. Handles exact zeros, near-zero dropouts, partial dips, and sync artifacts.

## Install

Requires Python 3.10+ and [pipx](https://pipx.pypa.io/).

```bash
pipx install -e /path/to/mastering-tools
```

All tools are then available globally.

`stems` also requires `audio-separator` (`pipx install 'audio-separator[cpu]'`) and ffmpeg.
`loudness`, `normalize`, and `declick` require ffmpeg on PATH (`brew install ffmpeg`).

## Usage

```bash
# Separate drums from a track (output to separated/ folder)
stems --drums track.wav

# Extract multiple stems
stems --drums --bass --vocals track.wav

# All 6 stems as MP3
stems --all --mp3 track.wav

# Batch stem separation
stems --drums *.flac

# Peak normalize (default: -0.1 dB)
normalize track.wav

# LUFS normalize
normalize -l -14 track.wav

# Group normalize (same gain for all files)
normalize *.wav

# Single file loudness analysis
loudness track.wav

# Batch comparison with gain adjustments
loudness *.wav

# Compare against reference tracks
loudness track.wav -r reference.wav

# Fix dropouts in a file (in-place)
declick -d input.wav

# Fix clicks and dropouts
declick -dc input.wav
```

## Development

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e .
pip install pytest
pytest tests/
```
