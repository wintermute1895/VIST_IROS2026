# 坐标变换数学推导

完整的矩阵乘法链和数学表达式

## 符号定义

### 坐标系
- **Base**: 机器人基座坐标系
- **End/Flange**: 机械臂末端法兰坐标系
- **TCP**: 工具中心点坐标系（USB末端）
- **Cam_Hand**: 手内相机坐标系（RealSense D405）
- **Cam_Head**: 头顶相机坐标系（RealSense D435i）
- **Target**: 目标物体坐标系（插孔、ArUco标记等）

### 变换矩阵（4×4齐次变换矩阵）
- **T_A_to_B**: 从坐标系A到坐标系B的变换矩阵
- 所有矩阵都是SE(3)群的元素，形式为：
  ```
  T = [R  t]  (3×3旋转矩阵R，3×1平移向量t)
      [0  1]  (1×4齐次坐标行)
  ```

## 手内相机（Eye-in-Hand）完整变换链

### 1. 问题描述
已知：
- 目标在手内相机坐标系下的坐标：`P_target_in_cam_hand = [x_c, y_c, z_c]^T`
- 当前机器人位姿（FK计算）：`T_base_to_end`
- 手眼标定结果：`T_end_to_cam_hand`（标定时获得，固定值）

求：目标在基座坐标系下的坐标 `P_target_in_base`

### 2. 变换链

```
Target (目标物体)
    ↓
Cam_Hand (手内相机坐标系)
    ↓ T_cam_hand_to_end = T_end_to_cam_hand^(-1)
End/Flange (末端法兰坐标系)
    ↓ T_end_to_base = T_base_to_end^(-1)  [注意：这里需要求逆！]
Base (基座坐标系)
```

**错误的理解**（常见错误）：
```python
# ❌ 错误！这是反向的
P_base = T_base_to_end @ T_end_to_cam_hand @ P_cam_hand
```

**正确的推导**：

#### 步骤1：从相机坐标系到末端坐标系
```
P_end = T_cam_hand_to_end @ P_cam_hand_homo
```
其中：
- `P_cam_hand_homo = [x_c, y_c, z_c, 1]^T` （齐次坐标）
- `T_cam_hand_to_end = T_end_to_cam_hand^(-1)` （标定矩阵的逆）

#### 步骤2：从末端坐标系到基座坐标系
```
P_base = T_end_to_base @ P_end
```
其中：
- `T_end_to_base = T_base_to_end^(-1)` （FK结果的逆）

#### 步骤3：合并（完整的矩阵乘法链）
```
P_base_homo = T_end_to_base @ T_cam_hand_to_end @ P_cam_hand_homo
            = T_base_to_end^(-1) @ T_end_to_cam_hand^(-1) @ P_cam_hand_homo
```

**简化表达**（使用逆矩阵的性质）：
```
P_base_homo = (T_end_to_cam_hand @ T_base_to_end)^(-1) @ P_cam_hand_homo
```

但在代码中，我们通常分步计算：
```python
# 齐次坐标
P_cam_hand_homo = np.append(P_cam_hand, 1.0)  # [x_c, y_c, z_c, 1]

# 步骤1: 相机 → 末端
T_cam_hand_to_end = np.linalg.inv(T_end_to_cam_hand)
P_end_homo = T_cam_hand_to_end @ P_cam_hand_homo

# 步骤2: 末端 → 基座
P_base_homo = T_base_to_end @ P_end_homo

# 提取3D坐标
P_base = P_base_homo[:3]
```

**等价的一步计算**：
```python
P_cam_hand_homo = np.append(P_cam_hand, 1.0)
T_cam_hand_to_base = T_base_to_end @ np.linalg.inv(T_end_to_cam_hand)
P_base_homo = T_cam_hand_to_base @ P_cam_hand_homo
P_base = P_base_homo[:3]
```

### 3. 数值示例

