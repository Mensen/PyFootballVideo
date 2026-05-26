# Auto-Crop: Motion-Based Video Cropping for Static Camera Footage

## Overview

The `pyfootball.autocrop` module automatically crops/zooms football game clips filmed from a static camera (typically an endzone GoPro on a tripod). It detects where players are moving in each clip and crops to that region, producing a zoomed-in view of the action. Reach it interactively from the `pyfootball` CLI (option 3), or import the functions directly.

This is useful because with a wide-angle static camera, far-away plays only occupy a small portion of the frame. Manual digital zoom is tedious across hundreds of clips per game.

## How It Works

### 1. Field Calibration (one-time per camera setup)

Since the camera also captures sidelines, team benches, spectators, and other off-field areas where people move, we need to tell the system where the playing field is.

**Run:**
```
pyfootball  →  option 3 (Auto-crop)  →  option 1
```

This opens a frame from a video and lets you click the corners of the playing field to define a polygon mask. The polygon should trace the sidelines and endlines — everything outside it is ignored during motion detection.

**Tips:**
- Click clockwise or counter-clockwise around the field perimeter
- Include the full field from sideline to sideline, endzone to endzone
- Exclude team benches, spectator areas, and the area behind the endzone (where the camera sits)
- At least 4 points required; more points give a tighter fit on curved field edges
- Press ENTER to save, C to clear and restart, ESC to cancel

**Output:** `field_calibration.json` saved next to the video. Reusable for all clips from the same camera position.

### 2. Motion Detection

For each clip, the system:

1. **Skips the first 0.5 seconds** to avoid initial encoding transients (common with GoPro footage)
2. **Samples every 15th frame** (~2 frames/sec at 30fps) for speed
3. **Stabilizes each frame** against the reference using feature-based alignment (see Motion Correction below)
4. **Computes the absolute difference** between each sampled frame and the reference
5. **Applies the field mask** to ignore off-field areas
6. **Erodes then dilates** the difference to remove thin line artifacts and fill player gaps
7. **Accumulates** all frames into a motion heatmap
8. **Thresholds** the heatmap (pixels active in >10% of frames) and filters small contours (<0.5% of field area)
9. **Computes a bounding box** around the remaining motion

### 3. Crop Box Calculation

The raw motion bounding box is expanded:
- **Padding**: 15% on each side (configurable)
- **Aspect ratio**: adjusted to 16:9 for compatibility with analysis tools
- **Minimum size**: enforced relative to the field area
- **Clamped** to frame boundaries

### 4. Video Output

- If the crop covers **<95%** of the frame: cropped and scaled to 1920px wide via FFmpeg
- If the crop covers **>=95%**: original file is copied as-is (no quality loss)
- A **heatmap image** is saved for each clip showing the detected motion overlaid on the video frame, with the crop box drawn in green and the field polygon in cyan
- A **summary CSV** (`autocrop_summary.csv`) logs the motion box, crop box, crop percentage, and action for every clip

## Usage

```
pyfootball  →  option 3 (Auto-crop)
```

**Option 1:** Calibrate field boundary only
**Option 2:** Auto-crop clips in a folder (requires existing calibration)
**Option 3:** Calibrate + auto-crop in one step

### Programmatic usage

```python
from pyfootball.autocrop import process_clips_folder

process_clips_folder(
    clips_folder="path/to/clips",
    calibration_path="path/to/field_calibration.json",
    padding=0.15,          # padding around motion (fraction)
    sample_interval=15,    # analyze every Nth frame
    scale_width=1920,      # output width in pixels
    save_heatmaps=True,    # save heatmap images
    encoding_preset=None,  # see pyfootball.encoding.ENCODING_PRESETS
)
```

## Output Structure

```
clips_folder/
  autocropped/
    Play_001.mp4          # cropped (or copied) clips
    Play_002.mp4
    ...
    autocrop_summary.csv  # per-clip summary
    heatmaps/
      Play_001_heatmap.jpg
      Play_002_heatmap.jpg
      ...
```

## Performance

Typical processing times (per clip):
- 4K (3840x2160): ~10-15 seconds
- 5K (5120x2880): ~20-30 seconds

Total for a 130-clip game: ~20-45 minutes depending on resolution.

## Key Parameters

| Parameter | Default | Purpose |
|-----------|---------|---------|
| `padding` | 0.15 | Extra space around detected motion (fraction of box size) |
| `sample_interval` | 15 | Analyze every Nth frame (higher = faster, less precise) |
| `diff_threshold` | 30 | Pixel intensity change to count as motion (0-255) |
| `min_area_fraction` | 0.05 | Minimum crop size as fraction of field area |
| `scale_width` | 1920 | Output video width in pixels |
| `full_frame_threshold` | 0.95 | Crop percentage above which original is copied instead |

---

## Motion Correction: The Stabilization Story

### The Problem

