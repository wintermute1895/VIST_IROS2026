#!/usr/bin/env python3
"""
滤波器基类 - 统一接口
用于消融实验中的滤波器切换

Author: VIST Project
Date: 2026-02-22
"""

import numpy as np
from abc import ABC, abstractmethod


class BaseFilter(ABC):
    """
    滤波器基类

    所有滤波器必须实现此接口，以确保消融实验的公平性
    """

    def __init__(self, dim):
        """
        初始化滤波器

        Args:
            dim: 状态维度（例如关节数量）
        """
        self.dim = dim
        self.initialized = False

    @abstractmethod
    def update(self, measurement, dt=None, **kwargs):
        """
        更新滤波器状态

        Args:
            measurement: 观测值 (dim,)
            dt: 时间步长（秒），可选
            **kwargs: 其他参数（例如意图因子 alpha）

        Returns:
            filtered_state: 滤波后的状态 (dim,)
        """
        pass

    @abstractmethod
    def reset(self, initial_state=None):
        """
        重置滤波器状态

        Args:
            initial_state: 初始状态 (dim,)，可选
        """
        pass

    @abstractmethod
    def get_velocity(self):
        """
        获取速度估计

        Returns:
            velocity: 速度估计 (dim,)
        """
        pass

    def get_name(self):
        """获取滤波器名称"""
        return self.__class__.__name__


class NoFilter(BaseFilter):
    """
    无滤波器（直通）
    用作消融实验的对照组
    """

    def __init__(self, dim):
        super().__init__(dim)
        self.state = np.zeros(dim)
        self.velocity = np.zeros(dim)
        self.last_state = np.zeros(dim)
        self.last_time = 0.0

    def update(self, measurement, dt=None, **kwargs):
        """直接返回观测值"""
        if not self.initialized:
            self.state = np.array(measurement).copy()
            self.last_state = self.state.copy()
            self.initialized = True
            return self.state

        # 更新状态
        self.last_state = self.state.copy()
        self.state = np.array(measurement).copy()

        # 计算速度
        if dt is not None and dt > 0:
            self.velocity = (self.state - self.last_state) / dt

        return self.state

    def reset(self, initial_state=None):
        """重置状态"""
        if initial_state is not None:
            self.state = np.array(initial_state).copy()
        else:
            self.state = np.zeros(self.dim)
        self.velocity = np.zeros(self.dim)
        self.last_state = self.state.copy()
        self.initialized = False

    def get_velocity(self):
        """返回速度估计"""
        return self.velocity.copy()


class MovingAverageFilter(BaseFilter):
    """
    移动平均滤波器
    简单的基线方法
    """

    def __init__(self, dim, window_size=5):
        super().__init__(dim)
        self.window_size = window_size
        self.buffer = []
        self.state = np.zeros(dim)
        self.velocity = np.zeros(dim)
        self.last_state = np.zeros(dim)

    def update(self, measurement, dt=None, **kwargs):
        """移动平均滤波"""
        measurement = np.array(measurement)

        # 添加到缓冲区
        self.buffer.append(measurement)
        if len(self.buffer) > self.window_size:
            self.buffer.pop(0)

        # 计算平均值
        self.last_state = self.state.copy()
        self.state = np.mean(self.buffer, axis=0)

        # 计算速度
        if dt is not None and dt > 0:
            self.velocity = (self.state - self.last_state) / dt

        if not self.initialized:
            self.initialized = True

        return self.state

    def reset(self, initial_state=None):
        """重置状态"""
        self.buffer = []
        if initial_state is not None:
            self.state = np.array(initial_state).copy()
        else:
            self.state = np.zeros(self.dim)
        self.velocity = np.zeros(self.dim)
        self.last_state = self.state.copy()
        self.initialized = False

    def get_velocity(self):
        """返回速度估计"""
        return self.velocity.copy()


# ============================================================================
# 测试代码
# ============================================================================
if __name__ == "__main__":
    print("🧪 测试滤波器基类...")

    # 测试无滤波器
    print("\n测试 NoFilter:")
    no_filter = NoFilter(dim=3)

    for i in range(5):
        measurement = np.array([i, i*2, i*3]) + np.random.randn(3) * 0.1
        filtered = no_filter.update(measurement, dt=0.01)
        velocity = no_filter.get_velocity()
        print(f"  Step {i}: filtered={filtered}, velocity={velocity}")

    # 测试移动平均滤波器
    print("\n测试 MovingAverageFilter:")
    ma_filter = MovingAverageFilter(dim=3, window_size=3)

    for i in range(5):
        measurement = np.array([i, i*2, i*3]) + np.random.randn(3) * 0.1
        filtered = ma_filter.update(measurement, dt=0.01)
        velocity = ma_filter.get_velocity()
        print(f"  Step {i}: filtered={filtered}, velocity={velocity}")

    print("\n✅ 测试完成！")