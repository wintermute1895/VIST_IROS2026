import numpy as np
import pytest
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.estimator import IntentAdaptiveEstimator

def test_estimator_mechanics():
    # 1. 初始化测试
    est = IntentAdaptiveEstimator(dt=0.01)
    assert est.P.shape == (14, 14)
    
    # 2. 静态保持测试 (输入全0，输出应该收敛到0)
    z_human = np.zeros(7)
    z_virtual = np.zeros(7)
    
    for _ in range(50):
        q_cmd = est.update(z_human, z_virtual, alpha=0.5)
    
    assert np.allclose(q_cmd, np.zeros(7), atol=1e-3), "Estimator drifting!"

def test_virtual_attraction():
    # 测试：当 alpha=1 时，是否真的被吸附到了 z_virtual
    est = IntentAdaptiveEstimator(dt=0.01)
    
    z_human = np.ones(7) * 10.0  # 人想去很远的地方 (10.0)
    z_virtual = np.zeros(7)      # 孔在这里 (0.0)
    
    # 强制开启精密模式
    for _ in range(100):
        # alpha=1.0 意味着极其信任 z_virtual
        q_cmd = est.update(z_human, z_virtual, alpha=1.0)
        
    # 结果应该非常接近 0.0，而不是 10.0
    print(f"Final Q: {q_cmd[0]}")
    assert q_cmd[0] < 0.5, "Virtual Guide failed to attract!"