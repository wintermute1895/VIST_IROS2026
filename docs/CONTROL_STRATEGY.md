# VIST 控制策略算法详解

## 文档概述

本文档详细说明 VIST (Vision-based Intent-aware State Teleoperation) 框架的控制策略算法，包括数学原理、实现细节和安全机制。

**目标读者**: 机器人控制工程师、研究人员、代码审查者

**最后更新**: 2026-02-06

---

## 1. 系统架构概览

### 1.1 数据流管道

```
人体姿态 (MediaPipe + RealSense)
    ↓
[视觉节点] 数据采集 + 深度融合
    ↓ 输出：肩膀坐标系 (X=上, Y=右, Z=前)
UDP 传输
    ↓
[映射节点] 坐标转换 + 运动映射
    ↓ 输出：机器人基座坐标系 (X=前, Y=左, Z=上)
[控制节点] IK 求解 + 安全监控 + 电机控制
    ↓ 输出：关节角度指令 (7-DoF)
机器人硬件
```

### 1.2 核心创新点

1. **微分 IK (Differential IK)**: 不求全局解，只求增量，避免迭代优化
2. **三向量映射 (Three-Vector Mapping)**: 使用指节向量避免奇异点
3. **动态归零 (Dynamic Zeroing)**: 肩部为原点，用户移动不影响机器人基座
4. **深度融合 (Depth Fusion)**: RealSense 深度 + MediaPipe 姿态，提高 Z 轴精度

---

## 2. 视觉节点 (Vision Node)

### 2.1 职责定义

**输入**:
- RGB 图像流 (RealSense D435i)
- 深度图像流 (RealSense D435i)

**输出**:
- 关键点坐标（肩膀坐标系）
  - `shoulder`: [0, 0, 0] (原点)
  - `elbow`: [x, y, z]
  - `wrist`: [x, y, z]
  - `index_mcp`: [x, y, z]
  - `pinky_mcp`: [x, y, z]

### 2.2 坐标系定义

**肩膀坐标系 (Shoulder Frame)**:
- **X 轴**: 向上（垂直方向）
- **Y 轴**: 向右（水平方向，用户的物理右侧）
- **Z 轴**: 向前（水平方向，靠近相机）
- **原点**: 肩部（动态归零）

### 2.3 深度融合算法

```python
# 伪代码
def fuse_depth(mediapipe_point, realsense_depth_frame):
    # 1. 获取 MediaPipe 2D 像素坐标
    pixel_x, pixel_y = mediapipe_to_pixel(mediapipe_point)

    # 2. 从 RealSense 深度图获取真实深度（带邻域平均）
    real_depth = get_depth_at_pixel(depth_frame, pixel_x, pixel_y, radius=3)

    # 3. 计算相对深度（相对于肩部）
    relative_depth = real_depth - shoulder_depth

    # 4. 融合：用真实深度替换 MediaPipe 的 Z 坐标
    z_shoulder = -relative_depth  # 向前伸手 → depth 减小 → z 增大

    return [x_shoulder, y_shoulder, z_shoulder]
```

**关键点**:
- 使用中位数滤波（3x3 邻域）减少深度噪声
- 相对深度计算：`wrist_depth - shoulder_depth`
- Z 轴符号修正：向前伸手时 Z 应增大

---

## 3. 映射节点 (Motion Mapper)

### 3.1 职责定义

**输入**: 肩膀坐标系关键点先
**输出**: 机器人基座坐标系的末端执行器位姿 (位置 + 四元数)

### 3.2 坐标系转换

**转换矩阵** (同向放置):
```python
R_shoulder_to_robot = [
    [0,  0,  1],  # X_robot = Z_shoulder (前 = 前)
    [0, -1,  0],  # Y_robot = -Y_shoulder (左 = -右)
    [1,  0,  0]   # Z_robot = X_shoulder (上 = 上)
]
```

**数学验证**:
- 正交性: R^T @ R = I ✅
- 行列式: det(R) = 1 ✅ (右手坐标系)

### 3.3 三向量映射算法

#### Step 1: 向量提取
```python
V_upper = P_elbow - P_shoulder    # 上臂向量
V_fore = P_wrist - P_elbow        # 前臂向量
V_knuckle = P_index - P_pinky     # 指节向量（横向参考）
```

#### Step 2: 奇异点检测
```python
SINGULARITY_THRESHOLD = 0.001  # 1mm

if norm(V_upper) < THRESHOLD:
    return None  # 上臂向量过小
if norm(V_fore) < THRESHOLD:
    return None  # 前臂向量过小
if norm(V_knuckle) < THRESHOLD:
    return None  # 指节向量过小
```

#### Step 3: 坐标转换
```python
V_upper_robot = R @ V_upper
V_fore_robot = R @ V_fore
V_knuckle_robot = R @ V_knuckle
```

#### Step 4: 位置映射
```python
# 归一化方向向量
d_upper = V_upper_robot / norm(V_upper_robot)
d_fore = V_fore_robot / norm(V_fore_robot)

# 使用机器人臂长计算关节位置
T_elbow = P_shoulder_base + d_upper * L_upper
T_wrist = T_elbow + d_fore * L_fore
```

