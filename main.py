import cv2
import mediapipe as mp
import numpy as np
import time
import sys

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
    max_num_hands=1,
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

TOOLBAR_HEIGHT = 70
SWATCH_TOP, SWATCH_BOTTOM = 10, 60
SWATCH_WIDTH = 70
SWATCH_GAP = 20
SWATCH_START_X = 20
TOOLBAR_COLORS = [
    (255, 0, 255),  # purple
    (0, 255, 0),    # green
    (0, 0, 255),    # red
]


def finger_up(hand_landmarks, tip_id):
    tip_y = hand_landmarks.landmark[tip_id].y
    lower_y = hand_landmarks.landmark[tip_id - 2].y

    return tip_y < lower_y


def build_toolbar(frame_width):
    """Lay out color/eraser swatches left-to-right, dropping any that
    would not fit inside the current frame instead of overflowing it."""
    swatches = []
    x = SWATCH_START_X

    for color in TOOLBAR_COLORS:
        x2 = x + SWATCH_WIDTH
        if x2 > frame_width - 10:
            return swatches
        swatches.append({
            "x1": x, "y1": SWATCH_TOP, "x2": x2, "y2": SWATCH_BOTTOM,
            "color": color, "is_eraser": False,
        })
        x = x2 + SWATCH_GAP

    eraser_x2 = x + SWATCH_WIDTH + 20
    if eraser_x2 <= frame_width - 10:
        swatches.append({
            "x1": x, "y1": SWATCH_TOP, "x2": eraser_x2, "y2": SWATCH_BOTTOM,
            "color": (255, 255, 255), "is_eraser": True,
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

        cv2.rectangle(img, (0, 0), (w, TOOLBAR_HEIGHT), (50, 50, 50), -1)

        for swatch in toolbar:
            cv2.rectangle(img, (swatch["x1"], swatch["y1"]),
                           (swatch["x2"], swatch["y2"]), swatch["color"], -1)
            if swatch["is_eraser"]:
                cv2.putText(img, "ERASE", (swatch["x1"] + 10, swatch["y2"] - 15),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 2)


        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

        results = hands.process(img_rgb)

        if results.multi_hand_landmarks:

            for hand_landmarks in results.multi_hand_landmarks:

                mp_draw.draw_landmarks(
                    img,
                    hand_landmarks,
                    mp_hands.HAND_CONNECTIONS
                )

                index_tip = hand_landmarks.landmark[8]

                x = int(index_tip.x * w)
                y = int(index_tip.y * h)

                smooth_x = int((smooth_x + x) / 2)
                smooth_y = int((smooth_y + y) / 2)


                cv2.circle(img, (smooth_x, smooth_y),
                           brush_thickness,
                           brush_color,
                           -1)



                index_up = finger_up(hand_landmarks, 8)
                middle_up = finger_up(hand_landmarks, 12)


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
                        if swatch["x1"] < smooth_x < swatch["x2"] and swatch["y1"] < smooth_y < swatch["y2"]:
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


        else:
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

        toolbar_end = toolbar[-1]["x2"] if toolbar else SWATCH_START_X
        status_x = min(toolbar_end + 20, max(w - 200, 0))

        cv2.putText(img,
                    f"FPS: {int(fps)}",
                    (status_x, 60),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    (0, 255, 0),
                    2)


        cv2.putText(img,
                    f"MODE: {mode}",
                    (status_x, 40),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    1,
                    (255, 255, 255),
                    2)



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
