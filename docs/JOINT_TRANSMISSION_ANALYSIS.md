# 关节指令传输流程与序号映射分析

## 完整数据流

```
遥操臂 → ROS2话题 → VIST节点 → 单位转换 → VIST滤波器 → 输出 → ROS2话题 → 机械臂
LinkerTA  /exo_joint  timer_callback  deg→rad   update()    q_out   /filtered   控制器
         (角度)                                                      (弧度)
```

---

## 详细流程分析

### 1. 遥操臂输入 → ROS2话题

**话题**: `/left_exo_joint_control` 或 `/right_exo_joint_control`

**数据类型**: `sensor_msgs/JointState`

**关节序号**:
```python
msg.name = ['joint_1', 'joint_2', 'joint_3', 'joint_4', 'joint_5', 'joint_6', 'joint_7']
msg.position = [θ1, θ2, θ3, θ4, θ5, θ6, θ7]  # 单位：角度（degree）
```

**关节映射**:
```
joint_1 → Shoulder_Pitch
joint_2 → Shoulder_Roll
joint_3 → Shoulder_Yaw
joint_4 → Elbow_Pitch
joint_5 → Wrist_Yaw
joint_6 → Wrist_Pitch
joint_7 → Wrist_Roll
```

**⚠️ 潜在问题点1**:
- LinkerTA输出的是**角度**（degree），不是弧度
- 需要在后续环节转换

---

### 2. ROS2话题 → VIST节点接收

**代码位置**: `vist_filter_node.py` 第470-475行

```python
def exo_callback(self, msg: JointState):
    """外骨骼数据回调"""
    with self.exo_lock:
        self.exo_data = msg  # 直接保存，不做任何处理
        self.freq_exo_receive.tick()
```

**关节序号**: **保持不变**
```python
self.exo_data.position = [θ1, θ2, θ3, θ4, θ5, θ6, θ7]  # 角度
```

**✅ 检查点**: 这里没有序号重排，直接保存原始数据

---

### 3. 定时器回调 → 提取关节角

**代码位置**: `vist_filter_node.py` 第489-518行

```python
def timer_callback(self):
    # 获取数据副本
    with self.exo_lock:
        exo_data = self.exo_data

    # 选择数据源（优先外骨骼）
    source_data = exo_data if exo_data is not None else vision_data

    # 提取输入关节角
    q_in = list(source_data.position)  # 直接使用position列表
```

**关节序号**: **保持不变**
```python
q_in = [θ1, θ2, θ3, θ4, θ5, θ6, θ7]  # 角度
```

**✅ 检查点**: 使用 `list(source_data.position)` 直接转换，序号不变

---

### 4. 单位转换（VIST专用）

**代码位置**: `vist_filter_node.py` 第563-565行

```python
if self.filter_type == 'vist':
    q_in_array = np.array(q_in)
    q_in_rad = np.deg2rad(q_in_array).tolist()
```

**关节序号**: **保持不变**
```python
q_in_rad = [θ1_rad, θ2_rad, θ3_rad, θ4_rad, θ5_rad, θ6_rad, θ7_rad]
```

**✅ 检查点**: `np.deg2rad()` 是逐元素转换，不改变序号

---

### 5. 调用VIST滤波器

**代码位置**: `vist_filter_node.py` 第573行

```python
q_out = self.current_filter.update(q_in_rad, dt)
```

**传入**: `filters.py` 的 `VISTFilter.update()`

**代码位置**: `filters.py` 第208行

```python
def update(self, q_in, dt, robot_joints=None):
    # 调用VIST卡尔曼滤波器
    filtered_joints = self.vist_filter.update(
        shadow_joints=q_in,  # 直接传递
        target_pose=self.target_pose,
        virtual_joints=None
    )
    return filtered_joints
```

**关节序号**: **保持不变**
```python
shadow_joints = [θ1_rad, θ2_rad, θ3_rad, θ4_rad, θ5_rad, θ6_rad, θ7_rad]
```

**✅ 检查点**: 直接传递，没有重排

---

### 6. VIST卡尔曼滤波器内部处理

**代码位置**: `vist_kalman_filter.py` 第619行

