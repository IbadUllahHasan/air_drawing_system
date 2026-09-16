"""Gesture-controlled air drawing with a webcam."""

import argparse
import math
import os
import sys
import time

import cv2
import mediapipe as mp
import numpy as np
from PIL import Image, ImageDraw, ImageFont

WINDOW_NAME = "Air Drawing"

mp_hands = mp.solutions.hands

# ----------------------------------------------------------------- appearance

PANEL_TINT = (30, 26, 34)
PANEL_STRENGTH = 0.62
PANEL_BLUR = 21

TEXT_PRIMARY = (242, 242, 247)
TEXT_MUTED = (170, 170, 185)
RING_COLOR = (255, 255, 255)

BRUSH_COLORS = [
    (255, 0, 255),   # magenta
    (0, 255, 0),     # green
    (0, 0, 255),     # red
]
ERASER_COLOR = (0, 0, 0)
ERASER_SWATCH_COLOR = (238, 238, 242)

MODE_COLORS = {
    "DRAW": (90, 230, 120),
    "SELECT": (255, 200, 60),
    "IDLE": (150, 150, 165),
    "BOX FILTER": (255, 120, 255),
}

DWELL_SECONDS = 0.55
TOAST_LIFETIME = 2.2
HINT_LIFETIME = 6.0

# Left-hand pinch (thumb tip to index tip, in pixels) mapped to brush width
PINCH_MIN_DIST = 25
PINCH_MAX_DIST = 220
PINCH_THICKNESS_MIN = 2
PINCH_THICKNESS_MAX = 60

BOX_MIN_SIZE = 20

FONT_CANDIDATES = [
    "C:/Windows/Fonts/segoeui.ttf",
    "C:/Windows/Fonts/arial.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/usr/share/fonts/TTF/DejaVuSans.ttf",
]

_font_cache = {}
_tile_cache = {}
_font_path = None
_font_path_resolved = False


# --------------------------------------------------------------- text drawing

def get_font(size):
    """Load a real TrueType face, falling back to Pillow's bitmap font."""
    global _font_path, _font_path_resolved

    if not _font_path_resolved:
        _font_path = next((p for p in FONT_CANDIDATES if os.path.exists(p)), None)
        _font_path_resolved = True

    if size not in _font_cache:
        try:
            _font_cache[size] = (ImageFont.truetype(_font_path, size)
                                 if _font_path else ImageFont.load_default())
        except OSError:
            _font_cache[size] = ImageFont.load_default()

    return _font_cache[size]


def _text_tile(text, size, color, alpha):
    """Render text to a cached (BGR, alpha) pair. Alpha is bucketed so that
    fading text still hits the cache instead of re-rasterising every frame."""
    key = (text, size, color, round(alpha, 1))
    if key in _tile_cache:
        return _tile_cache[key]

    font = get_font(size)
    bbox = ImageDraw.Draw(Image.new("L", (1, 1))).textbbox((0, 0), text, font=font)
    tw = max(1, bbox[2] - bbox[0])
    th = max(1, bbox[3] - bbox[1])

    pad = 2
    tile = Image.new("RGBA", (tw + pad * 2, th + pad * 2), (0, 0, 0, 0))
    ImageDraw.Draw(tile).text(
        (pad - bbox[0], pad - bbox[1]), text, font=font,
        fill=(color[2], color[1], color[0], int(255 * alpha)),
    )

    arr = np.array(tile)
    result = (arr[..., 2::-1].copy(), arr[..., 3].copy())

    if len(_tile_cache) > 300:
        _tile_cache.clear()
    _tile_cache[key] = result
    return result


def blit(img, tile_bgr, tile_alpha, x, y):
    h, w = img.shape[:2]
    th, tw = tile_bgr.shape[:2]

    x1, y1 = max(0, x), max(0, y)
    x2, y2 = min(w, x + tw), min(h, y + th)
    if x2 <= x1 or y2 <= y1:
        return

    sx, sy = x1 - x, y1 - y
    src = tile_bgr[sy:sy + (y2 - y1), sx:sx + (x2 - x1)].astype(np.float32)
    a = tile_alpha[sy:sy + (y2 - y1), sx:sx + (x2 - x1)][..., None].astype(np.float32) / 255.0
    dst = img[y1:y2, x1:x2].astype(np.float32)
    img[y1:y2, x1:x2] = (dst * (1 - a) + src * a).astype(np.uint8)


