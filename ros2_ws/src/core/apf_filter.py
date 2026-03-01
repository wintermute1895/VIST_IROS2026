"""
人工势场滤波器核心算法
实现基于虚拟力场的避障与引导控制
"""
from typing import List, Tuple, Optional
import numpy as np


class APFCore:
    """人工势场核心计算类"""

    def __init__(self,
                 attractive_gain: float = 1.0,      # 引力增益
                 repulsive_gain: float = 0.5,       # 斥力增益
                 influence_distance: float = 0.1,   # 斥力影响距离 (m)
                 max_force: float = 10.0):          # 最大合力限制 (N)
        """
        初始化APF参数

        Args:
            attractive_gain: 目标引力系数
            repulsive_gain: 障碍物斥力系数
            influence_distance: 斥力场影响范围
            max_force: 虚拟力的最大值限制
        """
        self.k_att = attractive_gain
        self.k_rep = repulsive_gain
        self.d0 = influence_distance
        self.f_max = max_force

    def compute_attractive_force(self,
                                  current_pos: np.ndarray,
                                  target_pos: np.ndarray) -> np.ndarray:
        """
        计算目标点的引力

        Args:
            current_pos: 当前位置 [x, y, z]
            target_pos: 目标位置 [x, y, z]

        Returns:
            引力向量 [fx, fy, fz]
        """
        # 引力方向：从当前位置指向目标
        direction = target_pos - current_pos
        distance = np.linalg.norm(direction)

        if distance < 1e-6:
            return np.zeros(3)

        # 引力大小与距离成正比
        force_magnitude = self.k_att * distance
        force = force_magnitude * (direction / distance)

        return self._limit_force(force)

    def compute_repulsive_force(self,
                                 current_pos: np.ndarray,
                                 obstacle_positions: List[np.ndarray]) -> np.ndarray:
        """
        计算所有障碍物的斥力合力

        Args:
            current_pos: 当前位置 [x, y, z]
            obstacle_positions: 障碍物位置列表

        Returns:
            斥力合力向量 [fx, fy, fz]
        """
        total_repulsive_force = np.zeros(3)

        for obs_pos in obstacle_positions:
            # 计算到障碍物的距离和方向
            direction = current_pos - obs_pos
            distance = np.linalg.norm(direction)

            # 只有在影响范围内才产生斥力
            if distance < self.d0 and distance > 1e-6:
                # 斥力大小与距离平方成反比
                force_magnitude = self.k_rep * (1.0/distance - 1.0/self.d0) / (distance**2)
                force = force_magnitude * (direction / distance)
                total_repulsive_force += force

        return self._limit_force(total_repulsive_force)

    def compute_total_force(self,
                            current_pos: np.ndarray,
                            target_pos: np.ndarray,
                            obstacle_positions: Optional[List[np.ndarray]] = None) -> np.ndarray:
        """
        计算总的虚拟力（引力 + 斥力）

        Args:
            current_pos: 当前位置
            target_pos: 目标位置
            obstacle_positions: 障碍物位置列表（可选）

        Returns:
            总虚拟力向量
        """
        # 计算引力
        f_attractive = self.compute_attractive_force(current_pos, target_pos)

        # 计算斥力
        f_repulsive = np.zeros(3)
        if obstacle_positions:
            f_repulsive = self.compute_repulsive_force(current_pos, obstacle_positions)

        # 合力
        total_force = f_attractive + f_repulsive

        return self._limit_force(total_force)

    def _limit_force(self, force: np.ndarray) -> np.ndarray:
        """限制力的大小"""
        magnitude = np.linalg.norm(force)
        if magnitude > self.f_max:
            return force * (self.f_max / magnitude)
        return force

    def apply_force_to_pose(self,
                            current_pose: np.ndarray,
                            force: np.ndarray,
                            dt: float,
                            mass: float = 1.0) -> np.ndarray:
        """
        将虚拟力转换为位姿增量（占位函数）

        Args:
            current_pose: 当前位姿 [x, y, z, rx, ry, rz]
            force: 虚拟力向量
            dt: 时间步长
            mass: 虚拟质量

        Returns:
            调整后的目标位姿
        """
        # TODO: 实现力到位姿的转换（考虑虚拟质量、阻尼等）
        # 简化版本：直接将力作为位置增量
        acceleration = force / mass
        velocity = acceleration * dt
        position_delta = velocity * dt

        adjusted_pose = current_pose.copy()
        adjusted_pose[:3] += position_delta

        return adjusted_pose