# VSCode代码审查清单 - 双臂数据流

## 阶段1: LinkerTA节点（数据源）

### 文件: `ros2_ws/src/external_sdk/arm_teleop/src/linkerta/src/main_ros2.cpp`

- [ ] **第40-41行**: 找到发布器创建
  - 话题: `/left_arm_joint_control`, `/right_arm_joint_control`
  - 消息类型: `sensor_msgs::msg::JointState`

- [ ] **第58行**: 找到数据源
  - `arm.getJointPosition()` 返回14个关节（左7+右7）

- [ ] **第63-69行**: 理解数据分割逻辑
  - 索引0-6 → 左臂
  - 索引7-13 → 右臂

- [ ] **第74-75行**: 找到数据发布
  - 同时发布左右臂数据
  - 频率: 80Hz (第56行)

**验证方法**:
```bash
ros2 topic echo /left_arm_joint_control --once
ros2 topic hz /left_arm_joint_control
```

---

## 阶段2: 滤波节点（数据处理）

### 文件: `ros2_ws/src/nodes/vist_filter_node.py`

- [ ] **第435-440行**: 找到订阅器创建
  - 订阅: `/left_arm_joint_control` 或 `/right_arm_joint_control`
  - 回调: `exo_callback`

- [ ] **第496-501行**: 理解回调函数
  - 只保存数据，不做处理
  - 使用线程锁保护

- [ ] **第515-661行**: 理解定时器回调 `timer_callback`
  - 频率: 80Hz
  - 关键步骤:
    1. 获取数据副本 (第527行)
    2. 应用方向修正 (第592行)
    3. 滤波处理 (第618行)
    4. 发布结果 (第650行)

- [ ] **第592行**: 验证方向修正
  ```python
  q_in_corrected = q_in_array * self.joint_directions
  ```
  - 左臂: `[1, 1, -1, 1, -1, 1, 1]`
  - 右臂: `[-1, 1, -1, 1, -1, -1, 1]`

- [ ] **第309行**: 追踪配置加载
  - 配置文件: `config/joint_directions.yaml`
  - 根据 `arm_side` 参数选择左/右臂配置

- [ ] **第663-687行**: 理解发布逻辑
  - 发布: `/filtered_left_joint_control` 或 `/filtered_right_joint_control`
  - 数据已包含方向修正
  - 单位: 角度（GELLO/OneEuro保持原单位）

**验证方法**:
```bash
ros2 topic echo /filtered_left_joint_control --once
python3 validate_data_flow.py
```

---

## 阶段3: 桥接节点（真机接口）

### 文件: `ros2_ws/src/external_sdk/arm_teleop/src/lbot_teleop/src/teleop_bridge_node.cpp`

- [ ] **第58-63行**: 找到订阅器创建
  - 订阅: `/filtered_left_joint_control`, `/filtered_right_joint_control`
  - 回调: `left_joint_callback`, `right_joint_callback`

- [ ] **第301-331行**: 理解左臂回调
  - 调用 `process_joints` 处理数据
  - 发布到 `/robot1/left_arm/joint_follow`

- [ ] **第221-261行**: 深入理解 `process_joints`
  - 步骤1: 关节映射 (第232-238行)
  - 步骤2: 方向修正 (第243-245行) ← 第二次修正
  - 步骤3: 角度→弧度 (第248行)
  - 步骤4: 缩放 (第251行)
  - 步骤5: 安全限位 (第254-256行)

- [ ] **第118-178行**: 理解参数加载
  - 第148-160行: 解析 `negation` 参数
  - 第154-156行: 分割为左右臂配置
  - 左臂: `negation[0:7]`
  - 右臂: `negation[7:14]`

- [ ] **第37-40行**: 找到发布器创建
  - 发布: `/robot1/left_arm/joint_follow`, `/robot1/right_arm/joint_follow`
  - 消息类型: `lbot_arm_interfaces::msg::FollowJoint`

**验证方法**:
```bash
ros2 topic echo /robot1/left_arm/joint_follow --once
ros2 interface show lbot_arm_interfaces/msg/FollowJoint
```

---

## 关键理解点

### 1. 三层方向定义

```
遥操臂物理方向
  ↓ (LinkerTA SDK)
URDF模型方向 ← joint_directions.yaml (滤波节点)
  ↓ (滤波节点)
真机电机方向 ← negation (桥接节点)
  ↓ (桥接节点)
真机控制
```

### 2. 数据单位转换

```
LinkerTA: 角度 (degree)
  ↓
滤波节点: 角度 (degree) [GELLO/OneEuro保持原单位]
  ↓
桥接节点: 弧度 (radian) [第248行转换]
  ↓
真机驱动: 弧度 (radian)
```

### 3. 双臂支持验证

- [ ] LinkerTA: 同时发布左右臂 ✓
- [ ] 滤波节点: 需要两个实例 ✓
- [ ] 桥接节点: 独立处理左右臂 ✓
- [ ] 配置文件: 右臂是否启用？

---

## 实战操作步骤

### 步骤1: 启动节点（4个终端）

```bash
# 终端1
./launch_linkerta.sh

# 终端2
./launch_filter_left.sh

# 终端3
./launch_filter_right.sh

# 终端4
./launch_bridge.sh
```

### 步骤2: 验证数据流

```bash
# 终端5
python3 validate_data_flow.py
```

### 步骤3: VSCode代码追踪

按照上面的清单，逐个文件、逐个方法追踪：
1. 使用 `F12` 转到定义
2. 使用 `Shift+F12` 查找引用
3. 使用 `Shift+Alt+H` 查看调用层次
4. 使用 `Ctrl+F` 搜索关键词

### 步骤4: 回答思考问题

完成所有思考问题（问题1-8），确保理解每个环节。

---

## 常见问题排查

### 问题1: 右臂无数据

**检查点**:
- [ ] 桥接节点配置: `enable_right_arm: true`
- [ ] 桥接节点配置: `master_right_topic: "/filtered_right_joint_control"`
- [ ] 右臂滤波节点是否启动

### 问题2: 方向不对

**检查点**:
- [ ] `config/joint_directions.yaml` 配置是否正确
- [ ] 滤波节点是否应用了方向修正（第592行）
- [ ] 桥接节点的 `negation` 配置是否正确

### 问题3: 数据不变化

**检查点**:
- [ ] LinkerTA是否连接硬件（CAN1）
- [ ] 是否移动了遥操臂
- [ ] 使用 `ros2 topic echo` 查看原始数据

---

## 完成标志

当你能够：
- [ ] 在VSCode中快速定位任何一个数据处理环节
- [ ] 解释每个方向修正的作用和位置
- [ ] 理解数据从LinkerTA到桥接节点的完整流程
- [ ] 回答所有8个思考问题
- [ ] 验证工具显示数据流正常

恭喜你完成了完整的代码审查！
