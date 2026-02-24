# VIST 视觉感知模块改进说明

## 📋 改进概览

本次改进重点提升了视觉感知模块的**鲁棒性**和**配置化**，主要包括：

### ✅ 已实施的改进

1. **配置化相机管理** (`config/camera_config.yaml`)
   - 统一管理所有相机参数
   - 支持多相机配置（每个相机有不同角色）
   - 外参标定配置化
   - 目标检测配置

2. **鲁棒的相机管理器** (`src/camera_manager/camera_manager/robust_camera_manager.py`)
   - 自动发现RealSense相机
   - 相机故障自动重连
   - 硬件时间戳支持
   - 健康状态监控

3. **AprilTag目标检测** (`src/perception/apriltag_detector.py`)
   - AprilTag检测和3D位姿估计
   - 目标管理和优先级选择
   - 深度融合

4. **集成视觉节点** (`src/nodes/integrated_vision_node.py`)
   - 多相机管理（按角色分配）
   - 手部追踪 + 目标检测
   - 场景感知意图计算
   - 降级策略

---

## 🎯 多相机管理架构

### 相机角色定义

系统支持多个相机同时工作，每个相机有不同的角色：

| 角色 | 功能 | 典型位置 |
|------|------|---------|
| `intent_detection` | 手部追踪、意图计算 | 俯视/桌面视角 |
| `fine_manipulation` | 精密操作、目标检测 | 腕部/近距离 |
| `workspace_monitoring` | 工作空间监控 | 侧视/全局视角 |

### 配置示例

```yaml
# config/camera_config.yaml
cameras:
  # 主相机：手部追踪
  - id: "overhead"
    role: "intent_detection"
    serial: "auto"  # 自动检测
    enabled: true
    streams:
      color: {resolution: [848, 480], fps: 30}
      depth: {resolution: [848, 480], fps: 30}

  # 腕部相机：精密操作
  - id: "wrist"
    role: "fine_manipulation"
    serial: "123456789"  # 指定序列号
    enabled: true
    streams:
      color: {resolution: [640, 480], fps: 30}
      depth: {resolution: [640, 480], fps: 30}
```

### 相机不会串台的保证

1. **序列号绑定**：每个相机通过序列号唯一标识
2. **角色隔离**：代码中通过角色名称访问相机，不会混淆
3. **独立Pipeline**：每个相机有独立的RealSense pipeline

---

## 🚀 使用方法

### 方法1：使用ROS2相机管理器（推荐）

```bash
# 启动鲁棒相机管理器
cd /home/ilex/Dev/VIST
source /opt/ros/humble/setup.bash
python3 src/camera_manager/camera_manager/robust_camera_manager.py

# 查看相机状态
ros2 topic echo /camera_manager/status

# 查看相机图像
ros2 run rqt_image_view rqt_image_view /overhead/color/image_raw
ros2 run rqt_image_view rqt_image_view /wrist/color/image_raw
```

### 方法2：使用集成视觉节点

```bash
# 启动集成视觉节点（手部追踪 + 目标检测）
python3 src/nodes/integrated_vision_node.py
```

---

## 🔧 配置说明

### 1. 相机配置

编辑 `config/camera_config.yaml`：

```yaml
cameras:
  - id: "overhead"  # 相机ID（唯一）
    role: "intent_detection"  # 角色
    serial: "auto"  # "auto"自动检测，或指定序列号
    enabled: true  # 是否启用

    # 流配置
    streams:
      color:
        resolution: [848, 480]
        fps: 30
      depth:
        resolution: [848, 480]
        fps: 30

    # 外参标定（相对于机器人基座）
    extrinsics:
      translation: [0.5, 0.0, 1.2]  # [x, y, z] 米
      rotation: [0, 0, 0, 1]  # [x, y, z, w] 四元数
      calibration_file: "calibration/overhead_camera.yaml"
```

### 2. 目标检测配置

```yaml
target_detection:
  enable: true
  detector_type: "apriltag"

  apriltag:
    family: "tag36h11"
    target_tags:
      - id: 0
        name: "insertion_hole"  # 插孔位置
        size: 0.05  # 标签尺寸（米）
        priority: 1  # 优先级

      - id: 1
        name: "workspace_origin"
        size: 0.08
        priority: 2
```

### 3. 降级策略配置

```yaml
fallback_strategy:
  # MediaPipe检测失败时
  mediapipe_failure:
    strategy: "use_last_frame"  # 使用上一帧
    max_failure_frames: 5  # 最大连续失败帧数

  # 深度数据无效时
  depth_failure:
    strategy: "use_mediapipe_depth"  # 使用MediaPipe深度

  # 目标检测失败时
  target_detection_failure:
    strategy: "use_last_target"  # 使用上一次目标
    default_target_offset: [0.0, 0.0, 0.2]  # 默认偏移
```

---

## 📊 功能对比

| 功能 | 旧版本 | 新版本 |
|------|--------|--------|
| 相机管理 | 硬编码 | 配置文件 |
| 多相机支持 | ❌ | ✅ |
| 故障恢复 | ❌ | ✅ 自动重连 |
| 时间戳 | 软件时间戳 | 硬件时间戳 |
| 目标检测 | ❌ | ✅ AprilTag |
| 降级策略 | ❌ | ✅ 多种策略 |
| 健康监控 | ❌ | ✅ 实时监控 |

