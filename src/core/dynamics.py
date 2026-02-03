import numpy as np

class SystemDynamics:
    """
    对应文档 2.2 和 2.3 节：过程模型与隐式冗余约束
    """
    def __init__(self, dt=0.01, n_dof=7):
        self.dt = dt
        self.n = n_dof
        self.dim_x = 2 * n_dof  # 状态维度 14 (7位置 + 7速度)

        # --- 1. 状态转移矩阵 F (State Transition Matrix) ---
        # x_k = F * x_{k-1}
        # [ q_new ] = [ I   dt*I ] * [ q_old ]
        # [ v_new ]   [ 0    I   ]   [ v_old ]
        self.F = np.eye(self.dim_x)
        self.F[0:self.n, self.n:2*self.n] = np.eye(self.n) * dt

    def get_process_noise(self, elbow_idx=2, lazy_factor=0.01):
        """
        构建各向异性过程噪声 Q
        :param elbow_idx: 肘部关节的索引 (通常是第2或3个关节)
        :param lazy_factor: 肘部相对于其他关节的活跃度 (越小越懒)
        """
        # 基础噪声方差
        sigma_pos = 1e-4
        sigma_vel = 1e-3
        
        # Q_pos 对角阵
        q_pos_diag = np.ones(self.n) * sigma_pos
        # 核心：降低肘部噪声方差，信任预测模型，抑制 IK 乱晃
        q_pos_diag[elbow_idx] *= lazy_factor 
        
        # Q_vel 对角阵
        q_vel_diag = np.ones(self.n) * sigma_vel
        
        # 组装 Q 矩阵 (14x14)
        Q = np.zeros((self.dim_x, self.dim_x))
        Q[0:self.n, 0:self.n] = np.diag(q_pos_diag)
        Q[self.n:2*self.n, self.n:2*self.n] = np.diag(q_vel_diag)
        
        return Q