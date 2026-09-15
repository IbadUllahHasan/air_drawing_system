import cv2
import mediapipe as mp
import numpy as np
import time
import sys
import math

cap = cv2.VideoCapture(0)

if not cap.isOpened():
    print(
        "Error: could not open webcam (device index 0). "
        "Check that a camera is connected and not already in use by "
        "another application.",
        file=sys.stderr,
    )
    sys.exit(1)

mp_hands = mp.solutions.hands

hands = mp_hands.Hands(
    static_image_mode=False,
    max_num_hands=2,
    min_detection_confidence=0.7,
    min_tracking_confidence=0.7
)

mp_draw = mp.solutions.drawing_utils

canvas = None
prev_x, prev_y = 0, 0
smooth_x, smooth_y = 0, 0

brush_color = (255, 0, 255)
brush_thickness = 5
draw_thickness = brush_thickness
eraser_thickness = 40

mode = "IDLE"

prev_time = 0

TOOLBAR_HEIGHT = 74
SWATCH_RADIUS = 26
SWATCH_GAP = 22
SWATCH_START_X = 46  # center x of the first swatch
SWATCH_CENTER_Y = TOOLBAR_HEIGHT // 2
TOOLBAR_COLORS = [
    (255, 0, 255),  # purple
    (0, 255, 0),    # green
    (0, 0, 255),    # red
]
ERASER_SWATCH_COLOR = (235, 235, 235)

PANEL_COLOR = (32, 32, 38)
PANEL_ALPHA = 0.82

MODE_COLORS = {
    "DRAW": (0, 220, 0),
    "SELECT": (0, 200, 255),
    "IDLE": (150, 150, 150),
    "BOX FILTER": (255, 120, 255),
}

# Left-hand pinch (thumb tip to index tip, in pixels) mapped to brush width
PINCH_MIN_DIST = 25
PINCH_MAX_DIST = 220
PINCH_THICKNESS_MIN = 2
PINCH_THICKNESS_MAX = 60

# Two-hand box-filter gesture
BOX_MIN_SIZE = 20


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


def draw_rounded_rect(img, pt1, pt2, radius, color, thickness=-1):
    x1, y1 = pt1
    x2, y2 = pt2
    line_type = cv2.LINE_AA

    if thickness < 0:
        cv2.rectangle(img, (x1 + radius, y1), (x2 - radius, y2), color, -1)
        cv2.rectangle(img, (x1, y1 + radius), (x2, y2 - radius), color, -1)
        for cx, cy in ((x1 + radius, y1 + radius), (x2 - radius, y1 + radius),
                       (x1 + radius, y2 - radius), (x2 - radius, y2 - radius)):
            cv2.circle(img, (cx, cy), radius, color, -1, line_type)
        return

    cv2.line(img, (x1 + radius, y1), (x2 - radius, y1), color, thickness, line_type)
    cv2.line(img, (x1 + radius, y2), (x2 - radius, y2), color, thickness, line_type)
    cv2.line(img, (x1, y1 + radius), (x1, y2 - radius), color, thickness, line_type)
    cv2.line(img, (x2, y1 + radius), (x2, y2 - radius), color, thickness, line_type)
    cv2.ellipse(img, (x1 + radius, y1 + radius), (radius, radius), 180, 0, 90, color, thickness, line_type)
    cv2.ellipse(img, (x2 - radius, y1 + radius), (radius, radius), 270, 0, 90, color, thickness, line_type)
    cv2.ellipse(img, (x1 + radius, y2 - radius), (radius, radius), 90, 0, 90, color, thickness, line_type)
    cv2.ellipse(img, (x2 - radius, y2 - radius), (radius, radius), 0, 0, 90, color, thickness, line_type)


def apply_cartoon_filter(region):
    gray = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)
    gray = cv2.medianBlur(gray, 5)
    edges = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C,
                                   cv2.THRESH_BINARY, 9, 9)
    smooth = cv2.bilateralFilter(region, 9, 250, 250)
    return cv2.bitwise_and(smooth, smooth, mask=edges)


def build_toolbar(frame_width):
    """Lay out color/eraser swatches left-to-right as circles, dropping any
    that would not fit inside the current frame instead of overflowing it."""
    swatches = []
    cx = SWATCH_START_X
    step = 2 * SWATCH_RADIUS + SWATCH_GAP

    for color in TOOLBAR_COLORS:
        if cx + SWATCH_RADIUS > frame_width - 10:
            return swatches
        swatches.append({
            "cx": cx, "cy": SWATCH_CENTER_Y, "radius": SWATCH_RADIUS,
            "color": color, "is_eraser": False,
        })
        cx += step

    if cx + SWATCH_RADIUS <= frame_width - 10:
        swatches.append({
            "cx": cx, "cy": SWATCH_CENTER_Y, "radius": SWATCH_RADIUS,
            "color": ERASER_SWATCH_COLOR, "is_eraser": True,
        })

    return swatches

