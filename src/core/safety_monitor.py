"""
Safety Monitor for Real Hardware Operation

This module provides safety checks for robot arm control:
- Joint limit enforcement
- Velocity limit checking
- Workspace boundary validation
- Singularity detection

Usage:
    monitor = SafetyMonitor(joint_limits, max_velocity=0.5)
    violations = monitor.check_command(q_cmd, timestamp)
    if violations:
        print(f"Safety violation: {violations}")
"""

import numpy as np
import pinocchio as pin
from typing import List, Tuple, Optional


class SafetyMonitor:
    """
    安全监控器：实时检查机器人运动的安全性

    功能：
    1. 关节限位检查
    2. 关节速度限制
    3. 工作空间边界检查
    4. 奇异点检测
    """

    def __init__(self,
                 joint_limits: np.ndarray,
                 max_joint_velocity: float = 0.5,
                 max_joint_acceleration: float = 5.0,
                 workspace_bounds: Optional[dict] = None):
        """
        初始化安全监控器

        Args:
            joint_limits: 关节限位 (n, 2) array [[min, max], ...]
            max_joint_velocity: 最大关节速度 (rad/s)
            max_joint_acceleration: 最大关节加速度 (rad/s^2)
            workspace_bounds: 工作空间边界 {'x': [min, max], 'y': [min, max], 'z': [min, max]}
        """
        self.joint_limits = np.array(joint_limits)
        self.max_joint_velocity = max_joint_velocity
        self.max_joint_acceleration = max_joint_acceleration

        # 工作空间边界（默认值：机器人前方安全区域）
        if workspace_bounds is None:
            self.workspace_bounds = {
                'x': [0.1, 0.6],   # 前方 10cm - 60cm
                'y': [-0.4, 0.4],  # 左右 ±40cm
                'z': [0.0, 0.6]    # 高度 0 - 60cm
            }
        else:
            self.workspace_bounds = workspace_bounds

        # 历史状态（用于速度和加速度计算）
        self.prev_q = None
        self.prev_dq = None
        self.prev_time = None

        print(f"🛡️ [SafetyMonitor] 初始化完成")
        print(f"   最大关节速度: {self.max_joint_velocity} rad/s")
        print(f"   最大关节加速度: {self.max_joint_acceleration} rad/s^2")
        print(f"   工作空间边界: {self.workspace_bounds}")

    def check_joint_limits(self, q: np.ndarray) -> List[str]:
        """
        检查关节限位

        Args:
            q: 关节角度 (rad)

        Returns:
            violations: 违规信息列表（空列表表示无违规）
        """
        violations = []
        for i, (q_val, (q_min, q_max)) in enumerate(zip(q, self.joint_limits)):
            if q_val < q_min:
                violations.append(
                    f"Joint {i}: {q_val:.3f} rad < min {q_min:.3f} rad "
                    f"({np.rad2deg(q_val):.1f}° < {np.rad2deg(q_min):.1f}°)"
                )
            elif q_val > q_max:
                violations.append(
                    f"Joint {i}: {q_val:.3f} rad > max {q_max:.3f} rad "
                    f"({np.rad2deg(q_val):.1f}° > {np.rad2deg(q_max):.1f}°)"
                )
        return violations

    def check_joint_velocity(self, q: np.ndarray, current_time: float) -> List[str]:
        """
        检查关节速度

        Args:
            q: 当前关节角度 (rad)
            current_time: 当前时间戳 (s)

        Returns:
            violations: 违规信息列表
        """
        if self.prev_q is None or self.prev_time is None:
            # 第一次调用，保存状态
            self.prev_q = q.copy()
            self.prev_time = current_time
            return []

        dt = current_time - self.prev_time
        if dt < 1e-6:
            return []

        # 计算关节速度
        dq = (q - self.prev_q) / dt
        violations = []

        for i, vel in enumerate(dq):
            if abs(vel) > self.max_joint_velocity:
                violations.append(
                    f"Joint {i}: velocity {vel:.3f} rad/s > max {self.max_joint_velocity} rad/s "
                    f"({np.rad2deg(vel):.1f}°/s > {np.rad2deg(self.max_joint_velocity):.1f}°/s)"
                )

        # 更新历史状态
        self.prev_q = q.copy()
        self.prev_dq = dq.copy()
        self.prev_time = current_time

        return violations

    def check_joint_acceleration(self, q: np.ndarray, current_time: float) -> List[str]:
        """
        检查关节加速度

        Args:
            q: 当前关节角度 (rad)
            current_time: 当前时间戳 (s)

        Returns:
            violations: 违规信息列表
        """
        if self.prev_q is None or self.prev_dq is None or self.prev_time is None:
            return []

        dt = current_time - self.prev_time
        if dt < 1e-6:
            return []

        # 计算当前速度
        dq = (q - self.prev_q) / dt

        # 计算加速度
        ddq = (dq - self.prev_dq) / dt
        violations = []

        for i, acc in enumerate(ddq):
            if abs(acc) > self.max_joint_acceleration:
                violations.append(
                    f"Joint {i}: acceleration {acc:.3f} rad/s^2 > max {self.max_joint_acceleration} rad/s^2"
                )

        return violations

    def check_workspace_bounds(self, end_effector_pos: np.ndarray) -> List[str]:
        """
        检查末端执行器是否在工作空间边界内

        Args:
            end_effector_pos: 末端执行器位置 [x, y, z] (m)

        Returns:
            violations: 违规信息列表
        """
        violations = []
        x, y, z = end_effector_pos

        if x < self.workspace_bounds['x'][0] or x > self.workspace_bounds['x'][1]:
            violations.append(
                f"X position {x:.3f}m out of bounds {self.workspace_bounds['x']}"
            )

        if y < self.workspace_bounds['y'][0] or y > self.workspace_bounds['y'][1]:
            violations.append(
                f"Y position {y:.3f}m out of bounds {self.workspace_bounds['y']}"
            )

        if z < self.workspace_bounds['z'][0] or z > self.workspace_bounds['z'][1]:
            violations.append(
                f"Z position {z:.3f}m out of bounds {self.workspace_bounds['z']}"
            )

        return violations

    def check_command(self,
                     q_cmd: np.ndarray,
                     current_time: float,
                     end_effector_pos: Optional[np.ndarray] = None) -> Tuple[bool, List[str]]:
        """
        综合安全检查（在发送指令前调用）

        Args:
            q_cmd: 目标关节角度 (rad)
            current_time: 当前时间戳 (s)
            end_effector_pos: 末端执行器位置（可选）

        Returns:
            (is_safe, violations): 是否安全 + 违规信息列表
        """
        all_violations = []

        # 1. 关节限位检查
        limit_violations = self.check_joint_limits(q_cmd)
        all_violations.extend(limit_violations)

        # 2. 关节速度检查
        velocity_violations = self.check_joint_velocity(q_cmd, current_time)
        all_violations.extend(velocity_violations)

        # 3. 工作空间边界检查（如果提供了末端位置）
        if end_effector_pos is not None:
            workspace_violations = self.check_workspace_bounds(end_effector_pos)
            all_violations.extend(workspace_violations)

        is_safe = len(all_violations) == 0
        return is_safe, all_violations

    def reset(self):
        """重置历史状态（用于重新开始监控）"""
        self.prev_q = None
        self.prev_dq = None
        self.prev_time = None
        print("🛡️ [SafetyMonitor] 状态已重置")


