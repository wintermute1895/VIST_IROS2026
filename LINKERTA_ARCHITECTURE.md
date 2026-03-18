# LinkerTA 双臂架构说明

## 🔑 关键发现

**LinkerTA是双臂一体设备！一个节点同时控制和发布左右两只臂的数据。**

## 📊 架构图

### 错误理解（之前）
```
┌──────────────┐         ┌──────────────┐
│ LinkerTA节点1 │         │ LinkerTA节点2 │
│ (左臂)       │         │ (右臂)       │
└──────┬───────┘         └──────┬───────┘
       │                        │
       ▼                        ▼
  /left_arm_joint_control  /right_arm_joint_control
```
❌ 这是错误的！会导致频率翻倍（160Hz）

### 正确理解
```
┌─────────────────────────────┐
│     LinkerTA节点 (单个)      │
│   读取14个关节（双臂一体）    │
│                             │
│  前7个关节 → 左臂            │
│  后7个关节 → 右臂            │
└──────┬──────────────┬───────┘
       │              │
       ▼              ▼
/left_arm_joint_control  /right_arm_joint_control
   (80Hz)                (80Hz)
```
✅ 这是正确的！

## 🔍 代码证据

查看 `main_ros2.cpp` 第58-75行：

```cpp
// 一次性读取所有关节（14个）
std::vector<float> position = arm.getJointPosition();

// 分配给左右臂
for (size_t i = 0; i < position.size(); ++i) {
    if (i <= 6) {
        left_joint_states.position.push_back(position[i]);  // 前7个
    } else {
        right_joint_states.position.push_back(position[i]); // 后7个
    }
}

// 同时发布两个话题
pub_left_arm_control->publish(left_joint_states);
pub_right_arm_control->publish(right_joint_states);
```

**一个循环，一次读取，同时发布两个话题！**

## ⚠️ 为什么会出现160Hz？

### 场景1：启动了两个LinkerTA节点

```bash
# 错误做法（会导致160Hz）
ros2 run linkerta linkerta_node &  # 节点1
ros2 run linkerta linkerta_node &  # 节点2
```

**结果**：
- 节点1发布 `/left_arm_joint_control` (80Hz)
- 节点1发布 `/right_arm_joint_control` (80Hz)
- 节点2发布 `/left_arm_joint_control` (80Hz) ← 重复！
- 节点2发布 `/right_arm_joint_control` (80Hz) ← 重复！

**总频率**：80Hz + 80Hz = **160Hz** ❌

### 场景2：只启动一个节点（正确）

```bash
# 正确做法
ros2 run linkerta linkerta_node
```

**结果**：
- 节点发布 `/left_arm_joint_control` (80Hz) ✅
- 节点发布 `/right_arm_joint_control` (80Hz) ✅

**总频率**：80Hz ✅

## 🐛 CAN错误的原因

```
Failed to send CAN frame: wrote -1 / 16  errno=6 (No such device or address)
```

这个错误是因为：
1. LinkerTA试图读取14个关节（双臂）
2. 但你可能只连接了一只臂（7个关节）
3. 读取另一只臂时，CAN总线上找不到设备

**这是正常的！** 如果你只使用单臂，这个错误可以忽略。

## ✅ 正确的启动方式

### 方法1：使用修复后的启动脚本

```bash
./start_linkerta.sh
# 选择选项1：启动LinkerTA (双臂一体设备)
```

### 方法2：手动启动

```bash
# 只启动一个节点
ros2 run linkerta linkerta_node --ros-args \
    --params-file ros2_ws/src/external_sdk/arm_teleop/src/linkerta/config/lta.yaml
```

### 方法3：使用launch文件

```bash
ros2 launch linkerta run.launch.py
```

## 📋 验证频率

```bash
# 检查左臂频率（应该是80Hz）
ros2 topic hz /left_arm_joint_control

# 检查右臂频率（应该是80Hz）
ros2 topic hz /right_arm_joint_control

# 检查有多少个发布者（应该只有1个）
ros2 topic info /left_arm_joint_control -v
```

**正确的输出**：
```
Publisher count: 1  ← 只有一个发布者！
```

**错误的输出**：
```
Publisher count: 2  ← 有两个发布者！说明启动了两个节点
```

## 🎯 完整的双臂遥操作系统启动

```bash
# 1. 启动CAN设备
sudo ip link set can0 up type can bitrate 1000000

# 2. 启动LinkerTA（一个节点，发布双臂数据）
./start_linkerta.sh
# 选择选项1

# 3. 新开终端，启动左臂滤波节点
python3 ros2_ws/src/nodes/vist_filter_node.py --ros-args \
    --params-file config/baseline_filters_config.yaml \
    -p arm_side:=left

# 4. 新开终端，启动右臂滤波节点
python3 ros2_ws/src/nodes/vist_filter_node.py --ros-args \
    --params-file config/baseline_filters_config.yaml \
    -p arm_side:=right

# 5. 新开终端，启动双臂可视化
python3 visualize_dual_arm_realtime.py

# 6. 在浏览器中查看
# http://127.0.0.1:7000/static/
```

## 📊 数据流图（完整版）

```
┌─────────────────────────────┐
│     LinkerTA节点 (1个)       │
│   CAN总线读取14个关节        │ 80Hz循环
└──────┬──────────────┬───────┘
       │              │
       ▼              ▼
/left_arm_joint_control  /right_arm_joint_control
   (80Hz)                (80Hz)
       │                    │
       ▼                    ▼
┌──────────────┐      ┌──────────────┐
│ 左臂滤波节点  │      │ 右臂滤波节点  │
│ (VIST/OneEuro)│      │ (VIST/OneEuro)│
└──────┬───────┘      └──────┬───────┘
       │                      │
       ▼                      ▼
/filtered_left_joint_control  /filtered_right_joint_control
   (80Hz)                        (80Hz)
       │                          │
       └──────────┬───────────────┘
                  ▼
         ┌────────────────┐
         │ 双臂可视化节点  │
         └────────────────┘
```

## 🔧 如果只想使用单臂

如果你只连接了一只臂，但不想看到CAN错误：

### 选项1：忽略错误（推荐）
- CAN错误不影响已连接臂的正常工作
- 只是尝试读取未连接的臂时报错

### 选项2：修改源码（高级）
修改 `main_ros2.cpp`，只发布已连接的臂的数据。

## 📝 总结

| 问题 | 原因 | 解决方案 |
|------|------|---------|
| 频率160Hz | 启动了两个LinkerTA节点 | 只启动一个节点 |
| CAN错误 | 试图读取未连接的臂 | 忽略错误或只连接双臂 |
| 话题重复 | 多个节点发布同一话题 | 检查 `ros2 topic info` |

---

**关键要点**：
- ✅ LinkerTA是双臂一体设备
- ✅ 只需要启动一个LinkerTA节点
- ✅ 一个节点同时发布左右臂数据
- ✅ 每个话题的频率都是80Hz
- ✅ CAN错误可以忽略（如果只用单臂）