"""
VIST 简化安全监控器

基于用户实际系统特点的简化版本：
- 机器人和 web 控制器已有急停按钮
- 配置文件已有速度限制
- SRS 构型 + 长度归一化自动约束工作空间

本监控器只提供"兜底保护"，参数设置宽松。

Author: VIST Team
Date: 2026-02-09
"""

import numpy as np
from typing import Tuple, Optional


class SimplifiedSafetyMonitor:
    """
    简化的安全监控器

    只提供兜底保护，不干扰正常工作：
    - 速度限制：比配置文件宽松 50%
    - 工作空间：非常宽松，只防极端情况
    - 不实现急停（机器人和 web 已有）
    """

    def __init__(self, config_max_velocity=0.10):
        """
        初始化简化安全监控器

        Args:
            config_max_velocity: 配置文件中的最大速度（米/秒）
        """
        # 速度限制：比配置文件宽松 50%（兜底保护）
        self.MAX_VELOCITY = config_max_velocity * 1.5

        # 工作空间限制：非常宽松（只防极端异常）
        # 根据您的机器人实际工作空间调整
        self.WORKSPACE_MIN = np.array([0.0, -0.5, 0.0])
        self.WORKSPACE_MAX = np.array([1.0, 0.5, 0.8])

        # 统计（用于调试）
        self.velocity_limit_triggered = 0
        self.workspace_violation_triggered = 0

        print(f"🛡️ [SimplifiedSafety] 初始化完成")
        print(f"   速度兜底限制: {self.MAX_VELOCITY*100:.1f} cm/s")
        print(f"   工作空间: 非常宽松（只防极端异常）")

    def check(
        self,
        position: np.ndarray,
        velocity: np.ndarray
    ) -> Tuple[np.ndarray, bool, str]:
        """
        简化的安全检查（只检查极端情况）

        Args:
            position: 当前位置 [x, y, z]
            velocity: 目标速度 [vx, vy, vz]

        Returns:
            safe_velocity: 安全的速度
            is_safe: 是否安全
            message: 消息（只在不安全时有内容）
        """
        # 1. 检查工作空间（极端情况）
        if not self._check_workspace(position):
            self.workspace_violation_triggered += 1
            return np.zeros(3), False, f"⚠️ 极端异常：超出工作空间 {position}"

        # 2. 限制速度（极端情况）
        safe_velocity, limited = self._limit_velocity(velocity)
        if limited:
            self.velocity_limit_triggered += 1
            return safe_velocity, True, f"⚠️ 速度兜底限制触发: {self.MAX_VELOCITY*100:.1f}cm/s"

        # 正常情况：不干扰
        return velocity, True, ""

    def _check_workspace(self, position: np.ndarray) -> bool:
        """检查工作空间（宽松）"""
        return np.all(position >= self.WORKSPACE_MIN) and np.all(position <= self.WORKSPACE_MAX)

    def _limit_velocity(self, velocity: np.ndarray) -> Tuple[np.ndarray, bool]:
        """限制速度（宽松）"""
        speed = np.linalg.norm(velocity)
        if speed > self.MAX_VELOCITY:
            safe_velocity = velocity / speed * self.MAX_VELOCITY
            return safe_velocity, True
        return velocity, False

    def get_stats(self) -> dict:
        """获取统计信息（用于调试）"""
        return {
            'velocity_limit_triggered': self.velocity_limit_triggered,
            'workspace_violation_triggered': self.workspace_violation_triggered
        }


# 使用示例
if __name__ == "__main__":
    print("\n简化安全监控器测试\n")

    # 创建监控器（配置文件速度限制 10cm/s）
    safety = SimplifiedSafetyMonitor(config_max_velocity=0.10)

    # 测试 1: 正常情况（不干扰）
    print("测试 1: 正常情况")
    pos = np.array([0.5, 0.0, 0.3])
    vel = np.array([0.08, 0.0, 0.0])  # 8cm/s（低于 15cm/s 兜底限制）
    safe_vel, is_safe, msg = safety.check(pos, vel)
    print(f"  输入速度: {np.linalg.norm(vel)*100:.1f}cm/s")
    print(f"  结果: {'✅ 通过' if is_safe else '❌ 拦截'} {msg}")
    assert is_safe and msg == ""

    # 测试 2: 极端速度（触发兜底）
    print("\n测试 2: 极端速度")
    vel = np.array([0.20, 0.0, 0.0])  # 20cm/s（超过 15cm/s 兜底限制）
    safe_vel, is_safe, msg = safety.check(pos, vel)
    print(f"  输入速度: {np.linalg.norm(vel)*100:.1f}cm/s")
    print(f"  输出速度: {np.linalg.norm(safe_vel)*100:.1f}cm/s")
    print(f"  结果: {'✅ 通过' if is_safe else '❌ 拦截'} {msg}")
    assert is_safe and np.linalg.norm(safe_vel) <= safety.MAX_VELOCITY

    # 测试 3: 极端位置（触发兜底）
    print("\n测试 3: 极端位置")
    pos = np.array([2.0, 0.0, 0.3])  # 超出工作空间
    vel = np.array([0.08, 0.0, 0.0])
    safe_vel, is_safe, msg = safety.check(pos, vel)
    print(f"  位置: {pos}")
    print(f"  结果: {'✅ 通过' if is_safe else '❌ 拦截'} {msg}")
    assert not is_safe

    # 统计
    print(f"\n统计: {safety.get_stats()}")
    print("\n✅ 所有测试通过！")
