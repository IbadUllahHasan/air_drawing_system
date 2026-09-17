"""Gesture-controlled air drawing with a webcam."""

import argparse
import math
import sys
import time

import cv2
import mediapipe as mp

from canvas import Canvas
from filters import apply_cartoon_filter
from gestures import BOX_MIN_SIZE, finger_up, landmark_px, pinch_to_thickness
import ui

WINDOW_NAME = "Air Drawing"

mp_hands = mp.solutions.hands


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

    brush_color = ui.BRUSH_COLORS[0]
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

            if canvas is None:
                canvas = Canvas(frame.shape)
            else:
                canvas.resize(frame.shape)

            m = ui.ui_metrics(w)
            layout = ui.build_layout(w, m)

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
                        canvas.end_stroke()
                        prev_x, prev_y = 0, 0
                        frame[y1:y2, x1:x2] = apply_cartoon_filter(frame[y1:y2, x1:x2])

            # Left hand pinch resizes whichever tool is active.
            if left_hand is not None and not box_active:
                tx, ty = landmark_px(left_hand, 4, w, h)
                ix, iy = landmark_px(left_hand, 8, w, h)
                brush_thickness = pinch_to_thickness(math.hypot(ix - tx, iy - ty))
                if brush_color == ui.ERASER_COLOR:
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
                    hover_idx, hover_locked = None, False

                    # Pinky up (index + pinky, middle down -- the "spider-man"
                    # gesture) lifts the pen: the cursor keeps tracking but
                    # nothing is drawn, so you can reposition before the next
                    # stroke without a connecting line back to where you were.
                    pinky_up = finger_up(right_hand, 20)
                    mode = "LIFT" if pinky_up else "DRAW"

                    if pinky_up or smooth_y <= bar_bottom:
                        canvas.end_stroke()
                        prev_x, prev_y = 0, 0
                    else:
                        if prev_x == 0 and prev_y == 0:
                            canvas.begin_stroke(smooth_x, smooth_y, brush_color, brush_thickness)
                        else:
                            canvas.extend_stroke(smooth_x, smooth_y)
                        prev_x, prev_y = smooth_x, smooth_y

                elif index_up and middle_up:
                    mode = "SELECT"
                    canvas.end_stroke()
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
                            hover_progress = (now - hover_start) / ui.DWELL_SECONDS
                            if hover_progress >= 1.0:
                                sw = layout["swatches"][hovered]
                                if sw["is_eraser"]:
                                    brush_color = ui.ERASER_COLOR
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
                    canvas.end_stroke()
                    prev_x, prev_y = 0, 0
                    hover_idx, hover_locked = None, False
            else:
                canvas.end_stroke()
                prev_x, prev_y = 0, 0
                if not box_active:
                    hover_idx, hover_locked = None, False

            # Composite the drawing over the camera image.
            canvas_gray = cv2.cvtColor(canvas.raster, cv2.COLOR_BGR2GRAY)
            _, inverse = cv2.threshold(canvas_gray, 50, 255, cv2.THRESH_BINARY_INV)
            inverse = cv2.cvtColor(inverse, cv2.COLOR_GRAY2BGR)
            img = cv2.bitwise_and(frame, inverse)
            img = cv2.bitwise_or(img, canvas.raster)

            fps = 1.0 / max(1e-4, now - prev_time)
            prev_time = now

            # Everything below is UI chrome, drawn on top of the composite.
            accent = ui.ERASER_SWATCH_COLOR if brush_color == ui.ERASER_COLOR else brush_color

            if box_active and box_rect:
                bx1, by1, bx2, by2 = box_rect
                ui.rounded_rect(img, (bx1, by1), (bx2, by2), int(12 * m["scale"]),
                                ui.MODE_COLORS["BOX FILTER"], 2)
                ui.draw_text(img, "CARTOON", bx1 + 10, by1 - int(6 * m["scale"]),
                             m["font_sm"], ui.MODE_COLORS["BOX FILTER"], anchor="lb")

            if show_hands:
                for landmarks in (left_hand, right_hand):
                    if landmarks is not None:
                        ui.draw_hand_skeleton(img, landmarks, w, h, mp_hands.HAND_CONNECTIONS)

            if right_hand is not None and not box_active:
                ui.draw_cursor(img, smooth_x, smooth_y, brush_thickness, accent, mode)

            if layout:
                ui.draw_toolbar(img, layout, m, accent, brush_thickness, swatch_anim,
                                hover_idx, hover_progress, brush_color, now)
            ui.draw_status(img, layout, m, mode, fps, brush_thickness)

            toasts[:] = [t for t in toasts if now - t["t"] < ui.TOAST_LIFETIME]
            if toasts:
                ui.draw_toasts(img, toasts, m, now)
            else:
                hint_age = now - started
                if hint_age < ui.HINT_LIFETIME:
                    ui.draw_hints(img, m, min(1.0, (ui.HINT_LIFETIME - hint_age) / 1.0))

            cv2.imshow(WINDOW_NAME, img)
            key = cv2.waitKey(1) & 0xFF

            # Checked after waitKey so the window has been pumped at least once.
            if cv2.getWindowProperty(WINDOW_NAME, cv2.WND_PROP_VISIBLE) < 1:
                break

            if key == ord('c'):
                toast("Canvas cleared" if canvas.clear() else "Canvas already empty")
            elif key == ord('z'):
                toast("Undo" if canvas.undo() else "Nothing to undo")
            elif key == ord('y'):
                toast("Redo" if canvas.redo() else "Nothing to redo")
            elif key == ord('s'):
                cv2.imwrite("drawing.png", canvas.raster)
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
                if brush_color == ui.ERASER_COLOR:
                    eraser_thickness = brush_thickness
                else:
                    draw_thickness = brush_thickness
            elif key == ord('-'):
                brush_thickness = max(1, brush_thickness - 1)
                if brush_color == ui.ERASER_COLOR:
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
