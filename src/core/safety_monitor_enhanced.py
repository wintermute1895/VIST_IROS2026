"""
VIST 安全监控器

实现关键的安全机制，确保真机测试的安全性。

核心功能：
1. 速度限制
2. 工作空间限制
3. 紧急停止
4. 看门狗定时器

Author: VIST Team
Date: 2026-02-09
"""

import numpy as np
import time
from typing import Tuple, Optional
from enum import Enum


class SafetyStatus(Enum):
    """安全状态"""
    OK = "ok"
    WARNING = "warning"
    EMERGENCY_STOP = "emergency_stop"
    WORKSPACE_VIOLATION = "workspace_violation"
    VELOCITY_LIMIT = "velocity_limit"
    WATCHDOG_TIMEOUT = "watchdog_timeout"


class VISTSafetyMonitor:
    """
    VIST 安全监控器

    实现关键的安全机制：
    - 速度限制
    - 工作空间限制
    - 紧急停止
    - 看门狗定时器
    """

    def __init__(self, config=None):
        """
        初始化安全监控器

        Args:
            config: 配置对象（可选）
        """
        # 速度限制
        self.MAX_VELOCITY = 0.10  # 10cm/s（最大速度）
        self.MAX_ACCELERATION = 0.5  # 0.5m/s²（最大加速度）

        # 工作空间限制（笛卡尔空间，单位：米）
        self.WORKSPACE_MIN = np.array([0.2, -0.3, 0.1])  # [x, y, z] 最小值
        self.WORKSPACE_MAX = np.array([0.8, 0.3, 0.6])   # [x, y, z] 最大值

        # 紧急停止
        self.emergency_stop_flag = False

        # 看门狗定时器
        self.WATCHDOG_TIMEOUT = 0.5  # 500ms
        self.last_command_time = time.time()

        # 统计信息
        self.stats = {
            'velocity_limit_count': 0,
            'workspace_violation_count': 0,
            'emergency_stop_count': 0,
            'watchdog_timeout_count': 0
        }

        print("🛡️ [SafetyMonitor] 安全监控器初始化完成")
        print(f"   最大速度: {self.MAX_VELOCITY*100:.1f} cm/s")
        print(f"   工作空间: X[{self.WORKSPACE_MIN[0]:.2f}, {self.WORKSPACE_MAX[0]:.2f}] "
              f"Y[{self.WORKSPACE_MIN[1]:.2f}, {self.WORKSPACE_MAX[1]:.2f}] "
              f"Z[{self.WORKSPACE_MIN[2]:.2f}, {self.WORKSPACE_MAX[2]:.2f}]")

    def check_safety(
        self,
        position: np.ndarray,
        velocity: np.ndarray
    ) -> Tuple[Optional[np.ndarray], SafetyStatus, str]:
        """
        综合安全检查

        Args:
            position: 当前位置 [x, y, z]
            velocity: 目标速度 [vx, vy, vz]

        Returns:
            safe_velocity: 安全的速度（如果不安全则为 None）
            status: 安全状态
            message: 状态消息
        """
        # 1. 检查紧急停止
        if self.emergency_stop_flag:
            return None, SafetyStatus.EMERGENCY_STOP, "紧急停止已激活"

        # 2. 检查看门狗超时
        if not self._check_watchdog():
            return None, SafetyStatus.WATCHDOG_TIMEOUT, "通信超时"

        # 3. 检查工作空间
        if not self._check_workspace(position):
            self.stats['workspace_violation_count'] += 1
            return None, SafetyStatus.WORKSPACE_VIOLATION, f"超出工作空间: {position}"

        # 4. 限制速度
        safe_velocity, limited = self._limit_velocity(velocity)
        if limited:
            self.stats['velocity_limit_count'] += 1
            return safe_velocity, SafetyStatus.VELOCITY_LIMIT, f"速度已限制到 {self.MAX_VELOCITY*100:.1f}cm/s"

        # 5. 更新看门狗
        self.update_watchdog()

        return safe_velocity, SafetyStatus.OK, "安全检查通过"

    def _check_workspace(self, position: np.ndarray) -> bool:
        """
        检查位置是否在安全工作空间内

        Args:
            position: 位置 [x, y, z]

        Returns:
            is_safe: 是否安全
        """
        if np.any(position < self.WORKSPACE_MIN) or np.any(position > self.WORKSPACE_MAX):
            print(f"⚠️ [SafetyMonitor] 超出工作空间！")
            print(f"   当前位置: [{position[0]:.3f}, {position[1]:.3f}, {position[2]:.3f}]")
            print(f"   允许范围: X[{self.WORKSPACE_MIN[0]:.2f}, {self.WORKSPACE_MAX[0]:.2f}] "
                  f"Y[{self.WORKSPACE_MIN[1]:.2f}, {self.WORKSPACE_MAX[1]:.2f}] "
                  f"Z[{self.WORKSPACE_MIN[2]:.2f}, {self.WORKSPACE_MAX[2]:.2f}]")
            return False
        return True

    def _limit_velocity(self, velocity: np.ndarray) -> Tuple[np.ndarray, bool]:
        """
        限制速度到安全范围

        Args:
            velocity: 目标速度 [vx, vy, vz]

        Returns:
            safe_velocity: 安全的速度
            limited: 是否被限制
        """
        speed = np.linalg.norm(velocity)

        if speed > self.MAX_VELOCITY:
            # 限制速度
            safe_velocity = velocity / speed * self.MAX_VELOCITY
            print(f"⚠️ [SafetyMonitor] 速度超限！")
            print(f"   原始速度: {speed*100:.1f} cm/s")
            print(f"   限制到: {self.MAX_VELOCITY*100:.1f} cm/s")
            return safe_velocity, True

        return velocity, False

    def _check_watchdog(self) -> bool:
        """
        检查看门狗超时

        Returns:
            is_ok: 是否正常
        """
        elapsed = time.time() - self.last_command_time

        if elapsed > self.WATCHDOG_TIMEOUT:
            print(f"🚨 [SafetyMonitor] 通信超时！")
            print(f"   超时时间: {elapsed*1000:.0f}ms (阈值: {self.WATCHDOG_TIMEOUT*1000:.0f}ms)")
            self.stats['watchdog_timeout_count'] += 1
            self.emergency_stop()
            return False

        return True

    def update_watchdog(self):
        """更新看门狗定时器"""
        self.last_command_time = time.time()

    def emergency_stop(self):
        """触发紧急停止"""
        if not self.emergency_stop_flag:
            self.emergency_stop_flag = True
            self.stats['emergency_stop_count'] += 1
            print("🚨 [SafetyMonitor] 紧急停止！")

    def reset_emergency_stop(self):
        """重置紧急停止"""
        self.emergency_stop_flag = False
        self.last_command_time = time.time()
        print("✅ [SafetyMonitor] 紧急停止已重置")

    def get_stats(self) -> dict:
        """获取统计信息"""
        return self.stats.copy()

    def print_stats(self):
        """打印统计信息"""
        print("\n" + "="*60)
        print("[SafetyMonitor] 统计信息")
        print("="*60)
        print(f"速度限制次数: {self.stats['velocity_limit_count']}")
        print(f"工作空间违规次数: {self.stats['workspace_violation_count']}")
        print(f"紧急停止次数: {self.stats['emergency_stop_count']}")
        print(f"看门狗超时次数: {self.stats['watchdog_timeout_count']}")
        print("="*60 + "\n")


