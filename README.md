Gesture-Based Air Drawing System

A real-time gesture-controlled air drawing application built using Python, OpenCV, and MediaPipe.

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

Different hand gestures activate different modes:

| Gesture                     | Action         |
| --------------------------- | -------------- |
| ☝️ Index Finger Up          | Draw Mode      |
| ✌️ Index + Middle Finger Up | Selection Mode |
| ✊ Fist                      | Idle Mode      |

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

## 📏 Brush Thickness Control

* Increase/decrease brush size
* More natural drawing experience

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

| Key   | Function            |
| ----- | ------------------- |
| `C`   | Clear Canvas        |
| `S`   | Save Drawing        |
| `ESC` | Exit Program        |
| `+`   | Increase Brush Size |
| `-`   | Decrease Brush Size |

---

# 🧠 How It Works

The webcam continuously captures video frames.

The system:

1. detects the user’s hand
2. tracks finger landmarks
3. identifies gestures
4. converts fingertip movement into drawing actions

A separate digital canvas stores all drawing operations and merges them with the webcam feed in real time.

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

* AI gesture recognition
* Multi-hand support
* Shape recognition
* Virtual mouse control
* Undo/Redo system
* Gesture-based brush resizing

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
.
