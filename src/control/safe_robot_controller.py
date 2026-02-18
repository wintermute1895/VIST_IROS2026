#!/usr/bin/env python3
"""
安全机器人控制器
提供速度限制、加速度限制、关节限位检查、紧急停止等安全功能

Author: VIST Project
Date: 2026-02-07
"""

import numpy as np
import time
import json
from pathlib import Path


class SafeRobotController:
    """
    安全机器人控制器

    功能：
    1. 速度限制（velocity limiting）
    2. 加速度限制（acceleration limiting）
    3. 关节限位检查（joint limit checking）
    4. 工作空间限制（workspace limiting）
    5. 紧急停止（emergency stop）
    6. 数据记录（data logging）
    """

    def __init__(self, config, enable_logging=True):
        """
        初始化安全控制器

        Args:
            config: VISTConfig 配置对象
            enable_logging: 是否启用数据记录
        """
        self.config = config
        self.enable_logging = enable_logging

        # 安全参数
        self.max_velocity = config.max_joint_velocity
        self.max_acceleration = config.max_joint_acceleration
        self.joint_limits = config.robot_joint_limits
        self.dt = config.control_dt

        # 状态变量
        self.q_current = np.zeros(7)
        self.q_dot_current = np.zeros(7)
        self.q_previous = np.zeros(7)
        self.q_dot_previous = np.zeros(7)
        self.last_update_time = time.time()

        # 心跳检测（Heartbeat）
        self.last_command_time = time.time()
        self.heartbeat_timeout = 0.1  # 100ms 超时
        self.heartbeat_violations = 0

        # 安全状态
        self.emergency_stop = False
        self.velocity_limited_count = 0
        self.acceleration_limited_count = 0
        self.position_limited_count = 0

        # 数据记录
        self.log_data = []
        self.log_file = None
        if enable_logging:
            self._init_logging()

        print("✅ [SafeController] 安全控制器初始化完成")
        print(f"   最大速度: {self.max_velocity} rad/s")
        print(f"   最大加速度: {self.max_acceleration} rad/s²")
        print(f"   控制周期: {self.dt} s")
        print(f"   心跳超时: {self.heartbeat_timeout} s")

    def check_heartbeat(self):
        """
        检查心跳（Heartbeat）

        如果超过 heartbeat_timeout 没有收到命令，返回 True（超时）

        Returns:
            timeout: 是否超时
        """
        current_time = time.time()
        elapsed = current_time - self.last_command_time

        if elapsed > self.heartbeat_timeout:
            self.heartbeat_violations += 1
            print(f"⚠️ [SafeController] 心跳超时！已 {elapsed:.3f}s 未收到命令")
            return True

        return False

    def _init_logging(self):
        """初始化数据记录"""
        log_dir = Path(__file__).parent.parent.parent / "logs"
        log_dir.mkdir(exist_ok=True)

        timestamp = time.strftime("%Y%m%d_%H%M%S")
        self.log_file = log_dir / f"robot_control_{timestamp}.jsonl"
        print(f"   数据记录: {self.log_file}")

    def set_emergency_stop(self, stop=True):
        """设置紧急停止状态"""
        self.emergency_stop = stop
        if stop:
            print("🚨 [SafeController] 紧急停止激活！")
        else:
            print("✅ [SafeController] 紧急停止解除")

    def check_joint_limits(self, q_target):
        """
        检查关节限位

        Args:
            q_target: 目标关节角度 (7,)

        Returns:
            q_safe: 限制后的安全关节角度 (7,)
            limited: 是否被限制
        """
        q_safe = q_target.copy()
        limited = False

        for i in range(len(q_target)):
            lower, upper = self.joint_limits[i]

            if q_target[i] < lower:
                q_safe[i] = lower
                limited = True
                print(f"⚠️ [SafeController] 关节 {i} 超出下限: {q_target[i]:.3f} < {lower:.3f}")
            elif q_target[i] > upper:
                q_safe[i] = upper
                limited = True
                print(f"⚠️ [SafeController] 关节 {i} 超出上限: {q_target[i]:.3f} > {upper:.3f}")

        if limited:
            self.position_limited_count += 1

        return q_safe, limited

    def limit_velocity(self, q_target):
        """
        限制关节速度

        Args:
            q_target: 目标关节角度 (7,)

        Returns:
            q_safe: 速度限制后的关节角度 (7,)
            limited: 是否被限制
        """
        # 计算目标速度
        q_dot_target = (q_target - self.q_current) / self.dt

        # 限制速度
        q_dot_safe = np.clip(q_dot_target, -self.max_velocity, self.max_velocity)

        # 检查是否被限制
        limited = not np.allclose(q_dot_target, q_dot_safe)

        if limited:
            self.velocity_limited_count += 1
            # 计算被限制的关节
            limited_joints = np.where(np.abs(q_dot_target) > self.max_velocity)[0]
            print(f"⚠️ [SafeController] 速度限制: 关节 {limited_joints}")

        # 计算安全的目标角度
        q_safe = self.q_current + q_dot_safe * self.dt

        return q_safe, limited

    def limit_acceleration(self, q_target):
        """
        限制关节加速度

        Args:
            q_target: 目标关节角度 (7,)

        Returns:
            q_safe: 加速度限制后的关节角度 (7,)
            limited: 是否被限制
        """
        # 计算目标速度
        q_dot_target = (q_target - self.q_current) / self.dt

        # 计算目标加速度
        q_ddot_target = (q_dot_target - self.q_dot_current) / self.dt

        # 限制加速度
        q_ddot_safe = np.clip(q_ddot_target, -self.max_acceleration, self.max_acceleration)

        # 检查是否被限制
        limited = not np.allclose(q_ddot_target, q_ddot_safe)

        if limited:
            self.acceleration_limited_count += 1
            # 计算被限制的关节
            limited_joints = np.where(np.abs(q_ddot_target) > self.max_acceleration)[0]
            print(f"⚠️ [SafeController] 加速度限制: 关节 {limited_joints}")

        # 计算安全的速度和角度
        q_dot_safe = self.q_dot_current + q_ddot_safe * self.dt
        q_safe = self.q_current + q_dot_safe * self.dt

        return q_safe, limited

    def process_command(self, q_target):
        """
        处理控制命令，应用所有安全限制

        Args:
            q_target: 目标关节角度 (7,)

        Returns:
            q_safe: 安全的关节角度 (7,)
            safety_status: 安全状态字典
        """
        # 更新心跳时间
        self.last_command_time = time.time()

        # 检查心跳超时
        if self.check_heartbeat():
            # 心跳超时，返回零速度命令（停止）
            return self.q_current, {
                'emergency_stop': False,
                'heartbeat_timeout': True,
                'velocity_limited': False,
                'acceleration_limited': False,
                'position_limited': False
            }

        # 检查紧急停止
        if self.emergency_stop:
            return self.q_current, {
                'emergency_stop': True,
                'heartbeat_timeout': False,
                'velocity_limited': False,
                'acceleration_limited': False,
                'position_limited': False
            }

        # 1. 关节限位检查
        q_safe, position_limited = self.check_joint_limits(q_target)

        # 2. 速度限制
        q_safe, velocity_limited = self.limit_velocity(q_safe)

        # 3. 加速度限制
        q_safe, acceleration_limited = self.limit_acceleration(q_safe)

        # 4. 再次检查关节限位（防止积分漂移）
        q_safe, _ = self.check_joint_limits(q_safe)

        # 更新状态
        self.q_previous = self.q_current.copy()
        self.q_dot_previous = self.q_dot_current.copy()
        self.q_current = q_safe.copy()
        self.q_dot_current = (q_safe - self.q_previous) / self.dt

        # 安全状态
        safety_status = {
            'emergency_stop': False,
            'heartbeat_timeout': False,
            'velocity_limited': velocity_limited,
            'acceleration_limited': acceleration_limited,
            'position_limited': position_limited
        }

        # 记录数据
        if self.enable_logging:
            self._log_data(q_target, q_safe, safety_status)

        return q_safe, safety_status

    def _log_data(self, q_target, q_safe, safety_status):
        """记录数据"""
        log_entry = {
            'timestamp': time.time(),
            'q_target': q_target.tolist(),
            'q_safe': q_safe.tolist(),
            'q_current': self.q_current.tolist(),
            'q_dot_current': self.q_dot_current.tolist(),
            'safety_status': safety_status
        }

        # 写入文件
        if self.log_file is not None:
            with open(self.log_file, 'a') as f:
                f.write(json.dumps(log_entry) + '\n')

    def get_statistics(self):
        """获取统计信息"""
        return {
            'velocity_limited_count': self.velocity_limited_count,
            'acceleration_limited_count': self.acceleration_limited_count,
            'position_limited_count': self.position_limited_count,
            'heartbeat_violations': self.heartbeat_violations,
            'emergency_stop': self.emergency_stop
        }

    def reset(self):
        """重置控制器状态"""
        self.q_current = np.zeros(7)
        self.q_dot_current = np.zeros(7)
        self.q_previous = np.zeros(7)
        self.q_dot_previous = np.zeros(7)
        self.last_command_time = time.time()
        self.emergency_stop = False
        self.velocity_limited_count = 0
        self.acceleration_limited_count = 0
        self.position_limited_count = 0
        self.heartbeat_violations = 0
        print("✅ [SafeController] 控制器已重置")