假设：
```python
# 目标在手内相机坐标系下的位置
P_cam_hand = np.array([0.1, 0.05, 0.3])  # 米

# 手眼标定结果（末端→相机）
T_end_to_cam_hand = np.array([
    [1,  0,  0,  0.05],   # 相机在末端右侧5cm
    [0,  1,  0,  0.02],   # 相机在末端前方2cm
    [0,  0,  1,  0.10],   # 相机在末端上方10cm
    [0,  0,  0,  1.00]
])

# 当前机器人位姿（基座→末端，FK计算）
T_base_to_end = np.array([
    [1,  0,  0,  0.30],   # 末端在基座右侧30cm
    [0,  1,  0,  0.20],   # 末端在基座前方20cm
    [0,  0,  1,  0.40],   # 末端在基座上方40cm
    [0,  0,  0,  1.00]
])

# 计算过程
P_cam_hand_homo = np.array([0.1, 0.05, 0.3, 1.0])

# 步骤1: 相机 → 末端
T_cam_hand_to_end = np.linalg.inv(T_end_to_cam_hand)
# T_cam_hand_to_end ≈ [
#     [1,  0,  0, -0.05],
#     [0,  1,  0, -0.02],
#     [0,  0,  1, -0.10],
#     [0,  0,  0,  1.00]
# ]

P_end_homo = T_cam_hand_to_end @ P_cam_hand_homo
# P_end_homo ≈ [0.05, 0.03, 0.20, 1.0]

# 步骤2: 末端 → 基座
P_base_homo = T_base_to_end @ P_end_homo
# P_base_homo ≈ [0.35, 0.23, 0.60, 1.0]

P_base = P_base_homo[:3]
# P_base ≈ [0.35, 0.23, 0.60]
```

## 头顶相机（Eye-to-Hand）完整变换链

### 1. 问题描述
已知：
- 目标在头顶相机坐标系下的坐标：`P_target_in_cam_head = [x_c, y_c, z_c]^T`
- 眼到手标定结果：`T_base_to_cam_head`（标定时获得，固定值）

求：目标在基座坐标系下的坐标 `P_target_in_base`

### 2. 变换链

```
Target (目标物体)
    ↓
Cam_Head (头顶相机坐标系)
    ↓ T_cam_head_to_base = T_base_to_cam_head^(-1)
Base (基座坐标系)
```

**完整的矩阵乘法链**：
```
P_base_homo = T_cam_head_to_base @ P_cam_head_homo
            = T_base_to_cam_head^(-1) @ P_cam_head_homo
```

**代码实现**：
```python
# 齐次坐标
P_cam_head_homo = np.append(P_cam_head, 1.0)

# 相机 → 基座
T_cam_head_to_base = np.linalg.inv(T_base_to_cam_head)
P_base_homo = T_cam_head_to_base @ P_cam_head_homo

# 提取3D坐标
P_base = P_base_homo[:3]
```

### 3. 数值示例

假设：
```python
# 目标在头顶相机坐标系下的位置
P_cam_head = np.array([0.2, 0.1, 0.5])  # 米

# 眼到手标定结果（基座→相机）
T_base_to_cam_head = np.array([
    [1,  0,  0,  0.50],   # 相机在基座右侧50cm
    [0,  1,  0,  0.30],   # 相机在基座前方30cm
    [0,  0,  1,  1.50],   # 相机在基座上方150cm（头顶）
    [0,  0,  0,  1.00]
])

# 计算过程
P_cam_head_homo = np.array([0.2, 0.1, 0.5, 1.0])

# 相机 → 基座
T_cam_head_to_base = np.linalg.inv(T_base_to_cam_head)
# T_cam_head_to_base ≈ [
#     [1,  0,  0, -0.50],
#     [0,  1,  0, -0.30],
#     [0,  0,  1, -1.50],
#     [0,  0,  0,  1.00]
# ]

P_base_homo = T_cam_head_to_base @ P_cam_head_homo
# P_base_homo ≈ [-0.30, -0.20, -1.00, 1.0]

P_base = P_base_homo[:3]
# P_base ≈ [-0.30, -0.20, -1.00]
```

## 关键理解

### 1. 为什么需要求逆？

**标定结果的含义**：
- `T_end_to_cam_hand`: 从末端坐标系到相机坐标系的变换
- `T_base_to_cam_head`: 从基座坐标系到相机坐标系的变换

**我们需要的变换**：
- 从相机坐标系到末端/基座坐标系的变换
- 因此需要求逆：`T_cam_to_end = T_end_to_cam^(-1)`

### 2. 矩阵乘法顺序

**齐次坐标变换的规则**：
```
P_B = T_A_to_B @ P_A
```

**链式变换**：
```
P_C = T_B_to_C @ T_A_to_B @ P_A
```

**注意**：矩阵乘法从右到左读，但变换从左到右应用！

### 3. 代码中的实现

在 `CoordinateTransformManager` 中：

