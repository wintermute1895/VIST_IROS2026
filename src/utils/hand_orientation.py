#!/usr/bin/env python3
"""
手部朝向检测工具
"""
import numpy as np


def check_palm_orientation(landmarks):
    """
    检查手心是否朝向摄像头

    Args:
        landmarks: MediaPipe hand landmarks, shape (21, 3)

    Returns:
        tuple: (facing_camera: bool, confidence: float, orientation: str)
    """
    wrist = landmarks[0]
    index_mcp = landmarks[5]
    pinky_mcp = landmarks[17]

    # 计算手掌平面的法向量
    v1 = index_mcp - wrist
    v2 = pinky_mcp - wrist
    normal = np.cross(v1, v2)
    normal_norm = np.linalg.norm(normal)

    if normal_norm < 1e-6:
        return False, 0.0, "unknown"

    normal = normal / normal_norm

    # z分量表示朝向
    # z < 0: 手心朝向摄像头
    # z > 0: 手背朝向摄像头
    z_component = normal[2]

    if z_component < -0.15:
        orientation = "palm"
        facing_camera = True
        confidence = min(abs(z_component), 1.0)
    elif z_component > 0.15:
        orientation = "back"
        facing_camera = False
        confidence = min(abs(z_component), 1.0)
    else:
        orientation = "side"
        facing_camera = False
        confidence = 0.5

    return facing_camera, confidence, orientation


def get_hand_quality_score(landmarks):
    """
    评估手部检测质量

    Args:
        landmarks: MediaPipe hand landmarks, shape (21, 3)

    Returns:
        tuple: (score: float, quality: str, issues: list)
    """
    issues = []
    score = 1.0

    # 检查1：手心朝向
    facing_camera, confidence, orientation = check_palm_orientation(landmarks)
    if not facing_camera:
        score *= 0.3
        issues.append(f"Hand {orientation} facing camera (should be palm)")

    # 检查2：手指是否展开
    fingertips = landmarks[[4, 8, 12, 16, 20]]
    wrist = landmarks[0]
    distances = np.linalg.norm(fingertips - wrist, axis=1)

    # 如果所有手指都很近（握拳），质量下降
    if distances.mean() < 0.15:
        score *= 0.7
        issues.append("Fingers too close (try opening hand)")

    # 检查3：手指间距
    finger_spread = np.std(fingertips[:, 0])  # x方向的标准差
    if finger_spread < 0.02:
        score *= 0.8
        issues.append("Fingers too close together")

    # 检查4：深度变化
    z_range = fingertips[:, 2].max() - fingertips[:, 2].min()
    if z_range > 0.15:
        score *= 0.6
        issues.append("Hand too tilted (keep hand flat)")

    # 确定质量等级
    if score >= 0.8:
        quality = "Excellent"
    elif score >= 0.6:
        quality = "Good"
    elif score >= 0.4:
        quality = "Fair"
    else:
        quality = "Poor"

    return score, quality, issues


def get_orientation_hint(orientation):
    """
    根据朝向给出提示

    Args:
        orientation: "palm", "back", or "side"

    Returns:
        str: 提示信息
    """
    hints = {
        "palm": "✓ Perfect! Palm facing camera",
        "back": "✗ Turn hand over (show palm)",
        "side": "✗ Rotate hand to face camera",
        "unknown": "? Cannot detect hand orientation"
    }
    return hints.get(orientation, "? Unknown orientation")
