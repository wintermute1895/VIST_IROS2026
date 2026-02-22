#!/usr/bin/env python3
"""
One-Euro 滤波器实现
经典的自适应低通滤波器，用于消融实验对比

参考文献:
Casiez, G., Roussel, N., & Vogel, D. (2012).
1€ filter: a simple speed-based low-pass filter for noisy input in interactive systems.
CHI '12: Proceedings of the SIGCHI Conference on Human Factors in Computing Systems.

Author: VIST Project
Date: 2026-02-22
"""

import numpy as np
import time
from .base_filter import BaseFilter


class OneEuroFilter(BaseFilter):
    """
    One-Euro 滤波器

    核心思想：
    - 当信号变化慢时，使用强滤波（低截止频率）以减少噪声
    - 当信号变化快时，使用弱滤波（高截止频率）以减少延迟

    参数：
    - min_cutoff: 最小截止频率（Hz），控制最强滤波强度
    - beta: 速度系数，控制截止频率对速度的敏感度
    - d_cutoff: 速度滤波的截止频率（Hz）
    """

    def __init__(self, dim, min_cutoff=1.0, beta=0.007, d_cutoff=1.0):
        """
        初始化 One-Euro 滤波器

        Args:
            dim: 状态维度
            min_cutoff: 最小截止频率（Hz），默认 1.0
            beta: 速度系数，默认 0.007
            d_cutoff: 速度滤波的截止频率（Hz），默认 1.0
        """
        super().__init__(dim)

        # 参数
        self.min_cutoff = min_cutoff
        self.beta = beta
        self.d_cutoff = d_cutoff

        # 状态
        self.x = np.zeros(dim)  # 滤波后的位置
        self.dx = np.zeros(dim)  # 滤波后的速度
        self.last_time = None

        print(f"✅ [OneEuroFilter] 初始化完成")
        print(f"   维度: {dim}")
        print(f"   最小截止频率: {min_cutoff} Hz")
        print(f"   速度系数 beta: {beta}")
        print(f"   速度截止频率: {d_cutoff} Hz")

    def _smoothing_factor(self, t_e, cutoff):
        """
        计算平滑因子

        Args:
            t_e: 时间步长（秒）
            cutoff: 截止频率（Hz）

        Returns:
            alpha: 平滑因子 [0, 1]
        """
        r = 2 * np.pi * cutoff * t_e
        return r / (r + 1)

    def _exponential_smoothing(self, a, x, x_prev):
        """
        指数平滑

        Args:
            a: 平滑因子
            x: 当前值
            x_prev: 上一次滤波值

        Returns:
            滤波后的值
        """
        return a * x + (1 - a) * x_prev

    def update(self, measurement, dt=None, **kwargs):
        """
        更新滤波器

        Args:
            measurement: 观测值 (dim,)
            dt: 时间步长（秒），如果为 None 则自动计算
            **kwargs: 其他参数（忽略）

        Returns:
            filtered_state: 滤波后的状态 (dim,)
        """
        measurement = np.array(measurement)

        # 计算时间步长
        current_time = time.time()
        if dt is None:
            if self.last_time is not None:
                dt = current_time - self.last_time
            else:
                dt = 1.0 / 30.0  # 默认 30Hz
        self.last_time = current_time

        # 防止异常的 dt 值
        if dt <= 0 or dt > 1.0:
            dt = 1.0 / 30.0

        # 第一次调用，直接初始化
        if not self.initialized:
            self.x = measurement.copy()
            self.dx = np.zeros(self.dim)
            self.initialized = True
            return self.x

        # 1. 估计速度（使用低通滤波）
        raw_dx = (measurement - self.x) / dt
        alpha_d = self._smoothing_factor(dt, self.d_cutoff)
        self.dx = self._exponential_smoothing(alpha_d, raw_dx, self.dx)

        # 2. 计算自适应截止频率
        # 速度越大，截止频率越高（滤波越弱）
        cutoff = self.min_cutoff + self.beta * np.linalg.norm(self.dx)

        # 3. 滤波位置
        alpha = self._smoothing_factor(dt, cutoff)
        self.x = self._exponential_smoothing(alpha, measurement, self.x)

        return self.x

    def reset(self, initial_state=None):
        """重置滤波器"""
        if initial_state is not None:
            self.x = np.array(initial_state).copy()
        else:
            self.x = np.zeros(self.dim)
        self.dx = np.zeros(self.dim)
        self.last_time = None
        self.initialized = False

    def get_velocity(self):
        """返回速度估计"""
        return self.dx.copy()


# ============================================================================
# 测试代码
# ============================================================================
if __name__ == "__main__":
    import matplotlib.pyplot as plt

    print("🧪 测试 One-Euro 滤波器...")

    # 生成测试信号：正弦波 + 噪声
    dt = 0.01  # 100Hz
    t = np.arange(0, 5, dt)
    signal = np.sin(2 * np.pi * 1.0 * t)  # 1Hz 正弦波
    noise = np.random.randn(len(t)) * 0.1  # 高斯噪声
    noisy_signal = signal + noise

    # 创建滤波器
    filter_weak = OneEuroFilter(dim=1, min_cutoff=0.5, beta=0.001)
    filter_strong = OneEuroFilter(dim=1, min_cutoff=2.0, beta=0.01)

    # 滤波
    filtered_weak = []
    filtered_strong = []

    for i in range(len(t)):
        measurement = np.array([noisy_signal[i]])
        filtered_weak.append(filter_weak.update(measurement, dt=dt)[0])
        filtered_strong.append(filter_strong.update(measurement, dt=dt)[0])

    # 绘图
    plt.figure(figsize=(12, 6))

    plt.subplot(2, 1, 1)
    plt.plot(t, signal, 'g-', label='Ground Truth', linewidth=2)
    plt.plot(t, noisy_signal, 'r.', label='Noisy', alpha=0.3, markersize=2)
    plt.plot(t, filtered_weak, 'b-', label='One-Euro (weak)', linewidth=1.5)
    plt.plot(t, filtered_strong, 'm-', label='One-Euro (strong)', linewidth=1.5)
    plt.xlabel('Time (s)')
    plt.ylabel('Signal')
    plt.title('One-Euro Filter Performance')
    plt.legend()
    plt.grid(True)

    # 计算误差
    error_weak = np.abs(np.array(filtered_weak) - signal)
    error_strong = np.abs(np.array(filtered_strong) - signal)

    plt.subplot(2, 1, 2)
    plt.plot(t, error_weak, 'b-', label='Error (weak)', linewidth=1.5)
    plt.plot(t, error_strong, 'm-', label='Error (strong)', linewidth=1.5)
    plt.xlabel('Time (s)')
    plt.ylabel('Absolute Error')
    plt.title('Filtering Error')
    plt.legend()
    plt.grid(True)

    plt.tight_layout()
    plt.savefig('one_euro_filter_test.png', dpi=150)
    print(f"✅ 测试完成！图像已保存到 one_euro_filter_test.png")

    # 打印统计
    print(f"\n统计信息:")
    print(f"  Weak filter - Mean error: {np.mean(error_weak):.4f}, Std: {np.std(error_weak):.4f}")
    print(f"  Strong filter - Mean error: {np.mean(error_strong):.4f}, Std: {np.std(error_strong):.4f}")