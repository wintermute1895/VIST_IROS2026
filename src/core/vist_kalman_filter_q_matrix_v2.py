"""
正确的Q矩阵实现（任务空间插值方案）

这个文件包含了理论正确的Q矩阵构建方法，可以直接替换vist_kalman_filter.py中的
_build_process_noise_covariance方法。

核心改进：
1. 在任务空间定义Σ_free和Σ_cons
2. 使用意图因子α进行平滑插值（不是突然启动）
3. 通过雅可比矩阵映射到关节空间
4. 确保Z轴相关关节的Q始终保持大值
"""

import numpy as np
import pinocchio as pin


def _build_process_noise_covariance_v2(self):
    """
    构建意图驱动的各向异性过程噪声协方差矩阵 Q（v2.0 - 任务空间插值）

    【核心创新】任务空间插值方案（论文英文草稿v1.0）：

    理论依据：
    - Q越大 → 系统认为预测不准 → 更相信观测 → 更听话
    - Q越小 → 系统认为预测很准 → 忽略观测 → 更僵硬

    公式：
    1. 自由空间（α=0）：Σ_free = diag([1, 1, 1]) * high_gain
       所有方向都允许自由移动
    2. 约束流形（α=1）：Σ_cons = diag([0.001, 0.001, 1]) * high_gain
       XY方向冻结（虚拟夹具），Z方向保持听话（允许推动）
    3. 平滑插值：Q_task = (1-α)Σ_free + αΣ_cons
    4. 映射到关节空间：Q_joint = J^T Q_task J

    关键洞察：
    - Z轴的Q始终保持大值（从1.0到1.0），不会"卡死"
    - 抖动抑制靠R矩阵增大，而不是Q矩阵减小
    - 配合R增大，实现"带阻尼的运动"（低通滤波效果）

    Returns:
        Q: 过程噪声协方差矩阵 (state_dim x state_dim)
    """
    try:
        # 1. 获取当前关节配置
        q_controlled = self.state[:self.n_joints]
        q_full = self._get_full_q_from_controlled(q_controlled)

        # 确保配置有效
        if not np.all(np.isfinite(q_full)):
            return self._build_default_Q()

        # 2. 计算雅可比矩阵
        pin.forwardKinematics(self.ik_solver.model, self.ik_solver.data, q_full)
        pin.updateFramePlacements(self.ik_solver.model, self.ik_solver.data)

        J_full = pin.computeFrameJacobian(
            self.ik_solver.model,
            self.ik_solver.data,
            q_full,
            self.ik_solver.ee_frame_id,
            pin.ReferenceFrame.LOCAL_WORLD_ALIGNED
        )

        # 只使用位置部分（前3行）和受控关节
        J = J_full[:3, self.ik_solver.controlled_indices]

        # 3. 在任务空间定义两种状态的协方差矩阵
        high_gain = self.config.vist_position_variance  # 例如 1e-2

        # 自由空间：所有方向都允许自由移动
        Sigma_free = np.diag([1.0, 1.0, 1.0]) * high_gain

        # 约束流形：Z轴保持听话，XY轴冻结
        # 关键：Z轴的值(1.0)必须保持很大，不能变小！
        Sigma_cons = np.diag([0.001, 0.001, 1.0]) * high_gain

        # 4. 意图驱动的平滑插值（这是关键！）
        # 不是突然启动，而是平滑过渡
        Q_task = (1.0 - self.alpha_smoothed) * Sigma_free + self.alpha_smoothed * Sigma_cons

        # 5. 映射到关节空间：Q_joint = J^T Q_task J
        Q_pos = J.T @ Q_task @ J

        # 添加最小正则化，避免奇异
        epsilon = 1e-6
        Q_pos += epsilon * np.eye(Q_pos.shape[0])

        # 6. 构建完整的Q矩阵（位置+速度）
        Q = np.zeros((self.state_dim, self.state_dim))
        Q[:self.n_joints, :self.n_joints] = Q_pos

        # 速度部分使用固定的噪声
        vel_variance = self.config.vist_velocity_variance
        Q[self.n_joints:, self.n_joints:] = vel_variance * np.eye(self.n_joints)

        # 7. 【可选】对特定关节施加额外的调整
        # 这是为了兼容原有的关节空间调整逻辑
        # J3 (Swivel) 施加强阻尼，抑制冗余自由度的抖动
        swivel_idx = 2
        swivel_damping = 0.1
        Q[swivel_idx, swivel_idx] *= swivel_damping
        Q[self.n_joints + swivel_idx, self.n_joints + swivel_idx] *= swivel_damping

        return Q

    except Exception as e:
        print(f"⚠️ [VIST] 任务空间Q矩阵计算失败: {e}")
        return self._build_default_Q()


def _build_default_Q(self):
    """默认的Q矩阵（当雅可比计算失败时使用）"""
    Q = np.zeros((self.state_dim, self.state_dim))

    # 位置部分
    pos_variance = self.config.vist_position_variance
    Q[:self.n_joints, :self.n_joints] = pos_variance * np.eye(self.n_joints)

    # 速度部分
    vel_variance = self.config.vist_velocity_variance
    Q[self.n_joints:, self.n_joints:] = vel_variance * np.eye(self.n_joints)

    # 基础的关节空间调整
    shoulder_pitch_idx = 0
    shoulder_roll_idx = 1
    swivel_idx = 2
    elbow_idx = 3

    Q[shoulder_pitch_idx, shoulder_pitch_idx] *= 3.0
    Q[self.n_joints + shoulder_pitch_idx, self.n_joints + shoulder_pitch_idx] *= 3.0
    Q[shoulder_roll_idx, shoulder_roll_idx] *= 2.0
    Q[self.n_joints + shoulder_roll_idx, self.n_joints + shoulder_roll_idx] *= 2.0
    Q[swivel_idx, swivel_idx] *= 0.1
    Q[self.n_joints + swivel_idx, self.n_joints + swivel_idx] *= 0.1
    Q[elbow_idx, elbow_idx] *= 1.2
    Q[self.n_joints + elbow_idx, self.n_joints + elbow_idx] *= 1.2

    return Q


# ============================================================
# 使用说明
# ============================================================
"""
要使用这个新的Q矩阵实现，需要在vist_kalman_filter.py中：

1. 添加_build_default_Q方法（如果还没有）
2. 将_build_process_noise_covariance方法替换为_build_process_noise_covariance_v2

或者，可以先保留原方法，添加一个配置开关：

def _build_process_noise_covariance(self):
    # 使用新的任务空间插值方案
    use_task_space_interpolation = getattr(self.config, 'vist_use_task_space_q', True)

    if use_task_space_interpolation:
        return self._build_process_noise_covariance_v2()
    else:
        return self._build_process_noise_covariance_v1()  # 原方法

这样可以在配置文件中切换，方便对比效果。
"""
