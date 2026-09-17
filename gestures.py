"""Hand-landmark helpers: finger state, pixel conversion, pinch mapping.

Pure functions with no cv2/mediapipe dependency of their own — they operate
on whatever duck-typed landmark object MediaPipe hands back (anything with
a `.landmark[i].x/.y` in normalized 0..1 coordinates).
"""

# Left-hand pinch (thumb tip to index tip, in pixels) mapped to brush width
PINCH_MIN_DIST = 25
PINCH_MAX_DIST = 220
PINCH_THICKNESS_MIN = 2
PINCH_THICKNESS_MAX = 60

# Minimum box-filter gesture size, in pixels, before it activates
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
