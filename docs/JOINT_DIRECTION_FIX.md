# 🔧 关节方向问题诊断与修复指南

## 问题描述

录制数据回放时，发现某个关节方向反了，与直接控制时的行为不一致。

---

## 🔍 诊断步骤

### Step 1: 运行诊断工具

```bash
# 检查当前关节方向配置
python scripts/diagnose_joint_directions.py

# 分析录制文件
python scripts/diagnose_joint_directions.py --recording data/recordings/your_file.jsonl
```

### Step 2: 对比测试

```bash
# 测试 1: 直接控制（不录制）
python scripts/simulate_full_flow.py
# 观察机器人运动，记录关节行为

# 测试 2: 录制后回放
python scripts/record_vision_data.py data/test.jsonl --duration 10
python scripts/simulate_full_flow.py &
python scripts/playback_vision_data.py data/test.jsonl
# 观察机器人运动，对比是否一致
```

### Step 3: 单关节测试

修改配置文件，锁定其他关节，只测试一个关节：

```yaml
# config/system_config.yaml
robot:
  joint_enabled:
    - true   # Joint 0: 测试这个
    - false  # Joint 1: 锁定
    - false  # Joint 2: 锁定
    - false  # Joint 3: 锁定
    - false  # Joint 4: 锁定
    - false  # Joint 5: 锁定
    - false  # Joint 6: 锁定
```

---

## 🎯 可能的原因

### 原因 1: 配置文件不一致

**问题**：仿真和真机使用了不同的配置文件

**检查**：
```bash
# 检查当前使用的配置
echo $VIST_CONFIG

# 如果为空，使用默认配置
# 默认: config/system_config.yaml
```

**解决方案**：
```bash
# 确保使用相同的配置文件
export VIST_CONFIG=config/system_config.yaml

# 仿真
python scripts/simulate_full_flow.py

# 真机
python scripts/run_real_robot_vist_refactored.py
```

### 原因 2: 关节方向配置错误

**问题**：`joint_directions` 配置不正确

**检查**：
```yaml
# config/system_config.yaml
robot:
  joint_directions:
    - -1  # Joint 0: Shoulder_Pitch (反向)
    - 1   # Joint 1: Shoulder_Roll
    - -1  # Joint 2: Shoulder_Yaw (反向)
    - 1   # Joint 3: Elbow_Pitch
    - 1   # Joint 4: Wrist_Yaw
    - 1   # Joint 5: Wrist_Pitch
    - 1   # Joint 6: Wrist_Roll
```

**解决方案**：
1. 确定哪个关节方向反了
2. 修改对应的 `joint_directions` 值（1 → -1 或 -1 → 1）
3. 重新测试

### 原因 3: 关节方向未正确应用

**问题**：代码中没有正确应用 `joint_directions`

**检查位置**：
1. `src/core/geometric_arm_solver.py` - 几何求解器
2. `src/robot/arm_driver.py` - 机器人驱动
3. `scripts/simulate_full_flow.py` - 仿真环境

**解决方案**：
确保在发送关节角度前应用方向：
```python
# 正确的做法
q_final = q_calculated * joint_directions[i] + joint_offsets[i]

# 错误的做法（忘记应用方向）
q_final = q_calculated + joint_offsets[i]
```

### 原因 4: 坐标系转换问题

**问题**：录制时和回放时使用了不同的坐标系

**检查**：
- `src/core/motion_mapper.py` - 坐标转换逻辑
- `config/system_config.yaml` - `coordinate_transform` 配置

**解决方案**：
确保坐标转换矩阵一致：
```yaml
coordinate_transform:
  rotation_matrix: [
    [0,  0,  1],  # X_robot = Z_shoulder
    [0, -1,  0],  # Y_robot = -Y_shoulder
    [1,  0,  0]   # Z_robot = X_shoulder
  ]
```

---

## 🛠️ 快速修复方法

### 方法 1: 调整关节方向配置

如果发现 Joint 2 方向反了：

```yaml
# config/system_config.yaml
robot:
  joint_directions:
    - -1  # Joint 0
    - 1   # Joint 1
    - 1   # Joint 2: 从 -1 改为 1 ✅
    - 1   # Joint 3
    - 1   # Joint 4
    - 1   # Joint 5
    - 1   # Joint 6
```

### 方法 2: 在回放时翻转关节

如果不想修改配置，可以在回放工具中添加翻转逻辑：

```python
# scripts/playback_vision_data.py
# 在发送数据前翻转特定关节
def flip_joint(keypoints, joint_index):
    # 这里添加翻转逻辑
    pass
```

### 方法 3: 重新录制数据

修复配置后，重新录制数据：

```bash
# 1. 修改配置文件
vim config/system_config.yaml

# 2. 重新录制
python scripts/record_vision_data.py data/fixed_recording.jsonl --duration 60

# 3. 测试
python scripts/simulate_full_flow.py &
python scripts/playback_vision_data.py data/fixed_recording.jsonl
```

---

## 📊 验证方法

### 验证 1: 视觉对比

```bash
# 同时运行直接控制和回放，观察是否一致
# 终端 1: 直接控制
python scripts/simulate_full_flow.py

# 终端 2: 回放
python scripts/simulate_full_flow.py &
python scripts/playback_vision_data.py data/test.jsonl
```

### 验证 2: 数据对比

添加日志记录关节角度：

```python
# 在 simulate_full_flow.py 中添加
print(f"关节角度: {q_solution}")

# 对比直接控制和回放时的关节角度
```

### 验证 3: 单关节测试

逐个测试每个关节：

```bash
# 测试 Joint 0
# 修改 config/system_config.yaml，只启用 Joint 0
python scripts/simulate_full_flow.py &
python scripts/playback_vision_data.py data/test.jsonl

# 测试 Joint 1
# 修改配置，只启用 Joint 1
# ...
```

---

## 🎯 常见问题

### Q1: 如何确定是哪个关节反了？

**A**: 使用单关节测试法：

1. 锁定所有关节
2. 只启用一个关节
3. 做简单的上下或左右运动
4. 观察机器人是否按预期方向运动
5. 重复测试每个关节

### Q2: 为什么直接控制正常，回放就反了？

**A**: 可能的原因：

1. 录制数据时使用了不同的配置文件
2. 回放工具没有正确应用关节方向
3. 数据格式问题（例如关节顺序不一致）

### Q3: 修改配置后需要重新录制吗？

**A**: 不一定：

- 如果修改的是 `joint_directions`，**不需要**重新录制（录制的是人体关键点，不是关节角度）
- 如果修改的是坐标转换矩阵，**需要**重新录制

### Q4: 如何在不修改配置的情况下临时翻转关节？

**A**: 在代码中添加临时翻转：

```python
# 临时翻转 Joint 2
q_solution[2] = -q_solution[2]
```

---

## 📚 相关文件

- [diagnose_joint_directions.py](../scripts/diagnose_joint_directions.py) - 诊断工具
- [system_config.yaml](../config/system_config.yaml) - 系统配置
- [geometric_arm_solver.py](../src/core/geometric_arm_solver.py) - 几何求解器
- [arm_driver.py](../src/robot/arm_driver.py) - 机器人驱动

---

## 🚀 下一步

1. 运行诊断工具确定问题
2. 修改配置文件
3. 重新测试
4. 如果问题持续，检查代码中的关节方向应用逻辑

---

**作者**: VIST Project
**日期**: 2026-02-22