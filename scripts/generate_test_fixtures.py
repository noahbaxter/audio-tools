#!/usr/bin/env python3
"""Generate synthetic test fixtures with known dropout patterns.

Creates WAV files with specific, documented click/dropout positions
for algorithm validation.
"""

import json
from pathlib import Path

import numpy as np
import soundfile as sf


def generate_clean_audio(duration_sec: float, sr: int = 48000) -> np.ndarray:
    """Generate clean test audio - sum of sines at various frequencies."""
    t = np.linspace(0, duration_sec, int(duration_sec * sr), endpoint=False)

    # Mix of frequencies to create realistic-ish audio
    signal = (
        0.25 * np.sin(2 * np.pi * 220 * t) +    # A3
        0.15 * np.sin(2 * np.pi * 440 * t) +    # A4
        0.10 * np.sin(2 * np.pi * 880 * t) +    # A5
        0.08 * np.sin(2 * np.pi * 330 * t) +    # E4
        0.05 * np.sin(2 * np.pi * 150 * t)      # Low rumble
    )

    # Add slow amplitude modulation
    envelope = 0.7 + 0.3 * np.sin(2 * np.pi * 0.5 * t)
    signal *= envelope

    return signal


def inject_exact_zero_dropout(samples: np.ndarray, position: int, length: int = 1) -> dict:
    """Inject exact zero dropout (original bug could catch these)."""
    for i in range(length):
        samples[position + i] = 0.0
    return {
        'type': 'exact_zero',
        'position': position,
        'length': length,
        'original_values': 'zeroed'
    }


def inject_near_zero_dropout(samples: np.ndarray, position: int, length: int = 1,
                              dc_offset: float = 0.002) -> dict:
    """Inject near-zero dropout with DC offset (original bug missed these)."""
    original_values = []
    for i in range(length):
        original_values.append(float(samples[position + i]))
        # Vary slightly around DC offset to simulate real-world variation
        samples[position + i] = dc_offset * (0.5 + np.random.random())
    return {
        'type': 'near_zero',
        'position': position,
        'length': length,
        'dc_offset': dc_offset,
        'original_values': original_values
    }


def inject_partial_dropout(samples: np.ndarray, position: int, length: int = 1,
                            attenuation: float = 0.05) -> dict:
    """Inject partial dropout - signal attenuated but not zeroed."""
    original_values = []
    for i in range(length):
        original_values.append(float(samples[position + i]))
        samples[position + i] *= attenuation
    return {
        'type': 'partial',
        'position': position,
        'length': length,
        'attenuation': attenuation,
        'original_values': original_values
    }


def inject_spike_click(samples: np.ndarray, position: int, magnitude: float = 0.95) -> dict:
    """Inject spike click (sudden large value)."""
    original = float(samples[position])
    samples[position] = magnitude * np.sign(samples[position]) if samples[position] != 0 else magnitude
    return {
        'type': 'spike',
        'position': position,
        'magnitude': magnitude,
        'original_value': original
    }