def draw_text(img, text, x, y, size, color=TEXT_PRIMARY, alpha=1.0, anchor="lt"):
    if not text or alpha <= 0.01:
        return 0, 0

    tile_bgr, tile_alpha = _text_tile(text, size, color, alpha)
    th, tw = tile_bgr.shape[:2]

    if anchor[0] == "m":
        x -= tw // 2
    elif anchor[0] == "r":
        x -= tw
    if anchor[1] == "m":
        y -= th // 2
    elif anchor[1] == "b":
        y -= th

    blit(img, tile_bgr, tile_alpha, x, y)
    return tw, th


def text_size(text, size):
    tile_bgr, _ = _text_tile(text, size, TEXT_PRIMARY, 1.0)
    return tile_bgr.shape[1], tile_bgr.shape[0]


# -------------------------------------------------------------- shape drawing

def rounded_rect(img, pt1, pt2, radius, color, thickness=-1):
    x1, y1 = pt1
    x2, y2 = pt2
    radius = max(0, min(radius, (x2 - x1) // 2, (y2 - y1) // 2))
    aa = cv2.LINE_AA

    if thickness < 0:
        cv2.rectangle(img, (x1 + radius, y1), (x2 - radius, y2), color, -1)
        cv2.rectangle(img, (x1, y1 + radius), (x2, y2 - radius), color, -1)
        for cx, cy in ((x1 + radius, y1 + radius), (x2 - radius, y1 + radius),
                       (x1 + radius, y2 - radius), (x2 - radius, y2 - radius)):
            cv2.circle(img, (cx, cy), radius, color, -1, aa)
        return

    cv2.line(img, (x1 + radius, y1), (x2 - radius, y1), color, thickness, aa)
    cv2.line(img, (x1 + radius, y2), (x2 - radius, y2), color, thickness, aa)
    cv2.line(img, (x1, y1 + radius), (x1, y2 - radius), color, thickness, aa)
    cv2.line(img, (x2, y1 + radius), (x2, y2 - radius), color, thickness, aa)
    for center, start in (((x1 + radius, y1 + radius), 180),
                          ((x2 - radius, y1 + radius), 270),
                          ((x1 + radius, y2 - radius), 90),
                          ((x2 - radius, y2 - radius), 0)):
        cv2.ellipse(img, center, (radius, radius), start, 0, 90, color, thickness, aa)


def frosted_panel(img, pt1, pt2, radius, opacity=1.0):
    """Blur the camera pixels under a rounded rect and tint them, so panels
    read as frosted glass rather than flat fills."""
    h, w = img.shape[:2]
    x1, y1 = max(0, pt1[0]), max(0, pt1[1])
    x2, y2 = min(w, pt2[0]), min(h, pt2[1])
    if x2 - x1 < 2 or y2 - y1 < 2 or opacity <= 0.01:
        return

    roi = img[y1:y2, x1:x2]

    mask = np.zeros(roi.shape[:2], np.uint8)
    rounded_rect(mask, (0, 0), (x2 - x1 - 1, y2 - y1 - 1), radius, 255, -1)
    alpha = (mask.astype(np.float32) / 255.0 * opacity)[..., None]

    blurred = cv2.GaussianBlur(roi, (PANEL_BLUR | 1, PANEL_BLUR | 1), 0)
    tint = np.empty_like(roi)
    tint[:] = PANEL_TINT
    glass = cv2.addWeighted(blurred, 1 - PANEL_STRENGTH, tint, PANEL_STRENGTH, 0)

    img[y1:y2, x1:x2] = (roi.astype(np.float32) * (1 - alpha) +
                         glass.astype(np.float32) * alpha).astype(np.uint8)


def draw_eraser_icon(img, cx, cy, r):
    angle = -35
    body = cv2.boxPoints(((cx, cy), (r * 1.35, r * 0.9), angle)).astype(np.int32)
    cv2.fillConvexPoly(img, body, (120, 118, 132), cv2.LINE_AA)

    rad = math.radians(angle)
    off = (math.cos(rad) * r * 0.42, math.sin(rad) * r * 0.42)
    band = cv2.boxPoints((((cx + off[0]), (cy + off[1])), (r * 0.5, r * 0.9), angle))
    cv2.fillConvexPoly(img, band.astype(np.int32), (78, 76, 92), cv2.LINE_AA)


# ------------------------------------------------------------- gesture helpers

def finger_up(hand_landmarks, tip_id):
    tip_y = hand_landmarks.landmark[tip_id].y
    lower_y = hand_landmarks.landmark[tip_id - 2].y
    return tip_y < lower_y


def landmark_px(hand_landmarks, index, frame_width, frame_height):
    lm = hand_landmarks.landmark[index]
    return int(lm.x * frame_width), int(lm.y * frame_height)


def pinch_to_thickness(distance):
    distance = max(PINCH_MIN_DIST, min(PINCH_MAX_DIST, distance))
    ratio = (distance - PINCH_MIN_DIST) / (PINCH_MAX_DIST - PINCH_MIN_DIST)
    return int(PINCH_THICKNESS_MIN + ratio * (PINCH_THICKNESS_MAX - PINCH_THICKNESS_MIN))


def apply_cartoon_filter(region):
    gray = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)
    gray = cv2.medianBlur(gray, 5)
    edges = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C,
                                  cv2.THRESH_BINARY, 9, 9)
    smooth = cv2.bilateralFilter(region, 9, 250, 250)
    return cv2.bitwise_and(smooth, smooth, mask=edges)


