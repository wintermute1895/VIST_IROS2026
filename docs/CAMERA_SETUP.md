# 相机配置指南
# Camera Setup Guide

## 配置层级

VIST 系统使用**配置文件优先，命令行覆盖**的策略：

```
配置文件 (system_config.yaml) → 命令行参数 → 最终配置
```

### 示例

**配置文件** (`config/system_config.yaml`):
```yaml
startup:
  camera:
    width: 848
    height: 480
    fps: 30
    serial_number: ""
```

**命令行覆盖**:
```bash
# 使用配置文件的默认值
./scripts/start_camera.sh

# 覆盖序列号
./scripts/start_camera.sh 123456789

# 覆盖序列号和分辨率
./scripts/start_camera.sh 123456789 1280 720 30
```

## 单相机使用

如果只使用一个相机，无需指定序列号：

```bash
./scripts/start_camera.sh
```

系统会自动检测并使用第一个可用的 D435i 相机。

## 多相机使用

如果有两个 D435i 相机，**必须**为每个相机指定序列号，避免话题冲突。

### 1. 查找相机序列号

```bash
rs-enumerate-devices | grep "Serial Number"
```

输出示例:
```
Serial Number: 123456789
Serial Number: 987654321
```

### 2. 启动指定相机

**方法 1: 使用命令行参数**

```bash
# Terminal 5a: 启动第一个相机
./scripts/start_camera.sh 123456789

# Terminal 5b: 启动第二个相机（需要修改话题命名空间）
# 注意: 当前脚本不支持命名空间，需要手动启动
ros2 run camera_manager data_camera_node --ros-args \
  -p serial_number:=987654321 \
  -r __ns:=/camera2
```

**方法 2: 修改配置文件**

编辑 `config/system_config.yaml`:

```yaml
startup:
  camera:
    serial_number: "123456789"  # 指定要使用的相机
```

### 3. 数据采集时的话题名称

如果使用命名空间，需要更新数据采集脚本中的话题列表：

```bash
# 默认话题（无命名空间）
/camera/color/image_raw
/camera/depth/image_raw

# 带命名空间的话题
/camera1/color/image_raw
/camera1/depth/image_raw
/camera2/color/image_raw
/camera2/depth/image_raw
```

## 推荐配置

### 数据采集实验（单相机）

使用一个相机记录手部运动和场景：

```yaml
startup:
  camera:
    enabled: true
    serial_number: "123456789"  # 指定你的相机序列号
    width: 848
    height: 480
    fps: 30
```

### 完整 VIST 系统（可能需要两个相机）

- **相机 1**: 手部追踪和意图检测
- **相机 2**: 目标物体检测（AprilTag/ArUco）

这种情况下需要使用命名空间区分两个相机的话题。

## 故障排除

### 问题: 启动相机时报错 "No device connected"

**解决方案**:
1. 检查相机 USB 连接
2. 运行 `rs-enumerate-devices` 确认相机被识别
3. 检查 USB 端口供电是否充足（建议使用 USB 3.0）

### 问题: 两个相机同时启动导致话题冲突

**解决方案**:
1. 为每个相机指定不同的序列号
2. 使用命名空间区分话题
3. 或者只启动一个相机用于数据采集

### 问题: 相机帧率不稳定

**解决方案**:
1. 降低分辨率（例如从 1280x720 降到 848x480）
2. 降低帧率（例如从 30fps 降到 15fps）
3. 检查 CPU 负载，关闭不必要的进程

---

更新日期: 2026-02-25
