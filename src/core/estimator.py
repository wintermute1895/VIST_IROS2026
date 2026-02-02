import numpy as np

class IntentAdaptiveEstimator:
    """
    IROS 2026 Innovation: Vision-based Intent-aware State Estimator
    
    原理：
    当用户意图被识别为"精细操作"（如低速靠近孔位）时，显著增加观测噪声协方差 R，
    迫使滤波器更多地依赖内部状态预测（F），从而实现"软锁定"效果，消除视觉抖动。
    """
    def __init__(self, dt=0.01):
        self.dt = dt
        self.initialized = False
        
        # 1. 状态向量 x = [px, py, pz, vx, vy, vz]^T (位置 + 速度)
        self.x = np.zeros(6)
        
        # 2. 状态协方差矩阵 P (初始不确定性)
        self.P = np.eye(6) * 1.0
        
        # 3. 状态转移矩阵 F (恒速模型 CV Model)
        # p_new = p + v * dt
        # v_new = v
        self.F = np.eye(6)
        self.F[0:3, 3:6] = np.eye(3) * dt
        
        # 4. 观测矩阵 H (我们只观测位置 px, py, pz)
        self.H = np.zeros((3, 6))
        self.H[0:3, 0:3] = np.eye(3)
        
        # 5. 噪声参数 (这些是需要调参的关键！)
        self.Q = np.eye(6) * 0.001       # 过程噪声：相信物理模型的程度
        self.R_base = np.eye(3) * 0.005  # 基础视觉噪声：当完全信任视觉时
        
    def init_state(self, initial_pos):
        """初始化滤波器状态"""
        self.x[0:3] = initial_pos
        self.x[3:6] = 0  # 初始速度设为0
        self.initialized = True
        print("✅ Estimator Initialized with pos:", initial_pos)

    def update(self, measurement_pos, intent_score):
        """
        核心更新步
        :param measurement_pos: 视觉原始观测值 [x, y, z] (Numpy array)
        :param intent_score: 0.0 (快速移动) ~ 1.0 (精细操作)
        :return: 平滑后的位置 [x, y, z]
        """
        if not self.initialized:
            self.init_state(measurement_pos)
            return measurement_pos

        # --- IROS 核心创新点: 自适应 R 矩阵 ---
        # 动态调节因子 alpha
        # intent=0 -> alpha=1.0 (保持原状)
        # intent=1 -> alpha=50.0 (极度不信视觉，像是在粘滞流体中运动)
        alpha = 1.0 + (intent_score * 50.0) 
        R_adaptive = self.R_base * alpha

        # --- 标准卡尔曼滤波流程 ---
        
        # 1. 预测 (Predict)
        self.x = self.F @ self.x
        self.P = self.F @ self.P @ self.F.T + self.Q
        
        # 2. 更新 (Update)
        y = measurement_pos - self.H @ self.x  # 观测残差 (Innovation)
        S = self.H @ self.P @ self.H.T + R_adaptive
        
        # 计算卡尔曼增益 K (最优融合权重)
        # K = P * H.T * inv(S)
        try:
            K = self.P @ self.H.T @ np.linalg.inv(S)
        except np.linalg.LinAlgError:
            # 极少数情况S不可逆，退化为相信预测
            K = np.zeros((6, 3))

        self.x = self.x + K @ y
        self.P = (np.eye(6) - K @ self.H) @ self.P
        
        return self.x[0:3] # 只返回位置用于控制