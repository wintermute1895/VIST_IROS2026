#!/usr/bin/env python3
"""
坐标变换管理器 (Coordinate Transform Manager)

统一管理VIST系统中的所有坐标系变换，包括：
1. 手眼标定结果（Eye-in-Hand: T_end_to_cam）
2. 眼到手标定结果（Eye-to-Hand: T_base_to_cam）
3. TCP偏移（Tool Center Point: T_tcp_flange）
4. 坐标系变换链的组合

设计原则：
- 单一职责：只负责坐标变换，不涉及视觉检测或控制逻辑
- 解耦：标定结果独立于运行时系统
- 鲁棒：支持标定文件缺失的降级处理

Author: VIST Project
Date: 2026-02-20
"""

import numpy as np
from pathlib import Path
from typing import Optional, Tuple
import warnings


class CoordinateTransformManager:
    """
    坐标变换管理器

    管理VIST系统中的所有坐标系变换矩阵，提供统一的坐标转换接口。

    坐标系定义：
    - Base: 机器人基座坐标系
    - End/Flange: 机械臂末端法兰坐标系
    - TCP: 工具中心点坐标系（USB末端）
    - Cam_Hand: 手内相机坐标系（RealSense D405）
    - Cam_Head: 头顶相机坐标系（RealSense D435i）
    - Target: 目标物体坐标系（插孔、ArUco标记等）
    """

    def __init__(self, config=None, project_root: Optional[Path] = None):
        """
        初始化坐标变换管理器

        Args:
            config: VISTConfig配置对象（可选）
            project_root: 项目根目录（可选，用于定位标定文件）
        """
        self.config = config

        # 确定项目根目录
        if project_root is None:
            project_root = Path(__file__).parent.parent.parent
        self.project_root = Path(project_root)

        # 标定结果矩阵（4x4齐次变换矩阵）
        self.T_end_to_cam_hand = None   # 末端法兰 → 手内相机
        self.T_base_to_cam_head = None  # 基座 → 头顶相机
        self.T_tcp_flange = None        # TCP → 法兰盘

        # 加载标定结果
        self._load_calibrations()

        # 加载TCP偏移
        self._load_tcp_offset()

        print("✅ [CoordinateTransformManager] 初始化完成")
        self._print_status()

    def _load_calibrations(self):
        """加载手眼标定结果"""
        # 1. 加载手内相机标定（Eye-in-Hand）
        hand_calib_file = self.project_root / "calibration" / "calibration_data" / "T_end_to_cam.npy"
        if hand_calib_file.exists():
            self.T_end_to_cam_hand = np.load(str(hand_calib_file))
            print(f"   ✓ 加载手内相机标定: {hand_calib_file}")
        else:
            warnings.warn(f"未找到手内相机标定文件: {hand_calib_file}")

        # 2. 加载头顶相机标定（Eye-to-Hand）
        head_calib_file = self.project_root / "calibration" / "calibration_data_head_camera" / "T_base_to_cam.npy"
        if head_calib_file.exists():
            self.T_base_to_cam_head = np.load(str(head_calib_file))
            print(f"   ✓ 加载头顶相机标定: {head_calib_file}")
        else:
            warnings.warn(f"未找到头顶相机标定文件: {head_calib_file}")

    def _load_tcp_offset(self):
        """加载TCP偏移配置"""
        if self.config is not None and hasattr(self.config, 'tcp_offset'):
            # 从配置文件读取TCP偏移
            offset = self.config.tcp_offset
            self.T_tcp_flange = self._build_transform_matrix(
                translation=offset[:3],
                rotation=offset[3:] if len(offset) > 3 else [0, 0, 0]
            )
            print(f"   ✓ 加载TCP偏移: {offset[:3]} (平移)")
        else:
            # 默认TCP偏移（假设USB沿Z轴延伸15cm）
            self.T_tcp_flange = np.eye(4)
            self.T_tcp_flange[2, 3] = 0.15  # Z轴偏移15cm
            warnings.warn("未配置TCP偏移，使用默认值: [0, 0, 0.15]")

    def _build_transform_matrix(self, translation, rotation, rotation_type='euler_xyz'):
        """
        构建4x4齐次变换矩阵

        Args:
            translation: 平移向量 [x, y, z]
            rotation: 旋转（欧拉角或旋转向量）
            rotation_type: 旋转表示类型

        Returns:
            4x4齐次变换矩阵
        """
        from scipy.spatial.transform import Rotation as R

        T = np.eye(4)
        T[:3, 3] = translation

        if rotation_type == 'euler_xyz':
            T[:3, :3] = R.from_euler('xyz', rotation).as_matrix()
        elif rotation_type == 'rotvec':
            T[:3, :3] = R.from_rotvec(rotation).as_matrix()

        return T

    def _print_status(self):
        """打印标定状态"""
        print("   标定状态:")
        print(f"     - 手内相机: {'✓' if self.T_end_to_cam_hand is not None else '✗'}")
        print(f"     - 头顶相机: {'✓' if self.T_base_to_cam_head is not None else '✗'}")
        print(f"     - TCP偏移: {'✓' if self.T_tcp_flange is not None else '✗'}")

    # ==========================================
    # 核心坐标变换接口
    # ==========================================

    def hand_camera_to_base(self, point_cam: np.ndarray, T_base_to_end: np.ndarray) -> np.ndarray:
        """
        将手内相机坐标系下的点转换到基座坐标系

        变换链: Cam_Hand → End → Base

        Args:
            point_cam: 点在手内相机坐标系下的坐标 [x, y, z]
            T_base_to_end: 当前机器人位姿（基座→末端，4x4矩阵）

        Returns:
            点在基座坐标系下的坐标 [x, y, z]
        """
        if self.T_end_to_cam_hand is None:
            raise ValueError("手内相机未标定，无法进行坐标变换")

        # 转换为齐次坐标
        point_homo = np.append(point_cam, 1.0)

        # 相机 → 末端 → 基座
        T_cam_to_end = np.linalg.inv(self.T_end_to_cam_hand)
        point_base_homo = T_base_to_end @ T_cam_to_end @ point_homo

        return point_base_homo[:3]

    def head_camera_to_base(self, point_cam: np.ndarray) -> np.ndarray:
        """
        将头顶相机坐标系下的点转换到基座坐标系

        变换链: Cam_Head → Base（直接变换，相机固定）

        Args:
            point_cam: 点在头顶相机坐标系下的坐标 [x, y, z]

        Returns:
            点在基座坐标系下的坐标 [x, y, z]
        """
        if self.T_base_to_cam_head is None:
            raise ValueError("头顶相机未标定，无法进行坐标变换")

        # 转换为齐次坐标
        point_homo = np.append(point_cam, 1.0)

        # 相机 → 基座
        T_cam_to_base = np.linalg.inv(self.T_base_to_cam_head)
        point_base_homo = T_cam_to_base @ point_homo

        return point_base_homo[:3]

    def get_tcp_pose_in_base(self, T_base_to_end: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        获取TCP在基座坐标系下的位姿

        变换链: TCP → Flange → Base

        Args:
            T_base_to_end: 当前机器人位姿（基座→末端，4x4矩阵）

        Returns:
            (position, orientation): TCP位置和姿态
                - position: [x, y, z]
                - orientation: 四元数 [x, y, z, w]
        """
        from scipy.spatial.transform import Rotation as R

        # TCP → 基座
        T_base_to_tcp = T_base_to_end @ self.T_tcp_flange

        # 提取位置和姿态
        position = T_base_to_tcp[:3, 3]
        orientation = R.from_matrix(T_base_to_tcp[:3, :3]).as_quat()

        return position, orientation

    def fuse_dual_camera_observations(
        self,
        point_hand_cam: Optional[np.ndarray],
        point_head_cam: Optional[np.ndarray],
        T_base_to_end: np.ndarray,
        confidence_hand: float = 1.0,
        confidence_head: float = 1.0
    ) -> Optional[np.ndarray]:
        """
        融合双相机观测（加权平均）

        Args:
            point_hand_cam: 手内相机观测 [x, y, z]（可选）
            point_head_cam: 头顶相机观测 [x, y, z]（可选）
            T_base_to_end: 当前机器人位姿
            confidence_hand: 手内相机置信度 [0, 1]
            confidence_head: 头顶相机置信度 [0, 1]

        Returns:
            融合后的目标位置（基座坐标系）[x, y, z]，如果两个观测都无效则返回None
        """
        observations = []
        weights = []

        # 手内相机观测
        if point_hand_cam is not None and self.T_end_to_cam_hand is not None:
            point_base_hand = self.hand_camera_to_base(point_hand_cam, T_base_to_end)
            observations.append(point_base_hand)
            weights.append(confidence_hand)

        # 头顶相机观测
        if point_head_cam is not None and self.T_base_to_cam_head is not None:
            point_base_head = self.head_camera_to_base(point_head_cam)
            observations.append(point_base_head)
            weights.append(confidence_head)

        # 加权融合
        if len(observations) == 0:
            return None
        elif len(observations) == 1:
            return observations[0]
        else:
            weights = np.array(weights)
            weights /= weights.sum()  # 归一化
            fused_point = sum(w * obs for w, obs in zip(weights, observations))
            return fused_point

    # ==========================================
    # 工具函数
    # ==========================================

    def is_hand_camera_calibrated(self) -> bool:
        """检查手内相机是否已标定"""
        return self.T_end_to_cam_hand is not None

    def is_head_camera_calibrated(self) -> bool:
        """检查头顶相机是否已标定"""
        return self.T_base_to_cam_head is not None

    def get_calibration_info(self) -> dict:
        """获取标定信息（用于调试和日志）"""
        return {
            'hand_camera_calibrated': self.is_hand_camera_calibrated(),
            'head_camera_calibrated': self.is_head_camera_calibrated(),
            'tcp_offset_configured': self.T_tcp_flange is not None,
            'T_end_to_cam_hand': self.T_end_to_cam_hand.tolist() if self.T_end_to_cam_hand is not None else None,
            'T_base_to_cam_head': self.T_base_to_cam_head.tolist() if self.T_base_to_cam_head is not None else None,
            'T_tcp_flange': self.T_tcp_flange.tolist() if self.T_tcp_flange is not None else None,
        }