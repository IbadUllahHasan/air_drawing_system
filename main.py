import cv2
import mediapipe as mp
import numpy as np
import time

cap = cv2.VideoCapture(0)

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
eraser_thickness = 40

mode = "IDLE"

prev_time = 0

def finger_up(hand_landmarks, tip_id):
    tip_y = hand_landmarks.landmark[tip_id].y
    lower_y = hand_landmarks.landmark[tip_id - 2].y

    return tip_y < lower_y

while True:

    success, img = cap.read()

    if not success:
        break

    img = cv2.flip(img, 1)

    h, w, c = img.shape

    if canvas is None:
        canvas = np.zeros_like(img)


    cv2.rectangle(img, (0, 0), (1280, 70), (50, 50, 50), -1)


    cv2.rectangle(img, (20, 10), (90, 60), (255, 0, 255), -1)
    cv2.rectangle(img, (110, 10), (180, 60), (0, 255, 0), -1)
    cv2.rectangle(img, (200, 10), (270, 60), (0, 0, 255), -1)


    cv2.rectangle(img, (290, 10), (380, 60), (255, 255, 255), -1)
    cv2.putText(img, "ERASE", (300, 45),
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

                # Color selection
                if 20 < smooth_x < 90 and 10<smooth_y< 60:
                    brush_color = (255, 0, 255)

                elif 110 < smooth_x < 180 and 10<smooth_y< 60:
                    brush_color = (0, 255, 0)

                elif 200 < smooth_x < 270 and 10<smooth_y< 60:
                    brush_color = (0, 0, 255)

                elif 290 < smooth_x < 380 and 10<smooth_y< 60:
                    brush_color = (0, 0, 0)
                    brush_thickness = eraser_thickness


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

    cv2.putText(img,
                f"FPS: {int(fps)}",
                (400, 60),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (0, 255, 0),
                2)


    cv2.putText(img,
                f"MODE: {mode}",
                (400, 40),
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



    if key == ord('-'): # Thickness decrease
        brush_thickness = max(1, brush_thickness - 1)



    if key == 27:# Exit
        break

    cv2.imshow("Air Drawing", img)


cap.release()
cv2.destroyAllWindows()