#!/usr/bin/env python3
"""
============================================================================
Gesture Detector for LinkerHand L10
============================================================================
Purpose: Detect specific hand gestures from MediaPipe landmarks
         for triggering hardcoded grasp poses

Supported gestures:
- Fine pinch: Thumb and index fingertip close together
- Power grasp: All fingers curled
- Open hand: All fingers extended
============================================================================
"""

import numpy as np
from typing import Tuple, Optional
import logging


class GestureDetector:
    """
    Detect hand gestures from MediaPipe landmarks
    """

    # MediaPipe landmark indices
    WRIST = 0
    THUMB_TIP = 4
    INDEX_TIP = 8
    MIDDLE_TIP = 12
    RING_TIP = 16
    PINKY_TIP = 20

    THUMB_MCP = 2
    INDEX_MCP = 5
    MIDDLE_MCP = 9
    RING_MCP = 13
    PINKY_MCP = 17

    def __init__(self,
                 pinch_threshold: float = 0.05,
                 curl_threshold: float = 0.7):
        """
        Initialize gesture detector

        Args:
            pinch_threshold: Distance threshold for pinch detection (normalized)
            curl_threshold: Ratio threshold for curl detection
        """
        self.logger = logging.getLogger(__name__)
        self.pinch_threshold = pinch_threshold
        self.curl_threshold = curl_threshold

    def detect_pinch(self, landmarks: np.ndarray) -> Tuple[bool, float]:
        """
        Detect fine pinch gesture (thumb + index fingertip)

        Args:
            landmarks: MediaPipe hand landmarks, shape (21, 3)

        Returns:
            (is_pinching, pinch_distance)
        """
        thumb_tip = landmarks[self.THUMB_TIP]
        index_tip = landmarks[self.INDEX_TIP]

        # Calculate 3D Euclidean distance
        distance = np.linalg.norm(thumb_tip - index_tip)

        is_pinching = distance < self.pinch_threshold

        return is_pinching, distance

    def detect_curl(self, landmarks: np.ndarray, finger_tip_idx: int, finger_mcp_idx: int) -> float:
        """
        Detect finger curl by comparing tip-to-wrist vs mcp-to-wrist distance

        Args:
            landmarks: MediaPipe hand landmarks, shape (21, 3)
            finger_tip_idx: Index of fingertip
            finger_mcp_idx: Index of finger MCP joint

        Returns:
            Curl ratio: 0.0 (extended) to 1.0+ (curled)
        """
        wrist = landmarks[self.WRIST]
        tip = landmarks[finger_tip_idx]
        mcp = landmarks[finger_mcp_idx]

        # Distance from wrist to MCP (base length)
        base_dist = np.linalg.norm(mcp - wrist)

        # Distance from wrist to tip
        tip_dist = np.linalg.norm(tip - wrist)

        # Curl ratio: if finger is extended, tip_dist > base_dist
        # if finger is curled, tip_dist < base_dist
        if base_dist < 1e-6:
            return 0.0

        curl_ratio = 1.0 - (tip_dist / base_dist)

        return max(0.0, curl_ratio)

    def detect_power_grasp(self, landmarks: np.ndarray) -> Tuple[bool, float]:
        """
        Detect power grasp (all fingers curled)

        Args:
            landmarks: MediaPipe hand landmarks, shape (21, 3)

        Returns:
            (is_grasping, average_curl)
        """
        # Check curl for all four fingers (excluding thumb)
        finger_pairs = [
            (self.INDEX_TIP, self.INDEX_MCP),
            (self.MIDDLE_TIP, self.MIDDLE_MCP),
            (self.RING_TIP, self.RING_MCP),
            (self.PINKY_TIP, self.PINKY_MCP),
        ]

        curls = [self.detect_curl(landmarks, tip, mcp) for tip, mcp in finger_pairs]
        avg_curl = np.mean(curls)

        is_grasping = avg_curl > self.curl_threshold

        return is_grasping, avg_curl

    def detect_open_hand(self, landmarks: np.ndarray) -> Tuple[bool, float]:
        """
        Detect open hand (all fingers extended)

        Args:
            landmarks: MediaPipe hand landmarks, shape (21, 3)

        Returns:
            (is_open, average_extension)
        """
        # Check extension for all four fingers
        finger_pairs = [
            (self.INDEX_TIP, self.INDEX_MCP),
            (self.MIDDLE_TIP, self.MIDDLE_MCP),
            (self.RING_TIP, self.RING_MCP),
            (self.PINKY_TIP, self.PINKY_MCP),
        ]

        curls = [self.detect_curl(landmarks, tip, mcp) for tip, mcp in finger_pairs]
        avg_extension = 1.0 - np.mean(curls)

        is_open = avg_extension > self.curl_threshold

        return is_open, avg_extension

    def get_gesture_state(self, landmarks: np.ndarray) -> dict:
        """
        Get comprehensive gesture state

        Args:
            landmarks: MediaPipe hand landmarks, shape (21, 3)

        Returns:
            Dictionary with gesture detection results
        """
        is_pinching, pinch_dist = self.detect_pinch(landmarks)
        is_grasping, grasp_strength = self.detect_power_grasp(landmarks)
        is_open, open_strength = self.detect_open_hand(landmarks)

        return {
            'pinch': {
                'active': is_pinching,
                'distance': pinch_dist,
                'strength': max(0.0, 1.0 - pinch_dist / self.pinch_threshold)
            },
            'grasp': {
                'active': is_grasping,
                'strength': grasp_strength
            },
            'open': {
                'active': is_open,
                'strength': open_strength
            }
        }
