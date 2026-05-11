"""
Auto-crop/zoom football clips based on motion detection.

For static endzone camera footage: detects where players are moving in each clip
and crops to that region automatically. Requires a one-time field boundary
calibration to exclude sideline activity.
"""

import cv2
import numpy as np
import subprocess
import json
import csv
import os
import re
import shutil
import logging

from pyfootball.encoding import SCRUB_FRIENDLY_VIDEO_ARGS

logger = logging.getLogger('pyfootball.autocrop')

# Minimum crop area as a fraction of the full frame. Prevents overly tight
# crops on plays with small motion regions (e.g. a short pass near the line).
# At 0.05, a 5120x2880 frame yields a minimum crop of ~1144x643.
MIN_CROP_FRACTION = 0.05

# -- Field calibration ---------------------------------------------------------

CALIBRATION_HELP = (
    "FIELD CALIBRATION\n"
    "  Click along the field edge to outline the playing area (4+ points,\n"
    "  clockwise or counter-clockwise). Exclude sideline benches, fans,\n"
    "  and off-field areas.\n"
    "  ENTER = save    C = clear & restart    ESC = cancel"
)


def _redraw_polygon(frame_display, original_frame, points):
    """Redraw the frame with current polygon state."""
    frame_display[:] = original_frame[:]

    for i, pt in enumerate(points):
        cv2.circle(frame_display, pt, 6, (0, 255, 0), -1)
        if i > 0:
            cv2.line(frame_display, points[i - 1], pt, (0, 255, 0), 2)

    if len(points) > 2:
        cv2.line(frame_display, points[-1], points[0], (0, 255, 0), 1)


def _calibration_mouse_callback(event, x, y, flags, param):
    """Mouse callback for field polygon selection."""
    points, frame_display, original_frame = param
    if event == cv2.EVENT_LBUTTONDOWN:
        points.append((x, y))
        _redraw_polygon(frame_display, original_frame, points)
        cv2.imshow("Field Calibration", frame_display)


def calibrate_field(video_path, output_json=None, display_width=1600):
    """
    Show a frame from the video and let the user click field boundary points.

    The displayed frame is pre-scaled to display_width and shown in a
    fixed-size window, so mouse coordinates always map cleanly back to the
    original image coordinates regardless of OpenCV's window-vs-image
    coordinate quirks.

    Args:
        video_path: Path to any video from this camera setup.
        output_json: Where to save the calibration. Defaults to same folder.
        display_width: Width to render the calibration frame at.

    Returns:
        list of (x, y) tuples defining the field polygon in original image
        coordinates, or None if cancelled.
    """
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        logger.error(f"Cannot open video: {video_path}")
        return None

    cap.set(cv2.CAP_PROP_POS_MSEC, 2000)
    ret, frame = cap.read()
    cap.release()

    if not ret:
        logger.error("Could not read a frame from the video.")
        return None

    orig_h, orig_w = frame.shape[:2]
    if display_width < orig_w:
        scale = display_width / orig_w
        display_h = int(round(orig_h * scale))
        display_frame = cv2.resize(frame, (display_width, display_h))
    else:
        scale = 1.0
        display_frame = frame.copy()

    points = []
    frame_display = display_frame.copy()
    original_display = display_frame.copy()

    print(CALIBRATION_HELP)

    cv2.namedWindow("Field Calibration", cv2.WINDOW_AUTOSIZE)
    cv2.setMouseCallback("Field Calibration", _calibration_mouse_callback,
                         (points, frame_display, original_display))

    cv2.imshow("Field Calibration", frame_display)

    while True:
        key = cv2.waitKey(0) & 0xFF
        if key == 13:  # ENTER
            if len(points) >= 4:
                break
            else:
                logger.info("Need at least 4 points. Keep clicking.")
        elif key == ord('c'):
            points.clear()
            _redraw_polygon(frame_display, original_display, points)
            cv2.imshow("Field Calibration", frame_display)
        elif key == 27:  # ESC
            cv2.destroyAllWindows()
            return None

    cv2.destroyAllWindows()

    inv_scale = 1.0 / scale
    points_orig = [(int(round(x * inv_scale)), int(round(y * inv_scale)))
                   for x, y in points]

    if output_json is None:
        video_dir = os.path.dirname(video_path)
        output_json = os.path.join(video_dir, "field_calibration.json")

    calibration = {
        "field_polygon": points_orig,
        "source_video": os.path.basename(video_path),
        "frame_width": orig_w,
        "frame_height": orig_h,
    }
    with open(output_json, 'w') as f:
        json.dump(calibration, f, indent=2)

    logger.info(f"Field calibration saved to {output_json}")
    return points_orig


def load_calibration(calibration_path):
    """Load a previously saved field calibration."""
    with open(calibration_path, 'r') as f:
        data = json.load(f)
    return data["field_polygon"], data["frame_width"], data["frame_height"]


def make_field_mask(polygon_points, frame_width, frame_height):
    """Create a binary mask from the field polygon."""
    mask = np.zeros((frame_height, frame_width), dtype=np.uint8)
    pts = np.array(polygon_points, dtype=np.int32).reshape((-1, 1, 2))
    cv2.fillPoly(mask, [pts], 255)
    return mask


