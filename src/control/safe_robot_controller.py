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

        # 安全参数（支持每个关节不同的限制）
        max_vel = config.max_joint_velocity
        max_acc = config.max_joint_acceleration

        # 转换为numpy数组（支持标量或列表）
        if isinstance(max_vel, (list, tuple, np.ndarray)):
            self.max_velocity = np.array(max_vel)
        else:
            self.max_velocity = np.full(7, max_vel)

        if isinstance(max_acc, (list, tuple, np.ndarray)):
            self.max_acceleration = np.array(max_acc)
        else:
            self.max_acceleration = np.full(7, max_acc)

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

    def limit_velocity(self, q_target, dt_actual=None):
        """
        限制关节速度

        Args:
            q_target: 目标关节角度 (7,)
            dt_actual: 实际时间间隔（秒），如果为None则使用self.dt

        Returns:
            q_safe: 速度限制后的关节角度 (7,)
            limited: 是否被限制
        """
        # 使用实际测量的时间间隔（关键修复！）
        dt = dt_actual if dt_actual is not None else self.dt

        # 计算目标速度
        q_dot_target = (q_target - self.q_current) / dt

        # 限制速度
        q_dot_safe = np.clip(q_dot_target, -self.max_velocity, self.max_velocity)

        # 检查是否被限制
        limited = not np.allclose(q_dot_target, q_dot_safe)

        if limited:
            self.velocity_limited_count += 1
            # 计算被限制的关节
            limited_joints = np.where(np.abs(q_dot_target) > self.max_velocity)[0]
            print(f"⚠️ [SafeController] 速度限制: 关节 {limited_joints}")
            print(f"   dt={dt:.6f}s")
            # 🔍 调试：打印实际的位置值来检查单位（角度 vs 弧度）
            print(f"   🔍 DEBUG: q_current[:3]={self.q_current[:3]}")
            print(f"   🔍 DEBUG: q_target[:3]={q_target[:3]}")
            # 打印每个被限制关节的max_vel
            for j in limited_joints:
                print(f"   J{j}: max_vel={self.max_velocity[j]:.3f} rad/s, q_dot_target={q_dot_target[j]:.3f}")
            print(f"   q_delta={q_target[limited_joints] - self.q_current[limited_joints]}")

        # 计算安全的目标角度（使用实际的dt）
        q_safe = self.q_current + q_dot_safe * dt

        return q_safe, limited

    def limit_acceleration(self, q_target, dt_actual=None):
        """
        限制关节加速度

        Args:
            q_target: 目标关节角度 (7,)
            dt_actual: 实际时间间隔（秒），如果为None则使用self.dt

        Returns:
            q_safe: 加速度限制后的关节角度 (7,)
            limited: 是否被限制
        """
        # 使用实际测量的时间间隔（关键修复！）
        dt = dt_actual if dt_actual is not None else self.dt

        # 计算目标速度
        q_dot_target = (q_target - self.q_current) / dt

        # 计算目标加速度
        q_ddot_target = (q_dot_target - self.q_dot_current) / dt

        # 限制加速度
        q_ddot_safe = np.clip(q_ddot_target, -self.max_acceleration, self.max_acceleration)

        # 检查是否被限制
        limited = not np.allclose(q_ddot_target, q_ddot_safe)

        if limited:
            self.acceleration_limited_count += 1
            # 计算被限制的关节
            limited_joints = np.where(np.abs(q_ddot_target) > self.max_acceleration)[0]
            print(f"⚠️ [SafeController] 加速度限制: 关节 {limited_joints}")
            print(f"   dt={dt:.6f}s")
            # 打印每个被限制关节的max_accel
            for j in limited_joints:
                print(f"   J{j}: max_accel={self.max_acceleration[j]:.3f} rad/s², q_ddot_target={q_ddot_target[j]:.3f}")
            print(f"   q_dot_target={q_dot_target[limited_joints]}, q_dot_current={self.q_dot_current[limited_joints]}")

        # 计算安全的速度和角度（使用实际的dt）
        q_dot_safe = self.q_dot_current + q_ddot_safe * dt
        q_safe = self.q_current + q_dot_safe * dt

        return q_safe, limited

    def process_command(self, q_target, q_dot_estimated=None):
        """
        处理控制命令，应用所有安全限制

        Args:
            q_target: 目标关节角度 (7,)
            q_dot_estimated: 估计的关节速度 (7,)，可选（已废弃，保留参数以兼容旧代码）
                           ⚠️ 为了保证速度/加速度计算一致性，现在完全基于位置差分计算

        Returns:
            q_safe: 安全的关节角度 (7,)
            safety_status: 安全状态字典
        """
        # ✅ 关键修复：测量实际的时间间隔
        current_time = time.time()
        dt_actual = current_time - self.last_update_time

        # 防止异常的dt值（例如第一次调用或长时间暂停）
        if dt_actual > 1.0 or dt_actual < 0.001:
            print(f"⚠️ [SafeController] 异常dt值: {dt_actual:.6f}s, 使用默认值 {self.dt}s")
            dt_actual = self.dt  # 使用默认值

        # 每100帧打印一次dt_actual用于调试
        if not hasattr(self, '_debug_frame_count'):
            self._debug_frame_count = 0
        self._debug_frame_count += 1
        if self._debug_frame_count % 100 == 0:
            print(f"🔍 [SafeController] dt_actual={dt_actual:.6f}s ({1.0/dt_actual:.1f} Hz)")

        # ⚠️ 不再使用外部提供的速度估计
        # 原因：外部速度（如卡尔曼滤波）与位置差分速度来源不一致
        # 导致加速度计算错误，触发100%安全限制
        # 解决方案：完全基于SafeRobotController自己维护的状态计算速度/加速度

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

        # 2. 速度限制（传递实际的dt）
        q_safe, velocity_limited = self.limit_velocity(q_safe, dt_actual)

        # ✅ 关键修复：在加速度限制之前先计算当前速度
        # 这样limit_acceleration()可以使用正确的q_dot_current
        q_dot_new = (q_safe - self.q_current) / dt_actual

        # 3. 加速度限制（传递实际的dt）
        # 注意：这里会使用self.q_dot_current（旧值）和q_dot_target（新值）计算加速度
        # 但是我们需要先更新q_dot_current为q_dot_new
        self.q_dot_current = q_dot_new
        q_safe, acceleration_limited = self.limit_acceleration(q_safe, dt_actual)

        # 4. 再次检查关节限位（防止积分漂移）
        q_safe, _ = self.check_joint_limits(q_safe)

        # ✅ 更新状态
        self.q_previous = self.q_current.copy()
        self.q_dot_previous = self.q_dot_current.copy()
        self.q_current = q_safe.copy()

        # 重新计算速度（基于最终的q_safe）
        self.q_dot_current = (q_safe - self.q_previous) / dt_actual

        # 更新时间戳（关键！）
        self.last_update_time = current_time

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
        self.last_update_time = time.time()  # ✅ 修复：重置更新时间

    def update_actual_command(self, q_actual, q_dot_actual=None):
        """
        更新实际发送给机器人的指令

        当控制器输出的指令被修改后（例如应用关节锁定），
        需要调用此方法更新安全控制器的内部状态，
        以确保下一帧的速度/加速度计算基于正确的状态。

        Args:
            q_actual: 实际发送给机器人的关节角度 (7,)
            q_dot_actual: 实际的关节速度 (7,)，可选
                         如果提供，将使用此速度而不是数值微分
        """
        # ✅ 关键修复：测量实际的时间间隔
        current_time = time.time()
        dt_actual = current_time - self.last_update_time

        # 防止异常的dt值
        if dt_actual > 1.0 or dt_actual < 0.001:
            dt_actual = self.dt

        # 先保存旧状态
        self.q_previous = self.q_current.copy()
        self.q_dot_previous = self.q_dot_current.copy()

        # 更新位置
        self.q_current = np.array(q_actual).copy()

        # 更新速度
        if q_dot_actual is not None:
            # 使用提供的速度（例如来自插值器或机器人SDK）
            self.q_dot_current = np.array(q_dot_actual).copy()
        else:
            # 使用数值微分计算速度（使用实际的dt）
            self.q_dot_current = (self.q_current - self.q_previous) / dt_actual

        # 更新时间戳（关键！）
        self.last_update_time = current_time


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