```python
def update(self, shadow_joints, target_pose, virtual_joints=None):
    # 角度归一化
    shadow_joints = self._normalize_joint_angles(shadow_joints, label="input_shadow")

    # 第一帧同步
    if self._is_first_frame:
        self.state[:self.n_joints] = shadow_joints.copy()

    # ... 卡尔曼滤波处理 ...

    # 输出转换（Model to Motor）
    filtered_joints[2] = -filtered_joints[2]  # Joint 3
    filtered_joints[3] = -filtered_joints[3]  # Joint 4
    filtered_joints[4] = -filtered_joints[4]  # Joint 5
    filtered_joints[5] = -filtered_joints[5]  # Joint 6

    return filtered_joints
```

**关节序号**: **保持不变**，但有**方向修正**

**⚠️ 潜在问题点2**:
- 索引2, 3, 4, 5对应的是Joint 3, 4, 5, 6
- 这些关节的**符号被取反**，但**序号不变**

**输出**:
```python
filtered_joints = [θ1, θ2, -θ3, -θ4, -θ5, -θ6, θ7]  # 弧度
```

---

### 7. 返回节点 → 发布输出

**代码位置**: `vist_filter_node.py` 第603-618行

```python
def publish_filtered_state(self, filtered_state: np.ndarray):
    msg = JointState()
    msg.header.stamp = self.get_clock().now().to_msg()
    msg.header.frame_id = 'base_link'
    msg.name = [f'joint_{i+1}' for i in range(len(filtered_state))]
    msg.position = filtered_state.tolist()

    self.filtered_pub.publish(msg)
```

**关节序号**: **保持不变**
```python
msg.name = ['joint_1', 'joint_2', 'joint_3', 'joint_4', 'joint_5', 'joint_6', 'joint_7']
msg.position = [θ1, θ2, -θ3, -θ4, -θ5, -θ6, θ7]  # 弧度
```

**✅ 检查点**: 使用 `f'joint_{i+1}'` 生成名称，序号从1开始，与输入一致

---

## 关节序号映射总结

### 整个流程中的序号

| 阶段 | Joint 1 | Joint 2 | Joint 3 | Joint 4 | Joint 5 | Joint 6 | Joint 7 |
|------|---------|---------|---------|---------|---------|---------|---------|
| 遥操臂输入 | θ1 | θ2 | θ3 | θ4 | θ5 | θ6 | θ7 |
| ROS2接收 | θ1 | θ2 | θ3 | θ4 | θ5 | θ6 | θ7 |
| 提取数组 | [0] | [1] | [2] | [3] | [4] | [5] | [6] |
| 单位转换 | [0] | [1] | [2] | [3] | [4] | [5] | [6] |
| VIST输入 | [0] | [1] | [2] | [3] | [4] | [5] | [6] |
| 方向修正 | [0] | [1] | **-[2]** | **-[3]** | **-[4]** | **-[5]** | [6] |
| VIST输出 | [0] | [1] | [2] | [3] | [4] | [5] | [6] |
| ROS2发布 | θ1' | θ2' | -θ3' | -θ4' | -θ5' | -θ6' | θ7' |

**结论**: **序号没有错位**，只有**符号修正**

---

## 潜在问题点分析

### 问题1: 单位转换

**位置**: `vist_filter_node.py` 第563-565行

**问题**: 只有VIST滤波器做了角度→弧度转换，其他滤波器没有

**影响**:
- VIST: 正确（弧度）
- FSM/其他: 可能错误（如果期望弧度但收到角度）

**建议**:
- 在节点层统一转换，而不是在滤波器层

---

### 问题2: 关节方向修正

**位置**: `vist_kalman_filter.py` 第850-853行

**代码**:
```python
filtered_joints[2] = -filtered_joints[2]  # Joint 3
filtered_joints[3] = -filtered_joints[3]  # Joint 4
filtered_joints[4] = -filtered_joints[4]  # Joint 5
filtered_joints[5] = -filtered_joints[5]  # Joint 6
```

**问题**:
- 这是**输出转换**（Model to Motor）
- 但在算法内部也有**输入转换**（Motor to Model）

**检查**: 是否有双重取反？

**代码位置**: `vist_kalman_filter.py` 第1024-1027行

