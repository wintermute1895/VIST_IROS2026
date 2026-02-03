import numpy as np

class IntentInference:
    """
    意图推断模块
    对应文档 [cite: 50-59]
    """
    def __init__(self, dist_thresh=0.05, vel_thresh=0.1):
        self.d_th = dist_thresh
        self.v_th = vel_thresh

    def _sigmoid(self, x, k=10.0, x0=0.5):
        """辅助 Sigmoid 函数，将输入映射到 0-1"""
        return 1.0 / (1.0 + np.exp(-k * (x - x0)))

    def compute_alpha(self, p_err, v_hand):
        """
        计算意图因子 alpha
        """
        # 1. 归一化输入 (越小越好 -> 越大越好)
        # 如果 p_err < d_th, norm_d 会从 0 变大到 1
        # 如果 p_err > d_th, norm_d 为 0
        norm_d = np.clip(1.0 - (p_err / (self.d_th + 1e-6)), 0.0, 1.0)
        norm_v = np.clip(1.0 - (v_hand / (self.v_th + 1e-6)), 0.0, 1.0)
        
        # 2. 融合分数 (简单的乘法)
        raw_score = norm_d * norm_v
        
        # 3. 非线性激活 (Sigmoid)
        # 文档  建议使用 Sigmoid 来强化判定
        # 当 raw_score > 0.5 时，迅速推向 1.0
        # 当 raw_score < 0.5 时，迅速推向 0.0
        alpha = self._sigmoid(raw_score, k=12.0, x0=0.6)
        
        return float(alpha)