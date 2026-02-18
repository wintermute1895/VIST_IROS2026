"""
安全工具函数 - 输出限幅、NaN检查等
确保机器人命令安全可靠
"""

import numpy as np
from typing import Union, Tuple, Optional


def safe_clip_command(
    command: np.ndarray,
    max_velocity: float,
    max_acceleration: Optional[float] = None,
    prev_command: Optional[np.ndarray] = None,
    dt: float = 0.01,
    verbose: bool = False
) -> np.ndarray:
    """
    安全限幅命令（防止异常值）

    Args:
        command: 输入命令（关节速度或位置）
        max_velocity: 最大速度限制
        max_acceleration: 最大加速度限制（可选）
        prev_command: 上一次命令（用于加速度限制）
        dt: 时间步长（秒）
        verbose: 是否打印警告信息

    Returns:
        限幅后的安全命令
    """
    # 1. NaN检查
    if np.any(np.isnan(command)):
        if verbose:
            print("⚠️ [SAFETY] 检测到NaN，使用零速度")
        return np.zeros_like(command)

    # 2. Inf检查
    if np.any(np.isinf(command)):
        if verbose:
            print("⚠️ [SAFETY] 检测到Inf，使用零速度")
        return np.zeros_like(command)

    # 3. 速度限幅
    command_clipped = np.clip(command, -max_velocity, max_velocity)

    if verbose and not np.allclose(command, command_clipped):
        max_violation = np.max(np.abs(command - command_clipped))
        print(f"⚠️ [SAFETY] 速度限幅: 最大违规 {max_violation:.4f} rad/s")

    # 4. 加速度限幅（如果提供）
    if max_acceleration is not None and prev_command is not None:
        # 计算加速度
        acceleration = (command_clipped - prev_command) / dt

        # 限制加速度
        max_accel_change = max_acceleration * dt
        delta = command_clipped - prev_command
        delta_clipped = np.clip(delta, -max_accel_change, max_accel_change)

        command_clipped = prev_command + delta_clipped

        if verbose and not np.allclose(delta, delta_clipped):
            max_accel_violation = np.max(np.abs(acceleration)) - max_acceleration
            print(f"⚠️ [SAFETY] 加速度限幅: 最大违规 {max_accel_violation:.4f} rad/s²")

    return command_clipped


def check_joint_limits(
    joint_positions: np.ndarray,
    joint_limits: np.ndarray,
    margin: float = 0.05,
    verbose: bool = False
) -> Tuple[bool, np.ndarray]:
    """
    检查关节是否接近限位

    Args:
        joint_positions: 当前关节位置 (n_joints,)
        joint_limits: 关节限位 (n_joints, 2) [min, max]
        margin: 安全裕度（弧度）
        verbose: 是否打印警告

    Returns:
        (is_safe, violations): 是否安全，违规量
    """
    lower_limits = joint_limits[:, 0] + margin
    upper_limits = joint_limits[:, 1] - margin

    # 计算违规量
    lower_violations = np.maximum(0, lower_limits - joint_positions)
    upper_violations = np.maximum(0, joint_positions - upper_limits)

    violations = lower_violations + upper_violations

    is_safe = np.all(violations == 0)

    if verbose and not is_safe:
        for i, v in enumerate(violations):
            if v > 0:
                print(f"⚠️ [SAFETY] 关节{i}接近限位: 违规 {v:.4f} rad")

    return is_safe, violations


def smooth_command_transition(
    current_command: np.ndarray,
    target_command: np.ndarray,
    alpha: float = 0.1
) -> np.ndarray:
    """
    平滑命令过渡（指数移动平均）

    Args:
        current_command: 当前命令
        target_command: 目标命令
        alpha: 平滑系数 (0-1)，越小越平滑

    Returns:
        平滑后的命令
    """
    return alpha * target_command + (1 - alpha) * current_command


def detect_command_anomaly(
    command: np.ndarray,
    history: list,
    window_size: int = 10,
    threshold: float = 3.0
) -> bool:
    """
    检测命令异常（基于统计）

    Args:
        command: 当前命令
        history: 历史命令列表
        window_size: 窗口大小
        threshold: 异常阈值（标准差倍数）

    Returns:
        是否检测到异常
    """
    if len(history) < window_size:
        return False

    # 计算最近window_size个命令的统计量
    recent_commands = np.array(history[-window_size:])
    mean = np.mean(recent_commands, axis=0)
    std = np.std(recent_commands, axis=0) + 1e-6  # 避免除零

    # 计算Z-score
    z_scores = np.abs((command - mean) / std)

    # 检测异常
    is_anomaly = np.any(z_scores > threshold)

    return is_anomaly


def safe_normalize_vector(
    vector: np.ndarray,
    epsilon: float = 1e-6
) -> np.ndarray:
    """
    安全的向量归一化（避免除零）

    Args:
        vector: 输入向量
        epsilon: 最小范数阈值

    Returns:
        归一化后的向量（如果范数太小则返回零向量）
    """
    norm = np.linalg.norm(vector)

    if norm < epsilon:
        return np.zeros_like(vector)

    return vector / norm