def main():
    fixtures_dir = Path(__file__).parent.parent / "tests" / "fixtures"
    fixtures_dir.mkdir(parents=True, exist_ok=True)

    sr = 48000
    duration = 2.0  # 2 seconds

    # Track all injected defects for documentation
    manifest = {
        'sample_rate': sr,
        'duration_sec': duration,
        'files': {}
    }

    # === Test file 1: Exact zeros (baseline - original algo should catch) ===
    clean = generate_clean_audio(duration, sr)
    corrupted = clean.copy()
    defects = []

    defects.append(inject_exact_zero_dropout(corrupted, 10000, length=1))
    defects.append(inject_exact_zero_dropout(corrupted, 30000, length=2))
    defects.append(inject_exact_zero_dropout(corrupted, 50000, length=3))
    defects.append(inject_exact_zero_dropout(corrupted, 70000, length=5))

    sf.write(fixtures_dir / "exact_zero_dropouts.wav", corrupted, sr)
    sf.write(fixtures_dir / "exact_zero_dropouts_clean.wav", clean, sr)
    manifest['files']['exact_zero_dropouts.wav'] = {
        'description': 'Exact zero dropouts - baseline test',
        'defects': defects,
        'expected_detections': sum(d['length'] for d in defects)
    }

    # === Test file 2: Near-zero dropouts (original algo MISSED these) ===
    clean = generate_clean_audio(duration, sr)
    corrupted = clean.copy()
    defects = []

    defects.append(inject_near_zero_dropout(corrupted, 10000, length=1, dc_offset=0.001))
    defects.append(inject_near_zero_dropout(corrupted, 30000, length=2, dc_offset=0.002))
    defects.append(inject_near_zero_dropout(corrupted, 50000, length=3, dc_offset=0.003))
    defects.append(inject_near_zero_dropout(corrupted, 70000, length=1, dc_offset=0.004))

    sf.write(fixtures_dir / "near_zero_dropouts.wav", corrupted, sr)
    sf.write(fixtures_dir / "near_zero_dropouts_clean.wav", clean, sr)
    manifest['files']['near_zero_dropouts.wav'] = {
        'description': 'Near-zero dropouts with DC offset - regression test for original bug',
        'defects': defects,
        'expected_detections': sum(d['length'] for d in defects)
    }

    # === Test file 3: Partial dropouts (dip pattern) ===
    clean = generate_clean_audio(duration, sr)
    corrupted = clean.copy()
    defects = []

    defects.append(inject_partial_dropout(corrupted, 15000, length=1, attenuation=0.05))
    defects.append(inject_partial_dropout(corrupted, 35000, length=2, attenuation=0.08))
    defects.append(inject_partial_dropout(corrupted, 55000, length=1, attenuation=0.03))
    defects.append(inject_partial_dropout(corrupted, 75000, length=3, attenuation=0.06))

    sf.write(fixtures_dir / "partial_dropouts.wav", corrupted, sr)
    sf.write(fixtures_dir / "partial_dropouts_clean.wav", clean, sr)
    manifest['files']['partial_dropouts.wav'] = {
        'description': 'Partial dropouts (attenuated but not zero) - dip pattern test',
        'defects': defects,
        'expected_detections': sum(d['length'] for d in defects)
    }

    # === Test file 4: Mixed defects (realistic scenario) ===
    clean = generate_clean_audio(duration, sr)
    corrupted = clean.copy()
    defects = []

    # Mix of all types
    defects.append(inject_exact_zero_dropout(corrupted, 8000, length=2))
    defects.append(inject_near_zero_dropout(corrupted, 20000, length=1, dc_offset=0.002))
    defects.append(inject_partial_dropout(corrupted, 32000, length=1, attenuation=0.04))
    defects.append(inject_spike_click(corrupted, 44000, magnitude=0.9))
    defects.append(inject_near_zero_dropout(corrupted, 56000, length=3, dc_offset=0.001))
    defects.append(inject_exact_zero_dropout(corrupted, 68000, length=1))
    defects.append(inject_partial_dropout(corrupted, 80000, length=2, attenuation=0.05))

    sf.write(fixtures_dir / "mixed_defects.wav", corrupted, sr)
    sf.write(fixtures_dir / "mixed_defects_clean.wav", clean, sr)
    manifest['files']['mixed_defects.wav'] = {
        'description': 'Mix of all defect types - comprehensive test',
        'defects': defects,
        'expected_detections': sum(d.get('length', 1) for d in defects)
    }

    # === Test file 5: Edge cases ===
    clean = generate_clean_audio(duration, sr)
    corrupted = clean.copy()
    defects = []

    # Near file boundaries
    defects.append(inject_exact_zero_dropout(corrupted, 5, length=1))
    defects.append(inject_near_zero_dropout(corrupted, len(corrupted) - 10, length=1, dc_offset=0.002))

    # Very small DC offset (might be missed)
    defects.append(inject_near_zero_dropout(corrupted, 25000, length=1, dc_offset=0.0005))

    # Borderline partial dropout
    defects.append(inject_partial_dropout(corrupted, 45000, length=1, attenuation=0.15))

    sf.write(fixtures_dir / "edge_cases.wav", corrupted, sr)
    sf.write(fixtures_dir / "edge_cases_clean.wav", clean, sr)
    manifest['files']['edge_cases.wav'] = {
        'description': 'Edge cases - boundary conditions and borderline detections',
        'defects': defects,
        'expected_detections': sum(d.get('length', 1) for d in defects)
    }

    # Write manifest
    with open(fixtures_dir / "manifest.json", 'w') as f:
        json.dump(manifest, f, indent=2)

    print(f"Generated test fixtures in {fixtures_dir}")
    print(f"Files created:")
    for filename in manifest['files']:
        info = manifest['files'][filename]
        print(f"  {filename}: {info['expected_detections']} expected detections")
        print(f"    {info['description']}")


if __name__ == "__main__":
    main()