```python
# 修改：对 3、4、5、6 号关节（索引 2、3、4、5）取反，修正关节方向
shadow_joints_corrected = shadow_joints.copy()
shadow_joints_corrected[2] = -shadow_joints_corrected[2]  # Joint 3
shadow_joints_corrected[3] = -shadow_joints_corrected[3]  # Joint 4
shadow_joints_corrected[4] = -shadow_joints_corrected[4]  # Joint 5
shadow_joints_corrected[5] = -shadow_joints_corrected[5]  # Joint 6
```

**结论**:
- ✅ 有闭环：输入取反 → 算法处理 → 输出取反
- ✅ 这是正确的，保证了算法内部使用统一的坐标系

---

### 问题3: 配置文件中的关节方向

**位置**: `config/system_config.yaml` 第47-54行

```yaml
joint_directions:
  - -1  # Joint 0: Shoulder_Pitch (反向)
  - 1   # Joint 1: Shoulder_Roll
  - -1  # Joint 2: Shoulder_Yaw (反向)
  - 1   # Joint 3: Elbow_Pitch
  - 1   # Joint 4: Wrist_Yaw
  - 1   # Joint 5: Wrist_Pitch
  - 1   # Joint 6: Wrist_Roll
```

**问题**:
- 配置文件中定义了关节方向系数
- 但代码中硬编码了Joint 3,4,5,6取反
- **两者不一致！**

**检查**: 配置文件的 `joint_directions` 是否被使用？

---

## 验证方法

### 方法1: 添加调试打印

在 `vist_filter_node.py` 的 `timer_callback` 中添加：

```python
# 在第518行后添加
if self.iteration_count % 100 == 0:  # 每100帧打印一次
    self.get_logger().info(f"关节序号检查:")
    self.get_logger().info(f"  输入 q_in: {q_in}")
    self.get_logger().info(f"  输出 q_out: {q_out}")
    self.get_logger().info(f"  差值: {np.array(q_out) - np.array(q_in)}")
```

### 方法2: 单关节测试

1. 只移动Joint 1，观察输出的哪个关节变化
2. 依次测试每个关节
3. 确认输入输出的序号对应关系

### 方法3: 检查ROS2话题

```bash
# 查看输入话题
ros2 topic echo /left_exo_joint_control --once

# 查看输出话题
ros2 topic echo /filtered_left_joint_control --once

# 对比关节名称和位置
```

---

## 建议的修改

### 1. 统一单位转换位置

**当前**: 在滤波器类型判断中转换

**建议**: 在节点层统一转换

```python
# vist_filter_node.py 第518行后
q_in = list(source_data.position)

# 统一转换为弧度（如果输入是角度）
if self.input_unit == 'degree':  # 从配置读取
    q_in = np.deg2rad(q_in).tolist()
```

### 2. 使用配置文件的关节方向

**当前**: 硬编码取反Joint 3,4,5,6

**建议**: 从配置文件读取

```python
# 读取配置
joint_directions = config.robot_joint_directions

# 应用方向修正
for i, direction in enumerate(joint_directions):
    filtered_joints[i] *= direction
```

### 3. 添加序号验证

```python
def verify_joint_mapping(self):
    """验证关节序号映射是否正确"""
    test_input = [1.0, 0, 0, 0, 0, 0, 0]  # 只有Joint 1有值
    test_output = self.current_filter.update(test_input, 0.01)

    # 检查输出的哪个位置有值
    max_idx = np.argmax(np.abs(test_output))
    if max_idx != 0:
        self.get_logger().warn(f"⚠️ 关节序号可能错位: 输入Joint 1, 输出Joint {max_idx+1}")
```

---

## 总结

### ✅ 确认正确的部分

1. **序号没有错位**: 整个流程中关节序号保持一致
2. **闭环方向修正**: 输入取反 → 算法 → 输出取反，保证一致性
3. **单位转换**: VIST滤波器正确处理了角度→弧度转换

### ⚠️ 需要注意的部分

1. **配置文件未使用**: `joint_directions` 配置与代码不一致
2. **硬编码方向**: Joint 3,4,5,6的方向修正是硬编码的
3. **单位转换位置**: 应该在节点层统一处理，而不是在滤波器层

### 🔍 建议验证

1. 运行单关节测试，确认序号对应关系
2. 检查配置文件的 `joint_directions` 是否应该被使用
3. 添加调试打印，监控输入输出的对应关系