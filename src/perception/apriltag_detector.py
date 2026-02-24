#!/usr/bin/env python3
"""
AprilTag 目标检测器
用于检测插孔位置、工作空间标记等目标

功能：
1. AprilTag 检测
2. 3D位姿估计（PnP + 深度融合）
3. 目标管理和优先级选择
"""

import cv2
import numpy as np
import pyrealsense2 as rs
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass


@dataclass
class DetectedTarget:
    """检测到的目标"""
    tag_id: int
    name: str
    position_3d: np.ndarray  # [x, y, z] 在相机坐标系
    rotation: np.ndarray  # 旋转矩阵 3x3
    confidence: float
    priority: int
    timestamp: float


class AprilTagDetector:
    """AprilTag 检测器（带3D位姿估计）"""

    def __init__(self, config: dict):
        """
        初始化AprilTag检测器

        Args:
            config: 配置字典，包含 apriltag 配置
        """
        try:
            import apriltag
            self.apriltag = apriltag
        except ImportError:
            raise ImportError(
                "请安装 apriltag: pip install apriltag\n"
                "或从源码安装: https://github.com/AprilRobotics/apriltag"
            )

        self.config = config
        apriltag_config = config.get('apriltag', {})

        # 创建检测器
        self.detector = apriltag.Detector(
            families=apriltag_config.get('family', 'tag36h11'),
            nthreads=apriltag_config.get('nthreads', 4),
            quad_decimate=apriltag_config.get('quad_decimate', 2.0),
            quad_sigma=apriltag_config.get('quad_sigma', 0.0),
            refine_edges=apriltag_config.get('refine_edges', True),
            decode_sharpening=apriltag_config.get('decode_sharpening', 0.25)
        )

        # 目标标签配置
        self.target_tags = {}
        for tag in apriltag_config.get('target_tags', []):
            self.target_tags[tag['id']] = {
                'name': tag['name'],
                'size': tag['size'],
                'priority': tag.get('priority', 99)
            }

        print(f"✅ [AprilTagDetector] 初始化完成")
        print(f"   家族: {apriltag_config.get('family', 'tag36h11')}")
        print(f"   目标标签: {list(self.target_tags.keys())}")

    def detect(
        self,
        color_frame,
        depth_frame,
        camera_intrinsics
    ) -> Dict[str, DetectedTarget]:
        """
        检测AprilTag并估计3D位姿

        Args:
            color_frame: RealSense彩色帧
            depth_frame: RealSense深度帧
            camera_intrinsics: 相机内参

        Returns:
            {target_name: DetectedTarget} 字典
        """
        # 转换为灰度图
        color_image = np.asanyarray(color_frame.get_data())
        gray = cv2.cvtColor(color_image, cv2.COLOR_BGR2GRAY)

        # 检测AprilTag
        detections = self.detector.detect(gray)

        # 处理检测结果
        targets = {}
        for det in detections:
            tag_id = det.tag_id

            # 检查是否是目标标签
            if tag_id not in self.target_tags:
                continue

            tag_config = self.target_tags[tag_id]

            # 估计3D位姿
            position_3d, rotation = self._estimate_pose(
                det, tag_config['size'], camera_intrinsics, depth_frame
            )

            if position_3d is None:
                continue

            # 创建目标对象
            target = DetectedTarget(
                tag_id=tag_id,
                name=tag_config['name'],
                position_3d=position_3d,
                rotation=rotation,
                confidence=det.decision_margin,
                priority=tag_config['priority'],
                timestamp=time.time()
            )

            targets[tag_config['name']] = target

        return targets

    def _estimate_pose(
        self,
        detection,
        tag_size: float,
        intrinsics,
        depth_frame
    ) -> Tuple[Optional[np.ndarray], Optional[np.ndarray]]:
        """
        估计标签的3D位姿

        Args:
            detection: AprilTag检测结果
            tag_size: 标签尺寸（米）
            intrinsics: 相机内参
            depth_frame: 深度帧

        Returns:
            (position_3d, rotation_matrix) 或 (None, None)
        """
        # 标签角点（3D，标签坐标系）
        half_size = tag_size / 2.0
        object_points = np.array([
            [-half_size, -half_size, 0],
            [ half_size, -half_size, 0],
            [ half_size,  half_size, 0],
            [-half_size,  half_size, 0]
        ], dtype=np.float32)

        # 图像角点（2D）
        image_points = detection.corners.astype(np.float32)

        # 相机内参矩阵
        camera_matrix = np.array([
            [intrinsics.fx, 0, intrinsics.ppx],
            [0, intrinsics.fy, intrinsics.ppy],
            [0, 0, 1]
        ], dtype=np.float32)

        # 畸变系数
        dist_coeffs = np.array(intrinsics.coeffs, dtype=np.float32)

        # PnP求解
        success, rvec, tvec = cv2.solvePnP(
            object_points,
            image_points,
            camera_matrix,
            dist_coeffs,
            flags=cv2.SOLVEPNP_IPPE_SQUARE
        )

        if not success:
            return None, None

        # 深度融合（使用标签中心的深度）
        center_x, center_y = detection.center
        depth = depth_frame.get_distance(int(center_x), int(center_y))

        if depth > 0:
            # 使用深度修正Z坐标
            # 保持X, Y方向，只修正Z
            scale = depth / tvec[2][0]
            tvec = tvec * scale

        # 转换旋转向量为旋转矩阵
        rotation_matrix, _ = cv2.Rodrigues(rvec)

        position_3d = tvec.flatten()

        return position_3d, rotation_matrix

    def visualize_detections(
        self,
        color_image: np.ndarray,
        targets: Dict[str, DetectedTarget]
    ) -> np.ndarray:
        """
        可视化检测结果

        Args:
            color_image: 彩色图像
            targets: 检测到的目标

        Returns:
            标注后的图像
        """
        annotated = color_image.copy()

        for name, target in targets.items():
            # 绘制标签ID和名称
            text = f"{name} (ID:{target.tag_id})"
            pos_text = f"({target.position_3d[0]:.2f}, {target.position_3d[1]:.2f}, {target.position_3d[2]:.2f})"

            # 计算文本位置（标签中心上方）
            # 注意：这里需要从3D投影回2D，简化处理直接用图像中心
            h, w = annotated.shape[:2]
            text_pos = (w // 2, 30 + len(targets) * 40)

            cv2.putText(
                annotated, text, text_pos,
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2
            )
            cv2.putText(
                annotated, pos_text, (text_pos[0], text_pos[1] + 20),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1
            )

        return annotated


class TargetManager:
    """目标管理器（选择和跟踪目标）"""

    def __init__(self, config: dict):
        self.config = config
        self.current_target: Optional[DetectedTarget] = None
        self.target_history: List[DetectedTarget] = []
        self.max_history = 10

    def select_target(
        self,
        detected_targets: Dict[str, DetectedTarget],
        current_position: Optional[np.ndarray] = None
    ) -> Optional[DetectedTarget]:
        """
        选择目标

        Args:
            detected_targets: 检测到的目标
            current_position: 当前位置（用于选择最近目标）

        Returns:
            选中的目标
        """
        if not detected_targets:
            # 没有检测到目标，使用上一次的目标
            return self.current_target

        strategy = self.config.get('target_selection_strategy', 'nearest')

        if strategy == 'highest_priority':
            # 选择优先级最高的
            target = min(detected_targets.values(), key=lambda t: t.priority)

        elif strategy == 'nearest' and current_position is not None:
            # 选择最近的
            target = min(
                detected_targets.values(),
                key=lambda t: np.linalg.norm(t.position_3d - current_position)
            )

        else:
            # 默认选择第一个
            target = next(iter(detected_targets.values()))

        # 更新当前目标
        self.current_target = target

        # 添加到历史
        self.target_history.append(target)
        if len(self.target_history) > self.max_history:
            self.target_history.pop(0)

        return target

    def get_target_position(self) -> Optional[np.ndarray]:
        """获取当前目标位置"""
        if self.current_target is not None:
            return self.current_target.position_3d
        return None


# 导入time模块（之前漏了）
import time

