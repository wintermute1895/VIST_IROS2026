# Vision Node - MediaPipe Hands Integration

## 概述

Vision Node 使用 MediaPipe Hands 进行实时手部检测，提取关键点并通过 UDP 发送给 Arm Node 进行机器人控制。

## 功能特性

- **MediaPipe Hands 集成**: 使用 Google MediaPipe 进行高精度手部检测
- **关键点提取**: 提取手腕、食指掌指关节、小指掌指关节
- **虚拟关节生成**: 自动生成虚拟肩部和肘部位置
- **坐标系转换**: MediaPipe 坐标系 → 机器人坐标系
- **UDP 通信**: 实时发送关键点数据到 Arm Node
- **可视化反馈**: 显示手部骨架、关键点标注和 FPS

## 坐标系转换

### MediaPipe 坐标系
- X: 右（用户视角）
- Y: 下
- Z: 向外（朝向用户）

### 机器人坐标系
- X: 前
- Y: 左
- Z: 上

### 转换公式
```python
x_robot = z_mp * scale    # 深度 → 前方
y_robot = -x_mp * scale   # 左右翻转
z_robot = -y_mp * scale   # 上下翻转
```

## 关键点定义

| 关键点 | MediaPipe Landmark | 描述 |
|--------|-------------------|------|
| wrist | 0 | 手腕 |
| index_mcp | 5 | 食指掌指关节 |
| pinky_mcp | 17 | 小指掌指关节 |
| shoulder | (虚拟) | 虚拟肩部位置 |
| elbow | (虚拟) | 虚拟肘部位置 |

## 虚拟关节生成策略

由于 MediaPipe Hands 只检测手部，我们需要生成虚拟的上臂关节：

```python
# 虚拟肩部：在手腕后方 0.3m，上方 0.2m
shoulder_offset = [-0.3, 0.0, 0.2]
shoulder_pos = wrist_pos + shoulder_offset

# 虚拟肘部：在肩部和手腕之间（加权平均）
elbow_pos = shoulder_pos * 0.4 + wrist_pos * 0.6
```

## 使用方法

### 1. 安装依赖

```bash
pip install mediapipe opencv-python numpy
```

### 2. 单独运行 Vision Node

```bash
python -m src.nodes.vision_node
```

### 3. 完整系统集成测试

```bash
python test_vision_integration.py
```

这将同时启动：
- Vision Node（摄像头输入 + MediaPipe 检测）
- Arm Node（6-DoF IK + MeshCat 可视化）

## 参数调整

### 灵敏度调整

修改 `scale` 参数来调整运动灵敏度：

```python
node = VisionNode(
    camera_id=0,
    udp_ip="127.0.0.1",
    udp_port=6001,
    scale=1.5  # 增加灵敏度
)
```

### MediaPipe 参数

在 `__init__` 方法中调整 MediaPipe Hands 参数：

```python
self.hands = self.mp_hands.Hands(
    static_image_mode=False,
    max_num_hands=1,
    min_detection_confidence=0.5,  # 检测置信度阈值
    min_tracking_confidence=0.5,   # 跟踪置信度阈值
    model_complexity=1  # 0=Lite, 1=Full
)
```

## 性能优化

- **分辨率**: 默认 640x480，可根据需要调整
- **模型复杂度**: 使用 `model_complexity=1` 平衡精度和速度
- **单手检测**: `max_num_hands=1` 减少计算量
- **目标 FPS**: 30+ FPS

## 数据格式

### UDP 发送格式 (JSON)

```json
{
  "shoulder": [x, y, z],
  "elbow": [x, y, z],
  "wrist": [x, y, z],
  "index_mcp": [x, y, z],
  "pinky_mcp": [x, y, z]
}
```

所有坐标单位为米（m），已转换为机器人坐标系。

## 故障排除

### 摄像头无法打开
- 检查摄像头是否被其他程序占用
- 尝试修改 `camera_id` 参数（0, 1, 2...）

### 检测不到手
- 确保光线充足
- 调整 `min_detection_confidence` 参数
- 手部完整出现在画面中

### FPS 过低
- 降低摄像头分辨率
- 使用 `model_complexity=0` (Lite 模型)
- 关闭不必要的可视化

## 下一步

- [ ] 添加手势识别（抓取、释放等）
- [ ] 支持双手检测
- [ ] 添加卡尔曼滤波器平滑轨迹
- [ ] 支持录制和回放功能