```python
def hand_camera_to_base(self, point_cam, T_base_to_end):
    """手内相机 → 基座"""
    # 齐次坐标
    point_homo = np.append(point_cam, 1.0)

    # 相机 → 末端 → 基座
    T_cam_to_end = np.linalg.inv(self.T_end_to_cam_hand)
    point_base_homo = T_base_to_end @ T_cam_to_end @ point_homo

    return point_base_homo[:3]

def head_camera_to_base(self, point_cam):
    """头顶相机 → 基座"""
    # 齐次坐标
    point_homo = np.append(point_cam, 1.0)

    # 相机 → 基座
    T_cam_to_base = np.linalg.inv(self.T_base_to_cam_head)
    point_base_homo = T_cam_to_base @ point_homo

    return point_base_homo[:3]
```

## 完整的系统流程

### 手内相机完整流程

```
1. 视觉检测
   image → detect_target() → P_cam_hand = [x_c, y_c, z_c]

2. 获取机器人位姿
   robot.get_current_pose() → T_base_to_end (4×4)

3. 坐标变换
   P_base = coord_mgr.hand_camera_to_base(P_cam_hand, T_base_to_end)

   内部计算:
   P_homo = [x_c, y_c, z_c, 1]
   P_base_homo = T_base_to_end @ inv(T_end_to_cam_hand) @ P_homo
   P_base = P_base_homo[:3]

4. VIST控制
   q_target = vist_filter.solve(target_pos=P_base)

5. 机器人执行
   robot.move_joint(q_target)
```

### 头顶相机完整流程

```
1. 视觉检测
   image → detect_target() → P_cam_head = [x_c, y_c, z_c]

2. 坐标变换（不需要机器人位姿）
   P_base = coord_mgr.head_camera_to_base(P_cam_head)

   内部计算:
   P_homo = [x_c, y_c, z_c, 1]
   P_base_homo = inv(T_base_to_cam_head) @ P_homo
   P_base = P_base_homo[:3]

3. VIST控制
   q_target = vist_filter.solve(target_pos=P_base)

4. 机器人执行
   robot.move_joint(q_target)
```

## 验证方法

### 1. 标定精度验证

```python
# 在标定板已知位置放置标定板
P_board_true = np.array([0.3, 0.2, 0.1])  # 真实位置

# 通过相机检测
P_board_cam = detect_board(image)
P_board_estimated = coord_mgr.hand_camera_to_base(P_board_cam, robot_pose)

# 计算误差
error = np.linalg.norm(P_board_estimated - P_board_true)
print(f"标定误差: {error*1000:.1f}mm")

# 精度评估
if error < 0.005:
    print("✓ 优秀 (< 5mm)")
elif error < 0.010:
    print("✓ 良好 (< 10mm)")
else:
    print("✗ 需要重新标定 (> 10mm)")
```

### 2. 双相机一致性验证

```python
# 两个相机同时观测同一目标
P_hand_cam = detect_target_hand(image_hand)
P_head_cam = detect_target_head(image_head)

# 转换到基座坐标系
P_base_from_hand = coord_mgr.hand_camera_to_base(P_hand_cam, robot_pose)
P_base_from_head = coord_mgr.head_camera_to_base(P_head_cam)

# 计算差异
diff = np.linalg.norm(P_base_from_hand - P_base_from_head)
print(f"双相机观测差异: {diff*1000:.1f}mm")

# 一致性评估
if diff < 0.05:
    print("✓ 观测一致")
else:
    print("✗ 观测冲突，可能原因：标定误差、检测错误、遮挡")
```

## 总结

### 手内相机（Eye-in-Hand）
```
完整矩阵链:
P_base = T_base_to_end @ inv(T_end_to_cam_hand) @ P_cam_hand

关键点:
- 需要实时FK: T_base_to_end
- 需要标定结果: T_end_to_cam_hand
- 需要求两次逆
```

### 头顶相机（Eye-to-Hand）
```
完整矩阵链:
P_base = inv(T_base_to_cam_head) @ P_cam_head

关键点:
- 不需要FK（相机固定）
- 需要标定结果: T_base_to_cam_head
- 只需要求一次逆
```

### 计算复杂度
- 手内相机: O(n³) × 2（两次矩阵求逆 + 两次矩阵乘法）
- 头顶相机: O(n³) × 1（一次矩阵求逆 + 一次矩阵乘法）

其中 n=4（4×4矩阵），实际计算非常快（微秒级）。