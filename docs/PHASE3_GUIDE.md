# Phase 3 实施指南：映射节点职责明确

## 目标
统一坐标转换逻辑，使用配置文件，移除废弃代码。

## 修改清单

### 文件：`src/core/motion_mapper.py`

#### 1. 添加配置导入（在文件开头）
**位置**: Line 19-20

**添加**:
```python
from src.config import get_config
```

#### 2. 修改 `__init__()` 方法使用配置
**位置**: Line 34-72

**修改前**:
```python
def __init__(self, robot_shoulder_pos, arm_lengths):
    self.P_base_shoulder = np.array(robot_shoulder_pos, dtype=np.float64)
    self.L_upper = arm_lengths['upper']
    self.L_fore = arm_lengths['fore']

    self.R_vision_to_robot = np.array([
        [0,  0,  1],
        [0, -1,  0],
        [1,  0,  0]
    ], dtype=np.float64)

    self.R_cam_to_base = np.eye(3, dtype=np.float64)
    self.alpha = 0.3
```

**修改后**:
```python
def __init__(self, robot_shoulder_pos=None, arm_lengths=None):
    """
    初始化运动映射器

    参数可以从配置文件自动加载，也可以手动指定（手动指定优先）

    Args:
        robot_shoulder_pos: 机器人肩部位置（可选，默认从配置文件读取）
        arm_lengths: 臂长字典（可选，默认从配置文件读取）
    """
    print("🗺️  [ArmMotionMapper] 初始化运动映射器...")

    # 加载配置
    config = get_config()

    # 使用配置文件参数（如果未手动指定）
    if robot_shoulder_pos is None:
        robot_shoulder_pos = config.robot_shoulder_position
    if arm_lengths is None:
        arm_lengths = config.robot_arm_lengths

    # 机器人参数
    self.P_base_shoulder = np.array(robot_shoulder_pos, dtype=np.float64)
    self.L_upper = arm_lengths['upper']
    self.L_fore = arm_lengths['forearm']  # 注意：配置文件中是 'forearm'

    # 坐标转换矩阵（从配置文件读取）
    self.R_vision_to_robot = config.rotation_matrix

    # 滤波参数（从配置文件读取）
    self.alpha = config.filter_alpha

    # 初始化滤波状态
    self.prev_pos = None
    self.prev_rot = None

    print(f"✅ [ArmMotionMapper] 初始化完成")
    print(f"   上臂长度: {self.L_upper:.3f}m")
    print(f"   前臂长度: {self.L_fore:.3f}m")
    print(f"   肩部位置: {self.P_base_shoulder}")
    print(f"   滤波系数: {self.alpha}")
```

#### 3. 删除废弃方法
删除以下方法（已不再使用）:
- `set_calibration_matrix()` (Line 82-93)
- `_warn_if_not_identity()` (Line 74-80)

#### 4. 更新注释
**位置**: Line 48-59

**修改前**:
```python
# Coordinate transformation matrix: Vision Frame → Robot Base Frame
# Vision Frame (Shoulder Frame): X=up, Y=right, Z=forward
# Robot Base Frame (body_base_link): X=forward, Y=left, Z=up
# 用户和机器人同向放置（不是面对面）
# Transformation:
#   X_robot = Z_vision (forward = forward, 同向)
#   Y_robot = -Y_vision (left = -right)
#   Z_robot = X_vision (up = up)
self.R_vision_to_robot = np.array([
    [0,  0,  1],  # X_robot = Z_vision (同向放置)
    [0, -1,  0],  # Y_robot = -Y_vision
    [1,  0,  0]   # Z_robot = X_vision
], dtype=np.float64)
```

**修改后**:
```python
# 坐标转换矩阵（从配置文件读取）
# Vision Frame (Shoulder Frame): X=up, Y=right, Z=forward
# Robot Base Frame (body_base_link): X=forward, Y=left, Z=up
# 转换矩阵定义在 config/system_config.yaml
self.R_vision_to_robot = config.rotation_matrix
```

#### 5. 更新 `human_to_robot()` 方法的注释
**位置**: Line 110-137

**修改前**:
```python
"""
Map human arm keypoints to robot end-effector pose using Three-Vector Mapping.

⚠️ IMPORTANT: Expects input data in ROBOT FRAME, relative to shoulder origin!
VisionNode already performs:
1. Dynamic zeroing (shoulder at [0,0,0])
2. Coordinate transformation (MediaPipe → Robot)
```

**修改后**:
```python
"""
Map human arm keypoints to robot end-effector pose using Three-Vector Mapping.

⚠️ IMPORTANT: Expects input data in SHOULDER FRAME, relative to shoulder origin!
VisionNode performs:
1. Dynamic zeroing (shoulder at [0,0,0])
2. Depth fusion (RealSense + MediaPipe)

This method performs:
1. Coordinate transformation (Shoulder Frame → Robot Base Frame)
2. Position mapping (human arm → robot arm)
3. Orientation calculation (three-vector method)
```

#### 6. 更新 `human_to_robot()` 方法的参数说明
**位置**: Line 119-125

**修改前**:
```python
Args:
    human_kps: Dictionary with keys:
              - 'shoulder': numpy array [0, 0, 0] (origin, in robot frame)
              - 'elbow': numpy array [x, y, z] (relative to shoulder, in robot frame)
              - 'wrist': numpy array [x, y, z] (relative to shoulder, in robot frame)
              - 'index_mcp': numpy array [x, y, z] - index finger (in robot frame)
              - 'pinky_mcp': numpy array [x, y, z] - pinky finger (in robot frame)
```

**修改后**:
```python
Args:
    human_kps: Dictionary with keys:
              - 'shoulder': numpy array [0, 0, 0] (origin, in shoulder frame)
              - 'elbow': numpy array [x, y, z] (relative to shoulder, in shoulder frame)
              - 'wrist': numpy array [x, y, z] (relative to shoulder, in shoulder frame)
              - 'index_mcp': numpy array [x, y, z] - index finger (in shoulder frame)
              - 'pinky_mcp': numpy array [x, y, z] - pinky finger (in shoulder frame)
```

#### 7. 更新坐标转换部分的注释
**位置**: Line 176-190

**修改前**:
```python
# ⚠️ CRITICAL: VisionNode sends data in Shoulder Frame, NOT Robot Frame!
# Must transform from Shoulder Frame to Robot Base Frame
#
# Shoulder Frame (from VisionNode):
#   X = up, Y = right, Z = forward
# Robot Base Frame:
#   X = forward, Y = left, Z = up
#
# Transformation: R_vision_to_robot @ vector
```

**修改后**:
```python
# Step 3: Coordinate Transformation (Shoulder Frame → Robot Base Frame)
#
# Input (Shoulder Frame from VisionNode):
#   X = up, Y = right, Z = forward
# Output (Robot Base Frame):
#   X = forward, Y = left, Z = up
#
# Transformation matrix from config: R_vision_to_robot @ vector
```

## 验证步骤

### 1. 测试配置加载
```bash
python3 -c "from src.core.motion_mapper import ArmMotionMapper; mapper = ArmMotionMapper(); print('✅ 初始化成功')"
```

### 2. 测试完整流程
```bash
python3 scripts/vist_teleoperation.py
```

检查：
- 配置是否正确加载
- 坐标转换是否正确
- 机器人运动是否符合预期

## 预期效果

### 修改前
- 硬编码参数
- 废弃代码（R_cam_to_base）
- 注释不清晰

### 修改后
- 配置文件管理参数
- 代码简洁清晰
- 注释准确明确

## 下一步

完成 Phase 3 后，继续 Phase 4：控制节点配置化
