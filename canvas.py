"""Stroke-based drawing surface with undo/redo.

The raster (`Canvas.raster`) is what actually gets composited onto the
camera feed each frame and is updated incrementally while drawing, exactly
like a plain pixel buffer would be. `strokes` is the real source of truth
underneath it: a list of {points, color, thickness} dicts. Undo/redo and
clear operate on that list via a small history/redo stack (command
pattern) and only re-rasterise the whole canvas on those infrequent
events, not on every drawn point.
"""

import cv2
import numpy as np

HISTORY_LIMIT = 100


class Canvas:
    def __init__(self, shape):
        self.raster = np.zeros(shape, dtype=np.uint8)
        self.strokes = []
        self.history = []       # entries: {"type": "add", "stroke": {...}}
                                 #        | {"type": "clear", "strokes": [...]}
        self.redo_stack = []
        self._active_stroke = None

    def resize(self, shape):
        """Camera resolution changing mid-session invalidates all stroke
        coordinates, so this starts over rather than trying to rescale."""
        if self.raster.shape == shape:
            return
        self.raster = np.zeros(shape, dtype=np.uint8)
        self.strokes = []
        self.history = []
        self.redo_stack = []
        self._active_stroke = None

    def begin_stroke(self, x, y, color, thickness):
        stroke = {"points": [(x, y)], "color": color, "thickness": thickness}
        self.strokes.append(stroke)
        self.history.append({"type": "add", "stroke": stroke})
        if len(self.history) > HISTORY_LIMIT:
            self.history.pop(0)
        self.redo_stack.clear()
        self._active_stroke = stroke
        cv2.circle(self.raster, (x, y), max(1, thickness // 2), color, -1)

    def extend_stroke(self, x, y):
        if self._active_stroke is None:
            return
        prev = self._active_stroke["points"][-1]
        cv2.line(self.raster, prev, (x, y),
                 self._active_stroke["color"], self._active_stroke["thickness"])
        self._active_stroke["points"].append((x, y))

    def end_stroke(self):
        self._active_stroke = None

    def clear(self):
        if not self.strokes:
            return False
        self.history.append({"type": "clear", "strokes": self.strokes})
        if len(self.history) > HISTORY_LIMIT:
            self.history.pop(0)
        self.strokes = []
        self.redo_stack.clear()
        self._active_stroke = None
        self.raster[:] = 0
        return True

    def undo(self):
        if not self.history:
            return False
        entry = self.history.pop()
        if entry["type"] == "add":
            if entry["stroke"] is self._active_stroke:
                self._active_stroke = None
            self.strokes.pop()
        else:
            self.strokes = list(entry["strokes"])
            self._active_stroke = None
        self.redo_stack.append(entry)
        self._redraw()
        return True

    def redo(self):
        if not self.redo_stack:
            return False
        entry = self.redo_stack.pop()
        if entry["type"] == "add":
            self.strokes.append(entry["stroke"])
        else:
            self.strokes = []
        self.history.append(entry)
        self._redraw()
        return True

    def _redraw(self):
        self.raster[:] = 0
        for stroke in self.strokes:
            points, color, thickness = stroke["points"], stroke["color"], stroke["thickness"]
            if len(points) == 1:
                cv2.circle(self.raster, points[0], max(1, thickness // 2), color, -1)
                continue
            for a, b in zip(points, points[1:]):
                cv2.line(self.raster, a, b, color, thickness)
