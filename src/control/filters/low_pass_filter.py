#!/usr/bin/env python3
"""
低通滤波器 - 用于平滑关节角度输出
使用指数移动平均(EMA)实现

Author: VIST Project
Date: 2026-02-22
"""

import numpy as np


class LowPassFilter:
    """
    低通滤波器（指数移动平均）

    输出公式：y[k] = α * x[k] + (1-α) * y[k-1]
    其中 α ∈ [0, 1] 是平滑系数：
    - α = 1: 无滤波（直接输出输入）
    - α = 0: 完全平滑（输出不变）
    - α = 0.1-0.3: 强平滑（推荐用于抑制跳变）
    """

    def __init__(self, alpha: float = 0.2, n_dims: int = 7):
        """
        初始化低通滤波器

        Args:
            alpha: 平滑系数 (0-1)，越小越平滑
            n_dims: 状态维度（关节数量）
        """
        self.alpha = alpha
        self.n_dims = n_dims
        self.y_prev = None
        self.initialized = False

    def reset(self, initial_value: np.ndarray = None):
        """重置滤波器状态"""
        if initial_value is not None:
            self.y_prev = initial_value.copy()
            self.initialized = True
        else:
            self.y_prev = None
            self.initialized = False

    def update(self, x: np.ndarray) -> np.ndarray:
        """
        更新滤波器并返回平滑后的输出

        Args:
            x: 输入信号 (n_dims,)

        Returns:
            y: 平滑后的输出 (n_dims,)
        """
        if not self.initialized:
            # 第一帧：直接使用输入值初始化
            self.y_prev = x.copy()
            self.initialized = True
            return self.y_prev.copy()

        # 指数移动平均
        y = self.alpha * x + (1 - self.alpha) * self.y_prev
        self.y_prev = y.copy()

        return y

    def set_alpha(self, alpha: float):
        """动态调整平滑系数"""
        self.alpha = np.clip(alpha, 0.0, 1.0)