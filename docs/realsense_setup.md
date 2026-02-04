# Intel RealSense D435i 配置指南

## 安装 pyrealsense2

### 方法 1: 使用 pip（推荐）

```bash
pip install pyrealsense2
```

### 方法 2: 使用 conda

```bash
conda install -c conda-forge pyrealsense2
```

## 验证安装

```bash
python -c "import pyrealsense2 as rs; print(rs.__version__)"
```

## 使用说明

### 使用 RealSense D435i 运行（默认）

```bash
python scripts/run_hand.py --mode real
```

### 使用普通相机运行

```bash
python scripts/run_hand.py --mode real --no-realsense --camera 0
```

## 配置更改

### 1. 相机切换
- 默认使用 Intel RealSense D435i
- 使用 `--no-realsense` 参数切换回普通相机

### 2. 舵机速度降低
配置文件中的速度已从 `[120, 250, 250, 250, 250]` 降低到 `[50, 100, 100, 100, 100]`（约 40%）

### 3. 碰撞检测
已在配置中添加 `collision_detection: false` 参数

## 故障排除

### RealSense 未检测到

1. 检查 D435i 是否正确连接到 USB 3.0 端口
2. 运行 `realsense-viewer` 测试相机
3. 检查权限：
   ```bash
   sudo usermod -a -G video $USER
   # 注销并重新登录
   ```

### 安装 RealSense SDK（如果 pip 安装失败）

```bash
# Ubuntu/Debian
sudo apt-key adv --keyserver keyserver.ubuntu.com --recv-key F6E65AC044F831AC80A06380C8B3A55A6F3EFCDE
sudo add-apt-repository "deb https://librealsense.intel.com/Debian/apt-repo $(lsb_release -cs) main"
sudo apt-get update
sudo apt-get install librealsense2-dkms librealsense2-utils librealsense2-dev
pip install pyrealsense2
```

## RealSense D435i 特性

- **分辨率**: 640x480 @ 30fps（当前配置）
- **深度范围**: 0.3m - 3m
- **视场角**: 69° x 42° x 77°
- **接口**: USB 3.0

## 性能优化

如果遇到性能问题，可以调整：

1. **降低帧率**:
   ```bash
   python scripts/run_hand.py --mode real --fps 15
   ```

2. **降低分辨率**（需修改代码中的 640x480）

3. **进一步降低舵机速度**（修改 config/hand_retargeting_config.yaml）
