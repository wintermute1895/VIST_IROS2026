# LinkerHand L10 Vision-Based Control System

## 📋 Overview

This system implements a vision-based control system for the LinkerHand L10 robotic hand using MediaPipe hand tracking and a state machine approach.

## 🏗️ Architecture

```
Camera → VisionController → LinkerHandDriver → Hardware
         (MediaPipe +        (CAN Bus)
          State Machine)
```

### Components

1. **VisionController** (`src/core/vision_controller.py`)
   - MediaPipe hand detection
   - Geometric feature extraction (pinch ratio)
   - State machine with debouncing
   - Outputs target joint angles

2. **LinkerHandDriver** (`src/robot/hand_driver.py`)
   - CAN bus communication
   - Hardware control with optimizations
   - Buffer overflow prevention

3. **Main Entry Point** (`scripts/run_hand.py`)
   - System integration
   - Camera capture
   - Visualization
   - User interface

## 🎯 State Machine

The system uses a 3-state machine based on pinch ratio:

| State | Pinch Ratio | Description |
|-------|-------------|-------------|
| **IDLE** | > 0.8 | Hand fully open |
| **PRE_GRASP** | 0.3 - 0.8 | Pre-grasp position |
| **GRASP** | ≤ 0.2 | Pinch/grasp (closed) |

### Pinch Ratio Calculation

```
pinch_ratio = distance(thumb_tip, index_tip) / distance(wrist, middle_mcp)
```

This normalized metric is independent of hand size and camera distance.

### Debouncing

The state machine requires **5 consecutive frames** of the same state before switching. This prevents jittery transitions.

## ⚙️ Joint Angle Configuration

**IMPORTANT**: You need to fill in the preset joint angles in `src/core/vision_controller.py`

### Location

Find these arrays at the top of the `VisionController` class (lines 30-80):

```python
JOINT_ANGLES_IDLE: List[float] = [0.0, 0.0, 0.0, ...]
JOINT_ANGLES_PRE_GRASP: List[float] = [0.0, 0.0, 0.0, ...]
JOINT_ANGLES_GRASP: List[float] = [0.0, 0.0, 0.0, ...]
```

### Joint Order (10 DOF)

```
[0] Thumb_Pitch    - Thumb root bend
[1] Thumb_Yaw      - Thumb rotation
[2] Index_Pitch    - Index finger bend
[3] Middle_Pitch   - Middle finger bend
[4] Ring_Pitch     - Ring finger bend
[5] Pinky_Pitch    - Pinky finger bend
[6] Index_Roll     - Index finger roll (passive)
[7] Ring_Roll      - Ring finger roll (passive)
[8] Pinky_Roll     - Pinky finger roll (passive)
[9] Thumb_Roll     - Thumb roll (passive)
```

**Units**: DEGREES (not radians!)

### How to Configure

1. **Test individual poses manually** using the driver test script
2. **Record the angle values** that produce desired poses
3. **Fill in the arrays** in `vision_controller.py`

Example:
```python
JOINT_ANGLES_GRASP: List[float] = [
    45.0,  # [0] Thumb_Pitch - bend thumb
    30.0,  # [1] Thumb_Yaw - rotate thumb
    60.0,  # [2] Index_Pitch - bend index
    60.0,  # [3] Middle_Pitch - bend middle
    60.0,  # [4] Ring_Pitch - bend ring
    60.0,  # [5] Pinky_Pitch - bend pinky
    0.0,   # [6] Index_Roll - passive
    0.0,   # [7] Ring_Roll - passive
    0.0,   # [8] Pinky_Roll - passive
    0.0,   # [9] Thumb_Roll - passive
]
```

## 🚀 Usage

### Basic Usage

```bash
# Run in mock mode (no hardware, for testing)
cd /home/luka/.ssh/VIST
python scripts/run_hand.py --mock

# Run with real hardware
python scripts/run_hand.py
```

### Advanced Options

