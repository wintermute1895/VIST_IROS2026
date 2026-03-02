#!/usr/bin/env python3
"""
虚拟夹具有限状态机 (Virtual Fixture FSM) - 关节空间版本
实现基于圆柱形结界的双状态关节角缩放控制

核心特性：
1. 关节空间绝对映射：自由态直接使用遥操臂关节角，无启动抖动
2. 状态锚点机制：粘滞态基于状态锚点进行关节角缩放
3. 圆柱形结界判定：通过正运动学计算法兰位置，判断是否在势场内
4. 双状态切换：自由态（1:1 绝对映射）和粘滞态（关节角缩放）
5. NO IK：全程在关节空间操作，无需逆运动学

作者: VIST Team
日期: 2026-02-28 (关节空间绝对映射版本)
"""

import numpy as np
from enum import Enum
from typing import Tuple, Optional
from dataclasses import dataclass
import time


class VirtualFixtureState(Enum):
    """虚拟夹具状态枚举"""
    FREE = "自由态"          # 在结界外，1:1 关节角跟随
    CONSTRAINED = "粘滞态"   # 在结界内，关节角缩放


@dataclass
class JointAnchorPoint:
    """
    关节空间锚点数据结构
    记录状态切换瞬间或启动时刻的关节角
    """
    exo_joints: np.ndarray      # 遥操臂关节角 [q1, q2, ..., q7]
    robot_joints: np.ndarray    # 机械臂关节角 [q1, q2, ..., q7]
    timestamp: float            # 记录时间戳


