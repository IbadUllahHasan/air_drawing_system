
# Gesture-Based Air Drawing System 🎨✋

A real-time gesture-controlled air drawing application built using **Python**, **OpenCV**, and **MediaPipe**.

This project allows users to draw in the air using only hand gestures captured through a webcam — creating a touchless and interactive virtual drawing experience.

---

# 🚀 Features

## ✋ Real-Time Hand Tracking

* Detects and tracks hand movements live through webcam input
* Uses 21 hand landmarks for precise finger positioning
* Smooth and responsive gesture interaction

---

## 🎨 Air Drawing System

* Draw in the air using your index finger
* Real-time stroke rendering
* Smooth continuous line generation

---

## 🧠 Gesture Recognition

The **right hand** drives drawing. Different gestures activate different modes:

| Gesture                     | Action         |
| --------------------------- | -------------- |
| ☝️ Index Finger Up          | Draw Mode      |
| ✌️ Index + Middle Finger Up | Selection Mode |
| ✊ Fist                      | Idle Mode      |

---

## 🤝 Two-Hand Gestures

With both hands in view, the **left hand** becomes a live control:

| Gesture                                        | Action                          |
| ----------------------------------------------- | -------------------------------- |
| 🤏 Left hand pinch (thumb + index)              | Resize the active brush/eraser, live |
| ✌️✌️ Both hands, index + middle up on each      | Frame a box between the two index tips and apply a live cartoon filter inside it |

The box-filter gesture takes priority — while both hands are making it, the left-hand pinch and right-hand draw/select are paused for that frame.

---

## 🖌️ Multiple Brush Colors

* Purple brush
* Green brush
* Red brush
* Gesture-controlled color selection

---

## 🧽 Eraser Tool

* Touchless erasing using gesture selection
* Larger eraser thickness for realistic editing

---

## 🖼️ Two-Hand Box Filter

* Frame any region of the live feed between your two index fingertips
* Applies a live cartoon/edge filter inside the frame while the gesture is held
* Your existing drawing still shows on top of the filtered background

---

## 📏 Brush Thickness Control

* Live, gesture-driven resizing: pinch your left hand's thumb and index finger closer together or farther apart to shrink or grow the active brush/eraser
* `+` / `-` keys still work as a manual fallback

---

## 🪄 Gesture Smoothing

* Reduces shaky lines
* Stabilizes hand movement
* Produces cleaner strokes

---

## 💾 Save Drawing Feature

Press:

```bash
S
```

to save your artwork instantly.

---

## 🧹 Clear Canvas

Press:

```bash
C
```

to clear the drawing canvas.

---

## ⚡ FPS Counter

Displays live performance metrics:

* Frames Per Second
* Real-time processing speed

---

## 🖥️ Interactive Toolbar UI

Includes:

* color selection
* eraser tool
* mode indicators
* real-time visual feedback

---

# 🛠️ Technologies Used

* Python
* OpenCV
* MediaPipe
* NumPy

---

# 📂 Project Structure

```bash
air-drawing-system/
│
├── main.py
├── requirements.txt
├── README.md
├── .gitignore
├── LICENSE
│
├── screenshots/
│   ├── Draw Mode.png
│   ├── Idle Mode.png
│   ├── Select Mode.png
```

---

# ⚙️ Installation

## 1. Clone Repository

```bash
git clone https://github.com/IbadUllahHasan/air_drawing_system
```

---

## 2. Open Project Folder

```bash
cd air_drawing_system
```

---

## 3. Install Dependencies

```bash
pip install -r requirements.txt
```

---

## 4. Run Project

```bash
python main.py
```

---

# 🎮 Controls

| Key   | Function                              |
| ----- | -------------------------------------- |
| `C`   | Clear Canvas                          |
| `S`   | Save Drawing (`drawing.png`)          |
| `ESC` | Exit Program                          |
| `+`   | Increase Brush Size (manual fallback) |
| `-`   | Decrease Brush Size (manual fallback) |

---

# 📖 How to Use

## 1. Get set up

* Sit facing your webcam in reasonably even lighting, with your hand(s) fully inside the frame.
* Run `python main.py`. A window titled **"Air Drawing"** opens showing your mirrored camera feed with a toolbar across the top.
* Press `ESC` any time to quit — the camera is always released cleanly on exit.

## 2. Draw with your right hand

| Do this                         | What happens                |
| -------------------------------- | ---------------------------- |
| Raise only your **index finger** | `DRAW` mode — a colored line follows your fingertip |
| Raise **index + middle** finger  | `SELECT` mode — move over the toolbar to pick a tool, nothing is drawn |
| Close your hand / drop your fingers | `IDLE` mode — tracking pauses, no drawing |

The current mode and live FPS are shown in the top-right of the window.

## 3. Pick a color or the eraser

While in `SELECT` mode (index + middle up), hover your fingertip over a toolbar swatch:

* **Purple / Green / Red** squares — switch the draw brush to that color
* **ERASE** box — switch to the eraser (uses a separate, larger thickness so it doesn't affect your draw brush size)

## 4. Resize the brush with your left hand

Bring your **left hand** into frame and pinch your thumb and index finger together or apart:

* Pinched tight → thinnest brush/eraser
* Spread wide → thickest brush/eraser

This adjusts whichever tool is currently active (draw brush or eraser) and updates live as you draw with your right hand. The `+`/`-` keys do the same thing manually if you'd rather not use two hands.

## 5. Apply the two-hand box filter

Raise **index + middle finger on both hands at once**. A rectangle is drawn between your two index fingertips and a live cartoon/edge filter is applied inside it — move your hands to move and resize the filtered region. Drop either hand's pose to turn it off. Anything already drawn stays visible on top of the filtered area.

## 6. Save or clear your work

* Press `S` to save the current canvas to `drawing.png` in the project folder.
* Press `C` to wipe the canvas and start over.

---

# 🧠 How It Works

The webcam continuously captures video frames, which are:

1. Flipped horizontally for a natural mirror view
2. Passed to MediaPipe Hands (tracking up to two hands, 21 landmarks each)
3. Classified as the **right hand** (drawing/toolbar) or **left hand** (pinch-resize), with a two-hand pose reserved for the box filter
4. Converted into drawing actions based on which fingers are raised and where the fingertip is

A separate digital canvas stores all drawing strokes and is composited over the live webcam feed every frame, so strokes persist even as the camera view keeps changing.

---

# 🌍 Real-World Applications

* Smart classrooms
* Virtual whiteboards
* Touchless interfaces
* Accessibility systems
* Gesture-controlled presentations
* AR/VR interaction systems

---

# 🔮 Future Improvements

* Shape recognition (snap freehand strokes to clean circles/rectangles/lines)
* Undo/Redo system
* Virtual mouse control
* More box-filter effects (grayscale, thermal colormap, invert) with a way to cycle between them

---

# 📈 What This Project Demonstrates

This project showcases:

* Computer Vision
* Real-Time Video Processing
* Human Computer Interaction (HCI)
* Gesture Recognition
* Interactive UI Systems
* Coordinate Mapping
* AI-assisted interaction concepts

---

# 📜 License

This project is licensed under the MIT License.

---

# ⭐ Final Note

This project started as a simple hand tracking experiment and evolved into a complete gesture-based interaction system.

The biggest learning came not from tutorials, but from:

* debugging
* experimenting
* modifying features
* solving real implementation problems

