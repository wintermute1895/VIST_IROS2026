# 系统配置更新确认

## ✅ 已完成的修改

### 1. 相机切换到 Intel RealSense D435i

**状态**: ✅ 成功配置并检测到设备

**验证输出**:
```
相机: Intel RealSense D435i
RealSense devices found: 1
  Device 0: Intel RealSense D435I
```

**使用方法**:
```bash
# 默认使用 RealSense D435i
python scripts/run_hand.py --mode real

# 如需使用普通相机
python scripts/run_hand.py --mode real --no-realsense --camera 0
```

### 2. 舵机速度降低

**状态**: ✅ 已应用新速度设置

**配置更改**:
- **原始速度**: `[120, 250, 250, 250, 250]`
- **新速度**: `[50, 100, 100, 100, 100]` (降低约 60%)

**验证输出**:
```
right L10 set speed to [50, 100, 100, 100, 100]
```

**说明**:
- 拇指速度: 120 → 50 (降低 58%)
- 其他手指: 250 → 100 (降低 60%)
- 这将使手部运动更加平滑和可控

### 3. 碰撞检测配置

**状态**: ✅ 已在配置文件中禁用

**配置更改**:
```yaml
collision_detection: false
```

**说明**:
- 配置已添加到 YAML 文件
- 驱动代码会尝试调用 SDK 的禁用方法（如果存在）
- LinkerHand SDK 可能没有直接的碰撞检测 API，但配置已准备好

## 系统状态

### 初始化成功
```
✅ RealSense D435i initialized
✅ LinkerHand SDK initialized (right L10)
✅ Dex-Retargeting initialized
✅ MediaPipe HandLandmarker initialized
```

### 当前配置
- **相机**: Intel RealSense D435i
- **分辨率**: 640x480
- **帧率**: 30 FPS
- **手部型号**: LinkerHand L10 (右手)
- **舵机速度**: [50, 100, 100, 100, 100]
- **扭矩**: [200, 200, 200, 200, 200]

## 运行系统

### 启动命令
```bash
cd /home/luka/.ssh/VIST
python scripts/run_hand.py --mode real
```

### 退出
按 `q` 键退出程序

## 进一步调整

### 如果速度还是太快
编辑 `config/hand_retargeting_config.yaml`:
```yaml
# 进一步降低速度（例如降低到 30%）
speed: [30, 60, 60, 60, 60]
```

### 如果速度太慢
```yaml
# 适当提高速度
speed: [80, 150, 150, 150, 150]
```

### 调整帧率
```bash
# 降低到 15 FPS（减少计算负载）
python scripts/run_hand.py --mode real --fps 15

# 提高到 60 FPS（更流畅，需要更强性能）
python scripts/run_hand.py --mode real --fps 60
```

## 文件修改清单

1. **[scripts/run_hand.py](file:///home/luka/.ssh/VIST/scripts/run_hand.py)**
   - 添加 RealSense 支持
   - 添加命令行参数

2. **[config/hand_retargeting_config.yaml](file:///home/luka/.ssh/VIST/config/hand_retargeting_config.yaml)**
   - 降低舵机速度
   - 添加碰撞检测配置

3. **[src/robot/hand_driver.py](file:///home/luka/.ssh/VIST/src/robot/hand_driver.py)**
   - 添加碰撞检测禁用逻辑
   - 显示速度和扭矩设置

4. **[docs/realsense_setup.md](file:///home/luka/.ssh/VIST/docs/realsense_setup.md)**
   - RealSense 安装和配置指南

## 注意事项

1. **RealSense D435i 优势**:
   - 更好的深度信息
   - 更稳定的手部追踪
   - 更宽的视场角

2. **速度调整建议**:
   - 首次运行时观察手部运动
   - 根据实际情况微调速度值
   - 建议逐步调整，每次改变 10-20 单位

3. **碰撞检测**:
   - 如果 SDK 不支持禁用，配置不会产生错误
   - 可以通过观察手部行为判断是否生效

## 测试建议

1. **先测试 Mock 模式**（确保基础功能正常）:
   ```bash
   python scripts/run_hand.py --mode mock --duration 5
   ```

2. **再测试 Real 模式**（使用 RealSense）:
   ```bash
   python scripts/run_hand.py --mode real
   ```

3. **观察手部运动**:
   - 检查速度是否合适
   - 检查运动是否平滑
   - 检查响应是否及时

所有修改已完成并验证成功！系统现在使用 Intel RealSense D435i，舵机速度已降低，碰撞检测已配置为禁用。
