#!/usr/bin/env python3
"""
EMA (Exponential Moving Average) Filter
指数移动平均滤波器 - 用于消融实验

Author: VIST Project
Date: 2026-02-25
"""

import numpy as np
from .base_filter import BaseFilter


class EMAFilter(BaseFilter):
    """
    指数移动平均滤波器

    公式: x_new = alpha * x_current + (1 - alpha) * x_prev

    参数:
        alpha: 平滑系数 [0, 1]
            - alpha = 1: 无滤波（直通）
            - alpha = 0: 完全平滑（不响应新数据）
            - 典型值: 0.1 - 0.5
    """

    def __init__(self, dim, alpha=0.3):
        """
        初始化EMA滤波器

        Args:
            dim: 状态维度（例如关节数量）
            alpha: 平滑系数 [0, 1]，默认0.3
        """
        super().__init__(dim)
        self.alpha = np.clip(alpha, 0.0, 1.0)
        self.state = np.zeros(dim)
        self.velocity = np.zeros(dim)
        self.last_state = np.zeros(dim)
        self.last_time = 0.0

    def update(self, measurement, dt=None, **kwargs):
        """
        更新滤波器状态

        Args:
            measurement: 观测值 (dim,)
            dt: 时间步长（秒），用于计算速度
            **kwargs: 其他参数（EMA不使用）

        Returns:
            filtered_state: 滤波后的状态 (dim,)
        """
        measurement = np.array(measurement, dtype=np.float64)

        if not self.initialized:
            # 首次初始化
            self.state = measurement.copy()
            self.last_state = self.state.copy()
            self.initialized = True
            return self.state.copy()

        # EMA滤波
        self.last_state = self.state.copy()
        self.state = self.alpha * measurement + (1.0 - self.alpha) * self.state

        # 计算速度（数值微分）
        if dt is not None and dt > 0:
            self.velocity = (self.state - self.last_state) / dt
        else:
            self.velocity = np.zeros(self.dim)

        return self.state.copy()

    def reset(self, initial_state=None):
        """
        重置滤波器状态

        Args:
            initial_state: 初始状态 (dim,)，可选
        """
        if initial_state is not None:
            self.state = np.array(initial_state, dtype=np.float64).copy()
        else:
            self.state = np.zeros(self.dim)
        self.velocity = np.zeros(self.dim)
        self.last_state = self.state.copy()
        self.initialized = False

    def get_velocity(self):
        """
        获取速度估计

        Returns:
            velocity: 速度估计 (dim,)
        """
        return self.velocity.copy()

    def set_alpha(self, alpha):
        """
        动态调整平滑系数

        Args:
            alpha: 新的平滑系数 [0, 1]
        """
        self.alpha = np.clip(alpha, 0.0, 1.0)


# ============================================================================
# 测试代码
# ============================================================================
if __name__ == "__main__":
    print("🧪 测试EMA滤波器...")

    # 创建滤波器
    ema = EMAFilter(dim=3, alpha=0.3)

    print("\n测试EMA滤波 (alpha=0.3):")
    for i in range(10):
        # 模拟带噪声的测量
        true_value = np.array([i, i*2, i*3])
        noise = np.random.randn(3) * 0.5
        measurement = true_value + noise

        filtered = ema.update(measurement, dt=0.01)
        velocity = ema.get_velocity()

        print(f"  Step {i}: meas={measurement.round(2)}, "
              f"filtered={filtered.round(2)}, vel={velocity.round(2)}")

    print("\n✅ 测试完成！")