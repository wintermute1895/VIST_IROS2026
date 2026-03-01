#!/usr/bin/env python3
"""
滤波器工厂 - 统一创建接口
用于消融实验中的滤波器切换

Author: VIST Project
Date: 2026-02-25 (Updated)
"""

from .base_filter import NoFilter, MovingAverageFilter
from .ema_filter import EMAFilter
from .one_euro_filter_adapter import OneEuroFilterAdapter


class FilterFactory:
    """
    滤波器工厂类

    用于根据配置创建不同类型的滤波器
    """

    @staticmethod
    def create_filter(filter_type, dim, **kwargs):
        """
        创建滤波器

        Args:
            filter_type: 滤波器类型
                - "none": 无滤波器（直通）- 消融实验对照组
                - "moving_average": 移动平均滤波器 - 基线方法
                - "ema": 指数移动平均滤波器 - 简单平滑
                - "one_euro": One-Euro 滤波器 - 自适应平滑
                - "vist_kalman": VIST卡尔曼滤波器 - 双源融合
            dim: 状态维度（例如7个关节）
            **kwargs: 滤波器特定参数

        Returns:
            filter: 滤波器实例（BaseFilter子类）

        Raises:
            ValueError: 未知的滤波器类型
        """
        if filter_type == "none":
            return NoFilter(dim)

        elif filter_type == "moving_average":
            window_size = kwargs.get('window_size', 5)
            return MovingAverageFilter(dim, window_size=window_size)

        elif filter_type == "ema":
            alpha = kwargs.get('alpha', 0.3)
            return EMAFilter(dim, alpha=alpha)

        elif filter_type == "one_euro":
            min_cutoff = kwargs.get('min_cutoff', 1.0)
            beta = kwargs.get('beta', 0.007)
            d_cutoff = kwargs.get('d_cutoff', 1.0)
            return OneEuroFilterAdapter(dim, min_cutoff=min_cutoff, beta=beta, d_cutoff=d_cutoff)

        elif filter_type == "vist_kalman":
            # VIST卡尔曼滤波器需要特殊处理
            # 返回None，由调用者使用VISTKalmanFilter
            return None

        else:
            raise ValueError(f"未知的滤波器类型: {filter_type}. "
                           f"可用类型: {FilterFactory.get_available_filters()}")

    @staticmethod
    def get_available_filters():
        """获取可用的滤波器列表"""
        return ["none", "moving_average", "ema", "one_euro", "vist_kalman"]

    @staticmethod
    def get_filter_description(filter_type):
        """
        获取滤波器描述

        Args:
            filter_type: 滤波器类型

        Returns:
            description: 滤波器描述字符串
        """
        descriptions = {
            "none": "无滤波（直通）- 消融实验对照组",
            "moving_average": "移动平均滤波器 - 简单基线方法",
            "ema": "指数移动平均 - 轻量级平滑",
            "one_euro": "One-Euro滤波器 - 自适应平滑，响应快速运动",
            "vist_kalman": "VIST卡尔曼滤波器 - 双源融合，意图检测"
        }
        return descriptions.get(filter_type, "未知滤波器")


# ============================================================================
# 测试代码
# ============================================================================
if __name__ == "__main__":
    import numpy as np

    print("🧪 测试滤波器工厂...")

    # 显示可用的滤波器
    print("\n可用的滤波器:")
    for filter_type in FilterFactory.get_available_filters():
        desc = FilterFactory.get_filter_description(filter_type)
        print(f"  - {filter_type:20s}: {desc}")

    # 测试创建不同类型的滤波器
    print("\n创建滤波器实例:")
    filters = {
        "none": FilterFactory.create_filter("none", dim=7),
        "moving_average": FilterFactory.create_filter("moving_average", dim=7, window_size=3),
        "ema": FilterFactory.create_filter("ema", dim=7, alpha=0.3),
        "one_euro": FilterFactory.create_filter("one_euro", dim=7, min_cutoff=1.0, beta=0.007),
    }

    for name, filter_obj in filters.items():
        if filter_obj is not None:
            print(f"  ✓ {name:20s}: {filter_obj.get_name()}")

    # 测试滤波效果
    print("\n测试滤波效果 (10步，带噪声):")
    test_data = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0])

    for i in range(5):
        measurement = test_data + np.random.randn(7) * 0.1
        print(f"\n  Step {i}:")
        for name, filter_obj in filters.items():
            if filter_obj is not None:
                filtered = filter_obj.update(measurement, dt=0.01)
                print(f"    {name:15s}: {filtered[0]:.3f}")

    print("\n✅ 测试完成！")