With a static tripod camera, frame differencing should cleanly isolate player movement. In practice, two issues cause false motion detection on high-contrast static elements (yard lines, goal lines, shadow edges):

#### 1. Encoding artifacts (minor)
GoPro clips sometimes have compression differences in the first few frames (I-frame vs P-frame encoding). High-contrast edges look slightly different in the initial frame compared to later frames.

**Solution:** Skip the first 0.5 seconds before taking the reference frame. Only applied to clips longer than 3 seconds.

#### 2. Camera sway from wind (major)
An elevated tripod in open air sways in the wind. Even sub-pixel movement causes the white yard lines to shift against the green grass background, creating strong false motion signals across the entire frame. This manifests as horizontal streaks in the motion heatmap along every yard line.

**Solutions tried, in order:**

1. **Phase correlation (translation only):** Detects the global X/Y shift between frames using frequency-domain correlation. Works well for pure lateral movement but fails when the camera also rotates slightly (which a swaying tripod does). Sub-pixel precision was also insufficient at reduced resolution — downscaling for speed lost the accuracy needed to cancel out yard line artifacts.

2. **Phase correlation with threshold:** Only compensated when shift exceeded 0.5px. This missed the sub-pixel shifts that were still enough to trigger yard line artifacts.

3. **Phase correlation on image strips:** Used a horizontal strip from the center of the frame to speed up computation. Failed because player motion within the strip corrupted the shift estimate.

4. **Morphological erosion:** Erode the thresholded difference image to remove thin line artifacts before dilating. Helps as a secondary measure but cannot fully solve the problem when the camera sway is significant — the yard line artifacts become too thick to erode without also removing distant players.

5. **Feature-based alignment with AKAZE + RANSAC (current solution):** Detect keypoints (AKAZE) on both the reference and current frame, match them, then use RANSAC to compute an affine transform (translation + rotation + scale). RANSAC naturally rejects player motion as outliers because the vast majority of matched keypoints are on static background (grass texture, field markings, structures). The affine transform handles the full range of tripod sway — not just translation but also the slight rotation that phase correlation missed.

**The current pipeline applies the 5px morphological erosion as a secondary cleanup on top of feature-based alignment.** This handles any residual artifacts from imperfect stabilization while being small enough to preserve distant player motion (typically 10-15px wide).

### Diagnostics

If yard line artifacts reappear in future footage, check the heatmap images:
- **Horizontal streaks along yard lines** → stabilization is not fully compensating camera movement
- **Scattered dots on field markings** → encoding artifacts; try increasing the initial skip time
- **Motion on sidelines** → field calibration polygon needs tightening

The `diff_threshold` (default 30) can also be raised to reduce sensitivity, at the cost of potentially missing subtle player movement far from the camera.

## Multi-Angle Selection

When the same plays are captured by two cameras of different focal lengths from the same tripod (a wide shot and a zoomed shot), most plays end up better-served by one angle than the other. The zoom gives higher resolution for far plays it can frame; the wide shot is the only option for plays that approach the camera and would be cropped out of the zoom.

The pipeline below avoids the cost of fully autocropping every clip from every angle: it does the cheap motion-detection step per angle, picks the best angle per play, and only encodes the winners.

### Pipeline

```
                analyze_clips_folder   (per angle)
                       │
                       ▼
            motion_summary.csv per angle (heatmaps + metrics)
                       │
                       ▼
                select_best_angle      (combines summaries)
                       │
                       ▼
                  manifest.csv  ◄─── interactive_select_angle  (review/override)
                       │
                       ▼
                autocrop_from_manifest (encodes only chosen angles)
                       │
                       ▼
                final clips folder
```

### Functions

- **`analyze_clips_folder(clips_folder, calibration_path, output_folder=None, ...)`** — motion detection only, no encoding. Writes heatmaps and a summary CSV with motion box, computed crop box, and selection metrics. Same heavy lifting as `process_clips_folder` but skips ffmpeg encoding, so ~3-5x faster.

- **`select_best_angle(angle_summaries, output_csv, angle_priority=None, rule=None)`** — combines per-angle summaries into a manifest CSV with `chosen_angle` and `reason` columns. The default rule is described below; pass `rule=` to override.

- **`render_angle_comparisons(manifest_csv, angle_heatmap_folders, output_folder, panel_height=540)`** — for each clip, renders a side-by-side comparison JPG with each angle's heatmap, the chosen angle highlighted in green. Useful for offline review.

- **`interactive_select_angle(manifest_csv, angle_heatmap_folders, output_csv=None, angle_priority=None)`** — OpenCV viewer for in-place editing of the manifest:
  - **Left/Right** or **a/d**: navigate plays
  - **1, 2, …**: select angle (matches `angle_priority` order)
  - **ENTER**: save manifest
  - **BACKSPACE**: revert this play to the auto-selection
  - **ESC** / **q**: exit (warns on unsaved changes)

