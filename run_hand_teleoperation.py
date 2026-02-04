#!/usr/bin/env python3
"""
============================================================================
LinkerHand L10 Teleoperation - Main Script
============================================================================
Purpose: Vision-based teleoperation for LinkerHand L10
Pipeline: Camera → MediaPipe → Dex-Retargeting → LinkerHand SDK

Key Features:
- Simplified architecture with no index remapping
- Robust error handling throughout pipeline
- Low-pass filtering for smooth motion
- Safety limits and validation
- Mock mode for testing without hardware

Usage:
    python run_hand_teleoperation.py                    # Mock mode
    python run_hand_teleoperation.py --real             # Real hardware
    python run_hand_teleoperation.py --real --debug     # With debug logging
============================================================================
"""

import sys
import os
import time
import argparse
import logging
import numpy as np
import cv2
from typing import Optional

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

# Import our modules
from src.core.linker_hand_retargeter import LinkerHandRetargeter
from src.hand_driver import LinkerHandDriver


class HandTeleoperationSystem:
    """
    Complete teleoperation system for LinkerHand L10

    Pipeline:
      1. Capture video from camera
      2. Detect hand with MediaPipe (21 landmarks)
      3. Compute joint angles with retargeting (10 values in radians)
      4. Convert radians to degrees and apply safety limits
      5. Send to hardware via SDK
    """

    # Constants
    CONTROL_FREQ = 30  # Hz
    FILTER_ALPHA = 0.3  # Low-pass filter coefficient

    # SDK uses 0-255 range: 0=bent(蜷缩), 255=straight(伸直)
    SDK_MIN = 0    # Fully bent
    SDK_MAX = 255  # Fully straight

    # Joint limits from URDF (exact values from robot.urdf)
    # These are the maximum bending angles for each joint
    JOINT_LIMITS = np.array([
        0.5146,   # thumb_cmc_pitch: 0 to 0.5146 rad
        1.9189,   # thumb_cmc_yaw: 0 to 1.9189 rad
        1.3607,   # index_mcp_pitch: 0 to 1.3607 rad (修正！)
        1.3607,   # middle_mcp_pitch: 0 to 1.3607 rad (修正！)
        1.3607,   # ring_mcp_pitch: 0 to 1.3607 rad (修正！)
        1.3607,   # pinky_mcp_pitch: 0 to 1.3607 rad (修正！)
        0.2181,   # index_mcp_roll: 0 to 0.2181 rad (修正！)
        0.2181,   # ring_mcp_roll: 0 to 0.2181 rad (修正！)
        0.3489,   # pinky_mcp_roll: 0 to 0.3489 rad (修正！)
        1.1339,   # thumb_cmc_roll: 0 to 1.1339 rad
    ])

    def __init__(self,
                 retarget_config: str,
                 camera_id: int = 0,
                 mock_mode: bool = False,
                 enable_filter: bool = True):
        """
        Initialize the teleoperation system

        Args:
            retarget_config: Path to retargeting config YAML
            camera_id: Camera device ID
            mock_mode: If True, run without hardware
            enable_filter: If True, enable low-pass filtering
        """
        self.logger = logging.getLogger(__name__)
        self.mock_mode = mock_mode
        self.enable_filter = enable_filter
        self.prev_command = None
        self.frame_count = 0
        self.success_count = 0

        self.logger.info("="*70)
        self.logger.info("Initializing Hand Teleoperation System")
        if mock_mode:
            self.logger.info("(MOCK MODE - No Hardware)")
        self.logger.info("="*70)

        # Initialize components
        self._init_camera(camera_id)
        self._init_mediapipe()
        self._init_retargeting(retarget_config)
        self._init_driver(mock_mode)

        self.logger.info("="*70)
        self.logger.info("✅ System initialized successfully")
        self.logger.info(f"  Control frequency: {self.CONTROL_FREQ} Hz")
        self.logger.info(f"  Low-pass filter: {'Enabled' if enable_filter else 'Disabled'}")
        self.logger.info(f"  SDK value range: [{self.SDK_MIN}, {self.SDK_MAX}] (0=bent, 255=straight)")
        self.logger.info("="*70)

    def _init_camera(self, camera_id: int):
        """Initialize camera"""
        self.logger.info(f"Initializing camera (ID: {camera_id})...")

        self.cap = cv2.VideoCapture(camera_id)
        if not self.cap.isOpened():
            raise RuntimeError(f"Failed to open camera {camera_id}")

        # Set camera properties
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

            # Initialize hand detector
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

    def _init_driver(self, mock_mode: bool):
        """Initialize hardware driver"""
        self.logger.info("Initializing hardware driver...")

        self.driver = LinkerHandDriver(
            can_id=0x27,
            can_channel="can0",
            mock_mode=mock_mode
        )

        self.logger.info("✅ Driver initialized")

    def process_frame(self, frame: np.ndarray) -> Optional[np.ndarray]:
        """
        Process a single frame

        Args:
            frame: BGR image from camera

        Returns:
            Joint commands in SDK format (0-255), or None if processing fails
        """
        # Convert to RGB for MediaPipe
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        # Detect hand
        results = self.hands.process(frame_rgb)

        if not results.multi_hand_landmarks:
            return None

        # Check handedness (left or right)
        # 不做左右手限制，接受任何手
        if results.multi_handedness:
            handedness = results.multi_handedness[0].classification[0].label

        # Get first hand
        hand_landmarks = results.multi_hand_landmarks[0]

        # Convert to numpy array (21, 3)
        landmarks = np.array([
            [lm.x, lm.y, lm.z]
            for lm in hand_landmarks.landmark
        ])

        # Run retargeting (output in radians)
        joint_angles_rad = self.retargeter.process(landmarks)

        if joint_angles_rad is None:
            return None

        # Clip to joint limits
        joint_angles_rad = np.clip(joint_angles_rad, 0, self.JOINT_LIMITS)

        # Normalize to 0-1 range
        normalized = joint_angles_rad / self.JOINT_LIMITS

        # Convert to SDK range
        # 恢复到最开始的版本：pitch反转，roll不反转
        # SDK: 0=bent(蜷缩), 255=straight(伸直)
        sdk_values = np.zeros(10, dtype=int)

        # Pitch关节索引：0,1,2,3,4,5,9（需要反转）
        pitch_indices = [0, 1, 2, 3, 4, 5, 9]
        # Roll关节索引：6,7,8（不反转）
        roll_indices = [6, 7, 8]

        # Pitch关节：反转
        sdk_values[pitch_indices] = (self.SDK_MAX * (1.0 - normalized[pitch_indices])).astype(int)
        # Roll关节：不反转
        sdk_values[roll_indices] = (self.SDK_MAX * normalized[roll_indices]).astype(int)

        # Clip to SDK range
        sdk_values = np.clip(sdk_values, self.SDK_MIN, self.SDK_MAX)

        return sdk_values

    def apply_filter(self, command: np.ndarray) -> np.ndarray:
        """
        Apply low-pass filter for smooth motion

        Args:
            command: Current command (10,)

        Returns:
            Filtered command (10,)
        """
        if not self.enable_filter or self.prev_command is None:
            self.prev_command = command
            return command

        # Low-pass filter: y[n] = α*x[n] + (1-α)*y[n-1]
        filtered = (
            self.FILTER_ALPHA * command +
            (1 - self.FILTER_ALPHA) * self.prev_command
        )

        self.prev_command = filtered
        return filtered

    def run(self):
        """
        Main teleoperation loop

        Press 'q' to quit
        Press 'r' to reset hand
        Press 's' to show statistics
        """
        self.logger.info("="*70)
        self.logger.info("Starting teleoperation loop")
        self.logger.info("  Press 'q' to quit")
        self.logger.info("  Press 'r' to reset hand")
        self.logger.info("  Press 's' to show statistics")
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
                joint_angles = self.process_frame(frame)

                if joint_angles is not None:
                    # Apply filter
                    joint_angles_filtered = self.apply_filter(joint_angles)

                    # Send to hardware
                    success = self.driver.move(joint_angles_filtered.tolist())

                    if success:
                        self.success_count += 1

                    # Display on frame
                    cv2.putText(
                        frame,
                        f"Frame: {self.frame_count} | Success: {self.success_count}",
                        (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.7,
                        (0, 255, 0),
                        2
                    )

                else:
                    # No hand detected
                    cv2.putText(
                        frame,
                        "No hand detected",
                        (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.7,
                        (0, 0, 255),
                        2
                    )

                # Show frame
                cv2.imshow("Hand Teleoperation", frame)

                # Handle keyboard input
                key = cv2.waitKey(1) & 0xFF
                if key == ord('q'):
                    self.logger.info("Quit requested")
                    break
                elif key == ord('r'):
                    self.logger.info("Reset requested")
                    self.driver.reset()
                    self.prev_command = None
                elif key == ord('s'):
                    self._show_statistics()

                # Maintain control frequency
                loop_time = time.time() - loop_start
                sleep_time = (1.0 / self.CONTROL_FREQ) - loop_time
                if sleep_time > 0:
                    time.sleep(sleep_time)

        except KeyboardInterrupt:
            self.logger.info("Interrupted by user")

        finally:
            self._cleanup()

    def _show_statistics(self):
        """Show system statistics"""
        success_rate = (
            100.0 * self.success_count / self.frame_count
            if self.frame_count > 0 else 0.0
        )

        self.logger.info("="*70)
        self.logger.info("System Statistics")
        self.logger.info("="*70)
        self.logger.info(f"  Total frames: {self.frame_count}")
        self.logger.info(f"  Successful commands: {self.success_count}")
        self.logger.info(f"  Success rate: {success_rate:.1f}%")
        self.logger.info(f"  Driver status: {self.driver.get_status()}")
        self.logger.info("="*70)

    def _cleanup(self):
        """Cleanup resources"""
        self.logger.info("="*70)
        self.logger.info("Cleaning up...")
        self.logger.info("="*70)

        # Show final statistics
        self._show_statistics()

        # Release resources
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
        description='LinkerHand L10 Teleoperation System',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_hand_teleoperation.py                    # Mock mode (no hardware)
  python run_hand_teleoperation.py --real             # Real hardware
  python run_hand_teleoperation.py --real --debug     # With debug logging
  python run_hand_teleoperation.py --camera 1         # Use camera 1
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
        '--no-filter',
        action='store_true',
        help='Disable low-pass filtering'
    )

    parser.add_argument(
        '--debug',
        action='store_true',
        help='Enable debug logging'
    )

    args = parser.parse_args()

    # Setup logging
    log_level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        datefmt='%H:%M:%S'
    )

    # Resolve config path
    config_path = os.path.join(PROJECT_ROOT, args.config)

    # Create and run system
    try:
        system = HandTeleoperationSystem(
            retarget_config=config_path,
            camera_id=args.camera,
            mock_mode=not args.real,
            enable_filter=not args.no_filter
        )

        system.run()

    except Exception as e:
        logging.error(f"Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
