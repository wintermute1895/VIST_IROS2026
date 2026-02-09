# VIST 冲突检测快速参考

## 🚀 快速开始

### 1. 基本使用

```python
from src.core.intent_detector import EnhancedIntentDetector
from src.core.intent_detector import compute_human_command, compute_algorithm_expectation

# 初始化检测器
detector = EnhancedIntentDetector()

# 主循环
while True:
    # 计算人类指令和算法期望
    human_command = compute_human_command(current_pos, target_pos, velocity)
    algorithm_expectation = compute_algorithm_expectation(current_pos, socket_pos)

    # 检测意图（带冲突检测）
    result = detector.detect_intent(
        distance=distance,
        velocity=velocity,
        human_command=human_command,
        algorithm_expectation=algorithm_expectation,
        alignment_error=alignment_error
    )

    # 使用有效意图因子
    alpha_eff = result.alpha_effective  # α_eff = α × (1-β)
    beta = result.beta  # 冲突因子

    # 混合人类和算法目标
    target = (1 - alpha_eff) * human_target + alpha_eff * algorithm_target
```

### 2. 运行测试

```bash
# 运行单元测试
python tests/test_intent_detector.py

# 运行集成示例
python examples/vist_enhanced_intent_control.py
```

## 📊 核心公式

```
α = f(v, d)           # 基础意图因子
β = f(θ, v)           # 冲突因子
α_eff = α × (1-β)     # 有效意图因子
```

## 🎯 状态机

```
APPROACHING          → α = 0.0 (人类主导)
VISUAL_ADMITTANCE    → α = 1.0 (算法主导)
CORRECTION_OVERRIDE  → α = 0.2 (人类接管)
CONSTRAINED_INSERTION → α = 1.0 (算法主导)
RELEASE              → α = 0.0 (人类主导)
```

## 📁 文件位置

```
src/core/intent_detector.py                    # 核心实现
config/vist_intent_detection.yaml              # 配置文件
examples/vist_enhanced_intent_control.py       # 集成示例
tests/test_intent_detector.py                  # 单元测试
docs/CONFLICT_DETECTION_AND_COMPLIANT_TAKEOVER.md  # 详细文档
docs/INTENT_DETECTION_README.md                # 快速开始
docs/IMPLEMENTATION_SUMMARY.md                 # 实现总结
```

## 🔧 关键参数

```yaml
conflict:
  angle_threshold_deg: 30      # 角度阈值
  velocity_threshold: 0.005    # 速度阈值（0.5cm/s）
  max_velocity: 0.05           # 最大速度（5cm/s）

alpha_values:
  approaching: 0.0
  visual_admittance: 1.0
  correction_override: 0.2
  constrained_insertion: 1.0
  release: 0.0
```

## 💡 使用场景

### 场景 1: 标定精度不足
```
算法引导位置偏离 → 人类微调 → 系统检测冲突 → 柔顺接管 → 成功修正
```

### 场景 2: 动态障碍物
```
突然出现障碍物 → 人类快速拉回 → 系统检测强烈冲突 → 快速避障
```

### 场景 3: 人类探索
```
人类探索性移动 → 系统检测持续冲突 → 进入修正模式 → 支持探索
```

## 📚 相关文档

- [CONFLICT_DETECTION_AND_COMPLIANT_TAKEOVER.md](./CONFLICT_DETECTION_AND_COMPLIANT_TAKEOVER.md) - 详细原理
- [INTENT_DETECTION_README.md](./INTENT_DETECTION_README.md) - API 文档
- [IMPLEMENTATION_SUMMARY.md](./IMPLEMENTATION_SUMMARY.md) - 实现总结
- [VIST_COMPLETE_WORKFLOW.md](./VIST_COMPLETE_WORKFLOW.md) - 完整工作流程

## ✅ 测试状态

```
ALL TESTS PASSED ✅
- No Conflict Detection ✅
- Full Conflict Detection ✅
- Partial Conflict Detection ✅
- Effective Alpha Calculation ✅
- State Transitions ✅
- Compliant Takeover Scenario ✅
```

---

**最后更新**: 2026-02-09
