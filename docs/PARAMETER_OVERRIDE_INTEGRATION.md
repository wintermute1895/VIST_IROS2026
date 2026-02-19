# 参数覆盖机制快速集成指南

**目的**: 将参数覆盖机制集成到VIST系统，实现实时参数调试

---

## 已完成的集成

### 1. 卡尔曼滤波器 - Q矩阵覆盖 ✅

**文件**: `src/core/vist_kalman_filter.py`

**已添加**:
```python
# 导入
from src.utils.parameter_override import ParameterOverrideManager

# 初始化
self.override_manager = ParameterOverrideManager()

# 在_build_process_noise_covariance中应用
override = self.override_manager.get_override()
Q_final = override.get_q_matrix(Q_computed)
```

---

## 待完成的集成

### 2. 卡尔曼滤波器 - R矩阵和α覆盖

在 `_build_observation_noise_covariance` 方法中添加（约Line 331）:

```python
# 获取参数覆盖
override = self.override_manager.get_override()

# 应用λ覆盖
lambda_h = override.human_lambda_override if override.human_lambda_override is not None else \
           (self.config.vist_human_lambda if hasattr(self.config, 'vist_human_lambda') else 3.0)

# 计算R_human
human_variance = R_base_human * np.exp(lambda_h * self.alpha_smoothed)

# 应用R_human覆盖
human_variance = override.get_r_human(human_variance, self.alpha_smoothed,
                                      R_base_human, lambda_h)
```

在虚拟引导部分（约Line 370）:

```python
# 应用R_min覆盖
R_min = override.virtual_min_override if override.virtual_min_override is not None else \
        self.config.vist_virtual_min_variance

# 应用冲突增益覆盖
gamma_c = override.conflict_gain_override if override.conflict_gain_override is not None else \
          self.config.vist_conflict_gain

# 计算R_virtual
virtual_variance = R_min / (self.alpha_smoothed + 1e-6) + gamma_c * conflict_norm

# 应用R_virtual覆盖
virtual_variance = override.get_r_virtual(virtual_variance, self.alpha_smoothed,
                                          R_min, conflict_norm, gamma_c)
```

### 3. 意图检测器 - α覆盖

在 `src/core/intent_detector.py` 的 `compute_alpha` 方法末尾添加:

```python
from src.utils.parameter_override import ParameterOverrideManager

def compute_alpha(self, ...):
    # ... 现有的α计算代码 ...

    # 应用α覆盖
    override_manager = ParameterOverrideManager()
    override = override_manager.get_override()
    alpha_final = override.get_alpha(alpha_computed)

    return alpha_final
```

### 4. 控制器 - 状态历史记录

在 `src/control/threaded_vist_controller.py` 的控制循环中添加:

```python
# 在文件开头导入
from scripts.debug_interface import state_history
import time

# 在控制循环中记录
start_time = time.time()

# 在每个控制周期
current_time = time.time() - start_time
state_history['time'].append(current_time)
state_history['alpha'].append(alpha)
state_history['alpha_override'].append(override.alpha_override or alpha)
state_history['r_human'].append(r_human_value)
state_history['r_virtual'].append(r_virtual_value)
state_history['end_effector_pos'].append(ee_pos.tolist())
```

---

## 快速测试

### 测试1: 启动调试界面

```bash
# 终端1: 启动调试界面
python scripts/debug_interface.py
```

浏览器打开: `http://localhost:7860`

### 测试2: 启动VIST控制器

```bash
# 终端2: 启动控制器
python scripts/run_vist_controller.py
```

### 测试3: 验证参数覆盖

1. 在调试界面中启用"α覆盖"，设置α=1.0
2. 观察控制器输出，确认α被强制设置为1.0
3. 在摄像头前移动手部，观察末端轨迹

---

## 完整集成示例

创建一个测试脚本 `scripts/test_parameter_override.py`:

```python
#!/usr/bin/env python3
"""
测试参数覆盖机制
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.utils.parameter_override import ParameterOverrideManager
from src.core.vist_kalman_filter import VISTKalmanFilter
from src.core.pinocchio_ik_solver import PinocchioIKSolver
from src.config.config_loader import load_config
import numpy as np

def test_alpha_override():
    """测试α覆盖"""
    print("=" * 60)
    print("测试α覆盖")
    print("=" * 60)

    # 创建系统
    config = load_config()
    ik_solver = PinocchioIKSolver(config)
    kf = VISTKalmanFilter(config, ik_solver)

    # 设置初始α
    kf.alpha_smoothed = 0.5
    print(f"初始α: {kf.alpha_smoothed}")

    # 启用α覆盖
    override_manager = ParameterOverrideManager()
    override_manager.update_alpha(1.0)
    print(f"启用α覆盖: 1.0")

    # 获取覆盖后的α
    override = override_manager.get_override()
    alpha_final = override.get_alpha(kf.alpha_smoothed)
    print(f"最终α: {alpha_final}")

    assert alpha_final == 1.0, "α覆盖失败"
    print("✅ α覆盖测试通过")

def test_r_human_override():
    """测试R_human覆盖"""
    print("\n" + "=" * 60)
    print("测试R_human覆盖")
    print("=" * 60)

    override_manager = ParameterOverrideManager()
    override = override_manager.get_override()

    # 计算的R_human
    r_base = 1e-2
    lambda_param = 3.0
    alpha = 1.0
    r_computed = r_base * np.exp(lambda_param * alpha)
    print(f"计算的R_human: {r_computed:.2e}")

    # 启用R_human覆盖
    override_manager.update_r_human(1e-1)
    override = override_manager.get_override()
    r_final = override.get_r_human(r_computed, alpha, r_base, lambda_param)
    print(f"覆盖后R_human: {r_final:.2e}")

    assert r_final == 1e-1, "R_human覆盖失败"
    print("✅ R_human覆盖测试通过")

def test_q_matrix_override():
    """测试Q矩阵覆盖"""
    print("\n" + "=" * 60)
    print("测试Q矩阵覆盖")
    print("=" * 60)

    override_manager = ParameterOverrideManager()

    # 原始Q矩阵
    Q_original = np.eye(14) * 1e-3
    print(f"原始Q对角元素: {Q_original[0,0]:.2e}")

    # 启用Q缩放覆盖
    override_manager.update_q_scale(10.0)
    override = override_manager.get_override()
    Q_final = override.get_q_matrix(Q_original)
    print(f"覆盖后Q对角元素: {Q_final[0,0]:.2e}")

    assert Q_final[0,0] == 1e-2, "Q矩阵覆盖失败"
    print("✅ Q矩阵覆盖测试通过")

def test_manifold_override():
    """测试流形约束覆盖"""
    print("\n" + "=" * 60)
    print("测试流形约束覆盖")
    print("=" * 60)

    override_manager = ParameterOverrideManager()
    override = override_manager.get_override()

    # 测试默认行为
    alpha = 0.7
    default_threshold = 0.8
    should_apply = override.should_apply_manifold(alpha, default_threshold)
    print(f"α={alpha}, 阈值={default_threshold}, 应用流形约束: {should_apply}")
    assert not should_apply, "默认行为错误"

    # 强制启用流形约束
    override_manager.update_manifold_enabled(True)
    override = override_manager.get_override()
    should_apply = override.should_apply_manifold(alpha, default_threshold)
    print(f"强制启用后, 应用流形约束: {should_apply}")
    assert should_apply, "流形约束覆盖失败"
    print("✅ 流形约束覆盖测试通过")

if __name__ == "__main__":
    test_alpha_override()
    test_r_human_override()
    test_q_matrix_override()
    test_manifold_override()

    print("\n" + "=" * 60)
    print("所有测试通过！")
    print("=" * 60)
```

运行测试:
```bash
python scripts/test_parameter_override.py
```

---

## 故障排除

### 问题1: 覆盖不生效

**检查**:
1. 确认导入了 `ParameterOverrideManager`
2. 确认调用了 `override.get_alpha()` 等方法
3. 确认调试界面正在运行

### 问题2: 状态历史不更新

**检查**:
1. 确认导入了 `state_history`
2. 确认在控制循环中记录数据
3. 确认调试界面的刷新按钮被点击

### 问题3: 参数覆盖后系统不稳定

**原因**: 参数设置不合理

**解决**:
- α覆盖: 保持在[0, 1]范围
- R覆盖: 不要设置过小（<1e-6）或过大（>1e0）
- Q覆盖: 缩放因子保持在[0.1, 10]范围

---

## 下一步

1. 完成R矩阵和α的覆盖集成
2. 在控制器中添加状态历史记录
3. 运行完整的验证实验
4. 收集论文数据

**预计时间**: 1-2小时完成完整集成