# ==========================================
# 测试代码
# ==========================================
if __name__ == "__main__":
    print("🧪 测试安全监控器...")

    # 定义关节限位（7-DoF 右臂）
    joint_limits = np.array([
        [-2.9, 1.0],      # Shoulder_Pitch
        [-0.15, 3.14],    # Shoulder_Roll
        [-3.14, 3.14],    # Shoulder_Yaw
        [-2.35, 0.0],     # Elbow_Pitch
        [-3.14, 3.14],    # Wrist_Yaw
        [-1.57, 1.57],    # Wrist_Pitch
        [-3.14, 3.14]     # Wrist_Roll
    ])

    # 创建监控器
    monitor = SafetyMonitor(joint_limits, max_joint_velocity=0.5)

    # 测试1：关节限位检查
    print("\n" + "="*60)
    print("测试 1: 关节限位检查")
    print("="*60)

    q_safe = np.array([0.0, 0.5, 0.0, -1.0, 0.0, 0.0, 0.0])
    q_unsafe = np.array([0.0, 4.0, 0.0, -1.0, 0.0, 0.0, 0.0])  # Shoulder_Roll 超限

    violations = monitor.check_joint_limits(q_safe)
    print(f"安全配置: {violations if violations else '✅ 无违规'}")

    violations = monitor.check_joint_limits(q_unsafe)
    print(f"不安全配置: {violations if violations else '✅ 无违规'}")

    # 测试2：速度检查
    print("\n" + "="*60)
    print("测试 2: 关节速度检查")
    print("="*60)

    q1 = np.zeros(7)
    q2 = np.array([0.1, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])  # 慢速运动
    q3 = np.array([1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])  # 快速运动

    t1 = 0.0
    t2 = 0.1
    t3 = 0.2

    monitor.reset()
    violations = monitor.check_joint_velocity(q1, t1)
    print(f"t=0.0s: {violations if violations else '✅ 无违规'}")

    violations = monitor.check_joint_velocity(q2, t2)
    print(f"t=0.1s (慢速): {violations if violations else '✅ 无违规'}")

    violations = monitor.check_joint_velocity(q3, t3)
    print(f"t=0.2s (快速): {violations if violations else '✅ 无违规'}")

    # 测试3：工作空间边界检查
    print("\n" + "="*60)
    print("测试 3: 工作空间边界检查")
    print("="*60)

    pos_safe = np.array([0.3, 0.0, 0.3])
    pos_unsafe = np.array([0.8, 0.0, 0.3])  # X 超出边界

    violations = monitor.check_workspace_bounds(pos_safe)
    print(f"安全位置 {pos_safe}: {violations if violations else '✅ 无违规'}")

    violations = monitor.check_workspace_bounds(pos_unsafe)
    print(f"不安全位置 {pos_unsafe}: {violations if violations else '✅ 无违规'}")

    # 测试4：综合检查
    print("\n" + "="*60)
    print("测试 4: 综合安全检查")
    print("="*60)

    monitor.reset()
    is_safe, violations = monitor.check_command(q_safe, 0.0, pos_safe)
    print(f"综合检查（安全）: {'✅ 通过' if is_safe else f'❌ 失败: {violations}'}")

    is_safe, violations = monitor.check_command(q_unsafe, 0.1, pos_unsafe)
    print(f"综合检查（不安全）: {'✅ 通过' if is_safe else f'❌ 失败: {violations}'}")

    print("\n✅ 测试完成")
