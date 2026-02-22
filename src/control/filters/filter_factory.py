#!/usr/bin/env python3
"""
滤波器工厂 - 统一创建接口
用于消融实验中的滤波器切换

Author: VIST Project
Date: 2026-02-22
"""

from .base_filter import NoFilter, MovingAverageFilter
from .one_euro_filter import OneEuroFilter


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
                - "none": 无滤波器（直通）
                - "moving_average": 移动平均滤波器
                - "one_euro": One-Euro 滤波器
                - "adaptive_kalman": 自适应卡尔曼滤波器（VIST）
            dim: 状态维度
            **kwargs: 滤波器特定参数

        Returns:
            filter: 滤波器实例
        """
        if filter_type == "none":
            return NoFilter(dim)

        elif filter_type == "moving_average":
            window_size = kwargs.get('window_size', 5)
            return MovingAverageFilter(dim, window_size=window_size)

        elif filter_type == "one_euro":
            min_cutoff = kwargs.get('min_cutoff', 1.0)
            beta = kwargs.get('beta', 0.007)
            d_cutoff = kwargs.get('d_cutoff', 1.0)
            return OneEuroFilter(dim, min_cutoff=min_cutoff, beta=beta, d_cutoff=d_cutoff)

        elif filter_type == "adaptive_kalman":
            # 这里返回 None，表示使用 VIST 的原生卡尔曼滤波
            # 在 VIST 控制器中会特殊处理
            return None

        else:
            raise ValueError(f"未知的滤波器类型: {filter_type}")

    @staticmethod
    def get_available_filters():
        """获取可用的滤波器列表"""
        return ["none", "moving_average", "one_euro", "adaptive_kalman"]


# ============================================================================
# 测试代码
# ============================================================================
if __name__ == "__main__":
    print("🧪 测试滤波器工厂...")

    # 测试创建不同类型的滤波器
    filters = {
        "none": FilterFactory.create_filter("none", dim=7),
        "moving_average": FilterFactory.create_filter("moving_average", dim=7, window_size=3),
        "one_euro": FilterFactory.create_filter("one_euro", dim=7, min_cutoff=1.0, beta=0.007),
    }

    print("\n可用的滤波器:")
    for name, filter_obj in filters.items():
        if filter_obj is not None:
            print(f"  - {name}: {filter_obj.get_name()}")

    print("\n✅ 测试完成！")