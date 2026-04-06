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
import shutil
import logging

logger = logging.getLogger('pyfootball.autocrop')

# -- Field calibration ---------------------------------------------------------

CALIBRATION_HELP = [
    "FIELD CALIBRATION: Click along the sidelines to outline the playing field.",
    "Include the ENTIRE field - sideline to sideline, endzone to endzone.",
    "The polygon masks out sideline benches, fans, and off-field areas.",
    "Click points clockwise or counter-clockwise around the field edge.",
    "",
    "  ENTER = save    C = clear & restart    ESC = cancel",
]


def _draw_help(frame):
    """Draw help text with a semi-transparent background."""
    y_start = 15
    for i, line in enumerate(CALIBRATION_HELP):
        y = y_start + i * 30
        cv2.putText(frame, line, (12, y + 2),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 3)
        cv2.putText(frame, line, (10, y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)


def _redraw_polygon(frame_display, original_frame, points):
    """Redraw the frame with current polygon state."""
    frame_display[:] = original_frame[:]
    _draw_help(frame_display)

    for i, pt in enumerate(points):
        cv2.circle(frame_display, pt, 10, (0, 255, 0), -1)
        cv2.putText(frame_display, str(i + 1), (pt[0] + 14, pt[1] + 6),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        if i > 0:
            cv2.line(frame_display, points[i - 1], pt, (0, 255, 0), 4)

    if len(points) > 2:
        cv2.line(frame_display, points[-1], points[0], (0, 255, 0), 2)

    status = f"Points: {len(points)}  (need at least 4)"
    cv2.putText(frame_display, status, (10, original_frame.shape[0] - 20),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 3)
    cv2.putText(frame_display, status, (10, original_frame.shape[0] - 22),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)


def _calibration_mouse_callback(event, x, y, flags, param):
    """Mouse callback for field polygon selection."""
    points, frame_display, original_frame = param
    if event == cv2.EVENT_LBUTTONDOWN:
        points.append((x, y))
        _redraw_polygon(frame_display, original_frame, points)
        cv2.imshow("Field Calibration", frame_display)


def calibrate_field(video_path, output_json=None):
    """
    Show a frame from the video and let the user click field boundary points.

    Args:
        video_path: Path to any video from this camera setup.
        output_json: Where to save the calibration. Defaults to same folder.

    Returns:
        list of (x, y) tuples defining the field polygon, or None if cancelled.
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

    points = []
    frame_display = frame.copy()
    original_frame = frame.copy()

    cv2.namedWindow("Field Calibration", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("Field Calibration", 1280, 720)
    cv2.setMouseCallback("Field Calibration", _calibration_mouse_callback,
                         (points, frame_display, original_frame))

    _draw_help(frame_display)
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
            _redraw_polygon(frame_display, original_frame, points)
            cv2.imshow("Field Calibration", frame_display)
        elif key == 27:  # ESC
            cv2.destroyAllWindows()
            return None

    cv2.destroyAllWindows()

    if output_json is None:
        video_dir = os.path.dirname(video_path)
        output_json = os.path.join(video_dir, "field_calibration.json")

    calibration = {
        "field_polygon": points,
        "source_video": os.path.basename(video_path),
        "frame_width": frame.shape[1],
        "frame_height": frame.shape[0],
    }
    with open(output_json, 'w') as f:
        json.dump(calibration, f, indent=2)

    logger.info(f"Field calibration saved to {output_json}")
    return points


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
    significant_contours = [c for c in contours if cv2.contourArea(c) > min_contour_area]

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
                     aspect_ratio=16/9):
    """
    Expand the motion bounding box with padding and adjust to target aspect ratio.

    Args:
        motion_box: (x, y, w, h) from detect_motion_region.
        frame_width: Original video width.
        frame_height: Original video height.
        padding: Fraction of the box size to add as padding on each side.
        aspect_ratio: Target width/height ratio (default 16:9).

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
        '-i', input_path,
        '-vf', ','.join(vf_filters),
        '-preset', 'fast',
        '-crf', '20',
        '-an',
        '-v', 'quiet',
        output_path
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        logger.error(f"FFmpeg error for {input_path}: {result.stderr}")
        return False
    return True


# -- Batch processing ----------------------------------------------------------

def process_clips_folder(clips_folder, calibration_path, output_folder=None,
                         padding=0.15, sample_interval=15, scale_width=1920,
                         save_heatmaps=True):
    """
    Auto-crop all video clips in a folder.

    Args:
        clips_folder: Folder containing the video clips.
        calibration_path: Path to field_calibration.json.
        output_folder: Where to save cropped clips. Defaults to a subfolder.
        padding: Padding fraction around detected motion.
        sample_interval: Analyze every Nth frame.
        scale_width: Output width in pixels.
        save_heatmaps: Save motion heatmap images alongside cropped clips.
    """
    polygon, cal_width, cal_height = load_calibration(calibration_path)
    field_mask = make_field_mask(polygon, cal_width, cal_height)

    if output_folder is None:
        output_folder = os.path.join(clips_folder, "autocropped")
    os.makedirs(output_folder, exist_ok=True)

    if save_heatmaps:
        heatmap_folder = os.path.join(output_folder, "heatmaps")
        os.makedirs(heatmap_folder, exist_ok=True)

    video_extensions = ('.mp4', '.MP4', '.mov', '.MOV', '.avi', '.AVI')
    clips = sorted([
        f for f in os.listdir(clips_folder)
        if f.endswith(video_extensions) and os.path.isfile(os.path.join(clips_folder, f))
    ])

    if not clips:
        logger.warning(f"No video files found in {clips_folder}")
        return

    logger.info(f"Processing {len(clips)} clips from {clips_folder}")

    csv_path = os.path.join(output_folder, "autocrop_summary.csv")
    csv_file = open(csv_path, 'w', newline='')
    csv_writer = csv.writer(csv_file)
    csv_writer.writerow([
        'clip', 'motion_x', 'motion_y', 'motion_w', 'motion_h',
        'crop_x', 'crop_y', 'crop_w', 'crop_h', 'crop_pct', 'action'
    ])

    for i, clip_name in enumerate(clips, 1):
        clip_path = os.path.join(clips_folder, clip_name)
        logger.info(f"[{i}/{len(clips)}] Analyzing {clip_name}...")

        motion_box, heatmap = detect_motion_region(
            clip_path, field_mask, sample_interval=sample_interval
        )

        if motion_box is None:
            logger.warning(f"  Skipping {clip_name} -- no motion detected.")
            csv_writer.writerow([clip_name, '', '', '', '', '', '', '', '', '', 'skipped'])
            continue

        crop_box = compute_crop_box(motion_box, cal_width, cal_height, padding=padding)
        x, y, w, h = crop_box
        crop_pct = round((w * h) / (cal_width * cal_height) * 100, 1)
        logger.info(f"  Motion crop: x={x}, y={y}, w={w}, h={h}")

        if save_heatmaps and heatmap is not None:
            heatmap_name = os.path.splitext(clip_name)[0] + "_heatmap.jpg"
            heatmap_path = os.path.join(heatmap_folder, heatmap_name)
            save_heatmap(heatmap, clip_path, heatmap_path,
                         crop_box=crop_box, field_polygon=polygon)

        output_path = os.path.join(output_folder, clip_name)
        full_frame_threshold = 0.95
        mx, my, mw, mh = motion_box
        if (w * h) / (cal_width * cal_height) >= full_frame_threshold:
            shutil.copy2(clip_path, output_path)
            logger.info(f"  Full frame -- copied original to {output_path}")
            csv_writer.writerow([clip_name, mx, my, mw, mh, x, y, w, h, crop_pct, 'copied'])
            continue

        success = crop_video(clip_path, output_path, crop_box, scale_width=scale_width)
        if success:
            logger.info(f"  Saved: {output_path}")
            csv_writer.writerow([clip_name, mx, my, mw, mh, x, y, w, h, crop_pct, 'cropped'])
        else:
            logger.error(f"  Failed to crop {clip_name}")
            csv_writer.writerow([clip_name, mx, my, mw, mh, x, y, w, h, crop_pct, 'failed'])

    csv_file.close()
    logger.info(f"Summary saved to {csv_path}")
    logger.info("Auto-crop complete.")
