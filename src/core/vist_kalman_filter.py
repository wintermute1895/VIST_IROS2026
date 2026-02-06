#!/usr/bin/env python3
"""
VIST Kalman Filter - 基于意图感知的遥操作统一状态估计框架

核心功能：
1. 卡尔曼滤波状态估计（关节空间）
2. 微分 IK 观测模型
3. 意图驱动的协方差调度
4. 各向异性过程噪声（肘部约束）

参考文档：docs/VIST_modeling.md
"""

import numpy as np
import pinocchio as pin
from scipy.linalg import inv


class VISTKalmanFilter:
    """
    VIST 卡尔曼滤波器

    状态向量: x = [θ, θ̇]^T  (14维)
    - θ: 7个关节角度
    - θ̇: 7个关节速度

    过程模型: x(k+1) = F·x(k) + w(k)
    - F: 恒速模型状态转移矩阵
    - w: 各向异性过程噪声（肘部方差更小）

    观测模型: z = H·x + v
    - z: [Δθ_human, Δθ_virtual]^T
    - Δθ_human: 人类指令（直接映射）
    - Δθ_virtual: 虚拟引导（微分 IK）
    - v: 意图驱动的观测噪声
    """

    def __init__(self, ik_solver, config):
        """
        初始化 VIST 卡尔曼滤波器

        Args:
            ik_solver: IK 求解器实例（用于微分 IK）
            config: 配置对象
        """
        self.ik_solver = ik_solver
        self.config = config

        # 状态空间维度
        self.n_joints = config.vist_n_joints
        self.state_dim = config.vist_state_dim  # 2 * n_joints

        # 时间步长
        self.dt = config.vist_process_dt

        # ==========================================
        # 1. 初始化状态向量和协方差
        # ==========================================
        self.state = np.zeros(self.state_dim)  # [θ, θ̇]
        self.P = np.eye(self.state_dim)  # 状态协方差矩阵

        # 初始化协方差
        self.P[:self.n_joints, :self.n_joints] *= config.vist_initial_state_variance
        self.P[self.n_joints:, self.n_joints:] *= config.vist_initial_velocity_variance

        # ==========================================
        # 2. 构建状态转移矩阵 F（恒速模型）
        # ==========================================
        # F = [I  dt*I]
        #     [0   I  ]
        self.F = np.eye(self.state_dim)
        self.F[:self.n_joints, self.n_joints:] = self.dt * np.eye(self.n_joints)

        # ==========================================
        # 3. 构建过程噪声协方差 Q（各向异性）
        # ==========================================
        self.Q = self._build_process_noise_covariance()

        # ==========================================
        # 4. 构建观测矩阵 H
        # ==========================================
        # 观测向量 z = [Δθ_human, Δθ_virtual]^T (14维)
        # H = [I  0]  (只观测位置，不观测速度)
        #     [I  0]
        self.H = np.zeros((2 * self.n_joints, self.state_dim))
        self.H[:self.n_joints, :self.n_joints] = np.eye(self.n_joints)
        self.H[self.n_joints:, :self.n_joints] = np.eye(self.n_joints)

        # ==========================================
        # 5. 意图检测状态
        # ==========================================
        self.alpha = 0.0  # 意图因子 (0=自由移动, 1=精密操作)
        self.alpha_smoothed = 0.0  # 平滑后的意图因子

        # ==========================================
        # 6. 历史数据（用于计算人类指令增量）
        # ==========================================
        self.previous_target_pos = None  # 上一帧目标位置

        # ==========================================
        # 7. 统计信息
        # ==========================================
        self.iteration_count = 0

    def _build_process_noise_covariance(self):
        """
        构建各向异性过程噪声协方差矩阵 Q

        特点：肘部关节的方差更小，防止 7-DoF 肘部漂移

        Returns:
            Q: 过程噪声协方差矩阵 (state_dim x state_dim)
        """
        Q = np.zeros((self.state_dim, self.state_dim))

        # 位置部分（关节角度）
        pos_variance = self.config.vist_position_variance
        Q[:self.n_joints, :self.n_joints] = pos_variance * np.eye(self.n_joints)

        # 速度部分（关节速度）
        vel_variance = self.config.vist_velocity_variance
        Q[self.n_joints:, self.n_joints:] = vel_variance * np.eye(self.n_joints)

        # 肘部约束：降低肘部关节的方差
        elbow_indices = self.config.vist_elbow_joint_indices
        elbow_damping = self.config.vist_elbow_damping_factor

        for idx in elbow_indices:
            if idx < self.n_joints:
                Q[idx, idx] *= elbow_damping
                Q[self.n_joints + idx, self.n_joints + idx] *= elbow_damping

        return Q

    def _build_observation_noise_covariance(self):
        """
        构建意图驱动的观测噪声协方差矩阵 R

        R = [R_human    0      ]
            [0       R_virtual]

        - R_human: 人类指令噪声（α → 0 时增大，强力去噪）
        - R_virtual: 虚拟引导噪声（α → 1 时减小，磁吸引导）

        Returns:
            R: 观测噪声协方差矩阵 (2*n_joints x 2*n_joints)
        """
        R = np.zeros((2 * self.n_joints, 2 * self.n_joints))

        # 人类指令噪声（意图驱动）
        # α → 0: 增大噪声，降低权重（强力去噪）
        # α → 1: 减小噪声，增大权重（跟随人类指令）
        human_variance = self.config.vist_human_base_variance + \
                        (self.config.vist_human_max_variance - self.config.vist_human_base_variance) * \
                        (1.0 - self.alpha_smoothed)
        R[:self.n_joints, :self.n_joints] = human_variance * np.eye(self.n_joints)

        # 虚拟引导噪声（意图驱动）
        # α → 0: 增大噪声，降低权重（自由移动）
        # α → 1: 减小噪声，增大权重（磁吸引导）
        virtual_variance = self.config.vist_virtual_base_variance + \
                          (self.config.vist_virtual_base_variance - self.config.vist_virtual_min_variance) * \
                          (1.0 - self.alpha_smoothed)
        R[self.n_joints:, self.n_joints:] = virtual_variance * np.eye(self.n_joints)

        return R

    def detect_intent(self, target_pos, current_pos, velocity):
        """
        检测操作意图

        意图因子 α ∈ [0, 1]:
        - α → 0: 自由移动模式（快速移动，远离目标）
        - α → 1: 精密操作模式（接近目标，速度慢）

        Args:
            target_pos: 目标位置 (3D)
            current_pos: 当前位置 (3D)
            velocity: 当前速度 (标量或3D)

        Returns:
            alpha: 意图因子
        """
        # 计算距离
        distance = np.linalg.norm(target_pos - current_pos)

        # 计算速度大小
        if np.isscalar(velocity):
            speed = abs(velocity)
        else:
            speed = np.linalg.norm(velocity)

        # Sigmoid 函数：距离越近，α 越大
        # α = 1 / (1 + exp(-k * (d_threshold - distance)))
        d_threshold = self.config.vist_distance_threshold
        k = self.config.vist_sigmoid_k

        alpha_distance = 1.0 / (1.0 + np.exp(-k * (d_threshold - distance)))

        # 速度因子：速度越慢，α 越大
        v_threshold = self.config.vist_velocity_threshold
        alpha_velocity = 1.0 / (1.0 + np.exp(-k * (v_threshold - speed)))

        # 综合意图因子（取平均）
        self.alpha = 0.5 * (alpha_distance + alpha_velocity)

        # EMA 平滑
        smoothing = self.config.vist_intent_smoothing
        self.alpha_smoothed = smoothing * self.alpha_smoothed + (1.0 - smoothing) * self.alpha

        return self.alpha_smoothed

    def compute_differential_ik(self, target_pos, target_quat=None):
        """
        计算微分 IK 观测：Δθ = J†·Δx

        这是 VIST 的核心创新：不计算绝对关节角，而是计算增量
        - 避免全局 IK 的多解问题
        - 天然保证连续性
        - 雅可比伪逆自动寻找最小动能路径

        Args:
            target_pos: 目标位置 (3D)
            target_quat: 目标四元数 (可选，4D)

        Returns:
            delta_theta: 关节角度增量 (n_joints,)
        """
        # 获取当前关节角度（受控关节）
        q_controlled = self.state[:self.n_joints]

        # 扩展到完整模型
        q_full = self._get_full_q_from_controlled(q_controlled)

        # 正运动学：计算当前末端位置
        pin.forwardKinematics(self.ik_solver.model, self.ik_solver.data, q_full)
        pin.updateFramePlacements(self.ik_solver.model, self.ik_solver.data)

        ee_placement = self.ik_solver.data.oMf[self.ik_solver.ee_frame_id]
        current_pos = ee_placement.translation

        # 计算位置误差
        delta_x = target_pos - current_pos

        # 计算雅可比矩阵
        J_full = pin.computeFrameJacobian(
            self.ik_solver.model,
            self.ik_solver.data,
            q_full,
            self.ik_solver.ee_frame_id,
            pin.ReferenceFrame.LOCAL_WORLD_ALIGNED
        )

        # 只使用位置部分（前3行）和受控关节
        J = J_full[:3, self.ik_solver.controlled_indices]

        # 阻尼伪逆：J† = J^T @ (J @ J^T + λ^2 * I)^(-1)
        damping = self.config.vist_differential_ik_damping
        JJT = J @ J.T
        damping_matrix = damping**2 * np.eye(3)
        J_pinv = J.T @ inv(JJT + damping_matrix)

        # 微分观测：Δθ = J†·Δx
        delta_theta = J_pinv @ delta_x

        return delta_theta

    def predict(self):
        """
        卡尔曼滤波预测步骤

        利用恒速模型进行前瞻预测，补偿传输滞后：
        - x_pred = F @ x
        - P_pred = F @ P @ F^T + Q
        """
        # 状态预测
        self.state = self.F @ self.state

        # 协方差预测
        self.P = self.F @ self.P @ self.F.T + self.Q

    def compute_human_delta_theta(self, target_pos, previous_target_pos):
        """
        从人手位置变化计算人类指令增量

        这是 VIST 的关键创新：将人手运动直接转换为关节角度增量
        - 使用微分 IK 将笛卡尔空间的位置变化转换为关节空间
        - 与虚拟引导观测独立，提供人类意图的直接表达

        Args:
            target_pos: 当前人手目标位置 (3D)
            previous_target_pos: 上一帧人手目标位置 (3D)

        Returns:
            human_delta_theta: 人类指令关节角度增量 (n_joints,)
        """
        # 计算人手位置变化
        delta_x_human = target_pos - previous_target_pos

        # 获取当前关节角度
        q_controlled = self.state[:self.n_joints]
        q_full = self._get_full_q_from_controlled(q_controlled)

        # 计算雅可比矩阵
        pin.forwardKinematics(self.ik_solver.model, self.ik_solver.data, q_full)
        pin.updateFramePlacements(self.ik_solver.model, self.ik_solver.data)

        J_full = pin.computeFrameJacobian(
            self.ik_solver.model,
            self.ik_solver.data,
            q_full,
            self.ik_solver.ee_frame_id,
            pin.ReferenceFrame.LOCAL_WORLD_ALIGNED
        )

        # 只使用位置部分和受控关节
        J = J_full[:3, self.ik_solver.controlled_indices]

        # 阻尼伪逆
        damping = self.config.vist_differential_ik_damping
        JJT = J @ J.T
        damping_matrix = damping**2 * np.eye(3)
        J_pinv = J.T @ inv(JJT + damping_matrix)

        # 人类指令增量：Δθ_human = J† @ Δx_human
        human_delta_theta = J_pinv @ delta_x_human

        return human_delta_theta

    def update(self, target_pos, target_quat=None, human_delta_theta=None, previous_target_pos=None):
        """
        卡尔曼滤波更新步骤

        融合人类指令和虚拟引导：
        - 计算卡尔曼增益 K
        - 更新状态估计 x = x + K @ (z - H @ x)
        - 更新协方差 P = (I - K @ H) @ P

        Args:
            target_pos: 目标位置 (3D)
            target_quat: 目标四元数 (可选)
            human_delta_theta: 人类指令增量 (可选，如果为 None 则自动计算)
            previous_target_pos: 上一帧目标位置 (可选，用于计算人类指令)

        Returns:
            q_solution: 估计的关节角度
            success: 是否成功
        """
        # 1. 计算微分 IK 观测（虚拟引导）
        delta_theta_virtual = self.compute_differential_ik(target_pos, target_quat)

        # 2. 计算或使用人类指令观测
        if human_delta_theta is None:
            if previous_target_pos is not None:
                # 从人手位置变化计算人类指令
                human_delta_theta = self.compute_human_delta_theta(target_pos, previous_target_pos)
            else:
                # 如果没有历史数据，使用零向量
                human_delta_theta = np.zeros(self.n_joints)

        # 3. 构建观测向量
        z = np.concatenate([human_delta_theta, delta_theta_virtual])

        # 4. 构建观测噪声协方差（意图驱动）
        R = self._build_observation_noise_covariance()

        # 5. 计算卡尔曼增益
        # K = P @ H^T @ (H @ P @ H^T + R)^(-1)
        S = self.H @ self.P @ self.H.T + R  # 创新协方差
        K = self.P @ self.H.T @ inv(S)  # 卡尔曼增益

        # 5. 更新状态
        innovation = z - self.H @ self.state
        self.state = self.state + K @ innovation

        # 6. 更新协方差
        I = np.eye(self.state_dim)
        self.P = (I - K @ self.H) @ self.P

        # 7. 关节限位（只对受控关节）
        q_solution = self.state[:self.n_joints]

        # 提取受控关节的限位
        q_min_controlled = np.array([self.ik_solver.q_min[idx] for idx in self.ik_solver.controlled_indices])
        q_max_controlled = np.array([self.ik_solver.q_max[idx] for idx in self.ik_solver.controlled_indices])

        q_solution = np.clip(q_solution, q_min_controlled, q_max_controlled)
        self.state[:self.n_joints] = q_solution

        # 8. 更新迭代计数
        self.iteration_count += 1

        return q_solution, True

    def solve(self, target_pos, target_quat=None, q_init=None):
        """
        VIST 求解主接口（兼容 IK 求解器接口）

        Args:
            target_pos: 目标位置 (3D)
            target_quat: 目标四元数 (可选)
            q_init: 初始关节角度 (可选，用于初始化状态)
                   可以是完整模型维度或受控关节维度

        Returns:
            q_solution: 关节角度解
            success: 是否成功
            error: 位置误差（用于兼容性）
        """
        # 如果提供了初始猜测，初始化状态
        if q_init is not None and self.iteration_count == 0:
            q_init = np.array(q_init, dtype=np.float64)

            # 检查维度并提取受控关节
            if len(q_init) == self.ik_solver.model.nq:
                # 完整模型维度，提取受控关节
                q_controlled = np.zeros(self.n_joints)
                for i, ctrl_idx in enumerate(self.ik_solver.controlled_indices):
                    if ctrl_idx < len(q_init):
                        q_controlled[i] = q_init[ctrl_idx]
                self.state[:self.n_joints] = q_controlled
            elif len(q_init) == self.n_joints:
                # 已经是受控关节维度
                self.state[:self.n_joints] = q_init
            else:
                # 维度不匹配，使用零初始化
                self.state[:self.n_joints] = np.zeros(self.n_joints)

            self.state[self.n_joints:] = 0.0  # 初始速度为零

        # 1. 预测步骤
        self.predict()

        # 2. 意图检测
        current_pos = self._get_current_end_effector_position()
        velocity = self.state[self.n_joints:self.n_joints+3]  # 前3个速度分量
        self.detect_intent(target_pos, current_pos, velocity)

        # 3. 更新步骤（自动使用历史位置计算人类指令）
        q_solution, success = self.update(
            target_pos,
            target_quat,
            previous_target_pos=self.previous_target_pos
        )

        # 4. 保存当前目标位置作为下一帧的历史
        self.previous_target_pos = target_pos.copy()

        # 5. 计算误差（用于统计）
        q_full = self._get_full_q_from_controlled(q_solution)
        pin.forwardKinematics(self.ik_solver.model, self.ik_solver.data, q_full)
        pin.updateFramePlacements(self.ik_solver.model, self.ik_solver.data)
        ee_placement = self.ik_solver.data.oMf[self.ik_solver.ee_frame_id]
        current_pos = ee_placement.translation
        error = np.linalg.norm(target_pos - current_pos)

        return q_solution, success, error

    def _get_full_q_from_controlled(self, q_controlled):
        """
        将受控关节角度扩展到完整模型关节角度

        Args:
            q_controlled: 受控关节角度 (n_joints,)

        Returns:
            q_full: 完整模型关节角度 (model.nq,)
        """
        q_full = pin.neutral(self.ik_solver.model).copy()
        for i, ctrl_idx in enumerate(self.ik_solver.controlled_indices):
            if i < len(q_controlled) and ctrl_idx < len(q_full):
                q_full[ctrl_idx] = q_controlled[i]
        return q_full

    def _get_current_end_effector_position(self):
        """获取当前末端执行器位置"""
        q_controlled = self.state[:self.n_joints]
        q_full = self._get_full_q_from_controlled(q_controlled)

        pin.forwardKinematics(self.ik_solver.model, self.ik_solver.data, q_full)
        pin.updateFramePlacements(self.ik_solver.model, self.ik_solver.data)
        ee_placement = self.ik_solver.data.oMf[self.ik_solver.ee_frame_id]
        return ee_placement.translation

    def reset(self):
        """重置滤波器状态"""
        self.state = np.zeros(self.state_dim)
        self.P = np.eye(self.state_dim)
        self.P[:self.n_joints, :self.n_joints] *= self.config.vist_initial_state_variance
        self.P[self.n_joints:, self.n_joints:] *= self.config.vist_initial_velocity_variance
        self.alpha = 0.0
        self.alpha_smoothed = 0.0
        self.previous_target_pos = None  # 重置历史位置
        self.iteration_count = 0


# ==========================================
# 测试代码
# ==========================================
if __name__ == "__main__":
    print("🧪 测试 VIST Kalman Filter...")
    print("请运行 scripts/simulate_full_flow.py 进行完整测试")
