# Declick Detection Investigation Notes

## Overview

Investigation into why the declick tool wasn't fixing audible clicks in test files `sara_main` and `sara_right`. The original detection only found some artifacts but missed others.

## Test Files

- `sara_main`: 4.14s mono, 48kHz - 2 known clicks (~1.1s, ~3.3s)
- `sara_right`: 9.98s mono, 48kHz - 3+ known clicks (~2.9s, ~5.1s, ~7.2s)

## Artifact Types Discovered

### 1. Zero Dropouts (Already Handled)

**Pattern**: Exact `0.0` sample values where the waveform should have signal.

**Example** (sara_main sample 53405-53406):
```
53404:  0.062338
53405:  0.000000  <-- dropout
53406:  0.000000  <-- dropout
53407:  0.097313
```

**Cause**: ADAT sync errors, buffer underruns, or digital transmission glitches that result in missing samples being filled with zeros.

**Detection**: Sample value < 1e-9 with neighboring samples having amplitude > threshold.

**Original issue**: Threshold was 0.05, but some dropouts had smaller neighbors (~0.01-0.02). Fixed by adding a separate `exact_zero_threshold` parameter (0.008) that's more sensitive for exact zeros.

### 2. Sync Artifacts (NEW - Previously Undetected)

**Pattern**: 3+ consecutive samples with nearly IDENTICAL large sample-to-sample differences.

**Example** (sara_right sample 245286-245288):
```
245285:  0.038727  (diff from prev: -0.021)
245286: -0.017242  (diff from prev: -0.056)  <-- artifact
245287: -0.073212  (diff from prev: -0.056)  <-- artifact
245288: -0.129181  (diff from prev: -0.056)  <-- artifact
245289: -0.139069  (diff from prev: -0.010)
```

Three consecutive jumps of exactly -0.055969 - this NEVER occurs in natural audio.

**Cause**: Likely phase/sync discontinuities where the audio stream was interrupted and samples were displaced uniformly. Could be caused by:
- Clock drift between digital devices
- Buffer boundary issues
- Sample rate conversion glitches

**Detection criteria**:
- Minimum jump size: 0.04 (absolute value)
- Tolerance for "identical": 0.001 (jumps must be within this of each other)
- Minimum consecutive: 3 jumps

**Found instances in sara_right**:
- Sample 103047 (2.15s): 4 consecutive jumps of +0.054
- Sample 245286 (5.11s): 3 consecutive jumps of -0.056

## Repair Methods Tested

### Linear Interpolation
- **Method**: Draw straight line from last good sample to next good sample
- **Result**: Reduces artifact but doesn't eliminate it
- **Why**: Audio waveforms are curved (sinusoidal), not linear. A straight line creates audible discontinuity at the transition points.

### Polynomial Interpolation (BETTER)
- **Method**: Fit cubic polynomial to 5 good samples on each side, interpolate bad samples
- **Result**: Significantly reduces/eliminates artifact
- **Why**: Polynomial curve matches the natural shape of audio waveforms

### Wider vs Narrower Repair Window
- **Tested**: Repairing exactly the artifact samples (3) vs including neighbors (5+)
- **Result**: Narrower is better - repairing extra samples that aren't actually bad introduces new artifacts
- **Lesson**: Only repair samples that are actually damaged

## Implementation Changes

### detect_dropouts()
- Added `exact_zero_threshold` parameter (default 0.008) for exact zeros
- Kept higher `dropout_threshold` (0.05) for near-zeros to avoid false positives
- Exact zeros are very likely dropouts, so they can use a lower neighbor threshold

### detect_sync_artifacts() (NEW)
- Detects runs of 3+ consecutive samples with identical large jumps
- Parameters: `min_jump=0.04`, `tolerance=0.001`, `min_consecutive=3`

### repair_clicks()
- Short runs (1-2 samples): Linear interpolation (fast, sufficient)
- Longer runs (3+): Polynomial curve fitting with 5 samples context on each side
- Uses degree-3 polynomial (cubic) for smooth curves

## Validation

### Confirmed Working
- Zero dropouts at ~1.1s and ~3.3s in sara_main: FIXED
- Zero dropouts at ~2.9s in sara_right: FIXED
- Sync artifact at ~5.1s in sara_right: SIGNIFICANTLY IMPROVED

### Still Investigating
- User reported click at ~7.2s in sara_right - no clear artifact found at that timestamp
- May be a different type of artifact or user timestamp was approximate

## Key Learnings

1. **Multiple artifact types exist** - can't assume all clicks are the same pattern
2. **Threshold tuning matters** - too high misses real artifacts, too low creates false positives
3. **Exact zeros are special** - they're almost always artifacts when surrounded by signal
4. **Repair method matters** - polynomial interpolation is worth the extra computation for multi-sample artifacts
5. **Identical consecutive diffs are unnatural** - this is a reliable indicator of sync problems