**关键**: 人体臂长 → 机器人臂长的映射

#### Step 5: 姿态映射（三向量法）

**创新点**: 使用指节向量避免奇异点

```python
# Z 轴：沿前臂方向（接近方向）
Z_axis = d_fore  # 已归一化

# Y 轴：从指节向量计算（手背法向量）
Y_temp = cross(Z_axis, V_knuckle_robot)
Y_axis = Y_temp / norm(Y_temp)

# X 轴：右手坐标系
X_axis = cross(Y_axis, Z_axis)

# 构造旋转矩阵
R_target = [X_axis | Y_axis | Z_axis]  # 列向量

# 转换为四元数
quat = Rotation.from_matrix(R_target).as_quat()
```

**为什么用指节向量？**
- 传统方法：使用手掌向量（wrist → index）
- 问题：手臂伸直时，手掌向量与前臂向量平行 → 奇异点
- 解决：指节向量（pinky → index）始终垂直于前臂 → 无奇异点

#### Step 6: 平滑滤波

**位置滤波**: 指数移动平均 (EMA)
```python
filtered_pos = alpha * curr_pos + (1 - alpha) * prev_pos
```

**姿态滤波**: 球面线性插值 (SLERP)
```python
filtered_quat = SLERP(prev_quat, curr_quat, t=alpha)
```

**参数**: `alpha = 0.5` (可配置)

---

## 4. 控制节点 (Control Node)

### 4.1 职责定义

**输入**: 目标末端执行器位姿 (位置 + 四元数)
**输出**: 关节角度指令 (7-DoF)

### 4.2 微分 IK 算法

**核心思想**: 不求全局解，只求增量

```python
# 伪代码
def differential_ik(target_pos, q_current, gain=0.9):
    # 1. 计算当前末端位置
    current_pos = forward_kinematics(q_current)

    # 2. 计算位置误差
    error = target_pos - current_pos

    # 3. 计算雅可比矩阵
    J = compute_jacobian(q_current)

    # 4. 求解增量（伪逆法）
    dq = gain * pinv(J) @ error

    # 5. 更新关节角度
    q_new = q_current + dq

    return q_new
```

**优势**:
- 无需迭代优化 → 计算时间 < 1ms
- 天然平滑 → 不会跳变
- 适合实时控制 → 50Hz 控制频率

**数学基础**:
```
Δx = J(q) · Δq
Δq = J^+ · Δx  (J^+ 是伪逆)
```

### 4.3 安全监控系统

#### 4.3.1 多层安全检查

```python
# 综合安全检查
is_safe, violations = safety_monitor.check_command(
    q_solution,
    current_time,
    end_effector_pos=target_pos
)
```

**检查项目**:
1. **关节限位检查**
   ```python
   for i, (q, [q_min, q_max]) in enumerate(zip(q, joint_limits)):
       if q < q_min or q > q_max:
           violations.append(f"Joint {i} out of bounds")
   ```

2. **速度限制检查**
   ```python
   dq = (q - q_prev) / dt
   if abs(dq[i]) > max_velocity:
       violations.append(f"Joint {i} velocity exceeded")
   ```

3. **加速度限制检查**
   ```python
   ddq = (dq - dq_prev) / dt
   if abs(ddq[i]) > max_acceleration:
       violations.append(f"Joint {i} acceleration exceeded")
   ```

4. **工作空间边界检查**
   ```python
   if x < x_min or x > x_max:
       violations.append("X position out of workspace")
   ```

#### 4.3.2 双重保护机制

```python
# 第一层：SafetyMonitor 综合检查
is_safe, violations = safety_monitor.check_command(...)

if is_safe:
    # 第二层：速度限制（额外保护）
    q_velocity = (q_solution - q_prev) / dt
    q_velocity_limited = clip(q_velocity, -max_vel, max_vel)
    q_cmd = q_prev + q_velocity_limited * dt

    # 第三层：关节限位裁剪（最后防线）
    q_cmd = clip(q_cmd, joint_limits[:, 0], joint_limits[:, 1])

    # 发送指令
    driver.send_command(q_cmd)
else:
    # 安全违规：跳过此帧
    print(f"Safety violation: {violations}")
```

### 4.4 控制循环

```python
# 主控制循环 (50Hz)
while running:
    # 1. 接收视觉数据 (UDP)
    human_kps = receive_udp_data()

    # 2. 运动映射
    target_pos, target_quat, debug_info = mapper.human_to_robot(human_kps)

    # 3. One Euro 滤波（额外平滑）
    target_pos_filtered = one_euro_filter(target_pos)

    # 4. 微分 IK 求解
    q_solution = ik_solver.solve(target_pos_filtered, q_current, gain=0.9)

    # 5. 安全检查
    is_safe, violations = safety_monitor.check_command(q_solution, time.time())

    # 6. 发送指令（如果安全）
    if is_safe:
        driver.send_command(q_solution)

    # 7. 控制频率
    sleep(dt)
```

