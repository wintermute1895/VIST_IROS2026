# ⚠️ 配置冲突分析与解决方案

## 问题发现

在创建消融实验框架时，发现了与现有系统配置的潜在冲突：

### 1. 配置命名冲突

**现有配置**（`system_config.yaml`）：
```yaml
# Line 348-369
filtering:
  enable_mapper_filter: true
  mapper_filter_type: "oneeuro"
  enable_control_filter: true
  control_filter_type: "oneeuro"
```

**消融实验配置**（原版 `ablation_config.yaml`）：
```yaml
filter:  # ❌ 与 filtering 命名不一致
  type: "none"
```

### 2. 滤波器层级混淆

系统中有多层滤波器，但消融实验配置没有明确指定要替换哪一层：

```
视觉输入 → Mapper 层滤波 → VIST 卡尔曼滤波 → 安全控制器 → 机器人
           ↑                ↑                  ↑
           filtering.       vist_kalman.       SafeRobotController
           mapper_filter    enabled            (内置安全限制)
```

### 3. 配置继承问题

消融实验配置使用 `inherit_from: "system_config.yaml"`，但没有明确说明哪些配置会被覆盖。

---

## 解决方案

### 方案 1: 修正配置命名空间（推荐）

创建新的配置文件 `ablation_config_fixed.yaml`，明确指定替换 VIST 卡尔曼滤波层：

```yaml
experiment_1_no_filter:
  name: "No Filter (Baseline)"

  # 明确指定：只替换 VIST 卡尔曼滤波器
  vist_kalman:
    enabled: false  # 禁用 VIST 卡尔曼滤波
    ablation_filter_type: "none"  # 使用无滤波器替代

  inherit_from: "system_config.yaml"
```

**优点**：
- ✅ 命名空间清晰，不会与 `filtering` 段冲突
- ✅ 明确指定替换的层级
- ✅ 不影响 Mapper 层和安全控制器

**缺点**：
- ⚠️ 需要修改 VIST 控制器代码以支持消融实验模式

### 方案 2: 使用独立的配置文件

为每个消融实验创建完整的配置文件，不使用继承：

```bash
config/
├── system_config.yaml          # 主配置
├── ablation_no_filter.yaml     # 实验 1 完整配置
├── ablation_moving_average.yaml # 实验 2 完整配置
└── ...
```

**优点**：
- ✅ 完全独立，不会有继承冲突
- ✅ 每个实验的配置一目了然

**缺点**：
- ❌ 配置文件冗余，维护困难
- ❌ 修改主配置时需要同步所有消融实验配置

### 方案 3: 使用环境变量覆盖

在运行时通过环境变量覆盖特定配置：

```bash
export VIST_ABLATION_MODE=true
export VIST_ABLATION_FILTER="one_euro"
python scripts/run_real_robot_vist_refactored.py
```

**优点**：
- ✅ 不需要修改配置文件
- ✅ 灵活性高

**缺点**：
- ❌ 配置分散，不易追踪
- ❌ 需要修改代码以支持环境变量

---

## 推荐实施方案

### Step 1: 使用修正后的配置文件

使用 `ablation_config_fixed.yaml` 替代原来的 `ablation_config.yaml`：

```bash
# 删除旧配置
rm config/ablation_config.yaml

# 使用新配置
mv config/ablation_config_fixed.yaml config/ablation_config.yaml
```

### Step 2: 修改 VIST 控制器以支持消融实验

在 `VISTController` 中添加消融实验模式：

```python
class VISTController:
    def __init__(self, config):
        # 检查是否启用消融实验模式
        if hasattr(config, 'vist_kalman') and hasattr(config.vist_kalman, 'ablation_filter_type'):
            # 消融实验模式：使用替代滤波器
            self.ablation_mode = True
            self.ablation_filter = self._create_ablation_filter(config)
        else:
            # 正常模式：使用 VIST 卡尔曼滤波
            self.ablation_mode = False
            self.vist_filter = VISTKalmanFilter(...)
```

### Step 3: 更新消融实验脚本

修改 `run_ablation_study.py` 以正确合并配置：

```python
def _create_temp_config(self, exp_config):
    # 加载基础配置
    with open(f"config/{exp_config['inherit_from']}", 'r') as f:
        base_config = yaml.safe_load(f)

    # 合并 vist_kalman 配置（而不是 filter 配置）
    if 'vist_kalman' in exp_config:
        if 'vist_kalman' not in base_config:
            base_config['vist_kalman'] = {}
        base_config['vist_kalman'].update(exp_config['vist_kalman'])

    # 保存临时配置
    ...
```

---

## 配置层级说明

为了避免混淆，明确各层滤波器的作用：

### 1. Mapper 层滤波器（`filtering.mapper_filter_type`）

**位置**：视觉节点 → Mapper → VIST 控制器
**作用**：平滑人体关键点数据
**配置**：
```yaml
filtering:
  enable_mapper_filter: true
  mapper_filter_type: "oneeuro"
```
**消融实验**：不替换此层（保持原样）

### 2. VIST 卡尔曼滤波器（`vist_kalman.enabled`）

**位置**：VIST 控制器内部
**作用**：意图驱动的自适应状态估计
**配置**：
```yaml
vist_kalman:
  enabled: true
```
**消融实验**：替换此层（对比不同滤波器）

### 3. 安全控制器（`SafeRobotController`）

**位置**：VIST 控制器 → 安全控制器 → 机器人
**作用**：速度/加速度限制、关节限位检查
**配置**：无独立配置段（内置逻辑）
**消融实验**：不替换此层（保持原样）

---

## 测试验证

### 验证配置不冲突

```bash
# 1. 加载主配置
python -c "
import yaml
with open('config/system_config.yaml') as f:
    config = yaml.safe_load(f)
print('filtering' in config)  # 应该输出 True
print('vist_kalman' in config)  # 应该输出 True
"

# 2. 加载消融实验配置
python -c "
import yaml
with open('config/ablation_config_fixed.yaml') as f:
    config = yaml.safe_load(f)
exp = config['experiment_1_no_filter']
print('vist_kalman' in exp)  # 应该输出 True
print('filter' in exp)  # 应该输出 False（已修正）
"
```

### 验证配置合并

```bash
# 测试配置合并逻辑
python scripts/run_ablation_study.py --config config/ablation_config_fixed.yaml --dry-run
```

---

## 总结

### 问题根源

1. **命名不一致**：`filter` vs `filtering`
2. **层级不明确**：没有指定替换哪一层滤波器
3. **配置继承不清晰**：覆盖规则不明确

### 解决方案

1. ✅ 使用 `vist_kalman.ablation_filter_type` 明确指定替换 VIST 卡尔曼滤波层
2. ✅ 保持 `filtering` 段不变，不影响 Mapper 层和安全控制器
3. ✅ 在 VIST 控制器中添加消融实验模式支持

### 下一步

1. 删除旧的 `ablation_config.yaml`
2. 使用 `ablation_config_fixed.yaml`
3. 修改 VIST 控制器以支持消融实验模式
4. 更新消融实验脚本的配置合并逻辑

---

**相关文件**：
- [system_config.yaml](../config/system_config.yaml) - 主配置文件
- [ablation_config_fixed.yaml](../config/ablation_config_fixed.yaml) - 修正后的消融实验配置
- [vist_controller.py](../src/control/vist_controller.py) - VIST 控制器（需要修改）
- [run_ablation_study.py](../scripts/run_ablation_study.py) - 消融实验脚本（需要修改）

**作者**: VIST Project
**日期**: 2026-02-22