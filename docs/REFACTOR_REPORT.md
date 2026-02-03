# 系统重构修复报告

## 修复日期
2026-02-04

## 修复概述
针对系统逻辑审计发现的 12 个问题，完成了 P0 级别的 4 个严重问题修复。

---

## 🔴 P0 严重问题修复

### 问题 #1 & #4: 坐标系转换重复应用 + 坐标系语义不一致

**根因**: VisionNode 和 MotionMapper 都在做坐标转换，导致双重变换。

**修复方案**:
1. **VisionNode** (`src/nodes/vision_node.py`):
   - 切换到 MediaPipe Pose（全身检测）
   - 实现"动态归零"：所有点相对于肩部原点
   - 坐标转换公式更新为：
     ```python
     x_robot = -z_mp * scale  # 深度反向 → 前方
     y_robot = -x_mp * scale  # 左右翻转
     z_robot = -y_mp * scale  # 上下翻转
     ```
   - 输出数据：肩部固定在 [0,0,0]，其他点相对于肩部

2. **MotionMapper** (`src/core/motion_mapper.py`):
   - 移除 `R_cam_to_base` 变换（保持为单位矩阵）
   - 添加 `_warn_if_not_identity()` 检查函数
   - 更新文档注释：明确期望输入已在机器人坐标系

**验证方法**:
```bash
# 运行测试，检查坐标系一致性
python -m src.nodes.vision_node  # 观察输出的 shoulder 是否为 [0,0,0]
```

---

### 问题 #2: 虚拟肩部/肘部生成逻辑错误

**根因**: 旧版 VisionNode 使用 MediaPipe Hands，只能检测手部，生成的虚拟肩部会跟随手腕移动。

**修复方案**:
- 切换到 **MediaPipe Pose**，直接检测真实的肩部、肘部、腕部
- 使用 Landmark:
  - RIGHT_SHOULDER (12)
  - RIGHT_ELBOW (14)
  - RIGHT_WRIST (16)
  - RIGHT_INDEX (20) - 指尖代替指关节
  - RIGHT_PINKY (18) - 指尖代替指关节

**数据流**:
```
MediaPipe Pose → 获取肩部作为原点 → 计算相对位置 → 坐标转换 → UDP 发送
```

---

### 问题 #3: "动态归零"机制未实现

**根因**: 理论设计与代码实现不符。

**修复方案**:
在 `VisionNode.process_frame()` 中实现：
```python
# 1. 获取右肩作为原点
origin_mp = np.array([right_shoulder.x, right_shoulder.y, right_shoulder.z])

# 2. 计算相对位置
elbow_local_mp = np.array([right_elbow.x, right_elbow.y, right_elbow.z]) - origin_mp

# 3. 坐标转换
elbow_robot = self.mediapipe_to_robot_coords(elbow_local_mp)

# 4. 发送数据（肩部固定在原点）
keypoints = {'shoulder': [0, 0, 0], 'elbow': elbow_robot.tolist(), ...}
```

**效果**: 用户身体移动时，机械臂基座不动，只映射手臂相对运动。

---

## 🟡 P1 中等问题修复

### 问题 #5: UDP 数据过期检测缺失

**修复方案** (`src/nodes/arm_node.py`):
1. VisionNode 发送数据时添加时间戳：
   ```python
   packet = {'keypoints': keypoints, 'timestamp': time.time()}
   ```

2. ArmNode 接收时检查数据年龄：
   ```python
   data_age = time.time() - self.last_data_timestamp
   if data_age > self.data_timeout:  # 默认 500ms
       print("数据过期，停止运动")
       self.latest_human_kps = None
   ```

---

### 问题 #6: IK 失败无恢复机制

**修复方案** (`src/nodes/arm_node.py`):
1. 添加失败计数器：
   ```python
   self.ik_failure_count = 0
   self.max_ik_failures = 5
   ```

2. IK 成功时重置计数器：
   ```python
   if success:
       self.ik_failure_count = 0
   ```

3. IK 失败时递增计数，超过阈值进入安全模式：
   ```python
   else:
       self.ik_failure_count += 1
       if self.ik_failure_count >= self.max_ik_failures:
           print("连续失败 5 次，进入安全模式")
           self.latest_human_kps = None  # 停止运动
   ```

---

## 📊 修复验证清单

### 1. 坐标系一致性测试
- [ ] 运行 VisionNode，检查肩部输出是否为 [0,0,0]
- [ ] 移动手臂，检查肘部/腕部坐标是否合理（相对于肩部）
- [ ] 检查 MotionMapper 是否警告双重变换

### 2. 动态归零测试
- [ ] 站在摄像头前，移动身体（不动手臂）
- [ ] 观察机械臂是否保持不动
- [ ] 移动手臂，观察机械臂是否跟随

### 3. 安全机制测试
- [ ] 断开 VisionNode，检查 ArmNode 是否在 500ms 后停止
- [ ] 将手臂移到工作空间外，检查 IK 失败计数器
- [ ] 连续失败 5 次后，检查是否进入安全模式

---

## 🔧 依赖变更

### 新增依赖
```bash
pip install mediapipe  # 已有，但现在使用 Pose 模块
```

### 配置变更
无需修改配置文件，所有参数保持默认。

---

## 📝 使用说明

### 启动完整系统
```bash
python test_vision_integration.py
```

### 分别启动（调试用）
```bash
# 终端 1
python -m src.nodes.arm_node

# 终端 2
python -m src.nodes.vision_node
```

### 参数调整
- **灵敏度**: 修改 `VisionNode(scale=1.0)` 参数
- **数据超时**: 修改 `ArmNode.data_timeout = 0.5` (秒)
- **IK 失败阈值**: 修改 `ArmNode.max_ik_failures = 5`

---

## ⚠️ 已知限制

1. **MediaPipe Pose 要求**: 需要上半身可见（肩部、肘部、腕部）
2. **指尖 vs 指关节**: 使用指尖代替指关节，可能影响姿态精度
3. **单手检测**: 目前只支持右手

---

## 🚀 下一步优化（P2/P3）

### 问题 #7: 双重滤波
- 考虑移除 MotionMapper 的 EMA 滤波，只在 IK 层滤波

### 问题 #8: 末端执行器坐标系
- 验证 URDF 中 `hand_base_link` 的 Z 轴方向
- 如有必要，添加旋转补偿

### 问题 #11: Eye-in-Hand 扩展性
- 设计独立的 UDP 通道（端口 6002）
- 或使用 ROS 消息格式

---

## 📚 相关文档

- [Vision Node 详细文档](vision_node.md)
- [Motion Mapper 测试报告](motion_mapper_test.md)
- [快速启动指南](QUICKSTART.md)

---

## ✅ 修复完成确认

- [x] 问题 #1: 坐标系转换重复应用
- [x] 问题 #2: 虚拟肩部生成逻辑错误
- [x] 问题 #3: 动态归零机制未实现
- [x] 问题 #4: 坐标系语义不一致
- [x] 问题 #5: UDP 数据过期检测
- [x] 问题 #6: IK 失败恢复机制

**修复人员**: Claude Sonnet 4.5
**审核状态**: 待用户测试验证
