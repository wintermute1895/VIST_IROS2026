# 标定系统配置说明

## 📋 配置文件说明

### 为什么有两个配置文件？

你的系统现在有**两个相机**，需要**两种不同的标定**：

| 配置文件 | 相机型号 | 标定类型 | 用途 |
|---------|---------|---------|------|
| **hand_camera_config.yaml** | RealSense D405 | Eye-in-Hand | 手内相机标定 |
| **head_camera_config.yaml** | RealSense D435i | Eye-to-Hand | 头部相机标定 |

### config.py 的作用

`config.py` 是配置系统的**核心代码**，定义了：
- 所有配置参数的数据结构
- 配置文件的加载和保存逻辑
- 配置验证规则
- 辅助方法（如获取相机内参、SDK 路径等）

**YAML 配置文件**（如 `hand_camera_config.yaml`）是**数据文件**，存储具体的配置值。

### 使用方式

```bash
# 手内相机标定（D405）
python3 data_collection.py --config hand_camera_config.yaml
python3 calibration_solver.py --config hand_camera_config.yaml

# 头部相机标定（D435i）
python3 data_collection.py --config head_camera_config.yaml
python3 calibration_solver.py --config head_camera_config.yaml
```

---

## ✅ 系统检查结果

### 通过的检查

✓ **Python 环境**: 3.10.19 (符合要求 >= 3.8)
✓ **OpenCV**: 4.8.0 (符合要求 >= 4.7)
✓ **NumPy**: 1.26.4
✓ **RealSense SDK**: 已安装
✓ **PyYAML**: 已安装
✓ **标定文件**: 所有必需文件都存在
✓ **配置加载**: 两个配置文件都能正常加载
✓ **机器人 SDK**: 找到 SDK 路径
✓ **相机连接**: 检测到 Intel RealSense D405 (序列号: 218622276017)

### 需要注意的问题

✗ **机器人连接**: 无法连接到 192.168.10.21
- **原因**: 机器人可能未开机或未连接到网络
- **影响**: 不影响配置检查，但标定时需要机器人连接
- **解决**: 开始标定前确保机器人已开机并连接到网络

---

## 🔍 可能的错误检查清单

### 1. 配置文件错误

**检查项**：
- [ ] 标定板尺寸是否精确测量？
- [ ] 机器人 IP 地址是否正确？
- [ ] 标定类型是否正确设置？
  - 手内相机: `calibration_type: "eye_in_hand"`
  - 头部相机: `calibration_type: "eye_to_hand"`

**验证方法**：
```bash
# 检查配置是否能正常加载
python3 -c "from config import CalibrationConfig; config = CalibrationConfig(config_file='hand_camera_config.yaml'); config.print_config()"
```

### 2. 硬件连接错误

**检查项**：
- [ ] 相机是否连接并通电？
- [ ] 机器人是否开机？
- [ ] 网络连接是否正常？

**验证方法**：
```bash
# 检查相机
rs-enumerate-devices

# 检查机器人连接
ping 192.168.10.21

# 运行完整系统检查
python3 check_system.py
```

### 3. 标定板问题

**检查项**：
- [ ] 标定板是否打印清晰？
- [ ] 标定板尺寸是否准确？
- [ ] 标定板是否平整（无弯曲）？
- [ ] 光照条件是否良好（无反光、无阴影）？

**验证方法**：
```bash
# 测试相机画面
realsense-viewer
```

### 4. 数据采集错误

**常见问题**：
- 检测不到标定板 → 检查光照和标定板质量
- 位姿变化不足 → 确保机器人移动到不同位置
- 样本数量不足 → 至少采集 15 组数据

**验证方法**：
- 运行数据采集程序，观察是否能检测到标定板
- 检查采集的图像质量

### 5. 标定计算错误

**常见问题**：
- 所有位姿相同 → 使用真实机器人（不是 Mock）
- 有效样本不足 → 重新采集数据
- 标定误差过大 → 检查标定板尺寸和数据质量

**验证方法**：
```bash
# 运行标定求解器
python3 calibration_solver.py --config hand_camera_config.yaml

# 检查重投影误差
python3 calibration_error_analysis.py --config hand_camera_config.yaml
```

---

## 🚀 开始标定前的准备

### 手内相机标定（D405）

1. **硬件准备**：
   - ✓ 相机已检测到: Intel RealSense D405
   - ⚠️ 标定板固定在桌面上（不要移动）
   - ⚠️ 机器人需要开机并连接

2. **配置文件**：
   - 使用 `hand_camera_config.yaml`
   - 检查标定板尺寸参数

3. **开始标定**：
   ```bash
   python3 data_collection.py --config hand_camera_config.yaml
   ```

### 头部相机标定（D435i）

1. **硬件准备**：
   - ⚠️ 需要 D435i 相机（当前只检测到 D405）
   - ⚠️ 标定板安装在机械臂末端（不是固定在桌面）
   - ⚠️ 机器人需要开机并连接

2. **配置文件**：
   - 使用 `head_camera_config.yaml`
   - 检查标定板尺寸参数

3. **开始标定**：
   ```bash
   python3 data_collection.py --config head_camera_config.yaml
   ```

---

## 📊 配置文件对比

### 关键区别

| 参数 | 手内相机 | 头部相机 |
|------|---------|---------|
| `calibration_type` | `eye_in_hand` | `eye_to_hand` |
| `camera_type` | `realsense_d405` | `realsense_d435i` |
| `data_dir` | `calibration_data` | `calibration_data_head_camera` |
| `result_filename` | `hand_eye_result.json` | `eye_to_hand_result.json` |
| `window_name` | "Hand Camera Calibration" | "Head Camera Calibration" |

### 相同参数

- 标定板尺寸（`square_size`, `marker_size`）
- 机器人配置（`tcp_host`, `arm_side`）
- 采集参数（`min_samples`, `min_position_change`）
- 验证阈值（`excellent_threshold`, `good_threshold`）

---

## 🛠️ 快速检查命令

```bash
# 1. 运行完整系统检查
python3 check_system.py

# 2. 检查配置文件
python3 -c "from config import CalibrationConfig; CalibrationConfig(config_file='hand_camera_config.yaml').print_config()"

# 3. 检查相机
rs-enumerate-devices

# 4. 检查机器人
ping 192.168.10.21

# 5. 测试相机画面
realsense-viewer
```

---

## 📝 总结

### 当前状态

✅ **系统已准备好进行标定**
- 所有软件依赖已安装
- 配置文件已创建并验证
- 相机已连接（D405）
- 代码无语法错误

⚠️ **需要注意**
- 机器人需要开机并连接网络
- 头部相机（D435i）需要连接后才能标定
- 标定板尺寸需要精确测量

### 下一步

1. **开机并连接机器人**
2. **精确测量标定板尺寸**
3. **选择要标定的相机**：
   - 手内相机（D405）→ 使用 `hand_camera_config.yaml`
   - 头部相机（D435i）→ 使用 `head_camera_config.yaml`
4. **运行数据采集**
5. **运行标定计算**
6. **验证标定结果**

**最后更新**: 2026-02-10
