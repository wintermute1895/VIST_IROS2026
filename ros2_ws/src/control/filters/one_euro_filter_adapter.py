#!/usr/bin/env python3
"""
One-Euro Filter Adapter
适配现有的OneEuroFilter到BaseFilter接口

Author: VIST Project
Date: 2026-02-25
"""

import numpy as np
import sys
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from src.control.filters.base_filter import BaseFilter
from src.core.one_euro_filter import OneEuroFilter


class OneEuroFilterAdapter(BaseFilter):
    """
    One-Euro滤波器适配器

    将现有的OneEuroFilter适配到BaseFilter接口
    用于消融实验中的统一接口
    """

    def __init__(self, dim, min_cutoff=1.0, beta=0.007, d_cutoff=1.0):
        """
        初始化One-Euro滤波器

        Args:
            dim: 状态维度（例如关节数量）
            min_cutoff: 最小截止频率 (Hz)，控制低速时的平滑度
            beta: 速度系数，控制对快速运动的响应
            d_cutoff: 导数截止频率 (Hz)，平滑速度估计
        """
        super().__init__(dim)
        self.min_cutoff = min_cutoff
        self.beta = beta
        self.d_cutoff = d_cutoff

        # 为每个维度创建独立的One-Euro滤波器
        self.filters = [
            OneEuroFilter(min_cutoff=min_cutoff, beta=beta, d_cutoff=d_cutoff)
            for _ in range(dim)
        ]

        self.state = np.zeros(dim)
        self.velocity = np.zeros(dim)
        self.last_state = np.zeros(dim)
        self.current_time = 0.0

    def update(self, measurement, dt=None, **kwargs):
        """
        更新滤波器状态

        Args:
            measurement: 观测值 (dim,)
            dt: 时间步长（秒），用于时间戳
            **kwargs: 其他参数

        Returns:
            filtered_state: 滤波后的状态 (dim,)
        """
        measurement = np.array(measurement, dtype=np.float64)

        # 更新时间戳
        if dt is not None:
            self.current_time += dt
        else:
            self.current_time += 0.01  # 默认10ms

        # 对每个维度应用One-Euro滤波
        filtered = np.zeros(self.dim)
        for i in range(self.dim):
            filtered[i] = self.filters[i](measurement[i], self.current_time)

        # 更新状态
        self.last_state = self.state.copy()
        self.state = filtered.copy()

        # 计算速度（数值微分）
        if dt is not None and dt > 0:
            self.velocity = (self.state - self.last_state) / dt
        else:
            self.velocity = np.zeros(self.dim)

        if not self.initialized:
            self.initialized = True

        return self.state.copy()

    def reset(self, initial_state=None):
        """
        重置滤波器状态

        Args:
            initial_state: 初始状态 (dim,)，可选
        """
        # 重置所有One-Euro滤波器
        for f in self.filters:
            f.reset()

        if initial_state is not None:
            self.state = np.array(initial_state, dtype=np.float64).copy()
        else:
            self.state = np.zeros(self.dim)

        self.velocity = np.zeros(self.dim)
        self.last_state = self.state.copy()
        self.current_time = 0.0
        self.initialized = False

    def get_velocity(self):
        """
        获取速度估计

        Returns:
            velocity: 速度估计 (dim,)
        """
        return self.velocity.copy()


# ============================================================================
# 测试代码
# ============================================================================
if __name__ == "__main__":
    print("🧪 测试One-Euro滤波器适配器...")

    # 创建滤波器
    one_euro = OneEuroFilterAdapter(dim=3, min_cutoff=1.0, beta=0.007)

    print("\n测试One-Euro滤波:")
    for i in range(10):
        # 模拟带噪声的测量
        true_value = np.array([i, i*2, i*3])
        noise = np.random.randn(3) * 0.5
        measurement = true_value + noise

        filtered = one_euro.update(measurement, dt=0.01)
        velocity = one_euro.get_velocity()

        print(f"  Step {i}: meas={measurement.round(2)}, "
              f"filtered={filtered.round(2)}, vel={velocity.round(2)}")

    print("\n✅ 测试完成！")