def safe_matrix_inverse(
    matrix: np.ndarray,
    epsilon: float = 1e-6,
    method: str = 'pinv'
) -> np.ndarray:
    """
    安全的矩阵求逆（处理奇异矩阵）

    Args:
        matrix: 输入矩阵
        epsilon: 正则化参数
        method: 求逆方法 ('pinv', 'damped')

    Returns:
        逆矩阵或伪逆矩阵
    """
    if method == 'pinv':
        # 使用伪逆
        return np.linalg.pinv(matrix)

    elif method == 'damped':
        # 阻尼最小二乘
        n = matrix.shape[0]
        return np.linalg.inv(matrix.T @ matrix + epsilon * np.eye(n)) @ matrix.T

    else:
        raise ValueError(f"Unknown method: {method}")


class CommandSafetyMonitor:
    """
    命令安全监控器（有状态）

    功能：
    1. 持续监控命令安全性
    2. 记录历史命令
    3. 检测异常
    4. 自动限幅
    """

    def __init__(
        self,
        max_velocity: float,
        max_acceleration: float,
        joint_limits: np.ndarray,
        history_size: int = 100
    ):
        """
        初始化安全监控器

        Args:
            max_velocity: 最大速度
            max_acceleration: 最大加速度
            joint_limits: 关节限位
            history_size: 历史记录大小
        """
        self.max_velocity = max_velocity
        self.max_acceleration = max_acceleration
        self.joint_limits = joint_limits
        self.history_size = history_size

        self.command_history = []
        self.prev_command = None
        self.violation_count = 0

        print(f"🛡️ [SafetyMonitor] 初始化完成")
        print(f"   最大速度: {max_velocity} rad/s")
        print(f"   最大加速度: {max_acceleration} rad/s²")

    def check_and_clip(
        self,
        command: np.ndarray,
        dt: float = 0.01,
        verbose: bool = False
    ) -> Tuple[np.ndarray, bool]:
        """
        检查并限幅命令

        Args:
            command: 输入命令
            dt: 时间步长
            verbose: 是否打印详细信息

        Returns:
            (safe_command, is_safe): 安全命令，是否安全
        """
        is_safe = True

        # 1. 基本安全检查和限幅
        safe_command = safe_clip_command(
            command,
            self.max_velocity,
            self.max_acceleration,
            self.prev_command,
            dt,
            verbose
        )

        # 2. 异常检测
        if len(self.command_history) >= 10:
            is_anomaly = detect_command_anomaly(
                safe_command,
                self.command_history,
                window_size=10,
                threshold=3.0
            )

            if is_anomaly:
                if verbose:
                    print("⚠️ [SafetyMonitor] 检测到命令异常")
                is_safe = False
                self.violation_count += 1

        # 3. 更新历史
        self.command_history.append(safe_command.copy())
        if len(self.command_history) > self.history_size:
            self.command_history.pop(0)

        self.prev_command = safe_command.copy()

        return safe_command, is_safe

    def get_statistics(self) -> dict:
        """获取统计信息"""
        return {
            'history_size': len(self.command_history),
            'violation_count': self.violation_count,
        }


# 使用示例
if __name__ == '__main__':
    print("="*60)
    print("安全工具函数使用示例")
    print("="*60)

    # 示例1: 基本限幅
    print("\n示例1: 基本限幅")
    command = np.array([2.0, -3.0, 0.5, 1.5, -0.8, 0.3, 1.2])
    safe_cmd = safe_clip_command(command, max_velocity=1.0, verbose=True)
    print(f"原始命令: {command}")
    print(f"安全命令: {safe_cmd}")

    # 示例2: NaN检查
    print("\n示例2: NaN检查")
    bad_command = np.array([1.0, np.nan, 0.5, np.inf, -0.8, 0.3, 1.2])
    safe_cmd = safe_clip_command(bad_command, max_velocity=1.0, verbose=True)
    print(f"异常命令: {bad_command}")
    print(f"安全命令: {safe_cmd}")

    # 示例3: 安全监控器
    print("\n示例3: 安全监控器")
    joint_limits = np.array([
        [-np.pi, np.pi],
        [-np.pi/2, np.pi/2],
        [-np.pi, np.pi],
        [-np.pi/2, np.pi/2],
        [-np.pi, np.pi],
        [-np.pi/2, np.pi/2],
        [-np.pi, np.pi],
    ])

    monitor = CommandSafetyMonitor(
        max_velocity=1.0,
        max_acceleration=5.0,
        joint_limits=joint_limits
    )

    # 模拟10个命令
    for i in range(10):
        cmd = np.random.randn(7) * 0.5
        safe_cmd, is_safe = monitor.check_and_clip(cmd, dt=0.01, verbose=False)
        print(f"  Step {i}: is_safe={is_safe}")

    stats = monitor.get_statistics()
    print(f"\n统计信息: {stats}")

    print("\n" + "="*60)
    print("✅ 示例完成！")
    print("="*60)
