"""
VIST参数覆盖机制
用于实时调试和验证机制效果

使用文件进行进程间通信
"""

import numpy as np
import json
import os
from dataclasses import dataclass, asdict
from typing import Optional
from pathlib import Path

# 参数覆盖文件路径
OVERRIDE_FILE = Path.home() / ".vist_parameter_override.json"

@dataclass
class ParameterOverride:
    """参数覆盖配置"""

    # 意图因子覆盖
    alpha_override: Optional[float] = None  # 强制设置α值

    # 观测噪声覆盖
    r_human_override: Optional[float] = None  # 强制设置R_human
    r_virtual_override: Optional[float] = None  # 强制设置R_virtual

    # 过程噪声覆盖
    q_scale_override: Optional[float] = None  # Q矩阵整体缩放

    # 流形约束覆盖
    manifold_enabled_override: Optional[bool] = None  # 强制启用/禁用流形约束
    z_lock_threshold_override: Optional[float] = None  # Z轴锁定阈值

    # 协方差调度参数覆盖
    human_lambda_override: Optional[float] = None  # R_human指数系数
    virtual_min_override: Optional[float] = None  # R_virtual最小值
    conflict_gain_override: Optional[float] = None  # 冲突增益

    def is_active(self) -> bool:
        """检查是否有任何覆盖激活"""
        return any([
            self.alpha_override is not None,
            self.r_human_override is not None,
            self.r_virtual_override is not None,
            self.q_scale_override is not None,
            self.manifold_enabled_override is not None,
            self.z_lock_threshold_override is not None,
            self.human_lambda_override is not None,
            self.virtual_min_override is not None,
            self.conflict_gain_override is not None,
        ])

    def to_dict(self):
        """转换为字典"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data):
        """从字典创建"""
        return cls(**data)

    def get_alpha(self, computed_alpha: float) -> float:
        """获取α值（覆盖或计算值）"""
        if self.alpha_override is not None:
            return self.alpha_override
        return computed_alpha

    def get_r_human(self, computed_r_human: float, alpha: float,
                    r_base: float, lambda_param: float) -> float:
        """获取R_human值"""
        if self.r_human_override is not None:
            return self.r_human_override

        # 如果lambda被覆盖，重新计算
        if self.human_lambda_override is not None:
            return r_base * np.exp(self.human_lambda_override * alpha)

        return computed_r_human

    def get_r_virtual(self, computed_r_virtual: float, alpha: float,
                     r_min: float, conflict: float, gamma_c: float) -> float:
        """获取R_virtual值"""
        if self.r_virtual_override is not None:
            return self.r_virtual_override

        # 如果参数被覆盖，重新计算
        if self.virtual_min_override is not None or self.conflict_gain_override is not None:
            r_min_use = self.virtual_min_override if self.virtual_min_override is not None else r_min
            gamma_c_use = self.conflict_gain_override if self.conflict_gain_override is not None else gamma_c
            return r_min_use / (alpha + 1e-6) + gamma_c_use * conflict

        return computed_r_virtual

    def get_q_matrix(self, computed_q: np.ndarray) -> np.ndarray:
        """获取Q矩阵"""
        if self.q_scale_override is not None:
            return computed_q * self.q_scale_override
        return computed_q

    def should_apply_manifold(self, alpha: float, default_threshold: float) -> bool:
        """判断是否应用流形约束"""
        if self.manifold_enabled_override is not None:
            return self.manifold_enabled_override

        threshold = self.z_lock_threshold_override if self.z_lock_threshold_override is not None else default_threshold
        return alpha > threshold


class ParameterOverrideManager:
    """参数覆盖管理器（使用文件进行进程间通信）"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.override = ParameterOverride()
            cls._instance._load_from_file()
        return cls._instance

    def _load_from_file(self):
        """从文件加载覆盖配置"""
        try:
            if OVERRIDE_FILE.exists():
                with open(OVERRIDE_FILE, 'r') as f:
                    data = json.load(f)
                    self.override = ParameterOverride.from_dict(data)
        except Exception as e:
            pass  # 静默失败

    def _save_to_file(self):
        """保存覆盖配置到文件"""
        try:
            with open(OVERRIDE_FILE, 'w') as f:
                json.dump(self.override.to_dict(), f)
        except Exception as e:
            print(f"⚠️ 保存参数覆盖文件失败: {e}")

    def set_override(self, override: ParameterOverride):
        """设置覆盖配置"""
        self.override = override
        self._save_to_file()

    def get_override(self) -> ParameterOverride:
        """获取当前覆盖配置（从文件重新加载）"""
        self._load_from_file()
        return self.override

    def reset(self):
        """重置所有覆盖"""
        self.override = ParameterOverride()
        self._save_to_file()

    def update_alpha(self, value: Optional[float]):
        """更新α覆盖"""
        self.override.alpha_override = value
        self._save_to_file()
        print(f"✅ α覆盖已更新: {value}")

    def update_r_human(self, value: Optional[float]):
        """更新R_human覆盖"""
        self.override.r_human_override = value
        self._save_to_file()
        print(f"✅ R_human覆盖已更新: {value}")

    def update_r_virtual(self, value: Optional[float]):
        """更新R_virtual覆盖"""
        self.override.r_virtual_override = value
        self._save_to_file()
        print(f"✅ R_virtual覆盖已更新: {value}")

    def update_q_scale(self, value: Optional[float]):
        """更新Q缩放覆盖"""
        self.override.q_scale_override = value
        self._save_to_file()
        print(f"✅ Q缩放覆盖已更新: {value}")

    def update_manifold_enabled(self, value: Optional[bool]):
        """更新流形约束启用覆盖"""
        self.override.manifold_enabled_override = value
        self._save_to_file()
        print(f"✅ 流形约束覆盖已更新: {value}")

    def update_z_lock_threshold(self, value: Optional[float]):
        """更新Z轴锁定阈值覆盖"""
        self.override.z_lock_threshold_override = value
        self._save_to_file()
        print(f"✅ Z轴锁定阈值覆盖已更新: {value}")

    def update_human_lambda(self, value: Optional[float]):
        """更新R_human指数系数覆盖"""
        self.override.human_lambda_override = value
        self._save_to_file()
        print(f"✅ R_human指数系数覆盖已更新: {value}")

    def update_virtual_min(self, value: Optional[float]):
        """更新R_virtual最小值覆盖"""
        self.override.virtual_min_override = value
        self._save_to_file()
        print(f"✅ R_virtual最小值覆盖已更新: {value}")

    def update_conflict_gain(self, value: Optional[float]):
        """更新冲突增益覆盖"""
        self.override.conflict_gain_override = value
        self._save_to_file()
        print(f"✅ 冲突增益覆盖已更新: {value}")