# ============================================================================
# 测试代码
# ============================================================================
if __name__ == "__main__":
    print("🧪 测试安全控制器...")

    # 加载配置
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from config.config_loader import VISTConfig

    config = VISTConfig()

    # 创建安全控制器
    controller = SafeRobotController(config, enable_logging=False)

    # 测试 1: 正常命令
    print("\n测试 1: 正常命令")
    q_target = np.array([0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7])
    q_safe, status = controller.process_command(q_target)
    print(f"目标: {q_target}")
    print(f"安全: {q_safe}")
    print(f"状态: {status}")

    # 测试 2: 速度超限
    print("\n测试 2: 速度超限")
    q_target = np.array([5.0, 5.0, 5.0, 5.0, 5.0, 5.0, 5.0])  # 巨大跳变
    q_safe, status = controller.process_command(q_target)
    print(f"目标: {q_target}")
    print(f"安全: {q_safe}")
    print(f"状态: {status}")

    # 测试 3: 关节限位
    print("\n测试 3: 关节限位")
    q_target = np.array([10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0])  # 超出限位
    q_safe, status = controller.process_command(q_target)
    print(f"目标: {q_target}")
    print(f"安全: {q_safe}")
    print(f"状态: {status}")

    # 测试 4: 紧急停止
    print("\n测试 4: 紧急停止")
    controller.set_emergency_stop(True)
    q_target = np.array([1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0])
    q_safe, status = controller.process_command(q_target)
    print(f"目标: {q_target}")
    print(f"安全: {q_safe}")
    print(f"状态: {status}")

    # 统计信息
    print("\n统计信息:")
    stats = controller.get_statistics()
    for key, value in stats.items():
        print(f"  {key}: {value}")

    print("\n✅ 测试完成！")