# -- Motion detection ----------------------------------------------------------

def detect_motion_region(video_path, field_mask, sample_interval=15,
                         diff_threshold=30, min_area_fraction=0.05):
    """
    Analyze a video clip to find the bounding box of on-field motion.

    Args:
        video_path: Path to the video clip.
        field_mask: Binary mask of the playing field.
        sample_interval: Process every Nth frame.
        diff_threshold: Pixel intensity change threshold (0-255).
        min_area_fraction: Minimum crop area as fraction of field bounding box.

    Returns:
        tuple: ((x, y, w, h), motion_accumulator) or (None, None).
    """
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        logger.error(f"Cannot open video: {video_path}")
        return None, None

    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    total_frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)
    duration = total_frames / fps if fps > 0 else 0
    if duration > 3.0:
        skip_frames = int(fps * 0.5)
        for _ in range(skip_frames):
            ret = cap.grab()
            if not ret:
                break

    ret, first_frame = cap.read()
    if not ret:
        cap.release()
        return None, None

    first_gray = cv2.cvtColor(first_frame, cv2.COLOR_BGR2GRAY)
    first_gray = cv2.GaussianBlur(first_gray, (21, 21), 0)

    detector = cv2.AKAZE_create()
    matcher = cv2.BFMatcher(cv2.NORM_HAMMING)
    kp_ref, desc_ref = detector.detectAndCompute(first_gray, None)

    motion_accumulator = np.zeros_like(field_mask, dtype=np.float32)
    frame_count = 0
    sampled = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break
        frame_count += 1

        if frame_count % sample_interval != 0:
            continue

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (21, 21), 0)

        kp_cur, desc_cur = detector.detectAndCompute(gray, None)
        if desc_cur is not None and desc_ref is not None and len(kp_cur) >= 4:
            matches = matcher.knnMatch(desc_ref, desc_cur, k=2)
            good = [m for m, n in matches if m.distance < 0.7 * n.distance]
            if len(good) >= 4:
                pts_ref = np.float32([kp_ref[m.queryIdx].pt for m in good]).reshape(-1, 1, 2)
                pts_cur = np.float32([kp_cur[m.trainIdx].pt for m in good]).reshape(-1, 1, 2)
                M, inliers = cv2.estimateAffinePartial2D(pts_cur, pts_ref,
                                                         method=cv2.RANSAC,
                                                         ransacReprojThreshold=3.0)
                if M is not None:
                    gray = cv2.warpAffine(gray, M, (gray.shape[1], gray.shape[0]))

        diff = cv2.absdiff(first_gray, gray)
        _, thresh = cv2.threshold(diff, diff_threshold, 255, cv2.THRESH_BINARY)

        thresh = cv2.bitwise_and(thresh, field_mask)

        erode_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        thresh = cv2.erode(thresh, erode_kernel, iterations=1)
        dilate_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15))
        thresh = cv2.dilate(thresh, dilate_kernel, iterations=2)

        motion_accumulator += thresh.astype(np.float32)
        sampled += 1

    cap.release()

    if sampled == 0:
        logger.warning(f"No frames sampled from {video_path}")
        return None, None

    motion_binary = (motion_accumulator > (sampled * 0.10)).astype(np.uint8) * 255

    contours, _ = cv2.findContours(motion_binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    if not contours:
        logger.warning(f"No motion detected in {video_path}")
        return None, motion_accumulator

    field_area = np.count_nonzero(field_mask)
    min_contour_area = field_area * 0.005
    significant_contours = []
    max_heat = motion_accumulator.max() if motion_accumulator.max() > 0 else 1.0
    heat_threshold = 0.3

    for c in contours:
        if cv2.contourArea(c) > min_contour_area:
            significant_contours.append(c)
        else:
            # Small contour — include if motion intensity is high enough
            # (e.g. an isolated receiver running a route)
            contour_mask = np.zeros_like(field_mask)
            cv2.drawContours(contour_mask, [c], -1, 255, -1)
            region_heat = motion_accumulator[contour_mask > 0]
            if len(region_heat) > 0 and region_heat.mean() / max_heat > heat_threshold:
                significant_contours.append(c)

    if not significant_contours:
        significant_contours = contours

    all_points = np.vstack(significant_contours)
    x, y, w, h = cv2.boundingRect(all_points)

    field_contours, _ = cv2.findContours(field_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if field_contours:
        fx, fy, fw, fh = cv2.boundingRect(np.vstack(field_contours))
        min_w = int(fw * min_area_fraction)
        min_h = int(fh * min_area_fraction)
        if w < min_w:
            cx = x + w // 2
            w = min_w
            x = cx - w // 2
        if h < min_h:
            cy = y + h // 2
            h = min_h
            y = cy - h // 2

    return (x, y, w, h), motion_accumulator


def save_heatmap(motion_accumulator, first_frame_path, output_path,
                 crop_box=None, field_polygon=None):
    """Save a visual heatmap of motion overlaid on the first frame."""
    cap = cv2.VideoCapture(first_frame_path)
    cap.set(cv2.CAP_PROP_POS_MSEC, 2000)
    ret, bg_frame = cap.read()
    cap.release()
    if not ret:
        return

    heatmap = motion_accumulator.copy()
    max_val = heatmap.max()
    if max_val > 0:
        heatmap = (heatmap / max_val * 255).astype(np.uint8)
    else:
        heatmap = heatmap.astype(np.uint8)

    heatmap_color = cv2.applyColorMap(heatmap, cv2.COLORMAP_JET)

    blend_mask = (heatmap > 10).astype(np.float32)[:, :, np.newaxis]
    overlay = (bg_frame * (1 - blend_mask * 0.6) + heatmap_color * blend_mask * 0.6).astype(np.uint8)

    if field_polygon:
        pts = np.array(field_polygon, dtype=np.int32).reshape((-1, 1, 2))
        cv2.polylines(overlay, [pts], True, (255, 255, 0), 3)

    if crop_box:
        x, y, w, h = crop_box
        cv2.rectangle(overlay, (x, y), (x + w, y + h), (0, 255, 0), 4)

    out_w = 1920
    scale = out_w / overlay.shape[1]
    out_h = int(overlay.shape[0] * scale)
    overlay = cv2.resize(overlay, (out_w, out_h))

    cv2.imwrite(output_path, overlay, [cv2.IMWRITE_JPEG_QUALITY, 90])
    logger.info(f"Heatmap saved: {output_path}")


# -- Cropping ------------------------------------------------------------------

def compute_crop_box(motion_box, frame_width, frame_height, padding=0.15,
                     aspect_ratio=16/9, min_crop_fraction=None):
    """
    Expand the motion bounding box with padding and adjust to target aspect ratio.

    Args:
        motion_box: (x, y, w, h) from detect_motion_region.
        frame_width: Original video width.
        frame_height: Original video height.
        padding: Fraction of the box size to add as padding on each side.
        aspect_ratio: Target width/height ratio (default 16:9).
        min_crop_fraction: Minimum crop area as fraction of the full frame.
            Enforced as a minimum width (height follows from aspect ratio).

    Returns:
        (x, y, w, h) crop box clamped to frame boundaries.
    """
    x, y, w, h = motion_box

    pad_x = int(w * padding)
    pad_y = int(h * padding)
    x -= pad_x
    y -= pad_y
    w += 2 * pad_x
    h += 2 * pad_y

    current_ratio = w / h if h > 0 else aspect_ratio
    if current_ratio < aspect_ratio:
        new_w = int(h * aspect_ratio)
        x -= (new_w - w) // 2
        w = new_w
    else:
        new_h = int(w / aspect_ratio)
        y -= (new_h - h) // 2
        h = new_h

    # Enforce minimum crop size
    import math
    if min_crop_fraction is None:
        min_crop_fraction = MIN_CROP_FRACTION
    min_w = int(math.sqrt(min_crop_fraction * frame_width * frame_height * aspect_ratio))
    min_w = min_w + (min_w % 2)
    if w < min_w:
        cx = x + w // 2
        min_h = int(min_w / aspect_ratio)
        min_h = min_h + (min_h % 2)
        x = cx - min_w // 2
        y = (y + h // 2) - min_h // 2
        w = min_w
        h = min_h

    w = w + (w % 2)
    h = h + (h % 2)

    x = max(0, x)
    y = max(0, y)
    if x + w > frame_width:
        x = frame_width - w
    if y + h > frame_height:
        y = frame_height - h
    x = max(0, x)
    y = max(0, y)
    w = min(w, frame_width)
    h = min(h, frame_height)

    return (x, y, w, h)


def crop_video(input_path, output_path, crop_box, scale_width=1920):
    """
    Crop and optionally scale a video using FFmpeg.

    Args:
        input_path: Source video path.
        output_path: Destination video path.
        crop_box: (x, y, w, h) crop region.
        scale_width: Scale output to this width. None to keep crop resolution.
    """
    x, y, w, h = crop_box

    vf_filters = [f"crop={w}:{h}:{x}:{y}"]
    if scale_width and w != scale_width:
        scale_height = int(scale_width * h / w)
        scale_height = scale_height + (scale_height % 2)
        vf_filters.append(f"scale={scale_width}:{scale_height}")

    cmd = [
        'ffmpeg', '-y',
        '-hide_banner',
        '-loglevel', 'error',
        '-i', input_path,
        '-vf', ','.join(vf_filters),
        *SCRUB_FRIENDLY_VIDEO_ARGS,
        '-an',
        output_path
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        logger.error(f"FFmpeg error for {input_path}: {result.stderr}")
        return False
    return True


# -- Batch processing ----------------------------------------------------------

SUMMARY_FIELDS = [
    'clip', 'motion_x', 'motion_y', 'motion_w', 'motion_h',
    'crop_x', 'crop_y', 'crop_w', 'crop_h', 'crop_pct',
    'centroid_y_frac', 'motion_bottom_frac', 'motion_area_frac', 'action',
]
FULL_FRAME_THRESHOLD = 0.95


def _summarize_motion(motion_box, polygon, frame_width, frame_height):
    """
    Return (centroid_y_frac, motion_bottom_frac, motion_area_frac).

    centroid_y_frac and motion_bottom_frac are normalised to the field
    polygon's vertical span (0=top, 1=bottom). motion_bottom_frac tracks
    the lowest extent of the motion box, which is a stronger signal for
    "did the play come close to the camera" since back-of-field spectators
    only inflate the *top* of the motion box.
    """
    _, my, _, mh = motion_box
    poly_ys = [p[1] for p in polygon]
    poly_top, poly_bot = min(poly_ys), max(poly_ys)
    span = poly_bot - poly_top
    if span <= 0:
        return 0.0, 0.0, 0.0
    centroid_y_frac = (my + mh / 2 - poly_top) / span
    motion_bottom_frac = (my + mh - poly_top) / span
    motion_area_frac = (motion_box[2] * motion_box[3]) / (frame_width * frame_height)
    return centroid_y_frac, motion_bottom_frac, motion_area_frac


def _list_clips(clips_folder):
    video_extensions = ('.mp4', '.MP4', '.mov', '.MOV', '.avi', '.AVI')
    return sorted([
        f for f in os.listdir(clips_folder)
        if f.endswith(video_extensions) and os.path.isfile(os.path.join(clips_folder, f))
    ])


def _analyze_one(clip_path, field_mask, polygon, cal_width, cal_height,
                 sample_interval, padding):
    """Run motion detection + crop_box + summary stats for one clip."""
    motion_box, heatmap = detect_motion_region(
        clip_path, field_mask, sample_interval=sample_interval
    )
    if motion_box is None:
        return None
    crop_box = compute_crop_box(motion_box, cal_width, cal_height, padding=padding)
    cy_frac, mb_frac, ma_frac = _summarize_motion(motion_box, polygon, cal_width, cal_height)
    return {
        'motion_box': motion_box,
        'crop_box': crop_box,
        'heatmap': heatmap,
        'centroid_y_frac': cy_frac,
        'motion_bottom_frac': mb_frac,
        'motion_area_frac': ma_frac,
    }


def _summary_row(clip_name, analysis, action, cal_width, cal_height):
    """Build a summary CSV row dict from an analysis result."""
    if analysis is None:
        return {f: '' for f in SUMMARY_FIELDS} | {'clip': clip_name, 'action': action}
    mx, my, mw, mh = analysis['motion_box']
    x, y, w, h = analysis['crop_box']
    crop_pct = round((w * h) / (cal_width * cal_height) * 100, 1)
    return {
        'clip': clip_name,
        'motion_x': mx, 'motion_y': my, 'motion_w': mw, 'motion_h': mh,
        'crop_x': x, 'crop_y': y, 'crop_w': w, 'crop_h': h,
        'crop_pct': crop_pct,
        'centroid_y_frac': round(analysis['centroid_y_frac'], 4),
        'motion_bottom_frac': round(analysis['motion_bottom_frac'], 4),
        'motion_area_frac': round(analysis['motion_area_frac'], 6),
        'action': action,
    }


def analyze_clips_folder(clips_folder, calibration_path, output_folder=None,
                         padding=0.15, sample_interval=15, save_heatmaps=True,
                         summary_filename='autocrop_summary.csv'):
    """
    Run motion detection on every clip in a folder without encoding output.
    Writes heatmaps and a summary CSV with motion box, crop box, and the two
    angle-selection metrics (centroid_y_frac, motion_area_frac).

    Returns:
        Path to the summary CSV.
    """
    polygon, cal_width, cal_height = load_calibration(calibration_path)
    field_mask = make_field_mask(polygon, cal_width, cal_height)

    if output_folder is None:
        output_folder = os.path.join(clips_folder, 'analysis')
    os.makedirs(output_folder, exist_ok=True)

    heatmap_folder = os.path.join(output_folder, 'heatmaps')
    if save_heatmaps:
        os.makedirs(heatmap_folder, exist_ok=True)

    clips = _list_clips(clips_folder)
    if not clips:
        logger.warning(f"No video files found in {clips_folder}")
        return None

    logger.info(f"Analyzing {len(clips)} clips from {clips_folder}")

    csv_path = os.path.join(output_folder, summary_filename)
    with open(csv_path, 'w', newline='') as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=SUMMARY_FIELDS)
        writer.writeheader()

        for i, clip_name in enumerate(clips, 1):
            clip_path = os.path.join(clips_folder, clip_name)
            logger.info(f"[{i}/{len(clips)}] Analyzing {clip_name}...")
            analysis = _analyze_one(clip_path, field_mask, polygon,
                                    cal_width, cal_height, sample_interval, padding)
            if analysis is None:
                logger.warning(f"  Skipping {clip_name} -- no motion detected.")
                writer.writerow(_summary_row(clip_name, None, 'skipped', cal_width, cal_height))
                continue

            x, y, w, h = analysis['crop_box']
            logger.info(f"  Motion crop: x={x}, y={y}, w={w}, h={h}")

            if save_heatmaps and analysis['heatmap'] is not None:
                heatmap_name = os.path.splitext(clip_name)[0] + '_heatmap.jpg'
                save_heatmap(analysis['heatmap'], clip_path,
                             os.path.join(heatmap_folder, heatmap_name),
                             crop_box=analysis['crop_box'], field_polygon=polygon)

            writer.writerow(_summary_row(clip_name, analysis, 'analyzed',
                                         cal_width, cal_height))

    logger.info(f"Summary saved to {csv_path}")
    return csv_path


def process_clips_folder(clips_folder, calibration_path, output_folder=None,
                         padding=0.15, sample_interval=15, scale_width=1920,
                         save_heatmaps=True):
    """
    Auto-crop all video clips in a folder.

    Runs analyze_clips_folder for motion detection + heatmaps + summary, then
    encodes/copies each clip per its computed crop box.
    """
    polygon, cal_width, cal_height = load_calibration(calibration_path)
    field_mask = make_field_mask(polygon, cal_width, cal_height)

    if output_folder is None:
        output_folder = os.path.join(clips_folder, "autocropped")
    os.makedirs(output_folder, exist_ok=True)

    heatmap_folder = os.path.join(output_folder, "heatmaps")
    if save_heatmaps:
        os.makedirs(heatmap_folder, exist_ok=True)

    clips = _list_clips(clips_folder)
    if not clips:
        logger.warning(f"No video files found in {clips_folder}")
        return

    logger.info(f"Processing {len(clips)} clips from {clips_folder}")

    csv_path = os.path.join(output_folder, "autocrop_summary.csv")
    with open(csv_path, 'w', newline='') as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=SUMMARY_FIELDS)
        writer.writeheader()

        for i, clip_name in enumerate(clips, 1):
            clip_path = os.path.join(clips_folder, clip_name)
            logger.info(f"[{i}/{len(clips)}] Analyzing {clip_name}...")
            analysis = _analyze_one(clip_path, field_mask, polygon,
                                    cal_width, cal_height, sample_interval, padding)
            if analysis is None:
                logger.warning(f"  Skipping {clip_name} -- no motion detected.")
                writer.writerow(_summary_row(clip_name, None, 'skipped', cal_width, cal_height))
                continue

            crop_box = analysis['crop_box']
            x, y, w, h = crop_box
            logger.info(f"  Motion crop: x={x}, y={y}, w={w}, h={h}")

            if save_heatmaps and analysis['heatmap'] is not None:
                heatmap_name = os.path.splitext(clip_name)[0] + "_heatmap.jpg"
                save_heatmap(analysis['heatmap'], clip_path,
                             os.path.join(heatmap_folder, heatmap_name),
                             crop_box=crop_box, field_polygon=polygon)

            output_path = os.path.join(output_folder, clip_name)
            if (w * h) / (cal_width * cal_height) >= FULL_FRAME_THRESHOLD:
                shutil.copy2(clip_path, output_path)
                logger.info(f"  Full frame -- copied original to {output_path}")
                writer.writerow(_summary_row(clip_name, analysis, 'copied', cal_width, cal_height))
                continue

            success = crop_video(clip_path, output_path, crop_box, scale_width=scale_width)
            action = 'cropped' if success else 'failed'
            (logger.info if success else logger.error)(
                f"  {'Saved' if success else 'Failed to crop'}: {output_path}"
            )
            writer.writerow(_summary_row(clip_name, analysis, action, cal_width, cal_height))

    logger.info(f"Summary saved to {csv_path}")
    logger.info("Auto-crop complete.")


# -- Multi-angle selection -----------------------------------------------------
#
# When the same plays are captured by two cameras of different focal lengths
# (e.g. a wide and a zoomed shot from the same tripod), most plays end up
# better-served by one angle than the other -- the zoom gives higher resolution
# for far plays it can frame, while the wide shot is the only option for plays
# that approach the camera and would be cropped out of the zoom.
#
# The functions below implement ONE approach to this selection: per-clip motion
# detection in each angle, then a heuristic decision based on where motion
# occurs in the wide angle's field polygon.
#
#   - analyze_clips_folder():  motion detection only (no encoding) per angle.
#   - select_best_angle():     combine summaries, pick angle per play.
#   - render_angle_comparisons() / interactive_select_angle(): review/override.
#   - autocrop_from_manifest(): encode only the chosen angle per play.
#
# The default rule below uses motion_bottom_frac (lowest extent of the wide
# angle's motion box, normalised to the field polygon) plus a kick-play
# special case. On hand-labelled ground truth from the Lausanne W05 dataset
# (88 overlap clips) this lands ~77% accuracy with the predicted distribution
# close to actual; the interactive viewer covers the remaining ~20%.
#
# This approach has known limitations worth flagging for future iteration:
#   - The signal is sensitive to camera placement quirks (a wide angle aimed
#     too high or low can bias motion_bottom_frac systematically).
#   - Camera sway can leak into motion at the bottom edge of the polygon and
#     produce false positives even when AKAZE motion correction is on.
#   - The "always wide for kicks" rule is hard-coded to the project's clip
#     filename convention (Play_NNN_ODK_Type.mp4) and only matches K_Kick.
#   - It uses only the wide angle's motion data; a more robust approach
#     could combine signals from both angles (e.g. EZ2 cutoff detection),
#     incorporate play-type metadata directly, or use object detection /
#     player tracking instead of frame-difference motion.
#
# Treat this as an option, not the only path. Other approaches (different
# heuristics, ML-based selection, per-camera-setup calibration of the rule)
# should be considered as more datasets become available.

_DEFAULT_KICK_PATTERN = re.compile(r'_K_Kick', re.IGNORECASE)


def _default_angle_rule(per_angle_rows, angle_priority, threshold=0.25,
                        kick_pattern=_DEFAULT_KICK_PATTERN):
    """
    Default rule for picking between a wide and a zoomed angle:

    1. If the clip filename matches kick_pattern, prefer the wide angle —
       kicks span both ends of the field and the wide shot covers near
       (kicker / blockers) plus far (returner) action together.
    2. Otherwise, prefer the zoomed angle unless the wide angle's motion
       box bottom extends beyond `threshold` of the field, indicating the
       play approached the camera (a near play the zoom would crop).

    Uses motion_bottom_frac (the deepest extent of detected motion) rather
    than the centroid, since back-of-field spectators tend to inflate the
    top of the motion box but not its bottom — the bottom tracks "did the
    play approach the camera" more reliably.

    angle_priority is [wide, zoomed]. Falls back gracefully when only one
    angle has data for a clip.
    """
    available = [a for a in angle_priority if a in per_angle_rows
                 and per_angle_rows[a].get('action') == 'analyzed']
    if not available:
        for a in angle_priority:
            if a in per_angle_rows:
                return a, f'{a} only (no motion data)'
        return None, 'no angle has this clip'

    if len(available) == 1:
        return available[0], f'{available[0]} only'

    wide = angle_priority[0]
    zoomed = angle_priority[1]

    clip_name = per_angle_rows[wide].get('clip', '')
    if kick_pattern and kick_pattern.search(clip_name):
        return wide, 'kick play -> wide'

    mb = float(per_angle_rows[wide].get('motion_bottom_frac') or 0.5)
    if mb >= threshold:
        return wide, f'near play (motion_bottom_frac={mb:.2f}>={threshold})'
    return zoomed, f'far play (motion_bottom_frac={mb:.2f}<{threshold})'


def select_best_angle(angle_summaries, output_csv, angle_priority=None, rule=None):
    """
    Combine per-angle motion summaries and choose the best angle per play.

    Args:
        angle_summaries: dict {angle_name: motion_summary_csv_path}.
        output_csv: path for the manifest CSV.
        angle_priority: ordered list of angle names; first is the wide
            reference. Defaults to sorted keys.
        rule: callable(per_angle_rows, angle_priority) -> (angle, reason).
            Defaults to _default_angle_rule.

    Returns:
        Path to the manifest CSV.
    """
    if angle_priority is None:
        angle_priority = sorted(angle_summaries.keys())
    if rule is None:
        rule = _default_angle_rule

    by_angle = {}
    all_clips = set()
    for angle, path in angle_summaries.items():
        with open(path, newline='') as f:
            rows = {r['clip']: r for r in csv.DictReader(f)}
        by_angle[angle] = rows
        all_clips.update(rows)

    fieldnames = ['clip', 'chosen_angle', 'reason']
    for a in angle_priority:
        fieldnames += [f'{a}_centroid_y_frac', f'{a}_motion_bottom_frac',
                       f'{a}_motion_area_frac', f'{a}_action']

    n_chosen = {a: 0 for a in angle_priority}
    n_chosen[None] = 0

    with open(output_csv, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for clip in sorted(all_clips):
            per_angle = {a: by_angle[a][clip] for a in angle_priority
                         if clip in by_angle.get(a, {})}
            chosen, reason = rule(per_angle, angle_priority)
            n_chosen[chosen if chosen in n_chosen else None] += 1
            row = {'clip': clip, 'chosen_angle': chosen or '', 'reason': reason}
            for a in angle_priority:
                r = per_angle.get(a, {})
                row[f'{a}_centroid_y_frac'] = r.get('centroid_y_frac', '')
                row[f'{a}_motion_bottom_frac'] = r.get('motion_bottom_frac', '')
                row[f'{a}_motion_area_frac'] = r.get('motion_area_frac', '')
                row[f'{a}_action'] = r.get('action', '')
            writer.writerow(row)

    summary = ', '.join(f'{a}={n_chosen[a]}' for a in angle_priority)
    logger.info(f"Selection manifest saved to {output_csv}  ({summary})")
    return output_csv


def _compose_compare_image(stem, angle_heatmap_folders, angles, chosen_angle,
                           title=None, panel_height=540, status=None):
    """Build the side-by-side comparison image for one clip."""
    panels = []
    for angle in angles:
        heatmap_path = os.path.join(angle_heatmap_folders[angle],
                                    stem + '_heatmap.jpg')
        if os.path.exists(heatmap_path):
            img = cv2.imread(heatmap_path)
        else:
            img = np.full((panel_height, int(panel_height * 16 / 9), 3),
                          60, dtype=np.uint8)
            cv2.putText(img, 'no heatmap', (20, panel_height // 2),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (180, 180, 180), 2)

        ph, pw = img.shape[:2]
        scale = panel_height / ph
        img = cv2.resize(img, (int(pw * scale), panel_height))

        label = angle + (' [SELECTED]' if angle == chosen_angle else '')
        bar_color = (0, 130, 0) if angle == chosen_angle else (50, 50, 50)
        bar = np.full((40, img.shape[1], 3), bar_color, dtype=np.uint8)
        cv2.putText(bar, label, (12, 28),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        panels.append(np.vstack([bar, img]))

    if not panels:
        return None

    max_h = max(p.shape[0] for p in panels)
    padded = []
    for p in panels:
        if p.shape[0] < max_h:
            pad = np.zeros((max_h - p.shape[0], p.shape[1], 3), dtype=np.uint8)
            p = np.vstack([p, pad])
        padded.append(p)
    combined = np.hstack(padded)

    if title:
        title_bar = np.zeros((36, combined.shape[1], 3), dtype=np.uint8)
        cv2.putText(title_bar, title, (10, 26),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (220, 220, 220), 1)
        combined = np.vstack([title_bar, combined])

    if status:
        status_bar = np.zeros((36, combined.shape[1], 3), dtype=np.uint8)
        cv2.putText(status_bar, status, (10, 26),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (180, 220, 255), 1)
        combined = np.vstack([combined, status_bar])

    return combined


def render_angle_comparisons(manifest_csv, angle_heatmap_folders, output_folder,
                             panel_height=540):
    """
    Render side-by-side heatmap comparisons for each clip in the manifest, with
    the chosen angle's panel highlighted.

    Args:
        manifest_csv: selection manifest from select_best_angle().
        angle_heatmap_folders: dict {angle_name: heatmap folder}.
        output_folder: where to save comparison JPGs.
        panel_height: pixel height of each angle panel (width is auto from aspect).
    """
    os.makedirs(output_folder, exist_ok=True)
    angles = list(angle_heatmap_folders.keys())

    with open(manifest_csv, newline='') as f:
        rows = list(csv.DictReader(f))

    written = 0
    for row in rows:
        clip = row['clip']
        stem = os.path.splitext(clip)[0]
        title = f"{clip}  ({row.get('reason', '')})"
        combined = _compose_compare_image(stem, angle_heatmap_folders, angles,
                                          row['chosen_angle'], title=title,
                                          panel_height=panel_height)
        if combined is None:
            continue
        out_path = os.path.join(output_folder, stem + '_compare.jpg')
        cv2.imwrite(out_path, combined, [cv2.IMWRITE_JPEG_QUALITY, 85])
        written += 1

    logger.info(f"Wrote {written} comparison images to {output_folder}")


_ARROW_LEFT_CODES = {2424832, 65361, 81}
_ARROW_RIGHT_CODES = {2555904, 65363, 83}


def interactive_select_angle(manifest_csv, angle_heatmap_folders,
                             output_csv=None, angle_priority=None,
                             panel_height=540):
    """
    Interactive viewer to scroll through the manifest and override per-play
    angle selections. Saves changes back to the manifest CSV.

    Keys:
        Left / a / h           previous play
        Right / d / l          next play
        1, 2, 3 ...            select angle from angle_priority
        ENTER                  save manifest
        BACKSPACE              revert this play's choice to the auto-selection
        ESC / q                exit (warns on unsaved changes)

    Args:
        manifest_csv: manifest path from select_best_angle().
        angle_heatmap_folders: dict {angle_name: heatmap folder}.
        output_csv: where to write changes; defaults to overwriting manifest_csv.
        angle_priority: numbered key order. Defaults to angle_heatmap_folders keys.
        panel_height: per-angle panel height.
    """
    if output_csv is None:
        output_csv = manifest_csv
    if angle_priority is None:
        angle_priority = list(angle_heatmap_folders.keys())

    with open(manifest_csv, newline='') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)

    if not rows:
        logger.warning("Manifest is empty; nothing to review.")
        return

    auto_choices = [r['chosen_angle'] for r in rows]
    auto_reasons = [r.get('reason', '') for r in rows]
    dirty = False
    idx = 0

    print("Angle review:  Left/Right navigate  | "
          + "  ".join(f"{i+1}={a}" for i, a in enumerate(angle_priority))
          + "  | ENTER=save  BKSPC=revert  ESC=exit")

    cv2.namedWindow("Angle Selector", cv2.WINDOW_AUTOSIZE)

    def render():
        row = rows[idx]
        chosen = row['chosen_angle']
        auto = auto_choices[idx]
        modified = ' *EDITED' if chosen != auto else ''
        title = f"[{idx+1}/{len(rows)}]  {row['clip']}    auto={auto or '-'}    chosen={chosen or '-'}{modified}"
        keys_hint = ("Left/Right nav  |  "
                     + "  ".join(f"{i+1}:{a}" for i, a in enumerate(angle_priority))
                     + "  |  ENTER=save  BKSPC=revert  ESC=exit")
        status = f"{row.get('reason', '')}    [{keys_hint}]"
        return _compose_compare_image(
            os.path.splitext(row['clip'])[0],
            angle_heatmap_folders, angle_priority,
            chosen, title=title, status=status, panel_height=panel_height,
        )

    def save():
        nonlocal dirty
        with open(output_csv, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        dirty = False
        logger.info(f"Saved manifest: {output_csv}")

    cv2.imshow("Angle Selector", render())

    while True:
        key = cv2.waitKeyEx(0)
        if key < 0:
            break
        masked = key & 0xFF

        if masked == 27 or masked == ord('q'):
            if dirty:
                logger.warning("Exiting with unsaved changes "
                               "(press ENTER before ESC to save).")
            break
        elif masked == 13:
            save()
        elif masked == 8:  # backspace -> revert this row to auto
            if rows[idx]['chosen_angle'] != auto_choices[idx]:
                rows[idx]['chosen_angle'] = auto_choices[idx]
                rows[idx]['reason'] = auto_reasons[idx]
                dirty = True
        elif key in _ARROW_LEFT_CODES or masked in (ord('a'), ord('h')):
            idx = (idx - 1) % len(rows)
        elif key in _ARROW_RIGHT_CODES or masked in (ord('d'), ord('l')):
            idx = (idx + 1) % len(rows)
        elif ord('1') <= masked <= ord('9'):
            ai = masked - ord('1')
            if ai < len(angle_priority):
                new_choice = angle_priority[ai]
                if rows[idx]['chosen_angle'] != new_choice:
                    rows[idx]['chosen_angle'] = new_choice
                    rows[idx]['reason'] = 'manual override'
                    dirty = True
                idx = (idx + 1) % len(rows)
        else:
            continue

        cv2.imshow("Angle Selector", render())

    cv2.destroyAllWindows()


def autocrop_from_manifest(manifest_csv, angle_clip_folders, angle_summaries,
                           output_folder, scale_width=1920):
    """
    Encode the chosen angle for each play in the manifest, using each angle's
    pre-computed crop box from analyze_clips_folder.

    Args:
        manifest_csv: selection manifest from select_best_angle().
        angle_clip_folders: dict {angle_name: clips folder}.
        angle_summaries: dict {angle_name: motion_summary_csv_path}.
        output_folder: where to write final clips.
        scale_width: output scale width.
    """
    os.makedirs(output_folder, exist_ok=True)

    by_angle = {}
    for angle, path in angle_summaries.items():
        with open(path, newline='') as f:
            by_angle[angle] = {r['clip']: r for r in csv.DictReader(f)}

    with open(manifest_csv, newline='') as f:
        manifest_rows = list(csv.DictReader(f))

    out_csv_path = os.path.join(output_folder, 'manifest_autocrop_summary.csv')
    with open(out_csv_path, 'w', newline='') as out_csv:
        writer = csv.writer(out_csv)
        writer.writerow(['clip', 'angle', 'action'])

        for i, row in enumerate(manifest_rows, 1):
            clip = row['clip']
            angle = row['chosen_angle']
            if not angle:
                logger.warning(f"[{i}/{len(manifest_rows)}] {clip}: no angle chosen, skipping")
                writer.writerow([clip, '', 'skipped_no_angle'])
                continue

            in_path = os.path.join(angle_clip_folders[angle], clip)
            if not os.path.exists(in_path):
                logger.warning(f"[{i}/{len(manifest_rows)}] {clip}: source missing in {angle}")
                writer.writerow([clip, angle, 'source_missing'])
                continue

            out_path = os.path.join(output_folder, clip)
            summary_row = by_angle.get(angle, {}).get(clip, {})

            logger.info(f"[{i}/{len(manifest_rows)}] {clip} <- {angle}")

            if not summary_row.get('crop_x'):
                shutil.copy2(in_path, out_path)
                writer.writerow([clip, angle, 'copied_no_crop'])
                continue

            crop_box = (int(summary_row['crop_x']), int(summary_row['crop_y']),
                        int(summary_row['crop_w']), int(summary_row['crop_h']))
            crop_pct = float(summary_row.get('crop_pct') or 0)
            if crop_pct >= FULL_FRAME_THRESHOLD * 100:
                shutil.copy2(in_path, out_path)
                writer.writerow([clip, angle, 'copied_full_frame'])
                continue

            ok = crop_video(in_path, out_path, crop_box, scale_width=scale_width)
            writer.writerow([clip, angle, 'cropped' if ok else 'failed'])

    logger.info(f"Manifest autocrop complete; summary: {out_csv_path}")
    return out_csv_path
