# VIST实时参数调试界面使用指南

**创建日期**: 2026-02-19
**目的**: 实时调整参数，验证VIST机制效果

---

## 快速开始

### 1. 安装依赖

```bash
pip install gradio matplotlib
```

### 2. 启动调试界面

```bash
python scripts/debug_interface.py
```

界面将在浏览器中打开：`http://localhost:7860`

---

## 界面功能

### Tab 1: 🎯 机制层参数

**用途**: 绕过VIST机制，直接设置最终参数值

#### 意图因子 α
- **覆盖开关**: 启用后强制设置α值
- **滑块**: 0.0 ~ 1.0
- **验证实验**:
  ```
  设置α=1.0 → 在摄像头前让手在XY方向抖动 → 观察末端是否锁定在Z轴
  ```

#### 观测噪声 R_human
- **覆盖开关**: 启用后强制设置R_human
- **滑块**: log10(R_human) = -4 ~ -1
- **验证实验**:
  ```
  设置R_human=1e-1（高噪声）→ 观察人类抖动是否被抑制
  ```

#### 观测噪声 R_virtual
- **覆盖开关**: 启用后强制设置R_virtual
- **滑块**: log10(R_virtual) = -4 ~ -1
- **验证实验**:
  ```
  设置R_virtual=1e-4（低噪声）→ 观察虚拟引导的磁吸引效果
  ```

#### 流形约束
- **覆盖开关**: 强制启用流形约束
- **验证实验**:
  ```
  强制启用 → 观察末端是否只在Z轴运动
  ```

---

### Tab 2: ⚙️ 配置层参数

**用途**: 调整VIST机制的配置参数（不绕过机制）

#### R_human指数系数 λ
- **公式**: R_human(α) = R_base × exp(λα)
- **范围**: 0.0 ~ 10.0
- **默认**: 3.0
- **效果**: λ越大，α→1时R_human增长越快，颤抖抑制越强

#### R_virtual最小值 R_min
- **公式**: R_virtual(α) = R_min/(α+ε)
- **范围**: log10(R_min) = -4 ~ -2
- **默认**: 1e-3
- **效果**: R_min越小，α→1时虚拟引导权重越大，磁吸引越强

#### Z轴锁定阈值
- **范围**: 0.0 ~ 1.0
- **默认**: 0.8
- **效果**: 阈值越低，流形约束越早激活

---

### Tab 3: 📊 实时监控

**用途**: 查看系统状态和历史数据

#### 当前状态
- 当前α值
- 当前R_human
- 当前R_virtual
- 末端位置

#### 统计信息
- XY漂移（m）
- Z运动（m）
- 轨迹长度（m）

#### 图表
- 意图因子α历史
- 协方差历史
- 末端轨迹（XY、XZ、YZ、3D）

---

### Tab 4: 🧪 实验指南

包含5个验证实验的详细步骤和预期结果。

---

## 典型使用场景

### 场景1: 验证α=1时的颤抖抑制

**步骤**:
1. 打开"机制层参数"标签
2. 启用"α覆盖"，设置α=1.0
3. 启动VIST控制器
4. 在摄像头前让手疯狂抖动
5. 切换到"实时监控"标签
6. 观察末端轨迹是否平滑

**预期结果**:
- 手部抖动幅度大
- 末端轨迹平滑
- R_human值很大（~1e-1）

---

### 场景2: 验证流形约束的Z轴锁定

**步骤**:
1. 打开"机制层参数"标签
2. 启用"α覆盖"，设置α=1.0
3. 启用"强制启用流形约束"
4. 启动VIST控制器
5. 在摄像头前让手在XY方向移动
6. 切换到"实时监控"标签
7. 观察末端轨迹

**预期结果**:
- 手在XY方向移动
- 末端只在Z轴运动
- XY漂移接近0

**关键验证**: 腕部关节（J5-J7）不被锁死，能配合运动

---

### 场景3: 参数敏感性分析

**步骤**:
1. 打开"配置层参数"标签
2. 调整λ从1.0到10.0
3. 对每个λ值，执行相同的插入动作
4. 记录末端轨迹平滑度
5. 绘制λ vs 平滑度曲线

**预期结果**:
- λ越大，轨迹越平滑
- λ=3.0是一个好的平衡点

---

## 与VIST控制器集成

### 方法1: 在控制器中读取覆盖

在 `src/control/threaded_vist_controller.py` 中：