try:
    while True:

        success, img = cap.read()

        if not success:
            print("Warning: failed to read a frame from the webcam; stopping.",
                  file=sys.stderr)
            break

        img = cv2.flip(img, 1)

        h, w, c = img.shape

        if canvas is None:
            canvas = np.zeros_like(img)


        toolbar = build_toolbar(w)

        panel = img.copy()
        cv2.rectangle(panel, (0, 0), (w, TOOLBAR_HEIGHT), PANEL_COLOR, -1)
        img = cv2.addWeighted(panel, PANEL_ALPHA, img, 1 - PANEL_ALPHA, 0)
        cv2.line(img, (0, TOOLBAR_HEIGHT), (w, TOOLBAR_HEIGHT),
                 brush_color, 3, cv2.LINE_AA)

        for swatch in toolbar:
            cx, cy, radius = swatch["cx"], swatch["cy"], swatch["radius"]

            cv2.circle(img, (cx + 2, cy + 3), radius, (12, 12, 12), -1, cv2.LINE_AA)
            cv2.circle(img, (cx, cy), radius, swatch["color"], -1, cv2.LINE_AA)
            cv2.circle(img, (cx, cy), radius, (15, 15, 15), 1, cv2.LINE_AA)

            is_active = (
                (swatch["is_eraser"] and brush_color == (0, 0, 0)) or
                (not swatch["is_eraser"] and swatch["color"] == brush_color)
            )
            if is_active:
                cv2.circle(img, (cx, cy), radius + 5, (255, 255, 255), 2, cv2.LINE_AA)

            if swatch["is_eraser"]:
                r = radius - 10
                cv2.line(img, (cx - r, cy - r), (cx + r, cy + r), (100, 100, 100), 3, cv2.LINE_AA)
                cv2.line(img, (cx - r, cy + r), (cx + r, cy - r), (100, 100, 100), 3, cv2.LINE_AA)


        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

        results = hands.process(img_rgb)

        right_hand = None
        left_hand = None

        if results.multi_hand_landmarks:
            for hand_landmarks, handedness in zip(
                    results.multi_hand_landmarks, results.multi_handedness):

                mp_draw.draw_landmarks(
                    img,
                    hand_landmarks,
                    mp_hands.HAND_CONNECTIONS
                )

                if handedness.classification[0].label == "Right":
                    right_hand = hand_landmarks
                else:
                    left_hand = hand_landmarks

        # Two-hand gesture: both hands showing index+middle up at once
        # frames a box between the index tips and live-filters that region.
        box_active = False

        if right_hand is not None and left_hand is not None:
            if (finger_up(right_hand, 8) and finger_up(right_hand, 12) and
                    finger_up(left_hand, 8) and finger_up(left_hand, 12)):

                rx, ry = landmark_px(right_hand, 8, w, h)
                lx, ly = landmark_px(left_hand, 8, w, h)

                x1, x2 = sorted((rx, lx))
                y1, y2 = sorted((ry, ly))
                y1 = max(y1, TOOLBAR_HEIGHT)

                if x2 - x1 > BOX_MIN_SIZE and y2 - y1 > BOX_MIN_SIZE:
                    box_active = True
                    mode = "BOX FILTER"
                    prev_x, prev_y = 0, 0

                    img[y1:y2, x1:x2] = apply_cartoon_filter(img[y1:y2, x1:x2])
                    draw_rounded_rect(img, (x1, y1), (x2, y2), 10, (255, 120, 255), 2)

        # Left hand: pinch (thumb tip to index tip) resizes whichever
        # tool is currently active, live, replacing the +/- keys.
        if left_hand is not None and not box_active:
            tx, ty = landmark_px(left_hand, 4, w, h)
            ix, iy = landmark_px(left_hand, 8, w, h)
            distance = math.hypot(ix - tx, iy - ty)

            brush_thickness = pinch_to_thickness(distance)
            if brush_color == (0, 0, 0):
                eraser_thickness = brush_thickness
            else:
                draw_thickness = brush_thickness

        # Right hand: draws, or selects from the toolbar (unchanged from
        # single-hand behavior; the left hand never touches this).
        if right_hand is not None and not box_active:

            x, y = landmark_px(right_hand, 8, w, h)

            smooth_x = int((smooth_x + x) / 2)
            smooth_y = int((smooth_y + y) / 2)

            cv2.circle(img, (smooth_x, smooth_y), brush_thickness,
                       brush_color, 2, cv2.LINE_AA)
            cv2.circle(img, (smooth_x, smooth_y), 2, brush_color, -1, cv2.LINE_AA)

            index_up = finger_up(right_hand, 8)
            middle_up = finger_up(right_hand, 12)

            if index_up and not middle_up:

                mode = "DRAW"

                if prev_x == 0 and prev_y == 0:
                    prev_x, prev_y = smooth_x, smooth_y

                cv2.line(
                    canvas,
                    (prev_x, prev_y),
                    (smooth_x, smooth_y),
                    brush_color,
                    brush_thickness
                )

                prev_x, prev_y = smooth_x, smooth_y
            elif index_up and middle_up:

                mode = "SELECT"

                prev_x, prev_y = 0, 0

                # Color/eraser selection
                for swatch in toolbar:
                    dx = smooth_x - swatch["cx"]
                    dy = smooth_y - swatch["cy"]
                    if dx * dx + dy * dy <= swatch["radius"] ** 2:
                        if swatch["is_eraser"]:
                            brush_color = (0, 0, 0)
                            brush_thickness = eraser_thickness
                        else:
                            brush_color = swatch["color"]
                            brush_thickness = draw_thickness
                        break

            else:
                mode = "IDLE"
                prev_x, prev_y = 0, 0

        elif right_hand is None and not box_active:
            prev_x, prev_y = 0, 0

        img_gray = cv2.cvtColor(canvas, cv2.COLOR_BGR2GRAY)

        _, img_inv = cv2.threshold(img_gray, 50, 255,
                                   cv2.THRESH_BINARY_INV)

        img_inv = cv2.cvtColor(img_inv, cv2.COLOR_GRAY2BGR)

        img = cv2.bitwise_and(img, img_inv)

        img = cv2.bitwise_or(img, canvas)

        current_time = time.time()

        fps = 1 / (current_time - prev_time + 0.0001)

        prev_time = current_time

        toolbar_end = (toolbar[-1]["cx"] + toolbar[-1]["radius"]) if toolbar else SWATCH_START_X

        preview_cx = toolbar_end + 40
        preview_radius = min(max(brush_thickness // 2, 3), 26)

        pill_w, pill_h = 190, 46
        pill_x1 = preview_cx + preview_radius + 20
        pill_y1 = (TOOLBAR_HEIGHT - pill_h) // 2
        pill_x2 = pill_x1 + pill_w
        pill_y2 = pill_y1 + pill_h

        if pill_x2 <= w - 10:
            cv2.circle(img, (preview_cx, SWATCH_CENTER_Y), preview_radius,
                       brush_color, -1, cv2.LINE_AA)
            cv2.circle(img, (preview_cx, SWATCH_CENTER_Y), preview_radius,
                       (230, 230, 230), 1, cv2.LINE_AA)

            draw_rounded_rect(img, (pill_x1, pill_y1), (pill_x2, pill_y2), 12, (22, 22, 26))

            dot_color = MODE_COLORS.get(mode, (200, 200, 200))
            cv2.circle(img, (pill_x1 + 16, pill_y1 + pill_h // 2), 6,
                       dot_color, -1, cv2.LINE_AA)

            cv2.putText(img, mode, (pill_x1 + 32, pill_y1 + 21),
                        cv2.FONT_HERSHEY_DUPLEX, 0.55, (240, 240, 240), 1, cv2.LINE_AA)
            cv2.putText(img, f"{int(fps)} FPS", (pill_x1 + 32, pill_y1 + 38),
                        cv2.FONT_HERSHEY_DUPLEX, 0.42, (140, 220, 150), 1, cv2.LINE_AA)



        key = cv2.waitKey(1)



        if key == ord('c'):# Clear canvas
            canvas = np.zeros_like(img)



        if key == ord('s'):# Save image
            cv2.imwrite("drawing.png", canvas)
            print("Drawing saved")



        if key == ord('+'):# Thickness increase
            brush_thickness += 1
            if brush_color == (0, 0, 0):
                eraser_thickness = brush_thickness
            else:
                draw_thickness = brush_thickness



        if key == ord('-'): # Thickness decrease
            brush_thickness = max(1, brush_thickness - 1)
            if brush_color == (0, 0, 0):
                eraser_thickness = brush_thickness
            else:
                draw_thickness = brush_thickness



        if key == 27:# Exit
            break

        cv2.imshow("Air Drawing", img)


finally:
    cap.release()
    cv2.destroyAllWindows()