---

## 🎯 AprilTag使用指南

### 1. 安装AprilTag

```bash
# 方法1：pip安装（推荐）
pip install apriltag

# 方法2：从源码安装
git clone https://github.com/AprilRobotics/apriltag.git
cd apriltag
mkdir build && cd build
cmake ..
make -j4
sudo make install
```

### 2. 打印AprilTag标签

访问：https://github.com/AprilRobotics/apriltag-imgs

下载 `tag36h11` 家族的标签，打印到纸上或贴到目标物体上。

**重要**：测量实际打印尺寸，更新配置文件中的 `size` 参数。

### 3. 标定流程

```bash
# 1. 将AprilTag贴到插孔位置
# 2. 运行视觉节点，检查是否能检测到
python3 src/nodes/integrated_vision_node.py

# 3. 查看检测结果（会显示3D位置）
# 4. 如果位置不准确，进行Hand-eye标定
```

---

## 🔍 故障排查

### 问题1：相机无法启动

**症状**：`❌ 相机 overhead 启动失败`

**解决方法**：
```bash
# 检查相机是否连接
rs-enumerate-devices

# 检查USB权限
sudo chmod 666 /dev/bus/usb/*/*

# 重启udev规则
sudo udevadm control --reload-rules
sudo udevadm trigger
```

### 问题2：相机频繁断开

**症状**：`⚠️  相机 overhead 连续失败 10 次`

**解决方法**：
1. 检查USB线缆质量（使用USB 3.0线缆）
2. 检查USB端口（使用主板直连端口，不要用Hub）
3. 降低分辨率或帧率
4. 增加重连间隔：
   ```yaml
   camera_manager:
     reconnect_interval: 5.0  # 增加到5秒
   ```

### 问题3：多相机冲突

**症状**：两个相机的数据混淆

**解决方法**：
1. 确保每个相机有唯一的 `id` 和 `role`
2. 如果使用 `serial: "auto"`，改为指定具体序列号：
   ```bash
   # 查看序列号
   rs-enumerate-devices

   # 在配置文件中指定
   serial: "123456789"
   ```

### 问题4：AprilTag检测不到

**症状**：`target_position: null`

**解决方法**：
1. 检查标签是否在相机视野内
2. 检查光照条件（避免强光或阴影）
3. 检查标签尺寸配置是否正确
4. 降低检测参数：
   ```yaml
   apriltag:
     quad_decimate: 1.0  # 降低降采样
     refine_edges: true  # 启用边缘精化
   ```

---

## 📝 开发指南

### 添加新的相机角色

1. 在 `camera_config.yaml` 中定义新角色：
   ```yaml
   - id: "my_camera"
     role: "my_custom_role"
     ...
   ```

2. 在代码中访问：
   ```python
   color_image, color_frame, depth_frame = node.get_frames('my_custom_role')
   ```

### 添加新的目标检测器

1. 创建检测器类（参考 `apriltag_detector.py`）
2. 在 `camera_config.yaml` 中配置：
   ```yaml
   target_detection:
     detector_type: "my_detector"
     my_detector:
       param1: value1
   ```

3. 在 `integrated_vision_node.py` 中集成

---

## 🎓 设计原则

### 1. 不添加滤波补丁

**原则**：深度跳变、关键点抖动等问题由VIST卡尔曼滤波统一处理，不在视觉层添加额外滤波。

**实现**：
- ✅ 只做数据质量检测（检测异常）
- ✅ 只做降级策略（使用备用数据）
- ❌ 不做SG滤波、中值滤波等工程补丁

### 2. 配置化优先

**原则**：所有参数都应该可配置，不硬编码。

**实现**：
- ✅ 相机参数在 `camera_config.yaml`
- ✅ 系统参数在 `system_config.yaml`
- ✅ 支持运行时热更新（部分参数）

### 3. 故障透明化

**原则**：故障应该被检测、记录、恢复，但不应该隐藏。

**实现**：
- ✅ 健康状态实时发布
- ✅ 故障日志详细记录
- ✅ 自动重连但不静默失败

---

## 📚 相关文档

- [RealSense SDK文档](https://github.com/IntelRealSense/librealsense)
- [AprilTag文档](https://github.com/AprilRobotics/apriltag)
- [MediaPipe文档](https://google.github.io/mediapipe/)
- [VIST系统架构](../README.md)

---

## 🔄 后续改进计划

### P0 - 已完成 ✅
- [x] 配置化相机管理
- [x] 故障自动恢复
- [x] 硬件时间戳支持
- [x] AprilTag目标检测
- [x] 降级策略

### P1 - 短期计划
- [ ] Hand-eye标定工具
- [ ] 多相机时间同步验证
- [ ] 性能监控仪表盘

### P2 - 中期计划
- [ ] YOLO目标检测（可选）
- [ ] 自适应标定
- [ ] 云端标定服务

---

**最后更新**: 2026-02-24
**维护者**: VIST Team