```bash
# Use different camera
python scripts/run_hand.py --camera 1

# Change control frequency
python scripts/run_hand.py --freq 20

# Debug mode with verbose logging
python scripts/run_hand.py --log-level DEBUG

# Custom CAN configuration
python scripts/run_hand.py --can-id 0x27 --can-channel can0
```

### Keyboard Controls

- **'q'** - Quit safely
- **'r'** - Reset hand to zero position
- **'s'** - Print system status

## 📊 Visualization

The system displays:

1. **Hand landmarks** - MediaPipe skeleton overlay
2. **Detection status** - "HAND DETECTED" or "NO HAND"
3. **Current state** - IDLE / PRE_GRASP / GRASP (color-coded)
4. **Pinch ratio** - Real-time value
5. **Debounce counter** - Shows transition progress
6. **Target angles** - First 6 active joints
7. **FPS and statistics** - Performance metrics

## 🔧 Testing Workflow

### Step 1: Test in Mock Mode

```bash
python scripts/run_hand.py --mock
```

This will:
- Initialize camera and vision system
- Show visualization
- NOT send commands to hardware
- Useful for testing vision pipeline

### Step 2: Test Driver Separately

```bash
cd /home/luka/.ssh/VIST
python -m src.robot.hand_driver --real
```

This will:
- Test hardware communication
- Run predefined movements
- Verify CAN bus connection

### Step 3: Calibrate Joint Angles

1. Use the driver test script to find good angles for each pose
2. Update the arrays in `vision_controller.py`
3. Test each state individually

### Step 4: Run Full System

```bash
python scripts/run_hand.py
```

## 🐛 Troubleshooting

### Camera Issues

```bash
# List available cameras
ls /dev/video*

# Test camera
python scripts/run_hand.py --camera 0 --mock
```

### CAN Bus Issues

```bash
# Check CAN interface
ip link show can0

# Bring up CAN interface (if needed)
sudo ip link set can0 up type can bitrate 1000000
```

### Import Errors

Make sure you're running from the project root:
```bash
cd /home/luka/.ssh/VIST
python scripts/run_hand.py
```

The script automatically adds the project root to `sys.path`.

### MediaPipe Not Found

```bash
pip install mediapipe opencv-python numpy
```

## 📁 File Structure

```
VIST/
├── src/
│   ├── core/
│   │   ├── __init__.py
│   │   └── vision_controller.py    # ← Vision + state machine
│   └── robot/
│       └── hand_driver.py           # ← Hardware driver
├── scripts/
│   └── run_hand.py                  # ← Main entry point
└── config/
    └── linkerhand_l10_right.urdf    # ← Robot description
```

## 🎓 Key Concepts

### Why Normalized Pinch Ratio?

Using absolute distances would fail when:
- User moves closer/farther from camera
- Different hand sizes
- Camera zoom changes

The normalized ratio is robust to these variations.

### Why Debouncing?

Without debouncing:
- Noisy detection causes rapid state changes
- Hand jitters between states
- Uncomfortable control

With 5-frame debouncing:
- Smooth, deliberate transitions
- More predictable behavior
- Better user experience

### Why State Machine?

Instead of continuous mapping:
- **Discrete states** are easier to control
- **Predictable behavior** - you know what each gesture does
- **Easy to extend** - add more states/gestures later
- **Robust** - less sensitive to noise

## 📝 Next Steps

1. **Fill in joint angles** in `vision_controller.py`
2. **Test in mock mode** to verify vision pipeline
3. **Test with hardware** to verify movements
4. **Tune thresholds** if needed (ratio thresholds, debounce frames)
5. **Add more states** if desired (e.g., pointing gesture)

## 🔍 Code Quality

- ✅ Type hints throughout
- ✅ Comprehensive docstrings
- ✅ Logging at appropriate levels
- ✅ Safe cleanup on exit
- ✅ Error handling
- ✅ Command-line interface

## 📞 Support

If you encounter issues:
1. Check the logs (use `--log-level DEBUG`)
2. Test components individually
3. Verify hardware connections
4. Check camera and CAN bus

---

**Created**: 2026-02-05
**Author**: Claude (Anthropic)
**Project**: VIST - Vision-based Hand Control
