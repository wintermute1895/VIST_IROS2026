#!/usr/bin/env python3
"""
VIST Kalman Filter - 基础版本（渐进式开发 v1.0）

从最简单的线性卡尔曼滤波开始，逐步叠加功能：
v1.0: 基础恒速模型 + 固定噪声
v2.0: 添加意图检测
v3.0: 添加动态噪声调度
v4.0: 添加协方差回拉
"""

import numpy as np
import time


class VISTKalmanFilter:
    """
    VIST 卡尔曼滤波器 - 基础版本 v1.0

    状态向量: x = [θ, θ̇]^T  (14维)
    - θ: 7个关节角度
    - θ̇: 7个关节速度

    过程模型: x(k+1) = F·x(k) + w(k)
    - F: 恒速模型状态转移矩阵
    - w: 过程噪声（固定协方差）

    观测模型: z = H·x + v
    - z: 观测关节角度
    - v: 观测噪声（固定协方差）
    """

    def __init__(self, ik_solver, config, geometric_solver=None):
        """
        初始化基础卡尔曼滤波器

        Args:
            ik_solver: IK 求解器实例（保留接口兼容性）
            config: 配置对象
            geometric_solver: 几何求解器（保留接口兼容性）
        """
        self.ik_solver = ik_solver
        self.config = config
        self.geometric_solver = geometric_solver

        # 状态空间维度
        self.n_joints = 7
        self.state_dim = 14  # 2 * n_joints

        # 时间步长
        self.dt = 0.0125  # 80Hz

        # 初始化状态向量和协方差
        self.state = np.zeros(self.state_dim)  # [θ, θ̇]
        self.P = np.eye(self.state_dim)  # 状态协方差矩阵

        # 初始化协方差（位置和速度）
        self.P[:self.n_joints, :self.n_joints] *= 0.01  # 位置初始方差
        self.P[self.n_joints:, self.n_joints:] *= 0.1   # 速度初始方差

        # 构建状态转移矩阵 F（恒速模型）
        # F = [I  dt*I]
        #     [0   I  ]
        self.F = np.eye(self.state_dim)
        self.F[:self.n_joints, self.n_joints:] = self.dt * np.eye(self.n_joints)

        # 构建观测矩阵 H（只观测位置）
        # H = [I  0]
        self.H = np.zeros((self.n_joints, self.state_dim))
        self.H[:self.n_joints, :self.n_joints] = np.eye(self.n_joints)

        # 固定过程噪声协方差 Q
        # 使用离散化的恒速模型噪声
        q_std = 0.01  # 过程噪声标准差
        Q_vel = q_std**2 * np.eye(self.n_joints)

        self.Q = np.zeros((self.state_dim, self.state_dim))
        self.Q[:self.n_joints, :self.n_joints] = (self.dt**3 / 3.0) * Q_vel
        self.Q[:self.n_joints, self.n_joints:] = (self.dt**2 / 2.0) * Q_vel
        self.Q[self.n_joints:, :self.n_joints] = (self.dt**2 / 2.0) * Q_vel
        self.Q[self.n_joints:, self.n_joints:] = self.dt * Q_vel

        # 固定观测噪声协方差 R
        r_std = 0.05  # 观测噪声标准差
        self.R = (r_std**2) * np.eye(self.n_joints)

        # 第一帧标志
        self._is_first_frame = True

        # 统计信息
        self.iteration_count = 0
        self.last_update_time = None

        print("✅ VIST卡尔曼滤波器初始化完成（基础版本 v1.0）")
        print(f"   - 状态维度: {self.state_dim} (7关节 × 2)")
        print(f"   - 时间步长: {self.dt}s ({1.0/self.dt:.1f}Hz)")
        print(f"   - 过程噪声: q_std={q_std}")
        print(f"   - 观测噪声: r_std={r_std}")

    def update(self, shadow_joints, target_pose, virtual_joints=None):
        """
        卡尔曼滤波器主更新函数

        Args:
            shadow_joints: 观测关节角度（来自遥操臂）
            target_pose: 目标末端位姿（保留接口兼容性，暂不使用）
            virtual_joints: 虚拟引导关节角度（保留接口兼容性，暂不使用）

        Returns:
            filtered_joints: 滤波后的关节角度
        """
        self.iteration_count += 1

        # 转换为 numpy 数组
        z = np.array(shadow_joints)

        # 第一帧：初始化状态为观测值
        if self._is_first_frame:
            print(f"[VIST v1.0] 第一帧同步")
            print(f"  观测值: {z}")
            self.state[:self.n_joints] = z.copy()
            self.state[self.n_joints:] = 0.0  # 速度初始化为0
            self._is_first_frame = False
            print(f"  初始化完成\n")

        # 动态更新时间步长
        current_time = time.time()
        if self.last_update_time is not None:
            actual_dt = current_time - self.last_update_time
            if 0.001 < actual_dt < 0.1:  # 10Hz到1000Hz之间
                self.F[:self.n_joints, self.n_joints:] = actual_dt * np.eye(self.n_joints)
        self.last_update_time = current_time

        # ==========================================
        # 卡尔曼滤波标准流程
        # ==========================================

        # 1. 预测步骤
        # 状态预测: x̂_{k|k-1} = F * x̂_{k-1}
        x_pred = self.F @ self.state

        # 协方差预测: P_{k|k-1} = F * P_{k-1} * F^T + Q
        P_pred = self.F @ self.P @ self.F.T + self.Q

        # 2. 更新步骤
        # 创新（innovation）: y = z - H * x̂_{k|k-1}
        innovation = z - self.H @ x_pred

        # 创新协方差: S = H * P_{k|k-1} * H^T + R
        S = self.H @ P_pred @ self.H.T + self.R

        # 卡尔曼增益: K = P_{k|k-1} * H^T * S^{-1}
        K = P_pred @ self.H.T @ np.linalg.inv(S)

        # 状态更新: x̂_k = x̂_{k|k-1} + K * y
        self.state = x_pred + K @ innovation

        # 协方差更新: P_k = (I - K * H) * P_{k|k-1}
        I = np.eye(self.state_dim)
        self.P = (I - K @ self.H) @ P_pred

        # 提取滤波后的关节角度
        filtered_joints = self.state[:self.n_joints].copy()

        # 每100帧打印一次统计信息
        if self.iteration_count % 100 == 0:
            print(f"\n[VIST v1.0] 第{self.iteration_count}帧统计:")
            print(f"  观测值: {z[:3]}... (前3个关节)")
            print(f"  滤波值: {filtered_joints[:3]}... (前3个关节)")
            print(f"  速度估计: {self.state[self.n_joints:self.n_joints+3]}... (前3个关节)")
            print(f"  创新范数: {np.linalg.norm(innovation):.6f}")
            print(f"  增益范数: {np.linalg.norm(K):.6f}\n")

        return filtered_joints

    def reset(self, initial_joints=None):
        """重置滤波器状态"""
        if initial_joints is not None:
            self.state[:self.n_joints] = initial_joints
        else:
            self.state = np.zeros(self.state_dim)

        self.P = np.eye(self.state_dim)
        self.P[:self.n_joints, :self.n_joints] *= 0.01
        self.P[self.n_joints:, self.n_joints:] *= 0.1

        self._is_first_frame = True
        print("✅ VIST卡尔曼滤波器已重置")

    def get_velocity_estimate(self):
        """获取速度估计"""
        return self.state[self.n_joints:]

    def get_intent_factor(self):
        """获取意图因子（v1.0暂不支持，返回0）"""
        return 0.0
