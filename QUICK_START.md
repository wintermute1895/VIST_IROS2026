# VIST 快速启动参考

## 启动前检查 ✓

```bash
cd /home/ilex/Dev/VIST
./scripts/validate_startup_config.sh
```

## 启动命令

### Terminal 1 - 外骨骼
```bash
./scripts/start_1_exoskeleton.sh
```

### Terminal 2 - 滤波器
```bash
cd /home/ilex/Dev/VIST && ./scripts/start_2_filter.sh one_euro
```

### Terminal 3 - 机械臂驱动
```bash
cd /home/ilex/Dev/VIST && ./scripts/start_3_robot_driver.sh
```

### Terminal 4 - 遥操作桥接
```bash
cd /home/ilex/Dev/VIST && ./scripts/start_4_teleop_bridge.sh
```

### Terminal 5 (可选) - 数据采集相机
```bash
cd /home/ilex/Dev/VIST && ./scripts/start_camera.sh
```

## 数据采集

**不含相机**:
```bash
./scripts/collect_right_arm_data.sh exp1_one_euro 30
```

**包含相机** (需先启动 Terminal 5):
```bash
./scripts/collect_right_arm_data.sh exp1_one_euro_camera 30 --with-camera
```

## 配置控制

编辑 `config/system_config.yaml`:

```yaml
startup:
  camera:
    enabled: true  # 启用/禁用相机
    serial_number: "123456789"  # 指定相机序列号（多相机时必需）

data_logging:
  enable_camera_recording: true  # 录制相机数据
```

### 配置层级

**配置文件 → 命令行参数 → 最终配置**

- 配置文件提供默认值
- 命令行参数覆盖配置文件
- 示例: `./scripts/start_camera.sh 123456789 1280 720 30`

### 多相机使用

如果有两个 D435i 相机：

1. 查找序列号: `rs-enumerate-devices | grep "Serial Number"`
2. 启动指定相机: `./scripts/start_camera.sh <serial_number>`

详见: [docs/CAMERA_SETUP.md](docs/CAMERA_SETUP.md)

---

详细文档: [docs/STARTUP_GUIDE_SIMPLE.md](docs/STARTUP_GUIDE_SIMPLE.md)
