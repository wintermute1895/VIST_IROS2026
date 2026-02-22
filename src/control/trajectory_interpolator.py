#!/usr/bin/env python3
"""
轨迹插值器 - 梯形速度曲线
用于生成平滑的关节轨迹，避免突然的速度/加速度变化

Author: VIST Project
Date: 2026-02-22
"""

import numpy as np


class TrajectoryInterpolator:
    """
    梯形速度曲线插值器

    功能：
    1. 在当前位置和目标位置之间生成平滑的中间点
    2. 确保速度和加速度连续变化（无突变）
    3. 遵守速度和加速度限制

    原理：
    - 加速阶段：以恒定加速度加速到最大速度
    - 匀速阶段：保持最大速度运动
    - 减速阶段：以恒定加速度减速到零

    这样可以避免"咣当"现象（突然的方向改变）
    """

    def __init__(self, max_velocity, max_acceleration, dt):
        """
        初始化插值器

        Args:
            max_velocity: 最大关节速度 (rad/s)
            max_acceleration: 最大关节加速度 (rad/s²)
            dt: 控制周期 (s)
        """
        self.max_vel = max_velocity
        self.max_acc = max_acceleration
        self.dt = dt

        # 状态变量
        self.q_current = None  # 当前位置
        self.q_dot_current = np.zeros(7)  # 当前速度

        print("✅ [TrajectoryInterpolator] 梯形速度曲线插值器初始化完成")
        print(f"   最大速度: {self.max_vel} rad/s")
        print(f"   最大加速度: {self.max_acc} rad/s²")
        print(f"   控制周期: {self.dt} s")

    def reset(self, q_init):
        """
        重置插值器状态

        Args:
            q_init: 初始关节角度 (7,)
        """
        self.q_current = np.array(q_init).copy()
        self.q_dot_current = np.zeros(7)

    def interpolate(self, q_target):
        """
        生成下一个平滑的中间点（梯形速度曲线）

        Args:
            q_target: 目标关节角度 (7,)

        Returns:
            q_next: 下一个平滑的关节角度 (7,)

        原理：
        1. 计算期望速度（朝向目标）
        2. 限制速度变化（加速度限制）- 这是关键！
        3. 限制最大速度
        4. 更新位置

        这样可以确保：
        - 速度连续变化（无突变）
        - 加速度在限制范围内
        - 不会出现"咣当"现象
        """
        # 第一次调用，初始化
        if self.q_current is None:
            self.q_current = np.array(q_target).copy()
            return self.q_current

        # 1. 计算期望速度（朝向目标）
        q_error = q_target - self.q_current
        q_dot_desired = q_error / self.dt

        # 2. 限制速度变化（加速度限制）- 关键步骤！
        # 这一步确保速度不会突然跳变
        q_dot_change = q_dot_desired - self.q_dot_current
        max_change = self.max_acc * self.dt  # 一个周期内允许的最大速度变化
        q_dot_change = np.clip(q_dot_change, -max_change, max_change)

        # 3. 更新速度
        self.q_dot_current = self.q_dot_current + q_dot_change

        # 4. 限制最大速度
        self.q_dot_current = np.clip(
            self.q_dot_current, -self.max_vel, self.max_vel
        )

        # 5. 计算新位置
        q_next = self.q_current + self.q_dot_current * self.dt
        self.q_current = q_next

        return q_next

    def get_current_velocity(self):
        """
        获取当前速度

        Returns:
            q_dot_current: 当前关节速度 (7,)
        """
        return self.q_dot_current.copy()