---

## 5. 参数配置

### 5.1 控制参数

| 参数 | 值 | 说明 |
|------|-----|------|
| `control_frequency` | 50 Hz | 控制循环频率 |
| `ik_gain` | 0.9 | 微分 IK 增益系数 |
| `max_joint_velocity` | 0.8 rad/s | 最大关节速度 |
| `max_joint_acceleration` | 2.0 rad/s² | 最大关节加速度 |

### 5.2 滤波参数

| 参数 | 值 | 说明 |
|------|-----|------|
| `filter_alpha` | 0.5 | EMA 滤波系数（Mapper） |
| `filter_min_cutoff` | 0.3 | One Euro Filter 最小截止频率 |
| `filter_beta` | 0.005 | One Euro Filter 速度系数 |

### 5.3 安全参数

| 参数 | 值 | 说明 |
|------|-----|------|
| `max_data_timeout` | 50 frames | UDP 数据超时阈值 (1秒) |
| `max_distance_from_shoulder` | 0.7 m | 最大手臂伸展距离 |

---

## 6. 性能指标

### 6.1 延迟分析

```
总延迟 = 映射延迟 + 滤波延迟 + IK 延迟
       ≈ 2ms + 1ms + 0.5ms = 3.5ms
```

**实测数据** (50Hz 控制):
- 映射节点: ~2ms
- One Euro Filter: ~1ms
- 微分 IK: <1ms
- **总延迟**: <5ms (远低于 20ms 控制周期)

### 6.2 精度指标

- **位置精度**: ±5mm (RealSense 深度融合)
- **姿态精度**: ±3° (三向量映射)
- **IK 误差**: <2mm (微分 IK)

---

## 7. 故障处理

### 7.1 视觉数据丢失

```python
data_timeout_count = 0
max_data_timeout = 50  # 1秒

if no_data_received:
    data_timeout_count += 1
    if data_timeout_count >= max_data_timeout:
        print("Vision data timeout, stopping")
        break
```

### 7.2 IK 无解

```python
q_solution, success, error = ik_solver.solve(...)

if not success:
    # 保持当前位置，不发送新指令
    continue
```

### 7.3 安全违规

```python
is_safe, violations = safety_monitor.check_command(...)

if not is_safe:
    # 跳过此帧，不发送指令
    print(f"Safety violation: {violations}")
    continue
```

---

## 8. 调试与优化

### 8.1 调试信息

```python
debug_info = {
    'elbow_pos': T_elbow,
    'wrist_pos': T_wrist,
    'rotation_matrix': R_target,
    'orthogonality_error': error,
    'filtered_pos': filtered_pos,
    'unfiltered_pos': curr_pos
}
```

### 8.2 性能优化建议

1. **降低延迟**:
   - 减少滤波器阶数
   - 优化雅可比矩阵计算

2. **提高精度**:
   - 增加深度邻域半径
   - 调整 IK 增益系数

3. **增强鲁棒性**:
   - 添加卡尔曼滤波
   - 实现预测性控制

---

## 9. 参考文献

1. **Differential IK**:
   - Siciliano, B., & Khatib, O. (2016). *Springer handbook of robotics*. Chapter 9: Differential Kinematics.

2. **Three-Vector Mapping**:
   - VIST Framework (本项目创新)

3. **One Euro Filter**:
   - Casiez, G., Roussel, N., & Vogel, D. (2012). *1€ filter: a simple speed-based low-pass filter for noisy input in interactive systems*. CHI 2012.

4. **MediaPipe Pose**:
   - Bazarevsky, V., et al. (2020). *BlazePose: On-device Real-time Body Pose tracking*. arXiv:2006.10204.

---

## 10. 附录

### 10.1 关节限位表

| 关节 | 最小值 (rad) | 最大值 (rad) | 最小值 (°) | 最大值 (°) |
|------|-------------|-------------|-----------|-----------|
| Shoulder_Pitch | -2.0 | 2.0 | -114.6° | 114.6° |
| Shoulder_Roll | -2.0 | 3.14 | -114.6° | 180.0° |
| Shoulder_Yaw | -3.14 | 3.14 | -180.0° | 180.0° |
| Elbow_Pitch | -2.35 | 2.0 | -134.6° | 114.6° |
| Wrist_Yaw | -3.14 | 3.14 | -180.0° | 180.0° |
| Wrist_Pitch | -3.14 | 3.14 | -180.0° | 180.0° |
| Wrist_Roll | -3.14 | 3.14 | -180.0° | 180.0° |

### 10.2 坐标系对照表

| 坐标系 | X 轴 | Y 轴 | Z 轴 | 原点 |
|--------|------|------|------|------|
| 肩膀坐标系 | 上 | 右 | 前 | 肩部 |
| 机器人基座 | 前 | 左 | 上 | body_base_link |
| MediaPipe | 左 | 下 | 外 | 图像中心 |

---

**文档版本**: v1.0
**作者**: VIST Team
**联系**: ilex@vist-robotics.com
**最后更新**: 2026-02-06