```python
from src.utils.parameter_override import ParameterOverrideManager

# 在控制循环中
override_manager = ParameterOverrideManager()
override = override_manager.get_override()

# 应用覆盖
if override.alpha_override is not None:
    alpha = override.alpha_override
else:
    alpha = intent_detector.compute_alpha(...)
```

### 方法2: 在卡尔曼滤波器中应用覆盖

在 `src/core/vist_kalman_filter.py` 中：

```python
from src.utils.parameter_override import ParameterOverrideManager

def predict(self, ...):
    override_manager = ParameterOverrideManager()
    override = override_manager.get_override()

    # 应用α覆盖
    alpha = override.get_alpha(self.alpha_smoothed)

    # 应用R覆盖
    r_human = override.get_r_human(computed_r_human, alpha, r_base, lambda_param)
    r_virtual = override.get_r_virtual(computed_r_virtual, alpha, r_min, conflict, gamma_c)

    # 应用Q覆盖
    Q = override.get_q_matrix(computed_q)
```

---

## 数据记录

### 记录状态历史

在控制循环中：

```python
from scripts.debug_interface import state_history
import time

# 记录数据
state_history['time'].append(time.time() - start_time)
state_history['alpha'].append(alpha)
state_history['alpha_override'].append(override.alpha_override or alpha)
state_history['r_human'].append(r_human)
state_history['r_virtual'].append(r_virtual)
state_history['end_effector_pos'].append(ee_pos)
```

### 导出数据

```python
import numpy as np

# 保存为CSV
data = {
    'time': state_history['time'],
    'alpha': state_history['alpha'],
    'r_human': state_history['r_human'],
    'r_virtual': state_history['r_virtual'],
}
np.savetxt('vist_debug_data.csv', np.column_stack(list(data.values())),
           delimiter=',', header=','.join(data.keys()))
```

---

## 故障排除

### 问题1: 界面无法启动

**原因**: Gradio未安装

**解决**:
```bash
pip install gradio
```

### 问题2: 覆盖不生效

**原因**: 控制器未读取覆盖

**解决**: 确保在控制器中集成了参数覆盖机制（见上文）

### 问题3: 图表不更新

**原因**: 状态历史未记录

**解决**: 在控制循环中添加数据记录代码（见上文）

---

## 高级用法

### 自定义实验

创建自己的实验脚本：

```python
from src.utils.parameter_override import ParameterOverrideManager

# 实验1: α=0 vs α=1
override_manager = ParameterOverrideManager()

# 阶段1: α=0
override_manager.update_alpha(0.0)
run_experiment(duration=10)  # 运行10秒

# 阶段2: α=1
override_manager.update_alpha(1.0)
run_experiment(duration=10)

# 对比结果
compare_trajectories()
```

### 批量实验

```python
# 扫描λ参数
lambdas = [1.0, 2.0, 3.0, 5.0, 10.0]
results = []

for lambda_val in lambdas:
    override_manager.update_human_lambda(lambda_val)
    result = run_experiment(duration=10)
    results.append(result)

# 绘制λ vs 性能曲线
plot_parameter_sweep(lambdas, results)
```

---

## 论文实验建议

### 实验设置

1. **对比方法**:
   - Raw Teleop (α=0, 无滤波)
   - Fixed Kalman (α=0.5, 固定协方差)
   - VIST (α自动计算)

2. **评估指标**:
   - 轨迹平滑度（加速度标准差）
   - XY漂移
   - Z运动精度
   - 任务完成时间

3. **实验任务**:
   - USB插入（垂直插入）
   - 螺丝拧紧（旋转约束）
   - 精密对准（位置约束）

### 数据收集

使用调试界面记录：
- α时间序列
- R_human、R_virtual时间序列
- 末端轨迹
- 关节角度

### 结果可视化

使用"实时监控"标签的图表：
- α历史图 → 论文Figure 3
- 协方差历史图 → 论文Figure 4
- 末端轨迹图 → 论文Figure 5

---

## 总结

这个调试界面提供了两个层次的参数控制：

1. **机制层**: 绕过VIST机制，直接验证最终效果
2. **配置层**: 调整机制参数，理解参数影响

通过这个界面，你可以：
- ✅ 验证VIST机制的有效性
- ✅ 理解各参数的物理意义
- ✅ 设计和执行实验
- ✅ 收集论文数据

**下一步**: 将参数覆盖机制集成到VIST控制器中，开始实验！