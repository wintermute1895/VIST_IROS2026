# 配置引用错误修复

## 问题描述

在配置化重构后，多个文件中存在错误的配置引用，导致运行时出现 `AttributeError`。

## 发现的错误

### 1. calibration_solver.py

**错误 1**: 第 283-284 行
```python
if valid_count < self.config.min_samples:
    print(f"⚠️ 警告: 有效样本数量 ({valid_count}) 少于推荐值 ({self.config.min_samples})")
```

**修复**:
```python
if valid_count < self.config.data_collection.min_samples:
    print(f"⚠️ 警告: 有效样本数量 ({valid_count}) 少于推荐值 ({self.config.data_collection.min_samples})")
```

**错误 2**: 第 215 行
```python
method=self.config.calibration_method
```

**修复**:
```python
method=self.config.calibration_solver.method
```

**错误 3**: 第 258 行
```python
"calibration_method": str(self.config.calibration_method)
```

**修复**:
```python
"calibration_method": str(self.config.calibration_solver.method)
```

### 2. visual_verification.py

**错误 1**: 第 203 行
```python
axis_length = self.config.square_size
```

**修复**:
```python
axis_length = self.config.charuco_board.square_size
```

**错误 2**: 第 242 行
```python
self.config.detected_corner_color
```

**修复**:
```python
self.config.validation.detected_corner_color
```

**错误 3**: 第 259-260 行
```python
self.config.reprojection_point_radius,
self.config.reprojection_point_color,
```

**修复**:
```python
self.config.validation.reprojection_point_radius,
self.config.validation.reprojection_point_color,
```

**错误 4**: 第 268 行
```python
self.config.reprojection_point_color,
```

**修复**:
```python
self.config.validation.reprojection_point_color,
```

## 配置引用规则

在新的配置系统中，所有配置参数都通过分层结构访问：

### 正确的配置引用格式

```python
# 机器人配置
config.robot.tcp_host
config.robot.arm_side
config.robot.move_speed
config.robot.move_accel

# 相机配置
config.camera.width
config.camera.height
config.camera.fps

# 标定板配置
config.charuco_board.rows
config.charuco_board.cols
config.charuco_board.square_size
config.charuco_board.marker_size

# 数据采集配置
config.data_collection.min_samples
config.data_collection.min_position_change
config.data_collection.capture_key
config.data_collection.quit_key

# 标定算法配置
config.calibration_solver.method
config.calibration_solver.max_identical_poses

# 验证配置
config.validation.excellent_threshold
config.validation.good_threshold
config.validation.detected_corner_color
config.validation.reprojection_point_radius
config.validation.reprojection_point_color

# 存储配置
config.storage.data_dir
config.storage.image_format
config.storage.image_prefix

# 路径属性（由主配置类管理）
config.data_dir
config.images_dir
config.poses_file
config.result_file
config.result_matrix_file
config.metadata_file
config.error_stats_file
```

### 错误的配置引用（已废弃）

```python
# ❌ 错误
config.min_samples
config.calibration_method
config.square_size
config.detected_corner_color
config.reprojection_point_radius
config.reprojection_point_color

# ✅ 正确
config.data_collection.min_samples
config.calibration_solver.method
config.charuco_board.square_size
config.validation.detected_corner_color
config.validation.reprojection_point_radius
config.validation.reprojection_point_color
```

## 修复的文件

1. ✅ calibration_solver.py - 3 处错误
2. ✅ visual_verification.py - 4 处错误

## 验证结果

✅ 所有模块导入成功
✅ 配置对象结构正确
✅ 所有配置引用检查通过

## 修复时间

2026-02-10

## 修复状态

✅ 已完成并验证
