"""Image effects applied to a region of the live camera frame."""

import cv2


def apply_cartoon_filter(region):
    gray = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)
    gray = cv2.medianBlur(gray, 5)
    edges = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C,
                                  cv2.THRESH_BINARY, 9, 9)
    smooth = cv2.bilateralFilter(region, 9, 250, 250)
    return cv2.bitwise_and(smooth, smooth, mask=edges)
