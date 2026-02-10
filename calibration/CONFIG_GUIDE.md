# 手眼标定配置系统使用指南

## 概述

本标定系统采用分层配置架构，支持灵活的参数配置和管理。所有可配置参数都集中在 `config.py` 中，支持代码配置和配置文件加载两种方式。

## 配置架构

配置系统分为以下几个模块：

### 1. 机器人配置 (RobotConfig)
- **连接参数**：IP 地址、机械臂选择
- **SDK 路径**：自动搜索或手动指定
- **运动控制**：速度、加速度、阻塞模式

### 2. 相机配置 (CameraConfig)
- **分辨率和帧率**：640x480@30fps（可调）
- **内参获取**：自动从相机读取或手动配置
- **硬件设置**：硬件复位、超时时间

### 3. 标定板配置 (CharucoBoardConfig)
- **ArUco 字典类型**：DICT_4X4_50 等
- **板尺寸**：行数、列数
- **物理尺寸**：方格大小、标记大小（米）

### 4. 数据采集配置 (DataCollectionConfig)
- **采集数量**：最少样本数、推荐样本数
- **位姿变化阈值**：位置变化、旋转变化
- **显示参数**：窗口名称、字体、颜色

### 5. 标定算法配置 (CalibrationSolverConfig)
- **标定方法**：TSAI、PARK、HORAUD 等
- **验证阈值**：位姿相似度检测

### 6. 验证配置 (ValidationConfig)
- **质量评估阈值**：优秀、良好、可接受
- **可视化参数**：颜色、线条粗细

### 7. 存储配置 (StorageConfig)
- **目录结构**：数据目录、图像子目录
- **文件命名**：各类文件的命名规则

## 使用方法

### 方法 1：使用默认配置

```python
from config import CalibrationConfig

# 使用默认配置
config = CalibrationConfig()
config.print_config()
```

### 方法 2：修改特定参数

```python
from config import CalibrationConfig

# 创建配置并修改参数
config = CalibrationConfig()

# 修改机器人 IP
config.robot.tcp_host = "192.168.10.100"

# 修改采集样本数
config.data_collection.min_samples = 20

# 修改标定板尺寸
config.charuco_board.square_size = 0.030  # 30mm
config.charuco_board.marker_size = 0.022  # 22mm
```

### 方法 3：从配置文件加载

```python
from config import CalibrationConfig

# 从 YAML 文件加载
config = CalibrationConfig(config_file="my_calibration.yaml")

# 或从 JSON 文件加载
config = CalibrationConfig(config_file="my_calibration.json")
```

### 方法 4：保存配置到文件

```python
from config import CalibrationConfig

config = CalibrationConfig()

# 修改一些参数
config.robot.tcp_host = "192.168.10.100"
config.data_collection.min_samples = 20

# 保存到文件
config.save_to_file("my_calibration.yaml")
```

## 配置文件示例

### YAML 格式

```yaml
robot:
  tcp_host: "192.168.10.21"
  arm_side: "right"
  move_speed: 0.3
  move_accel: 0.1

camera:
  width: 640
  height: 480
  fps: 30
  use_auto_intrinsics: true

charuco_board:
  rows: 5
  cols: 7
  square_size: 0.025  # 25mm
  marker_size: 0.018  # 18mm

data_collection:
  min_samples: 15
  min_position_change: 0.02  # 2cm
  min_rotation_change: 0.1
```

### JSON 格式

```json
{
  "robot": {
    "tcp_host": "192.168.10.21",
    "arm_side": "right",
    "move_speed": 0.3,
    "move_accel": 0.1
  },
  "camera": {
    "width": 640,
    "height": 480,
    "fps": 30,
    "use_auto_intrinsics": true
  }
}
```

## 生成配置文件模板

```python
from config import generate_config_template

# 生成 YAML 模板
generate_config_template("my_config.yaml")

# 生成 JSON 模板
generate_config_template("my_config.json")
```

## 关键参数说明

### 标定板物理尺寸

**非常重要**：必须使用卡尺精确测量标定板的实际尺寸！

- `square_size`：棋盘格方格的边长（米）
- `marker_size`：ArUco 标记的边长（米）
- 要求：`marker_size` 应为 `square_size` 的 0.5-0.9 倍

### 位姿变化阈值

用于确保采集的数据具有足够的多样性：

- `min_position_change`：最小位置变化（米），默认 0.02m (2cm)
- `min_rotation_change`：最小旋转变化，默认 0.1

### 质量评估阈值

重投影误差的质量评估标准（像素）：

- `excellent_threshold`：< 1.0 像素为优秀
- `good_threshold`：< 2.0 像素为良好
- `acceptable_threshold`：< 5.0 像素为可接受

## 配置验证

配置系统会自动验证参数的合理性：

- 标定板尺寸关系检查
- 相机分辨率和帧率检查
- 采集样本数量检查
- 机械臂参数检查

如果配置不合理，系统会抛出异常并给出提示。

## 最佳实践

1. **首次使用**：使用默认配置，生成模板文件
2. **测量标定板**：精确测量并更新 `square_size` 和 `marker_size`
3. **调整网络**：根据实际机器人 IP 修改 `tcp_host`
4. **保存配置**：将调整好的配置保存为文件
5. **版本控制**：将配置文件纳入版本控制

## 常见问题

### Q: 如何更改机器人 IP？
A: 修改 `config.robot.tcp_host` 或在配置文件中设置。

### Q: 如何使用左臂而不是右臂？
A: 修改 `config.robot.arm_side = "left"`。

### Q: 如何调整采集的样本数量？
A: 修改 `config.data_collection.min_samples`。

### Q: 相机内参从哪里来？
A: 默认自动从 RealSense 相机读取。如需手动配置，设置 `config.camera.use_auto_intrinsics = False` 并填写内参。

### Q: 如何更改数据存储位置？
A: 修改 `config.storage.data_dir`。

## 扩展性

配置系统采用 dataclass 设计，易于扩展：

1. 在对应的配置类中添加新字段
2. 更新使用该配置的代码
3. 配置文件会自动支持新字段

## 技术细节

- 使用 Python dataclass 实现类型安全
- 支持 YAML 和 JSON 两种格式
- 自动参数验证
- 分层配置，职责清晰
- 向后兼容，易于维护
