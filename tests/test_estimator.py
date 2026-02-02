import numpy as np
import pytest
import sys
import os

# 路径黑魔法，确保能 import src
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.estimator import IntentAdaptiveEstimator

def test_estimator_initialization():
    """测试初始化是否正常"""
    est = IntentAdaptiveEstimator(dt=0.01)
    # 第一帧数据输入
    res = est.update(np.array([0.1, 0.2, 0.3]), intent_score=0.0)
    # 第一帧应该直接返回原值（Warm start）
    assert np.allclose(res, np.array([0.1, 0.2, 0.3]))

def test_estimator_smoothing_effect():
    """测试：高意图分(精细操作)时，应该有强平滑效果"""
    est = IntentAdaptiveEstimator(dt=0.01)
    
    # 1. 初始化
    est.update(np.array([0.0, 0.0, 0.0]), intent_score=0.0)
    
    # 2. 突然输入一个大跳变 [1.0, 0, 0]
    # 意图分设为 1.0 (极度慢速/精细)，这时候 R 很大，信任模型
    input_pos = np.array([1.0, 0.0, 0.0])
    output_pos = est.update(input_pos, intent_score=1.0)
    
    # 3. 断言：输出绝对不应该直接变成 1.0，应该远小于 1.0 (比如 0.1 左右)
    print(f"Input: 1.0, Output with high intent: {output_pos[0]}")
    assert output_pos[0] < 0.5, "Error: Estimator did not smooth the signal enough!"

def test_estimator_fast_response():
    """测试：低意图分(快速移动)时，应该快速跟随"""
    est = IntentAdaptiveEstimator(dt=0.01)
    est.update(np.array([0.0, 0.0, 0.0]), intent_score=0.0)
    
    # 意图分设为 0.0 (快速)，这时候 R 很小，信任观测
    input_pos = np.array([1.0, 0.0, 0.0])
    output_pos = est.update(input_pos, intent_score=0.0)
    
    # 断言：输出应该很接近 1.0
    assert output_pos[0] > 0.8, "Error: Estimator is lagging too much!"