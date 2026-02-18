"""
正确的Q矩阵设计：任务空间插值方案

理论依据：
1. Q越大 → 系统认为预测不准 → 更相信观测 → 更听话
2. Q越小 → 系统认为预测很准 → 忽略观测 → 更僵硬

正确的逻辑：
- 自由空间（α=0）：XYZ都是高噪声（允许自由移动）
- 约束流形（α=1）：Z保持高噪声（允许推），XY变为极低噪声（强力约束）

公式：Q_task = (1-α)Σ_free + αΣ_cons
然后通过雅可比矩阵映射到关节空间：Q_joint = J^T Q_task J
"""

import numpy as np


def build_task_space_process_noise(alpha, config):
    """
    在任务空间构建过程噪声协方差矩阵

    Args:
        alpha: 意图因子 [0, 1]
        config: 配置对象

    Returns:
        Q_task: 任务空间过程噪声 (6x6)，前3维是位置，后3维是姿态
    """
    # 1. 定义自由空间协方差（各向同性）
    # 所有方向都允许自由移动
    high_gain = config.vist_position_variance  # 例如 1e-2
    Sigma_free = np.diag([1.0, 1.0, 1.0, 0.1, 0.1, 0.1]) * high_gain
    # 位置方差大，姿态方差小（因为我们主要关注位置）

    # 2. 定义约束流形协方差（各向异性）
    # Z轴保持高噪声（允许推动），XY轴极低噪声（虚拟夹具）
    Sigma_cons = np.diag([0.001, 0.001, 1.0, 0.001, 0.001, 0.1]) * high_gain
    # XY方向被"冻结"（0.001倍），Z方向保持"听话"（1.0倍）

    # 3. 意图驱动的平滑插值（这是关键！）
    Q_task = (1.0 - alpha) * Sigma_free + alpha * Sigma_cons

    return Q_task


def map_task_space_to_joint_space(Q_task, jacobian):
    """
    将任务空间的Q矩阵映射到关节空间

    理论依据：
    如果任务空间误差 δx ~ N(0, Q_task)
    那么关节空间误差 δq = J^† δx ~ N(0, J^† Q_task J^†^T)

    但在实践中，我们使用简化的映射：
    Q_joint ≈ J^T Q_task J

    Args:
        Q_task: 任务空间过程噪声 (6x6)
        jacobian: 雅可比矩阵 (6 x n_joints)

    Returns:
        Q_joint: 关节空间过程噪声 (n_joints x n_joints)
    """
    # 只使用位置部分的雅可比（前3行）
    J_pos = jacobian[:3, :]
    Q_task_pos = Q_task[:3, :3]

    # 映射到关节空间
    Q_joint = J_pos.T @ Q_task_pos @ J_pos

    # 添加最小正则化，避免奇异
    epsilon = 1e-6
    Q_joint += epsilon * np.eye(Q_joint.shape[0])

    return Q_joint


def build_process_noise_covariance_correct(self):
    """
    正确的Q矩阵构建方法（替换原来的_build_process_noise_covariance）

    核心改进：
    1. 在任务空间定义Σ_free和Σ_cons
    2. 使用意图因子α进行平滑插值
    3. 通过雅可比矩阵映射到关节空间
    """
    # 1. 构建任务空间Q矩阵
    Q_task = build_task_space_process_noise(self.alpha_smoothed, self.config)

    # 2. 获取当前雅可比矩阵
    try:
        q_controlled = self.state[:self.n_joints]
        q_full = self._get_full_q_from_controlled(q_controlled)

        # 确保配置有效
        if not np.all(np.isfinite(q_full)):
            # 配置无效，使用默认Q矩阵
            return self._build_default_Q()

        # 计算雅可比矩阵
        import pinocchio as pin
        pin.forwardKinematics(self.ik_solver.model, self.ik_solver.data, q_full)
        pin.updateFramePlacements(self.ik_solver.model, self.ik_solver.data)

        J_full = pin.computeFrameJacobian(
            self.ik_solver.model,
            self.ik_solver.data,
            q_full,
            self.ik_solver.ee_frame_id,
            pin.ReferenceFrame.LOCAL_WORLD_ALIGNED
        )

        # 只使用受控关节
        J = J_full[:, self.ik_solver.controlled_indices]

        # 3. 映射到关节空间
        Q_pos = map_task_space_to_joint_space(Q_task, J)

        # 4. 构建完整的Q矩阵（位置+速度）
        Q = np.zeros((self.state_dim, self.state_dim))
        Q[:self.n_joints, :self.n_joints] = Q_pos

        # 速度部分使用固定的噪声
        vel_variance = self.config.vist_velocity_variance
        Q[self.n_joints:, self.n_joints:] = vel_variance * np.eye(self.n_joints)

        return Q

    except Exception as e:
        print(f"⚠️ [VIST] 任务空间Q矩阵计算失败: {e}")
        return self._build_default_Q()


def _build_default_Q(self):
    """默认的Q矩阵（当雅可比计算失败时使用）"""
    Q = np.zeros((self.state_dim, self.state_dim))
    pos_variance = self.config.vist_position_variance
    vel_variance = self.config.vist_velocity_variance
    Q[:self.n_joints, :self.n_joints] = pos_variance * np.eye(self.n_joints)
    Q[self.n_joints:, self.n_joints:] = vel_variance * np.eye(self.n_joints)
    return Q


# ============================================================
# 关键理论解释
# ============================================================

"""
为什么这样做是理论自洽的？

1. 在自由空间（α=0）：
   - Q_task = Σ_free = diag([1, 1, 1, ...]) * high_gain
   - 所有方向都是高噪声
   - 系统"不相信"自己的预测，完全听从观测
   - 结果：XYZ都能自由移动

2. 在约束流形（α=1）：
   - Q_task = Σ_cons = diag([0.001, 0.001, 1, ...]) * high_gain
   - XY方向是极低噪声，Z方向是高噪声
   - 系统在XY方向"相信"预测（僵硬），在Z方向"不相信"预测（听话）
   - 结果：XY被"冻结"，Z能推动

3. 配合R矩阵的增大：
   - 当α→1时，R_human也增大（指数增长）
   - 虽然Q_z很大（允许动），但R也大（产生阻尼）
   - 卡尔曼增益 K_z = P_z / (P_z + R) ≈ 常数
   - 结果：Z轴能推动，但高频抖动被滤除（低通滤波效果）

4. 为什么不会"卡死"？
   - 因为Q_z始终保持大值（从1.0到1.0，不变）
   - P_z会被Q_z撑大，保持高不确定性
   - K_z不会趋近于0，系统依然"听话"
   - 只是响应变得"平滑"（阻尼），而不是"卡死"

这就是"Soft Landing"的数学原理！
"""