class VirtualFixtureFSM:
    """
    虚拟夹具有限状态机 - 关节空间版本

    实现圆柱形结界的双状态关节角缩放控制：
    - 状态 1（自由态）：D > R 时，1:1 绝对映射
    - 状态 2（粘滞态）：D ≤ R 时，关节角缩放（如 1:5）

    核心机制：
    1. 绝对映射：自由态直接使用遥操臂关节角，无需锚点
    2. 状态锚点：粘滞态基于状态锚点进行关节角缩放
    3. 平滑切换：状态切换时记录锚点，防止跳变

    公式（关节空间）：
    - 自由态：q_target = q_exo（绝对映射）
    - 粘滞态：q_target = q_anchor_robot + scale × (q_exo - q_anchor_exo)
    """

    def __init__(self,
                 socket_center_xy: np.ndarray,
                 cylinder_radius: float,
                 joint_scale_factor: float = 0.2):
        """
        初始化虚拟夹具 FSM

        Args:
            socket_center_xy: 插座中心的 XY 坐标 [x, y] (单位: m)
            cylinder_radius: 圆柱形结界半径 (单位: m)
            joint_scale_factor: 粘滞态下的关节角缩放比例 (默认 0.2，即 1:5)
        """
        # 结界参数
        self.socket_center_xy = np.array(socket_center_xy, dtype=np.float64)
        self.cylinder_radius = cylinder_radius

        # 缩放参数
        self.joint_scale_factor = joint_scale_factor

        # 状态变量
        self.current_state = VirtualFixtureState.FREE

        # 状态锚点（状态切换时记录，用于粘滞态的关节角缩放）
        self.state_anchor: Optional[JointAnchorPoint] = None

        # 统计信息
        self.state_transition_count = 0
        self.time_in_free = 0.0
        self.time_in_constrained = 0.0

        # 调试输出控制
        self.last_print_time = 0.0
        self.print_interval = 0.5  # 打印间隔（秒）

    def update(self,
               exo_joints: np.ndarray,
               robot_flange_position: np.ndarray) -> Tuple[np.ndarray, VirtualFixtureState]:
        """
        更新 FSM 状态并计算目标关节角（关节空间，NO IK）

        Args:
            exo_joints: 遥操臂当前关节角 [q1, q2, ..., q7] (单位: rad)
            robot_flange_position: 机械臂法兰当前位置 [x, y, z] (单位: m)
                                  通过正运动学计算得到

        Returns:
            target_joints: 机械臂目标关节角 [q1, q2, ..., q7] (单位: rad)
            current_state: 当前状态
        """
        # 确保输入是 numpy 数组
        if not isinstance(exo_joints, np.ndarray):
            exo_joints = np.array(exo_joints)
        if not isinstance(robot_flange_position, np.ndarray):
            robot_flange_position = np.array(robot_flange_position)

        # ========== 步骤 1: 计算法兰到结界中心的距离（仅 XY 平面） ==========
        # 🔍 调试：控制打印频率（每 0.5 秒打印一次详细信息）
        current_time = time.time()
        should_print_debug = (current_time - self.last_print_time) >= self.print_interval

        if should_print_debug:
            print(f"\n🔍 [FSM Debug] 原始输入:")
            print(f"  robot_flange_position = {robot_flange_position}")
            print(f"  socket_center_xy = {self.socket_center_xy}")

        flange_xy = robot_flange_position[:2]

        if should_print_debug:
            print(f"  flange_xy = {flange_xy}")

        # 🔍 单位检测：如果法兰位置的模长 > 10，很可能是毫米
        flange_norm = np.linalg.norm(flange_xy)

        if should_print_debug:
            print(f"  flange_xy 模长 = {flange_norm:.3f}")

        if flange_norm > 10:
            if should_print_debug:
                print(f"⚠️  [FSM] 检测到法兰位置单位可能是毫米（模长 {flange_norm:.1f} > 10）")
                print(f"  自动转换: {flange_xy} mm -> {flange_xy/1000.0} m")
            flange_xy = flange_xy / 1000.0
        else:
            if should_print_debug:
                print(f"✓ [FSM] 法兰位置单位正常（模长 {flange_norm:.3f} ≤ 10，单位为米）")

        distance_to_center = np.linalg.norm(flange_xy - self.socket_center_xy)

        if should_print_debug:
            print(f"  计算距离 = {distance_to_center:.6f} m = {distance_to_center*1000:.1f} mm")
            self.last_print_time = current_time  # 更新上次打印时间

        # ========== 实时打印距离和状态信息 ==========
        print(f"\r距离: {distance_to_center*1000:.1f}mm | 状态: {self.current_state.value} | 阈值: {self.cylinder_radius*1000:.1f}mm", end='', flush=True)

        # ========== 步骤 2: 判定新状态 ==========
        new_state = self._determine_state(distance_to_center)

        # ========== 步骤 3: 检测状态切换 ==========
        if new_state != self.current_state:
            # 状态切换时换行打印
            print(f"\n🔄 状态切换: {self.current_state.value} -> {new_state.value}")
            self._handle_state_transition(
                new_state=new_state,
                exo_joints=exo_joints,
                robot_joints=exo_joints.copy()
            )

        # ========== 步骤 4: 根据当前状态计算目标关节角（关节空间绝对映射） ==========
        target_joints = self._compute_target_joints(exo_joints=exo_joints)

        return target_joints, self.current_state

    def _determine_state(self, distance_to_center: float) -> VirtualFixtureState:
        """
        根据距离判定状态

        Args:
            distance_to_center: 法兰 XY 坐标到结界中心的距离 (单位: m)

        Returns:
            新状态
        """
        if distance_to_center <= self.cylinder_radius:
            return VirtualFixtureState.CONSTRAINED
        else:
            return VirtualFixtureState.FREE

    def _handle_state_transition(self,
                                  new_state: VirtualFixtureState,
                                  exo_joints: np.ndarray,
                                  robot_joints: np.ndarray):
        """
        处理状态切换，记录状态锚点

        这是防止状态切换跳变的核心机制：
        - 在状态切换的瞬间，记录遥操臂和机械臂的当前关节角作为状态锚点
        - 后续的粘滞态运动都基于这个状态锚点进行增量计算

        Args:
            new_state: 新状态
            exo_joints: 遥操臂当前关节角 [q1, q2, ..., q7]
            robot_joints: 机械臂当前关节角 [q1, q2, ..., q7]
        """
        # 记录状态锚点
        self.state_anchor = JointAnchorPoint(
            exo_joints=exo_joints.copy(),
            robot_joints=robot_joints.copy(),
            timestamp=self.time_in_free + self.time_in_constrained
        )

        # 更新状态
        old_state = self.current_state
        self.current_state = new_state
        self.state_transition_count += 1

        # 日志输出
        print(f"[VirtualFixtureFSM] 状态切换: {old_state.value} -> {new_state.value}")
        print(f"  状态锚点 - 遥操臂: {exo_joints}")
        print(f"  状态锚点 - 机械臂: {robot_joints}")

    def _compute_target_joints(self, exo_joints: np.ndarray) -> np.ndarray:
        """
        根据当前状态计算目标关节角（关节空间绝对映射）

        核心算法：
        1. 自由态：q_target = q_exo（绝对映射）
        2. 粘滞态：q_target = q_anchor_robot + scale × (q_exo - q_anchor_exo)

        Args:
            exo_joints: 遥操臂当前关节角 [q1, q2, ..., q7]

        Returns:
            target_joints: 目标关节角 [q1, q2, ..., q7]
        """
        if self.current_state == VirtualFixtureState.FREE:
            # ========== 自由态：绝对映射（直接使用遥操臂关节角） ==========
            return exo_joints.copy()

        else:  # CONSTRAINED
            # ========== 粘滞态：基于状态锚点的关节角缩放 ==========
            if self.state_anchor is None:
                # 如果没有状态锚点（首次进入粘滞态），创建锚点
                self.state_anchor = JointAnchorPoint(
                    exo_joints=exo_joints.copy(),
                    robot_joints=exo_joints.copy(),
                    timestamp=self.time_in_free + self.time_in_constrained
                )
                return exo_joints.copy()

            # 计算遥操臂相对于状态锚点的增量
            exo_delta = exo_joints - self.state_anchor.exo_joints

            # 应用关节角缩放
            target_joints = self.state_anchor.robot_joints + exo_delta * self.joint_scale_factor

            return target_joints

    def get_state_info(self) -> dict:
        """
        获取状态机信息（用于调试和可视化）

        Returns:
            状态信息字典
        """
        info = {
            'current_state': self.current_state.value,
            'state_transition_count': self.state_transition_count,
            'time_in_free': self.time_in_free,
            'time_in_constrained': self.time_in_constrained,
            'socket_center_xy': self.socket_center_xy.tolist(),
            'cylinder_radius': self.cylinder_radius,
            'joint_scale_factor': self.joint_scale_factor
        }

        if self.state_anchor is not None:
            info['state_anchor'] = {
                'exo_joints': self.state_anchor.exo_joints.tolist(),
                'robot_joints': self.state_anchor.robot_joints.tolist(),
                'timestamp': self.state_anchor.timestamp
            }

        return info

    def reset(self):
        """重置状态机"""
        self.current_state = VirtualFixtureState.FREE
        self.state_anchor = None
        self.state_transition_count = 0
        self.time_in_free = 0.0
        self.time_in_constrained = 0.0
        print("[VirtualFixtureFSM] 状态机已重置")


# ==================== 辅助函数 ====================

def compute_distance_to_cylinder(position_xy: np.ndarray,
                                  cylinder_center_xy: np.ndarray) -> float:
    """
    计算点到圆柱中心的距离（仅 XY 平面）

    Args:
        position_xy: 点的 XY 坐标 [x, y]
        cylinder_center_xy: 圆柱中心的 XY 坐标 [x, y]

    Returns:
        距离 (单位: m)
    """
    return np.linalg.norm(position_xy - cylinder_center_xy)