#!/usr/bin/env python3
"""
Separate audio into stems using audio-separator.
Uses BS-Rofo-SW-Fixed (6-stem RoFormer) — best open-source model for stem separation.
"""

import argparse
import glob
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.request import urlretrieve

GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
CYAN = "\033[36m"
RESET = "\033[0m"

VALID_STEMS = ["vocals", "drums", "bass", "guitar", "piano", "other"]
STEM_SUFFIX = {
    "vocals": "Vocals",
    "drums": "Drums",
    "bass": "Bass",
    "guitar": "Guitar",
    "piano": "Piano",
    "other": "Other",
}

MODEL_DIR = Path.home() / ".cache" / "audio-separator-models"
ROFO_MODEL = "BS-Rofo-SW-Fixed.ckpt"
ROFO_CONFIG = "BS-Rofo-SW-Fixed.yaml"
ROFO_HF_BASE = "https://huggingface.co/jarredou/BS-ROFO-SW-Fixed/resolve/main"


def ensure_model():
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    model_path = MODEL_DIR / ROFO_MODEL
    config_path = MODEL_DIR / ROFO_CONFIG

    if not model_path.exists():
        print(f"Downloading {CYAN}BS-Rofo-SW-Fixed{RESET} model (first run only)...")
        urlretrieve(f"{ROFO_HF_BASE}/{ROFO_MODEL}", model_path)

    if not config_path.exists():
        urlretrieve(f"{ROFO_HF_BASE}/{ROFO_CONFIG}", config_path)


def check_dependencies():
    if not shutil.which("audio-separator"):
        print(f"{RED}✗{RESET} audio-separator not found. Install with: pipx install 'audio-separator[cpu]'")
        sys.exit(1)
    if not shutil.which("ffmpeg"):
        print(f"{RED}✗{RESET} ffmpeg not found. Install with: brew install ffmpeg")
        sys.exit(1)


def find_stem_file(tmpdir: str, suffix: str) -> str | None:
    matches = glob.glob(os.path.join(tmpdir, f"*_({suffix})*.wav"))
    return matches[0] if matches else None


def output_stem(src: str, dst_base: str, fmt: str):
    if dst_base.endswith(".wav"):
        dst_base = dst_base[:-4]

    if fmt == "wav":
        dst = f"{dst_base}.wav"
        shutil.move(src, dst)
    elif fmt == "flac":
        dst = f"{dst_base}.flac"
        subprocess.run(
            ["ffmpeg", "-i", src, "-c:a", "flac", dst, "-y"],
            capture_output=True,
        )
        os.remove(src)
    elif fmt == "mp3":
        dst = f"{dst_base}.mp3"
        subprocess.run(
            ["ffmpeg", "-i", src, "-c:a", "libmp3lame", "-b:a", "320k", dst, "-y"],
            capture_output=True,
        )
        os.remove(src)

    print(f"  {GREEN}✓{RESET} {os.path.basename(dst)}")


def separate_file(input_file: str, requested: set, fmt: str):
    input_path = Path(input_file).resolve()
    if not input_path.is_file():
        print(f"{RED}✗{RESET} File not found: {input_file}")
        return

    basename = input_path.stem
    output_dir = input_path.parent / "separated"
    output_dir.mkdir(exist_ok=True)

    with tempfile.TemporaryDirectory() as tmpdir:
        print(f"Separating stems from {CYAN}{input_path.name}{RESET}...")

        cmd = [
            "audio-separator", str(input_path),
            "--model_filename", ROFO_MODEL,
            "--config_path", str(MODEL_DIR / ROFO_CONFIG),
            "--model_file_dir", str(MODEL_DIR),
            "--output_dir", tmpdir,
            "--output_format", "WAV",
            "--log_level", "warning",
        ]

        result = subprocess.run(cmd)
        if result.returncode != 0:
            print(f"{RED}✗{RESET} audio-separator failed")
            return

        # Extract requested stems (excluding "other" which is handled separately)
        for stem in VALID_STEMS:
            if stem == "other" or stem not in requested:
                continue
            suffix = STEM_SUFFIX[stem]
            src = find_stem_file(tmpdir, suffix)
            if not src:
                print(f"  {RED}✗{RESET} Could not find {stem} stem in output")
                continue
            dst = str(output_dir / f"{basename}_{stem}.wav")
            output_stem(src, dst, fmt)

        # Mix remainder stems only if --other was requested
        if "other" in requested:
            remainder_stems = [s for s in VALID_STEMS if s != "other" and s not in requested]

            # Collect all unrequested stem files + the model's "other" stem
            remainder_files = []
            other_src = find_stem_file(tmpdir, "Other")
            if other_src:
                remainder_files.append(other_src)
            for stem in remainder_stems:
                src = find_stem_file(tmpdir, STEM_SUFFIX[stem])
                if src:
                    remainder_files.append(src)

            remainder_dst = str(output_dir / f"{basename}_other.wav")

            if len(remainder_files) == 1:
                output_stem(remainder_files[0], remainder_dst, fmt)
            elif len(remainder_files) > 1:
                print(f"  Mixing {len(remainder_files)} remaining stems...")
                ffmpeg_cmd = ["ffmpeg"]
                for f in remainder_files:
                    ffmpeg_cmd.extend(["-i", f])
                ffmpeg_cmd.extend([
                    "-filter_complex",
                    f"amix=inputs={len(remainder_files)}:duration=longest:normalize=0",
                    remainder_dst, "-y",
                ])
                subprocess.run(ffmpeg_cmd, capture_output=True)

                if os.path.isfile(remainder_dst):
                    output_stem(remainder_dst, remainder_dst, fmt)
                else:
                    print(f"  {RED}✗{RESET} Failed to mix remainder stems")


def main():
    parser = argparse.ArgumentParser(
        prog="stems",
        description="Separate audio into stems using BS-Rofo-SW-Fixed (6-stem RoFormer)",
    )

    stem_group = parser.add_argument_group("stems")
    for stem in VALID_STEMS:
        stem_group.add_argument(f"--{stem}", action="store_true", help=f"Extract {stem}")
    stem_group.add_argument("--all", action="store_true", help="Extract all 6 stems")

    fmt_group = parser.add_argument_group("output format")
    fmt_group.add_argument("--flac", dest="format", action="store_const", const="flac",
                           help="FLAC (default) — lossless, sample-accurate")
    fmt_group.add_argument("--wav", dest="format", action="store_const", const="wav",
                           help="WAV — uncompressed lossless")
    fmt_group.add_argument("--mp3", dest="format", action="store_const", const="mp3",
                           help="MP3 320kbps — NOT sample-accurate (adds padding)")

    parser.add_argument("files", nargs="+", help="Input audio files")

    args = parser.parse_args()
    fmt = args.format or "flac"

    # Build set of requested stems
    requested = set()
    if args.all:
        requested = set(VALID_STEMS)
    else:
        for stem in VALID_STEMS:
            if getattr(args, stem):
                requested.add(stem)

    if not requested:
        parser.error("No stems requested. Use --drums, --vocals, etc. or --all")

    check_dependencies()
    ensure_model()
    print(f"Using {CYAN}BS-Rofo-SW-Fixed{RESET} (6-stem RoFormer)")

    for f in args.files:
        separate_file(f, requested, fmt)

    print(f"{GREEN}Done.{RESET}")


if __name__ == "__main__":
    main()