# 使用示例
if __name__ == "__main__":
    print("\n" + "="*60)
    print("VIST 安全监控器测试")
    print("="*60)

    # 创建安全监控器
    safety = VISTSafetyMonitor()

    # 测试 1: 正常情况
    print("\n测试 1: 正常情况")
    position = np.array([0.5, 0.0, 0.3])
    velocity = np.array([0.05, 0.0, 0.0])  # 5cm/s
    safe_vel, status, msg = safety.check_safety(position, velocity)
    print(f"结果: {status.value} - {msg}")
    assert status == SafetyStatus.OK

    # 测试 2: 速度超限
    print("\n测试 2: 速度超限")
    velocity = np.array([0.15, 0.0, 0.0])  # 15cm/s（超限）
    safe_vel, status, msg = safety.check_safety(position, velocity)
    print(f"结果: {status.value} - {msg}")
    assert status == SafetyStatus.VELOCITY_LIMIT
    assert np.linalg.norm(safe_vel) <= safety.MAX_VELOCITY

    # 测试 3: 工作空间违规
    print("\n测试 3: 工作空间违规")
    position = np.array([1.0, 0.0, 0.3])  # 超出 X 最大值
    velocity = np.array([0.05, 0.0, 0.0])
    safe_vel, status, msg = safety.check_safety(position, velocity)
    print(f"结果: {status.value} - {msg}")
    assert status == SafetyStatus.WORKSPACE_VIOLATION

    # 测试 4: 紧急停止
    print("\n测试 4: 紧急停止")
    safety.emergency_stop()
    position = np.array([0.5, 0.0, 0.3])
    velocity = np.array([0.05, 0.0, 0.0])
    safe_vel, status, msg = safety.check_safety(position, velocity)
    print(f"结果: {status.value} - {msg}")
    assert status == SafetyStatus.EMERGENCY_STOP

    # 重置紧急停止
    safety.reset_emergency_stop()

    # 测试 5: 看门狗超时
    print("\n测试 5: 看门狗超时")
    safety.last_command_time = time.time() - 1.0  # 模拟 1 秒前
    position = np.array([0.5, 0.0, 0.3])
    velocity = np.array([0.05, 0.0, 0.0])
    safe_vel, status, msg = safety.check_safety(position, velocity)
    print(f"结果: {status.value} - {msg}")
    assert status == SafetyStatus.WATCHDOG_TIMEOUT

    # 打印统计信息
    safety.print_stats()

    print("\n✅ 所有测试通过！")