# --------------------------------------------------------------------- layout

def ui_metrics(frame_width):
    scale = min(max(frame_width / 1280.0, 0.7), 1.8)
    return {
        "scale": scale,
        "margin": int(18 * scale),
        "pad": int(20 * scale),
        "bar_h": int(76 * scale),
        "swatch_r": int(25 * scale),
        "gap": int(20 * scale),
        "font_lg": max(11, int(17 * scale)),
        "font_sm": max(9, int(12 * scale)),
    }


def build_layout(frame_width, m):
    """Lay the floating toolbar out from the frame size, dropping swatches
    that would not fit rather than letting them overflow."""
    r, gap, pad = m["swatch_r"], m["gap"], m["pad"]
    items = [{"color": c, "is_eraser": False} for c in BRUSH_COLORS]
    items.append({"color": ERASER_SWATCH_COLOR, "is_eraser": True})

    available = frame_width - 2 * m["margin"]
    divider = int(26 * m["scale"])

    while items:
        content = pad * 2 + len(items) * 2 * r + max(0, len(items) - 1) * gap + divider + 2 * r
        if content <= available:
            break
        items.pop()

    if not items:
        return None

    x1, y1 = m["margin"], m["margin"]
    x2, y2 = x1 + content, y1 + m["bar_h"]
    cy = (y1 + y2) // 2

    cx = x1 + pad + r
    for item in items:
        item.update({"cx": cx, "cy": cy, "radius": r})
        cx += 2 * r + gap

    last_right = items[-1]["cx"] + r

    return {
        "swatches": items,
        "rect": (x1, y1, x2, y2),
        "divider_x": last_right + divider // 2,
        "preview": (x2 - pad - r, cy),
        "preview_max_r": r,
    }


# ----------------------------------------------------------------- UI drawing