- **`autocrop_from_manifest(manifest_csv, angle_clip_folders, angle_summaries, output_folder, scale_width=1920, encoding_preset=None)`** — encodes only the chosen angle per play, reusing each angle's pre-computed crop box. Writes `manifest_autocrop_summary.csv` with per-clip action (cropped / copied_full_frame / source_missing / failed). `encoding_preset` selects a preset from `pyfootball.encoding.ENCODING_PRESETS` (`all_intra`, `short_gop` [default], `standard`); `None` uses the module default. The same kwarg is available on `process_clips_folder()` and `crop_video()` for single-angle flows.

### Summary CSV columns

Both `analyze_clips_folder` and `process_clips_folder` write the same CSV format (`autocrop_summary.csv`):

| Column | Notes |
|--------|-------|
| `clip` | filename |
| `motion_x/y/w/h` | raw motion bounding box in original frame coords |
| `crop_x/y/w/h` | padded + aspect-corrected crop box |
| `crop_pct` | crop area as percent of full frame |
| `centroid_y_frac` | motion centroid Y, normalized to field polygon vertical span (0=top, 1=bottom) |
| `motion_bottom_frac` | motion box bottom, same normalization — primary selection signal |
| `motion_area_frac` | motion box area / full frame area |
| `action` | `cropped` / `copied` / `skipped` / `failed` / `analyzed` |

### Default selection rule

`_default_angle_rule(per_angle_rows, angle_priority, threshold=0.25, kick_pattern=...)`:

1. **Fallbacks first**: if only one angle has data for the clip, use it.
2. **Kick override**: if the clip filename matches `_K_Kick` (default `kick_pattern`), prefer the wide angle. Kicks span both ends of the field; the wide shot covers near (kicker) and far (returner) action together.
3. **Otherwise**, look at the wide angle's `motion_bottom_frac`:
   - `>= threshold` (default `0.25`) → wide angle (near play; the zoom would crop the action)
   - `< threshold` → zoomed angle (far play; the zoom adds resolution)

**Why `motion_bottom_frac` not centroid:** in static endzone footage, a thin band of moving people behind the back line (coaches, refs, fans) pulls the *top* of the motion box up regardless of the play's actual location. The centroid is dragged with it. The motion box *bottom* is set by the deepest player and is therefore a much cleaner "did the play approach the camera" signal.

### Known limitations

This rule was validated on one dataset (Lausanne W05, two cameras imperfectly placed) with manual ground-truth labels. It hits ~77% accuracy with the predicted distribution close to actual; the viewer covers the rest.

- **Sensitive to camera placement.** A wide angle aimed too high or low can bias `motion_bottom_frac` systematically; thresholds may need per-setup adjustment.
- **Camera-sway false positives.** AKAZE-based stabilization doesn't fully compensate; near-bottom-edge motion can be sway artifacts rather than real near-camera play. Mitigation is currently a manual override.
- **The kick rule is filename-coupled.** It assumes the project's `Play_NNN_ODK_Type.mp4` naming convention and only catches `_K_Kick`. Other patterns (e.g., punts) would need explicit handling.
- **Single-angle signal.** Only the wide angle's motion drives the decision. A more robust approach could combine signals from both angles (e.g., zoom-cutoff detection on motion bottom-touch), incorporate play-type metadata directly from the dartclip, or use object detection / player tracking instead of frame differencing.

Treat the current rule as one option, not the only path. Other approaches (different heuristics, ML-based selection, per-camera-setup calibration) should be considered as more datasets become available.

### Example: end-to-end multi-angle workflow

```python
from pyfootball.autocrop import (
    analyze_clips_folder, select_best_angle,
    render_angle_comparisons, interactive_select_angle,
    autocrop_from_manifest,
)

# 1. Analyze each angle (motion detection only)
ez1_summary = analyze_clips_folder('clips/EZ1', 'clips/EZ1/field_calibration.json')
ez2_summary = analyze_clips_folder('clips/EZ2', 'clips/EZ2/field_calibration.json')

# 2. Auto-select
select_best_angle(
    {'EZ1': ez1_summary, 'EZ2': ez2_summary},
    output_csv='manifest.csv',
    angle_priority=['EZ1', 'EZ2'],  # [wide, zoomed]
)

# 3. Optional: review and override interactively
interactive_select_angle(
    'manifest.csv',
    {'EZ1': 'clips/EZ1/analysis/heatmaps',
     'EZ2': 'clips/EZ2/analysis/heatmaps'},
)

# 4. Encode only chosen clips
autocrop_from_manifest(
    'manifest.csv',
    angle_clip_folders={'EZ1': 'clips/EZ1', 'EZ2': 'clips/EZ2'},
    angle_summaries={'EZ1': ez1_summary, 'EZ2': ez2_summary},
    output_folder='clips/best_angle',
)
```

## Dependencies

- **OpenCV** (`opencv-python`): frame reading, feature detection, image processing
- **FFmpeg**: video cropping and scaling (called via subprocess)
- **NumPy**: array operations
