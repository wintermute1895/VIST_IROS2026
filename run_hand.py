#!/usr/bin/env python3
"""
============================================================================
Linker Hand L10 Teleoperation Main Loop
============================================================================
Purpose: Vision-based teleoperation for Linker Hand L10
Architecture: Camera → MediaPipe → Retargeting → Dict-to-List → SDK

CRITICAL: SDK requires exactly 10 float values (converted to int internally)
          Values must be in degrees or pulse values (NOT radians)
============================================================================
"""

import sys
import os
import time
import yaml
import numpy as np
import cv2
import logging
from typing import Dict, List

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

# Import our modules
from src.hand_driver import LinkerHandDriver
from src.hand_retargeting import HandRetargeting


class HandTeleoperationSystem:
    """
    Complete teleoperation system for Linker Hand L10

    Pipeline:
    1. Capture video from camera
    2. Detect hand with MediaPipe
    3. Compute joint angles with retargeting (output: dict in radians)
    4. Convert dict to 10-element list with scaling (radians → degrees)
    5. Send to hardware via SDK
    """

    def __init__(self,
                 retarget_config: str,
                 hardware_config: str,
                 camera_id: int = 0):
        """
        Initialize the teleoperation system

        Args:
            retarget_config: Path to retargeting config YAML
            hardware_config: Path to hardware config YAML
            camera_id: Camera device ID
        """
        self.logger = logging.getLogger(__name__)

        # Load hardware configuration
        self._load_hardware_config(hardware_config)

        # Initialize components
        self.logger.info("="*60)
        self.logger.info("Initializing Teleoperation System")
        self.logger.info("="*60)

        # 1. Initialize camera
        self._init_camera(camera_id)

        # 2. Initialize MediaPipe
        self._init_mediapipe()

        # 3. Initialize retargeting
        self.retargeting = HandRetargeting(retarget_config)

        # 4. Initialize hardware driver
        hand_config = self.hw_config['hand']
        self.driver = LinkerHandDriver(
            can_id=0x27,  # LinkerHand L10 default CAN ID
            can_channel=hand_config['can_interface']
        )

        # Control parameters (use defaults if not specified)
        self.control_freq = 30  # Hz
        self.filter_enabled = True
        self.filter_alpha = 0.3
        self.prev_command = None  # For low-pass filtering

        self.logger.info("="*60)
        self.logger.info("✅ System initialized successfully")
        self.logger.info("="*60)

    def _load_hardware_config(self, config_path: str):
        """Load hardware configuration"""
        with open(config_path, 'r') as f:
            self.hw_config = yaml.safe_load(f)

        # Extract configuration from new format
        hand_config = self.hw_config['hand']
        self.scaling_factor = hand_config['scaling_factor']

        # Convert mapping format: {joint_name: [sdk_index, sign, offset]}
        # to: {joint_name: {'sdk_index': int, 'sign': float, 'offset': float}}
        self.active_joints = {}
        for joint_name, params in hand_config['mapping'].items():
            self.active_joints[joint_name] = {
                'sdk_index': int(params[0]),
                'sign': float(params[1]),
                'offset': float(params[2])
            }

        # Passive indices are 6-9 (always set to 0)
        self.passive_indices = [6, 7, 8, 9]

        self.logger.info(f"✅ Loaded hardware config")
        self.logger.info(f"  Scaling factor: {self.scaling_factor}")
        self.logger.info(f"  Active joints: {len(self.active_joints)}")

    def _init_camera(self, camera_id: int):
        """Initialize camera"""
        self.logger.info(f"Initializing camera (ID: {camera_id})...")

        self.cap = cv2.VideoCapture(camera_id)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        self.cap.set(cv2.CAP_PROP_FPS, 30)

        if not self.cap.isOpened():
            raise RuntimeError(f"Failed to open camera {camera_id}")

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

        except ImportError:
            self.logger.error("❌ MediaPipe not installed")
            self.logger.error("Install with: pip install mediapipe")
            raise

    def dict_to_list(self, joint_dict: Dict[str, float]) -> List[float]:
        """
        Convert joint angle dictionary to 10-element SDK command list

        This is the CRITICAL function that bridges retargeting and hardware.

        Process:
        1. Initialize 10-element list with zeros
        2. For each active joint in config:
           a. Get angle from dict (in radians)
           b. Apply sign correction
           c. Apply offset correction
           d. Convert to degrees (multiply by scaling_factor)
           e. Clip to limits
           f. Place in correct SDK index
        3. Passive indices (6-9) remain zero

        Args:
            joint_dict: Dictionary from retargeting (angles in radians)
                       Example: {'thumb_joint_pitch': 0.5, ...}

        Returns:
            List of 10 float values (in degrees) ready for SDK
            Example: [28.65, 17.19, 57.3, 57.3, 57.3, 57.3, 0.0, 0.0, 0.0, 0.0]
        """
        # Initialize 10-element command array
        cmd = [0.0] * 10

        # Process each active joint
        for joint_name, joint_config in self.active_joints.items():
            # Step 1: Get angle from dictionary (radians)
            angle_rad = joint_dict.get(joint_name, 0.0)

            # Step 2: Apply sign correction
            sign = joint_config['sign']
            angle_rad = angle_rad * sign

            # Step 3: Apply offset correction (in radians)
            offset = joint_config['offset']
            angle_rad = angle_rad + offset

            # Step 4: Convert to degrees (CRITICAL for SDK!)
            angle_deg = angle_rad * self.scaling_factor

            # Step 5: Clip to safety limits (in degrees)
            safety = self.hw_config['hand']['safety']
            angle_deg = np.clip(angle_deg, safety['min_limit'], safety['max_limit'])

            # Step 6: Place in correct SDK index
            sdk_index = joint_config['sdk_index']
            cmd[sdk_index] = float(angle_deg)

        # Passive indices (6-9) are already zero
        # No need to explicitly set them

        return cmd

    def apply_filter(self, current_cmd: List[float]) -> List[float]:
        """
        Apply low-pass filter for smooth motion

        Args:
            current_cmd: Current command (10 elements)

        Returns:
            Filtered command (10 elements)
        """
        if self.prev_command is None:
            self.prev_command = current_cmd
            return current_cmd

        # Low-pass filter: y[n] = α*x[n] + (1-α)*y[n-1]
        filtered = []
        for curr, prev in zip(current_cmd, self.prev_command):
            filtered_val = self.filter_alpha * curr + (1 - self.filter_alpha) * prev
            filtered.append(filtered_val)

        self.prev_command = filtered
        return filtered

    def run(self):
        """
        Main control loop

        This runs continuously:
        1. Capture frame
        2. Detect hand with MediaPipe
        3. Compute joint angles (retargeting → dict in radians)
        4. Convert dict to 10-element list (radians → degrees)
        5. Apply filter (optional)
        6. Send to hardware
        7. Display visualization
        """
        self.logger.info("\n" + "="*60)
        self.logger.info("Starting Teleoperation Loop")
        self.logger.info("Press 'q' to quit, 'r' to reset hand")
        self.logger.info("="*60 + "\n")

        frame_count = 0
        detection_count = 0
        start_time = time.time()

        try:
            while True:
                loop_start = time.time()

                # ============================================================
                # Step 1: Capture frame
                # ============================================================
                ret, frame = self.cap.read()
                if not ret:
                    self.logger.error("Failed to read frame")
                    break

                # Flip for mirror effect
                frame = cv2.flip(frame, 1)
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

                # ============================================================
                # Step 2: Detect hand with MediaPipe
                # ============================================================
                results = self.hands.process(frame_rgb)

                if results.multi_hand_landmarks:
                    for hand_landmarks in results.multi_hand_landmarks:
                        # Extract landmarks as numpy array
                        landmarks = np.array([
                            [lm.x, lm.y, lm.z]
                            for lm in hand_landmarks.landmark
                        ])

                        # ================================================
                        # Step 3: Compute joint angles (retargeting)
                        # Output: dict with angles in RADIANS
                        # ================================================
                        joint_dict = self.retargeting.process(landmarks)

                        # ================================================
                        # Step 4: Convert dict to 10-element list
                        # CRITICAL: Convert radians to degrees!
                        # ================================================
                        cmd = self.dict_to_list(joint_dict)

                        # ================================================
                        # Step 5: Apply smoothing filter (optional)
                        # ================================================
                        if self.filter_enabled:
                            cmd = self.apply_filter(cmd)

                        # ================================================
                        # Step 6: Send to hardware
                        # ================================================
                        success = self.driver.move(cmd)

                        if success:
                            detection_count += 1

                        # Draw landmarks on frame
                        self.mp_drawing.draw_landmarks(
                            frame,
                            hand_landmarks,
                            self.mp_hands.HAND_CONNECTIONS
                        )

                        # Display command values on frame
                        y_offset = 30
                        cv2.putText(frame, "SDK Command (degrees):", (10, y_offset),
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
                        for i, val in enumerate(cmd[:6]):  # Show first 6 (active joints)
                            text = f"[{i}]: {val:5.1f}"
                            cv2.putText(frame, text, (10, y_offset + 20 + i*20),
                                       cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 0), 1)

                # ============================================================
                # Display frame
                # ============================================================
                frame_count += 1
                fps = frame_count / (time.time() - start_time)

                # Status text
                status = f"FPS: {fps:.1f} | Frames: {frame_count} | Detected: {detection_count}"
                cv2.putText(frame, status, (10, frame.shape[0] - 10),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

                if results.multi_hand_landmarks:
                    cv2.putText(frame, "HAND DETECTED", (10, 20),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                else:
                    cv2.putText(frame, "NO HAND", (10, 20),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

                cv2.imshow('Linker Hand L10 Teleoperation', frame)

                # ============================================================
                # Handle keyboard input
                # ============================================================
                key = cv2.waitKey(1) & 0xFF
                if key == ord('q'):
                    self.logger.info("Quit requested by user")
                    break
                elif key == ord('r'):
                    self.logger.info("Resetting hand to zero position")
                    self.driver.reset()
                    self.prev_command = None  # Reset filter

                # ============================================================
                # Control loop timing
                # ============================================================
                loop_time = time.time() - loop_start
                target_time = 1.0 / self.control_freq
                if loop_time < target_time:
                    time.sleep(target_time - loop_time)

        except KeyboardInterrupt:
            self.logger.info("\n⚠️  Interrupted by user (Ctrl+C)")

        except Exception as e:
            self.logger.error(f"\n❌ Error in main loop: {e}")
            import traceback
            traceback.print_exc()

        finally:
            self._cleanup()

    def _cleanup(self):
        """
        Safe cleanup and shutdown

        CRITICAL: Reset hand to safe position and close CAN bus
        """
        self.logger.info("\n" + "="*60)
        self.logger.info("Shutting down system...")
        self.logger.info("="*60)

        # Reset hand to safe position
        self.logger.info("Resetting hand to zero position...")
        try:
            self.driver.reset()
            time.sleep(0.5)
        except:
            pass

        # Close driver (releases CAN bus)
        self.logger.info("Closing hardware driver...")
        try:
            self.driver.close()
        except:
            pass

        # Release camera
        self.logger.info("Releasing camera...")
        if hasattr(self, 'cap'):
            self.cap.release()

        # Close MediaPipe
        if hasattr(self, 'hands'):
            self.hands.close()

        # Close windows
        cv2.destroyAllWindows()

        self.logger.info("="*60)
        self.logger.info("✅ Shutdown complete")
        self.logger.info("="*60)


# ============================================================================
# Main Entry Point
# ============================================================================

def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(
        description='Linker Hand L10 Teleoperation System'
    )
    parser.add_argument(
        '--retarget-config',
        type=str,
        default='configs/hand_retargeting_config.yaml',
        help='Path to retargeting config'
    )
    parser.add_argument(
        '--hardware-config',
        type=str,
        default='configs/hand_config.yaml',
        help='Path to hardware config'
    )
    parser.add_argument(
        '--camera',
        type=int,
        default=0,
        help='Camera device ID'
    )
    parser.add_argument(
        '--log-level',
        type=str,
        default='INFO',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        help='Logging level'
    )

    args = parser.parse_args()

    # Setup logging
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format='%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%H:%M:%S'
    )

    # Print banner
    print("\n" + "="*60)
    print("  Linker Hand L10 Teleoperation System")
    print("  Vision-based Real-time Control")
    print("="*60)
    print(f"Retargeting Config: {args.retarget_config}")
    print(f"Hardware Config:    {args.hardware_config}")
    print(f"Camera ID:          {args.camera}")
    print("="*60 + "\n")

    try:
        # Initialize and run system
        system = HandTeleoperationSystem(
            retarget_config=args.retarget_config,
            hardware_config=args.hardware_config,
            camera_id=args.camera
        )

        system.run()

    except Exception as e:
        logging.error(f"\n❌ System failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
