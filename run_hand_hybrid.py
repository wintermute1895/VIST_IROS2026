#!/usr/bin/env python3
"""
============================================================================
LinkerHand L10 Hybrid Teleoperation System
============================================================================
Purpose: Hybrid control combining retargeting and hardcoded grasp poses

Control Modes:
1. RETARGETING: Normal hand retargeting (default)
2. FINE_PINCH: Hardcoded fine pinch pose (triggered by gesture)
3. POWER_GRASP: Hardcoded power grasp pose (triggered by gesture)

Features:
- Smooth transitions between modes
- Gesture-based mode switching
- Autonomous mode selection based on hand state
============================================================================
"""

import sys
import os
import time
import argparse
import logging
import numpy as np
import cv2
from enum import Enum
from typing import Optional

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

# Import our modules
from src.core.linker_hand_retargeter import LinkerHandRetargeter
from src.hand_driver import LinkerHandDriver
from src.utils.gesture_detector import GestureDetector
from src.utils.grasp_poses import GraspPoseManager


class ControlMode(Enum):
    """Control mode enumeration"""
    RETARGETING = "retargeting"
    FINE_PINCH = "fine_pinch"
    POWER_GRASP = "power_grasp"
    OPEN_HAND = "open_hand"


class HybridTeleoperationSystem:
    """
    Hybrid teleoperation system with retargeting and hardcoded poses
    """

    # Constants
    CONTROL_FREQ = 30  # Hz
    TRANSITION_SPEED = 0.15  # Blend speed for mode transitions

    # SDK uses 0-255 range: 0=bent(蜷缩), 255=straight(伸直)
    SDK_MIN = 0
    SDK_MAX = 255

    # Joint limits from URDF (relaxed version)
    JOINT_LIMITS = np.array([
        0.5146,   # thumb_cmc_pitch
        1.9189,   # thumb_cmc_yaw
        1.3607,   # index_mcp_pitch
        1.3607,   # middle_mcp_pitch
        1.3607,   # ring_mcp_pitch
        1.3607,   # pinky_mcp_pitch
        1.5708,   # index_mcp_roll (relaxed to 90°)
        1.5708,   # ring_mcp_roll (relaxed to 90°)
        1.5708,   # pinky_mcp_roll (relaxed to 90°)
        1.1339,   # thumb_cmc_roll
    ])

    def __init__(self,
                 retarget_config: str,
                 camera_id: int = 0,
                 mock_mode: bool = False,
                 enable_auto_mode: bool = True):
        """
        Initialize hybrid teleoperation system

        Args:
            retarget_config: Path to retargeting config YAML
            camera_id: Camera device ID
            mock_mode: If True, run without hardware
            enable_auto_mode: If True, enable automatic mode switching
        """
        self.logger = logging.getLogger(__name__)
        self.mock_mode = mock_mode
        self.enable_auto_mode = enable_auto_mode

        # State variables
        self.current_mode = ControlMode.RETARGETING
        self.target_mode = ControlMode.RETARGETING
        self.blend_progress = 1.0  # 1.0 = fully in current mode
        self.prev_command = None
        self.frame_count = 0

        self.logger.info("="*70)
        self.logger.info("Initializing Hybrid Hand Teleoperation System")
        if mock_mode:
            self.logger.info("(MOCK MODE - No Hardware)")
        self.logger.info(f"Auto mode switching: {'Enabled' if enable_auto_mode else 'Disabled'}")
        self.logger.info("="*70)

        # Initialize components
        self._init_camera(camera_id)
        self._init_mediapipe()
        self._init_retargeting(retarget_config)
        self._init_gesture_detector()
        self._init_grasp_poses()
        self._init_driver(mock_mode)

        self.logger.info("="*70)
        self.logger.info("✅ System initialized successfully")
        self.logger.info(f"  Control frequency: {self.CONTROL_FREQ} Hz")
        self.logger.info(f"  Transition speed: {self.TRANSITION_SPEED}")
        self.logger.info("="*70)

    def _init_camera(self, camera_id: int):
        """Initialize camera"""
        self.logger.info(f"Initializing camera (ID: {camera_id})...")

        self.cap = cv2.VideoCapture(camera_id)
        if not self.cap.isOpened():
            raise RuntimeError(f"Failed to open camera {camera_id}")

        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        self.cap.set(cv2.CAP_PROP_FPS, 30)

        self.logger.info("✅ Camera initialized")

    def _init_mediapipe(self):
        """Initialize MediaPipe hand tracking"""
        self.logger.info("Initializing MediaPipe...")

        try:
            import mediapipe as mp

            self.mp_hands = mp.solutions.hands
            self.mp_drawing = mp.solutions.drawing_utils

            self.hands = self.mp_hands.Hands(
                static_image_mode=False,
                max_num_hands=1,
                min_detection_confidence=0.5,
                min_tracking_confidence=0.5
            )

            self.logger.info("✅ MediaPipe initialized")

        except ImportError as e:
            self.logger.error(f"Failed to import MediaPipe: {e}")
            self.logger.error("Please install: pip install mediapipe")
            raise

    def _init_retargeting(self, config_path: str):
        """Initialize retargeting"""
        self.logger.info("Initializing retargeting...")

        self.retargeter = LinkerHandRetargeter(
            config_path=config_path,
            project_root=PROJECT_ROOT
        )

        self.logger.info("✅ Retargeting initialized")

    def _init_gesture_detector(self):
        """Initialize gesture detector"""
        self.logger.info("Initializing gesture detector...")

        self.gesture_detector = GestureDetector(
            pinch_threshold=0.05,
            curl_threshold=0.7
        )

        self.logger.info("✅ Gesture detector initialized")

    def _init_grasp_poses(self):
        """Initialize grasp pose manager"""
        self.logger.info("Initializing grasp poses...")

        self.grasp_manager = GraspPoseManager()

        self.logger.info("✅ Grasp poses initialized")
        self.logger.info(f"  Available poses: {', '.join(self.grasp_manager.list_poses())}")

    def _init_driver(self, mock_mode: bool):
        """Initialize hardware driver"""
        self.logger.info("Initializing hardware driver...")

        self.driver = LinkerHandDriver(
            can_id=0x27,
            can_channel="can0",
            mock_mode=mock_mode,
            enable_filtering=True  # Enable filtering for smooth motion
        )

        self.logger.info("✅ Driver initialized")

    def process_frame(self, frame: np.ndarray) -> Optional[np.ndarray]:
        """
        Process a single frame

        Args:
            frame: BGR image from camera

        Returns:
            SDK values in 0-255 range (10,), or None if processing fails
        """
        # Convert to RGB for MediaPipe
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        # Detect hand
        results = self.hands.process(frame_rgb)

        if not results.multi_hand_landmarks:
            return None

        # Get first hand
        hand_landmarks = results.multi_hand_landmarks[0]

        # Draw hand landmarks
        self.mp_drawing.draw_landmarks(
            frame,
            hand_landmarks,
            self.mp_hands.HAND_CONNECTIONS,
            self.mp_drawing.DrawingSpec(color=(0, 255, 0), thickness=2, circle_radius=2),
            self.mp_drawing.DrawingSpec(color=(255, 0, 0), thickness=2)
        )

        # Convert to numpy array (21, 3)
        landmarks = np.array([
            [lm.x, lm.y, lm.z]
            for lm in hand_landmarks.landmark
        ])

        # Detect gestures
        gesture_state = self.gesture_detector.get_gesture_state(landmarks)

        # Update control mode based on gestures (if auto mode enabled)
        if self.enable_auto_mode:
            self._update_mode_from_gestures(gesture_state)

        # Get command based on current mode
        command = self._get_command_for_mode(landmarks, gesture_state)

        return command

    def _update_mode_from_gestures(self, gesture_state: dict):
        """
        Update control mode based on detected gestures

        Args:
            gesture_state: Gesture detection results
        """
        # Priority: fine_pinch > power_grasp > open_hand > retargeting

        if gesture_state['pinch']['active']:
            self.target_mode = ControlMode.FINE_PINCH
        elif gesture_state['grasp']['active']:
            self.target_mode = ControlMode.POWER_GRASP
        elif gesture_state['open']['active']:
            self.target_mode = ControlMode.OPEN_HAND
        else:
            self.target_mode = ControlMode.RETARGETING

        # Start transition if mode changed
        if self.target_mode != self.current_mode:
            self.blend_progress = 0.0
            self.logger.info(f"Mode transition: {self.current_mode.value} → {self.target_mode.value}")

    def _get_command_for_mode(self,
                              landmarks: np.ndarray,
                              gesture_state: dict) -> Optional[np.ndarray]:
        """
        Get command based on current control mode

        Args:
            landmarks: MediaPipe landmarks
            gesture_state: Gesture detection results

        Returns:
            SDK values (0-255) or None
        """
        # Get retargeting output
        joint_angles_rad = self.retargeter.process(landmarks)
        if joint_angles_rad is None:
            return None

        # Convert to SDK values
        retargeting_command = self._convert_to_sdk(joint_angles_rad)

        # If fully in retargeting mode, return directly
        if self.current_mode == ControlMode.RETARGETING and self.blend_progress >= 1.0:
            return retargeting_command

        # Get target pose based on target mode
        if self.target_mode == ControlMode.FINE_PINCH:
            target_pose = self.grasp_manager.get_pose('fine_pinch')
        elif self.target_mode == ControlMode.POWER_GRASP:
            target_pose = self.grasp_manager.get_pose('power_grasp')
        elif self.target_mode == ControlMode.OPEN_HAND:
            target_pose = self.grasp_manager.get_pose('open_hand')
        else:
            target_pose = retargeting_command

        # Blend between current and target
        if self.blend_progress < 1.0:
            # Transitioning
            self.blend_progress = min(1.0, self.blend_progress + self.TRANSITION_SPEED)

            if self.prev_command is not None:
                command = self.grasp_manager.blend_poses(
                    self.prev_command,
                    target_pose,
                    self.blend_progress
                )
            else:
                command = target_pose

            # Update current mode when transition complete
            if self.blend_progress >= 1.0:
                self.current_mode = self.target_mode
                self.logger.info(f"Mode transition complete: {self.current_mode.value}")

        else:
            # Fully in target mode
            command = target_pose

        return command

    def _convert_to_sdk(self, joint_angles_rad: np.ndarray) -> np.ndarray:
        """
        Convert joint angles (radians) to SDK values (0-255)

        Args:
            joint_angles_rad: Joint angles in radians (10,)

        Returns:
            SDK values (0-255)
        """
        # Clip to joint limits
        joint_angles_rad = np.clip(joint_angles_rad, 0, self.JOINT_LIMITS)

        # Normalize to 0-1 range
        normalized = joint_angles_rad / self.JOINT_LIMITS

        # Convert to SDK range with direction mapping
        sdk_values = np.zeros(10, dtype=int)

        # Pitch joints (indices 0,1,2,3,4,5,9): invert
        pitch_indices = [0, 1, 2, 3, 4, 5, 9]
        sdk_values[pitch_indices] = (self.SDK_MAX * (1.0 - normalized[pitch_indices])).astype(int)

        # Roll joints (indices 6,7,8): no inversion
        roll_indices = [6, 7, 8]
        sdk_values[roll_indices] = (self.SDK_MAX * normalized[roll_indices]).astype(int)

        # Clip to SDK range
        sdk_values = np.clip(sdk_values, self.SDK_MIN, self.SDK_MAX)

        return sdk_values

    def run(self):
        """
        Main teleoperation loop

        Keyboard controls:
        - 'q': Quit
        - 'r': Reset hand
        - 'm': Toggle auto mode
        - '1': Force retargeting mode
        - '2': Force fine pinch mode
        - '3': Force power grasp mode
        - '4': Force open hand mode
        """
        self.logger.info("="*70)
        self.logger.info("Starting Hybrid Teleoperation Loop")
        self.logger.info("  'q': Quit")
        self.logger.info("  'r': Reset hand")
        self.logger.info("  'm': Toggle auto mode")
        self.logger.info("  '1': Force retargeting mode")
        self.logger.info("  '2': Force fine pinch mode")
        self.logger.info("  '3': Force power grasp mode")
        self.logger.info("  '4': Force open hand mode")
        self.logger.info("="*70)

        try:
            while True:
                loop_start = time.time()

                # Capture frame
                ret, frame = self.cap.read()
                if not ret:
                    self.logger.error("Failed to capture frame")
                    break

                self.frame_count += 1

                # Process frame
                command = self.process_frame(frame)

                if command is not None:
                    # Store for blending
                    self.prev_command = command.copy()

                    # Send to hardware
                    self.driver.move(command.tolist())

                    # Display info on frame
                    self._draw_info(frame, command)

                else:
                    cv2.putText(frame, "No hand detected", (10, 30),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

                # Show frame
                cv2.imshow("Hybrid Hand Teleoperation", frame)

                # Handle keyboard input
                key = cv2.waitKey(1) & 0xFF
                if key == ord('q'):
                    self.logger.info("Quit requested")
                    break
                elif key == ord('r'):
                    self.logger.info("Reset requested")
                    self.driver.reset()
                    self.prev_command = None
                elif key == ord('m'):
                    self.enable_auto_mode = not self.enable_auto_mode
                    self.logger.info(f"Auto mode: {'Enabled' if self.enable_auto_mode else 'Disabled'}")
                elif key == ord('1'):
                    self.target_mode = ControlMode.RETARGETING
                    self.blend_progress = 0.0
                    self.logger.info("Forced mode: RETARGETING")
                elif key == ord('2'):
                    self.target_mode = ControlMode.FINE_PINCH
                    self.blend_progress = 0.0
                    self.logger.info("Forced mode: FINE_PINCH")
                elif key == ord('3'):
                    self.target_mode = ControlMode.POWER_GRASP
                    self.blend_progress = 0.0
                    self.logger.info("Forced mode: POWER_GRASP")
                elif key == ord('4'):
                    self.target_mode = ControlMode.OPEN_HAND
                    self.blend_progress = 0.0
                    self.logger.info("Forced mode: OPEN_HAND")

                # Maintain control frequency
                loop_time = time.time() - loop_start
                sleep_time = (1.0 / self.CONTROL_FREQ) - loop_time
                if sleep_time > 0:
                    time.sleep(sleep_time)

        except KeyboardInterrupt:
            self.logger.info("Interrupted by user")

        finally:
            self._cleanup()

    def _draw_info(self, frame: np.ndarray, command: np.ndarray):
        """Draw information overlay on frame"""
        y_offset = 30

        # Mode info
        mode_text = f"Mode: {self.current_mode.value}"
        if self.blend_progress < 1.0:
            mode_text += f" -> {self.target_mode.value} ({self.blend_progress*100:.0f}%)"

        cv2.putText(frame, mode_text, (10, y_offset),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
        y_offset += 25

        # Auto mode status
        auto_text = f"Auto: {'ON' if self.enable_auto_mode else 'OFF'}"
        cv2.putText(frame, auto_text, (10, y_offset),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 1)
        y_offset += 25

        # Command preview
        cmd_text = f"SDK: [{command[0]}, {command[1]}, {command[2]}, ...]"
        cv2.putText(frame, cmd_text, (10, y_offset),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

    def _cleanup(self):
        """Cleanup resources"""
        self.logger.info("="*70)
        self.logger.info("Cleaning up...")
        self.logger.info("="*70)

        if hasattr(self, 'cap'):
            self.cap.release()
            self.logger.info("✅ Camera released")

        if hasattr(self, 'hands'):
            self.hands.close()
            self.logger.info("✅ MediaPipe closed")

        if hasattr(self, 'driver'):
            self.driver.close()
            self.logger.info("✅ Driver closed")

        cv2.destroyAllWindows()
        self.logger.info("="*70)
        self.logger.info("✅ Cleanup complete")
        self.logger.info("="*70)


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='LinkerHand L10 Hybrid Teleoperation System',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_hand_hybrid.py                    # Mock mode (no hardware)
  python run_hand_hybrid.py --real             # Real hardware
  python run_hand_hybrid.py --real --no-auto   # Manual mode switching only
        """
    )

    parser.add_argument(
        '--real',
        action='store_true',
        help='Use real hardware (default: mock mode)'
    )

    parser.add_argument(
        '--camera',
        type=int,
        default=0,
        help='Camera device ID (default: 0)'
    )

    parser.add_argument(
        '--config',
        type=str,
        default='configs/hand_retargeting_config.yaml',
        help='Path to retargeting config (default: configs/hand_retargeting_config.yaml)'
    )

    parser.add_argument(
        '--no-auto',
        action='store_true',
        help='Disable automatic mode switching'
    )

    args = parser.parse_args()

    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        datefmt='%H:%M:%S'
    )

    # Resolve config path
    config_path = os.path.join(PROJECT_ROOT, args.config)

    # Create and run system
    try:
        system = HybridTeleoperationSystem(
            retarget_config=config_path,
            camera_id=args.camera,
            mock_mode=not args.real,
            enable_auto_mode=not args.no_auto
        )

        system.run()

    except Exception as e:
        logging.error(f"Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
