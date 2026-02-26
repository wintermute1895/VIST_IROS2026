# VIST 系统简化启动指南
# Simplified Startup Guide for VIST System

## 概述

本指南提供了简化的、鲁棒的启动流程，所有参数都已配置化，无需手动输入复杂参数。

## 启动前检查

在启动系统之前，**必须**运行配置验证脚本：

```bash
cd /home/ilex/Dev/VIST
./scripts/validate_startup_config.sh
```

## 启动流程

### Terminal 1: 外骨骼驱动

```bash
cd /home/ilex/Dev/VIST
./scripts/start_1_exoskeleton.sh
```

### Terminal 2: 滤波节点

```bash
cd /home/ilex/Dev/VIST
./scripts/start_2_filter.sh [filter_type] [params...]
```

### Terminal 3: 机械臂驱动

```bash
cd /home/ilex/Dev/VIST
./scripts/start_3_robot_driver.sh
```

### Terminal 4: 遥操作桥接

```bash
cd /home/ilex/Dev/VIST
./scripts/start_4_teleop_bridge.sh
```

### Terminal 5 (可选): 数据采集相机

```bash
cd /home/ilex/Dev/VIST
./scripts/start_camera.sh
```

**注意**: 这是可选组件，只在需要记录视觉数据时启动。

## 数据采集

### 不含相机数据

```bash
cd /home/ilex/Dev/VIST
./scripts/collect_right_arm_data.sh exp1_one_euro 30
```

### 包含相机数据

```bash
cd /home/ilex/Dev/VIST
./scripts/collect_right_arm_data.sh exp1_one_euro_with_camera 30 --with-camera
```

**重要**: 使用 `--with-camera` 参数前，必须先启动相机节点（Terminal 5）！

## 配置文件

所有系统参数都在以下配置文件中：

- **系统配置**: `/home/ilex/Dev/VIST/config/system_config.yaml`
  - `startup.camera.enabled`: 控制相机是否启用
  - `data_logging.enable_camera_recording`: 控制是否录制相机数据

---

更新日期: 2026-02-25  
版本: 2.1 (添加相机支持)
