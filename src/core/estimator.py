import numpy as np

class IntentAdaptiveEstimator:
    """
    VIST 核心：意图自适应卡尔曼滤波器 (Joint Space 7DOF)
    对应文档 [cite: 20, 70-79]
    """
    def __init__(self, dt=0.01):
        self.n = 7           # 关节自由度 [cite: 13]
        self.dim_x = 14      # 状态维度: 7 pos + 7 vel 
        self.dim_z = 14      # 观测维度: 7 human + 7 virtual [cite: 35]
        self.dt = dt
        
        # --- 1. 状态转移矩阵 F [cite: 24] ---
        # [ I   dt*I ]
        # [ 0    I   ]
        self.F = np.eye(self.dim_x)
        self.F[0:self.n, self.n:2*self.n] = np.eye(self.n) * dt
        
        # --- 2. 过程噪声 Q [cite: 28] ---
        # 隐式冗余约束：让关节速度变化稍微“懒”一点
        self.Q = np.eye(self.dim_x) * 1e-3
        # 我们可以稍微降低肘部对应的噪声（这里简化处理，均匀噪声）
        
        # --- 3. 观测矩阵 H [cite: 43] ---
        # [ I  0 ] -> z_human 观测位置
        # [ I  0 ] -> z_virtual 观测位置
        self.H = np.zeros((self.dim_z, self.dim_x))
        self.H[0:self.n, 0:self.n] = np.eye(self.n)
        self.H[self.n:2*self.n, 0:self.n] = np.eye(self.n)

        # 初始化状态和协方差
        self.x = np.zeros(self.dim_x)
        self.P = np.eye(self.dim_x) * 0.1

        # 噪声基准参数 [cite: 64, 66]
        self.R_base = 1e-3
        self.R_inf = 1e3
        self.R_min = 1e-5

    def update(self, z_human, z_virtual, alpha):
        """
        执行卡尔曼更新 [cite: 77]
        :param alpha: 意图因子 (0~1)
        """
        # --- A. 预测 (Time Update) ---
        x_pred = self.F @ self.x
        P_pred = self.F @ self.P @ self.F.T + self.Q
        
        # --- B. 协方差调度 (Covariance Scheduling) [cite: 63] ---
        R = np.zeros((self.dim_z, self.dim_z))
        
        # 1. 人类噪声 R_human: alpha 越大，噪声越大 (不信人) [cite: 64]
        # 使用 50.0 作为增益系数 gamma1
        r_hum_val = self.R_base * (1.0 + 50.0 * alpha)
        R[0:self.n, 0:self.n] = np.eye(self.n) * r_hum_val
        
        # 2. 虚拟噪声 R_virtual: alpha 越大，噪声越小 (信虚拟) [cite: 66]
        # 使用 20.0 作为衰减系数 gamma2
        # 当 alpha=0, val -> R_inf; 当 alpha=1, val -> R_min
        r_virt_val = self.R_inf * np.exp(-20.0 * alpha) + self.R_min
        R[self.n:2*self.n, self.n:2*self.n] = np.eye(self.n) * r_virt_val

        # --- C. 更新 (Measurement Update) ---
        z_k = np.concatenate([z_human, z_virtual])
        y = z_k - self.H @ x_pred
        
        S = self.H @ P_pred @ self.H.T + R
        S += np.eye(self.dim_z) * 1e-9 # 防奇异
        
        try:
            K = P_pred @ self.H.T @ np.linalg.inv(S)
        except np.linalg.LinAlgError:
            K = np.zeros((self.dim_x, self.dim_z))

        self.x = x_pred + K @ y
        self.P = (np.eye(self.dim_x) - K @ self.H) @ P_pred
        
        # 返回位置部分
        return self.x[0:self.n]