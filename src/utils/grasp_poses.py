#!/usr/bin/env python3
"""
============================================================================
Hardcoded Grasp Poses for LinkerHand L10
============================================================================
Purpose: Define and manage pre-programmed grasp poses for specific tasks

SDK Value Convention:
- Range: 0-255
- 0 = Fully bent (蜷缩)
- 255 = Fully straight (伸直)

Joint Order (10 elements):
  [0] thumb_cmc_pitch    - 拇指根部弯曲
  [1] thumb_cmc_yaw      - 拇指旋转
  [2] index_mcp_pitch    - 食指根部弯曲
  [3] middle_mcp_pitch   - 中指根部弯曲
  [4] ring_mcp_pitch     - 无名指根部弯曲
  [5] pinky_mcp_pitch    - 小指根部弯曲
  [6] index_mcp_roll     - 食指侧摆
  [7] ring_mcp_roll      - 无名指侧摆
  [8] pinky_mcp_roll     - 小指侧摆
  [9] thumb_cmc_roll     - 拇指侧摆
============================================================================
"""

import numpy as np
from typing import Dict
import logging


class GraspPoseManager:
    """
    Manage hardcoded grasp poses for specific tasks
    """

    def __init__(self):
        """Initialize grasp pose manager"""
        self.logger = logging.getLogger(__name__)

        # Define all grasp poses
        self.poses = self._define_poses()

        self.logger.info(f"Initialized GraspPoseManager with {len(self.poses)} poses")

    def _define_poses(self) -> Dict[str, np.ndarray]:
        """
        Define all hardcoded grasp poses

        Returns:
            Dictionary mapping pose names to SDK values (0-255)
        """
        poses = {}

        # ===== FINE PINCH =====
        # Precise pinch between thumb and index finger
        # Used for: picking small objects, fine manipulation
        poses['fine_pinch'] = np.array([
            80,   # thumb_cmc_pitch - moderately bent for opposition
            200,  # thumb_cmc_yaw - rotated toward index
            180,  # index_mcp_pitch - slightly bent for pinch
            255,  # middle_mcp_pitch - fully straight (not involved)
            255,  # ring_mcp_pitch - fully straight (not involved)
            255,  # pinky_mcp_pitch - fully straight (not involved)
            40,   # index_mcp_roll - slight inward for pinch
            0,    # ring_mcp_roll - neutral
            0,    # pinky_mcp_roll - neutral
            120,  # thumb_cmc_roll - positioned for pinch opposition
        ], dtype=int)

        # ===== POWER GRASP =====
        # All fingers curled for power grip
        # Used for: holding cylindrical objects, power grip
        poses['power_grasp'] = np.array([
            100,  # thumb_cmc_pitch - bent to wrap around object
            150,  # thumb_cmc_yaw - rotated for opposition
            80,   # index_mcp_pitch - curled
            80,   # middle_mcp_pitch - curled
            80,   # ring_mcp_pitch - curled
            80,   # pinky_mcp_pitch - curled
            30,   # index_mcp_roll - slight inward
            30,   # ring_mcp_roll - slight inward
            30,   # pinky_mcp_roll - slight inward
            100,  # thumb_cmc_roll - wrapped position
        ], dtype=int)

        # ===== OPEN HAND =====
        # All fingers fully extended
        # Used for: releasing objects, reset position
        poses['open_hand'] = np.array([
            255,  # thumb_cmc_pitch - fully straight
            255,  # thumb_cmc_yaw - neutral
            255,  # index_mcp_pitch - fully straight
            255,  # middle_mcp_pitch - fully straight
            255,  # ring_mcp_pitch - fully straight
            255,  # pinky_mcp_pitch - fully straight
            0,    # index_mcp_roll - neutral
            0,    # ring_mcp_roll - neutral
            0,    # pinky_mcp_roll - neutral
            0,    # thumb_cmc_roll - neutral
        ], dtype=int)

        # ===== TRIPOD PINCH =====
        # Pinch with thumb, index, and middle finger
        # Used for: precision grip, writing grip
        poses['tripod_pinch'] = np.array([
            80,   # thumb_cmc_pitch - bent for opposition
            200,  # thumb_cmc_yaw - rotated toward fingers
            180,  # index_mcp_pitch - slightly bent
            180,  # middle_mcp_pitch - slightly bent
            255,  # ring_mcp_pitch - straight (not involved)
            255,  # pinky_mcp_pitch - straight (not involved)
            40,   # index_mcp_roll - slight inward
            0,    # ring_mcp_roll - neutral
            0,    # pinky_mcp_roll - neutral
            120,  # thumb_cmc_roll - opposition position
        ], dtype=int)

        # ===== POINTING =====
        # Index finger extended, others curled
        # Used for: pointing, pressing buttons
        poses['pointing'] = np.array([
            100,  # thumb_cmc_pitch - bent
            150,  # thumb_cmc_yaw - neutral
            255,  # index_mcp_pitch - fully straight (pointing)
            80,   # middle_mcp_pitch - curled
            80,   # ring_mcp_pitch - curled
            80,   # pinky_mcp_pitch - curled
            0,    # index_mcp_roll - neutral
            30,   # ring_mcp_roll - slight inward
            30,   # pinky_mcp_roll - slight inward
            80,   # thumb_cmc_roll - neutral
        ], dtype=int)

        return poses

    def get_pose(self, pose_name: str) -> np.ndarray:
        """
        Get a specific grasp pose

        Args:
            pose_name: Name of the pose

        Returns:
            SDK values (0-255) for the pose

        Raises:
            KeyError: If pose name not found
        """
        if pose_name not in self.poses:
            available = ', '.join(self.poses.keys())
            raise KeyError(
                f"Pose '{pose_name}' not found. "
                f"Available poses: {available}"
            )

        return self.poses[pose_name].copy()

    def blend_poses(self,
                    pose_a: np.ndarray,
                    pose_b: np.ndarray,
                    blend_factor: float) -> np.ndarray:
        """
        Blend between two poses

        Args:
            pose_a: First pose (SDK values)
            pose_b: Second pose (SDK values)
            blend_factor: Blend factor (0.0 = pose_a, 1.0 = pose_b)

        Returns:
            Blended pose (SDK values)
        """
        blend_factor = np.clip(blend_factor, 0.0, 1.0)
        blended = pose_a * (1.0 - blend_factor) + pose_b * blend_factor
        return np.clip(blended, 0, 255).astype(int)

    def list_poses(self) -> list:
        """
        List all available pose names

        Returns:
            List of pose names
        """
        return list(self.poses.keys())

    def add_custom_pose(self, name: str, sdk_values: np.ndarray):
        """
        Add a custom pose

        Args:
            name: Name for the custom pose
            sdk_values: SDK values (0-255) for the pose

        Raises:
            ValueError: If sdk_values has wrong shape or invalid values
        """
        if sdk_values.shape != (10,):
            raise ValueError(f"Expected shape (10,), got {sdk_values.shape}")

        if not np.all((sdk_values >= 0) & (sdk_values <= 255)):
            raise ValueError("SDK values must be in range [0, 255]")

        self.poses[name] = sdk_values.astype(int)
        self.logger.info(f"Added custom pose: {name}")