def draw_toolbar(img, layout, m, accent, brush_thickness, anim, hover_idx,
                 hover_progress, brush_color, now):
    x1, y1, x2, y2 = layout["rect"]
    frosted_panel(img, (x1, y1), (x2, y2), m["bar_h"] // 2)

    for i, sw in enumerate(layout["swatches"]):
        cx, cy, r = sw["cx"], sw["cy"], sw["radius"]

        target = 1.14 if i == hover_idx else 1.0
        anim[i] = anim.get(i, 1.0) + (target - anim.get(i, 1.0)) * 0.25
        rr = max(4, int(r * anim[i]))

        is_active = (sw["is_eraser"] and brush_color == ERASER_COLOR) or \
                    (not sw["is_eraser"] and sw["color"] == brush_color)

        cv2.circle(img, (cx + 1, cy + 2), rr, (10, 10, 14), -1, cv2.LINE_AA)
        cv2.circle(img, (cx, cy), rr, sw["color"], -1, cv2.LINE_AA)

        if sw["is_eraser"]:
            draw_eraser_icon(img, cx, cy, rr)

        if is_active:
            pulse = 1.0 + 0.045 * math.sin(now * 5.0)
            cv2.circle(img, (cx, cy), int((rr + 6) * pulse), RING_COLOR, 2, cv2.LINE_AA)

        if i == hover_idx and hover_progress > 0.0:
            cv2.ellipse(img, (cx, cy), (rr + 9, rr + 9), -90, 0,
                        int(360 * min(1.0, hover_progress)), accent, 3, cv2.LINE_AA)

    dx = layout["divider_x"]
    cv2.line(img, (dx, y1 + m["pad"]), (dx, y2 - m["pad"]), (110, 108, 125), 1, cv2.LINE_AA)

    # Brush-size gauge: faint track shows the maximum, the filled dot the
    # current width, so it reads as a meter rather than another swatch.
    px, py = layout["preview"]
    max_r = layout["preview_max_r"]
    preview_r = int(min(max(brush_thickness / 2.0, 2), max_r))
    cv2.circle(img, (px, py), max_r, (96, 94, 112), 1, cv2.LINE_AA)
    cv2.circle(img, (px, py), preview_r, accent, -1, cv2.LINE_AA)


def draw_status(img, layout, m, mode, fps, brush_thickness):
    frame_w = img.shape[1]
    mode_text = mode
    sub_text = f"{int(fps)} FPS   {brush_thickness}px"

    mw, _ = text_size(mode_text, m["font_lg"])
    sw_, _ = text_size(sub_text, m["font_sm"])

    dot_r = int(6 * m["scale"])
    pad = m["pad"]
    inner = max(mw, sw_)
    pill_w = pad * 2 + dot_r * 2 + int(10 * m["scale"]) + inner
    pill_h = m["bar_h"]

    x2 = frame_w - m["margin"]
    x1 = x2 - pill_w
    y1 = m["margin"]
    y2 = y1 + pill_h

    if layout and x1 < layout["rect"][2] + int(10 * m["scale"]):
        return

    frosted_panel(img, (x1, y1), (x2, y2), pill_h // 2)

    cx = x1 + pad + dot_r
    cv2.circle(img, (cx, (y1 + y2) // 2), dot_r,
               MODE_COLORS.get(mode, TEXT_MUTED), -1, cv2.LINE_AA)

    tx = cx + dot_r + int(10 * m["scale"])
    draw_text(img, mode_text, tx, y1 + int(pill_h * 0.30), m["font_lg"],
              TEXT_PRIMARY, anchor="lm")
    draw_text(img, sub_text, tx, y1 + int(pill_h * 0.68), m["font_sm"],
              TEXT_MUTED, anchor="lm")


def draw_cursor(img, x, y, radius, accent, mode):
    radius = max(4, radius)
    cv2.circle(img, (x, y), radius + 1, (12, 12, 16), 3, cv2.LINE_AA)
    cv2.circle(img, (x, y), radius, accent, 2, cv2.LINE_AA)
    cv2.circle(img, (x, y), 2, accent, -1, cv2.LINE_AA)

    tick = radius + int(7)
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        cv2.line(img, (x + dx * (radius + 3), y + dy * (radius + 3)),
                 (x + dx * tick, y + dy * tick),
                 MODE_COLORS.get(mode, accent), 1, cv2.LINE_AA)


def draw_hand_skeleton(img, hand_landmarks, w, h):
    pts = [landmark_px(hand_landmarks, i, w, h) for i in range(21)]
    for a, b in mp_hands.HAND_CONNECTIONS:
        cv2.line(img, pts[a], pts[b], (185, 185, 200), 1, cv2.LINE_AA)
    for p in pts:
        cv2.circle(img, p, 2, (235, 235, 245), -1, cv2.LINE_AA)


def draw_toasts(img, toasts, m, now):
    h, w = img.shape[:2]
    y = h - m["margin"]

    for toast in reversed(toasts):
        age = now - toast["t"]
        if age < 0.15:
            alpha = age / 0.15
        elif age > TOAST_LIFETIME - 0.4:
            alpha = max(0.0, (TOAST_LIFETIME - age) / 0.4)
        else:
            alpha = 1.0

        tw, th = text_size(toast["text"], m["font_sm"])
        pill_w = tw + m["pad"] * 2
        pill_h = th + int(20 * m["scale"])
        x1 = (w - pill_w) // 2
        y1 = y - pill_h

        frosted_panel(img, (x1, y1), (x1 + pill_w, y), pill_h // 2, opacity=alpha)
        draw_text(img, toast["text"], w // 2, (y1 + y) // 2, m["font_sm"],
                  TEXT_PRIMARY, alpha=alpha, anchor="mm")

        y = y1 - int(8 * m["scale"])


def draw_hints(img, m, alpha):
    if alpha <= 0.01:
        return

    text = "C Clear    S Save    H Hands    F Fullscreen    ESC Quit"
    h, w = img.shape[:2]
    tw, th = text_size(text, m["font_sm"])
    pill_w, pill_h = tw + m["pad"] * 2, th + int(18 * m["scale"])
    x1 = (w - pill_w) // 2
    y1 = h - m["margin"] - pill_h

    frosted_panel(img, (x1, y1), (x1 + pill_w, y1 + pill_h), pill_h // 2, opacity=alpha)
    draw_text(img, text, w // 2, y1 + pill_h // 2, m["font_sm"],
              TEXT_MUTED, alpha=alpha, anchor="mm")


# ----------------------------------------------------------------------- main

def window_size(value):
    try:
        width, height = value.lower().split("x")
        return int(width), int(height)
    except ValueError:
        raise argparse.ArgumentTypeError("expected WIDTHxHEIGHT, e.g. 1280x720")


def parse_args():
    parser = argparse.ArgumentParser(description="Gesture-controlled air drawing.")
    parser.add_argument("--camera", type=int, default=0, help="camera device index")
    parser.add_argument("--width", type=int, default=1280, help="capture width")
    parser.add_argument("--height", type=int, default=720, help="capture height")
    parser.add_argument("--window", type=window_size, default=(1280, 720),
                        metavar="WxH", help="initial window size, e.g. 960x540")
    parser.add_argument("--fullscreen", action="store_true", help="start fullscreen")
    return parser.parse_args()


def main():
    args = parse_args()

    cap = cv2.VideoCapture(args.camera)
    if not cap.isOpened():
        print(
            f"Error: could not open camera index {args.camera}. "
            "Check that a camera is connected and not already in use by "
            "another application, or pass a different --camera index.",
            file=sys.stderr,
        )
        sys.exit(1)

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, args.width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, args.height)

    cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_NORMAL | cv2.WINDOW_KEEPRATIO)
    cv2.resizeWindow(WINDOW_NAME, *args.window)

    fullscreen = args.fullscreen
    if fullscreen:
        cv2.setWindowProperty(WINDOW_NAME, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)

    hands = mp_hands.Hands(
        static_image_mode=False,
        max_num_hands=2,
        min_detection_confidence=0.7,
        min_tracking_confidence=0.7,
    )

    canvas = None
    prev_x, prev_y = 0, 0
    smooth_x, smooth_y = 0, 0

    brush_color = BRUSH_COLORS[0]
    brush_thickness = 6
    draw_thickness = brush_thickness
    eraser_thickness = 40

    mode = "IDLE"
    prev_time = time.time()
    started = time.time()

    hover_idx = None
    hover_start = 0.0
    hover_locked = False
    swatch_anim = {}
    toasts = []
    show_hands = True

    def toast(message):
        toasts.append({"text": message, "t": time.time()})

    try:
        while True:
            success, frame = cap.read()
            if not success:
                print("Warning: failed to read a frame from the camera; stopping.",
                      file=sys.stderr)
                break

            frame = cv2.flip(frame, 1)
            h, w = frame.shape[:2]
            now = time.time()

            if canvas is None or canvas.shape != frame.shape:
                canvas = np.zeros_like(frame)

            m = ui_metrics(w)
            layout = build_layout(w, m)

            # Hand tracking runs on the clean frame, before any UI is drawn.
            results = hands.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))

            right_hand = left_hand = None
            if results.multi_hand_landmarks:
                for landmarks, handedness in zip(results.multi_hand_landmarks,
                                                 results.multi_handedness):
                    if handedness.classification[0].label == "Right":
                        right_hand = landmarks
                    else:
                        left_hand = landmarks

            # Two hands, index+middle up on both: frame a box and filter inside it.
            box_active = False
            box_rect = None

            if right_hand is not None and left_hand is not None:
                if (finger_up(right_hand, 8) and finger_up(right_hand, 12) and
                        finger_up(left_hand, 8) and finger_up(left_hand, 12)):
                    rx, ry = landmark_px(right_hand, 8, w, h)
                    lx, ly = landmark_px(left_hand, 8, w, h)

                    x1, x2 = sorted((max(0, min(w - 1, rx)), max(0, min(w - 1, lx))))
                    y1, y2 = sorted((max(0, min(h - 1, ry)), max(0, min(h - 1, ly))))

                    if x2 - x1 > BOX_MIN_SIZE and y2 - y1 > BOX_MIN_SIZE:
                        box_active = True
                        box_rect = (x1, y1, x2, y2)
                        mode = "BOX FILTER"
                        prev_x, prev_y = 0, 0
                        frame[y1:y2, x1:x2] = apply_cartoon_filter(frame[y1:y2, x1:x2])

            # Left hand pinch resizes whichever tool is active.
            if left_hand is not None and not box_active:
                tx, ty = landmark_px(left_hand, 4, w, h)
                ix, iy = landmark_px(left_hand, 8, w, h)
                brush_thickness = pinch_to_thickness(math.hypot(ix - tx, iy - ty))
                if brush_color == ERASER_COLOR:
                    eraser_thickness = brush_thickness
                else:
                    draw_thickness = brush_thickness

            # Right hand draws or selects.
            hover_progress = 0.0

            if right_hand is not None and not box_active:
                x, y = landmark_px(right_hand, 8, w, h)
                smooth_x = int((smooth_x + x) / 2)
                smooth_y = int((smooth_y + y) / 2)

                index_up = finger_up(right_hand, 8)
                middle_up = finger_up(right_hand, 12)
                bar_bottom = layout["rect"][3] if layout else 0

                if index_up and not middle_up:
                    mode = "DRAW"
                    hover_idx, hover_locked = None, False

                    if smooth_y > bar_bottom:
                        if prev_x == 0 and prev_y == 0:
                            prev_x, prev_y = smooth_x, smooth_y
                        cv2.line(canvas, (prev_x, prev_y), (smooth_x, smooth_y),
                                 brush_color, brush_thickness)
                        prev_x, prev_y = smooth_x, smooth_y
                    else:
                        prev_x, prev_y = 0, 0

                elif index_up and middle_up:
                    mode = "SELECT"
                    prev_x, prev_y = 0, 0

                    hovered = None
                    if layout:
                        for i, sw in enumerate(layout["swatches"]):
                            dx = smooth_x - sw["cx"]
                            dy = smooth_y - sw["cy"]
                            if dx * dx + dy * dy <= sw["radius"] ** 2:
                                hovered = i
                                break

                    if hovered != hover_idx:
                        hover_idx = hovered
                        hover_start = now
                        hover_locked = False

                    if hovered is not None:
                        if hover_locked:
                            hover_progress = 1.0
                        else:
                            hover_progress = (now - hover_start) / DWELL_SECONDS
                            if hover_progress >= 1.0:
                                sw = layout["swatches"][hovered]
                                if sw["is_eraser"]:
                                    brush_color = ERASER_COLOR
                                    brush_thickness = eraser_thickness
                                    toast("Eraser selected")
                                else:
                                    brush_color = sw["color"]
                                    brush_thickness = draw_thickness
                                    toast("Color selected")
                                hover_locked = True
                                hover_progress = 1.0
                else:
                    mode = "IDLE"
                    prev_x, prev_y = 0, 0
                    hover_idx, hover_locked = None, False
            else:
                prev_x, prev_y = 0, 0
                if not box_active:
                    hover_idx, hover_locked = None, False

            # Composite the drawing over the camera image.
            canvas_gray = cv2.cvtColor(canvas, cv2.COLOR_BGR2GRAY)
            _, inverse = cv2.threshold(canvas_gray, 50, 255, cv2.THRESH_BINARY_INV)
            inverse = cv2.cvtColor(inverse, cv2.COLOR_GRAY2BGR)
            img = cv2.bitwise_and(frame, inverse)
            img = cv2.bitwise_or(img, canvas)

            fps = 1.0 / max(1e-4, now - prev_time)
            prev_time = now

            # Everything below is UI chrome, drawn on top of the composite.
            accent = ERASER_SWATCH_COLOR if brush_color == ERASER_COLOR else brush_color

            if box_active and box_rect:
                bx1, by1, bx2, by2 = box_rect
                rounded_rect(img, (bx1, by1), (bx2, by2), int(12 * m["scale"]),
                             MODE_COLORS["BOX FILTER"], 2)
                draw_text(img, "CARTOON", bx1 + 10, by1 - int(6 * m["scale"]),
                          m["font_sm"], MODE_COLORS["BOX FILTER"], anchor="lb")

            if show_hands:
                for landmarks in (left_hand, right_hand):
                    if landmarks is not None:
                        draw_hand_skeleton(img, landmarks, w, h)

            if right_hand is not None and not box_active:
                draw_cursor(img, smooth_x, smooth_y, brush_thickness, accent, mode)

            if layout:
                draw_toolbar(img, layout, m, accent, brush_thickness, swatch_anim,
                             hover_idx, hover_progress, brush_color, now)
            draw_status(img, layout, m, mode, fps, brush_thickness)

            toasts[:] = [t for t in toasts if now - t["t"] < TOAST_LIFETIME]
            if toasts:
                draw_toasts(img, toasts, m, now)
            else:
                hint_age = now - started
                if hint_age < HINT_LIFETIME:
                    draw_hints(img, m, min(1.0, (HINT_LIFETIME - hint_age) / 1.0))

            cv2.imshow(WINDOW_NAME, img)
            key = cv2.waitKey(1) & 0xFF

            # Checked after waitKey so the window has been pumped at least once.
            if cv2.getWindowProperty(WINDOW_NAME, cv2.WND_PROP_VISIBLE) < 1:
                break

            if key == ord('c'):
                canvas = np.zeros_like(frame)
                toast("Canvas cleared")
            elif key == ord('s'):
                cv2.imwrite("drawing.png", canvas)
                toast("Saved drawing.png")
            elif key == ord('h'):
                show_hands = not show_hands
                toast(f"Hand overlay {'on' if show_hands else 'off'}")
            elif key == ord('f'):
                fullscreen = not fullscreen
                cv2.setWindowProperty(
                    WINDOW_NAME, cv2.WND_PROP_FULLSCREEN,
                    cv2.WINDOW_FULLSCREEN if fullscreen else cv2.WINDOW_NORMAL)
            elif key in (ord('+'), ord('=')):
                brush_thickness += 1
                if brush_color == ERASER_COLOR:
                    eraser_thickness = brush_thickness
                else:
                    draw_thickness = brush_thickness
            elif key == ord('-'):
                brush_thickness = max(1, brush_thickness - 1)
                if brush_color == ERASER_COLOR:
                    eraser_thickness = brush_thickness
                else:
                    draw_thickness = brush_thickness
            elif key == 27:
                break

    finally:
        hands.close()
        cap.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
