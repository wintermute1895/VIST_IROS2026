# 头部相机标定系统实现总结

## 📋 概述

为 Intel RealSense D435i 头部相机实现了独立的 Eye-to-Hand 标定系统，与现有的手内相机（D405）Eye-in-Hand 标定系统并行工作。

---

## ✅ 完成的工作

### 1. 配置系统更新

#### 1.1 修改 `config.py`
- 在 `CalibrationSolverConfig` 中添加了 `calibration_type` 参数
- 支持两种标定类型：`"eye_in_hand"` 和 `"eye_to_hand"`

```python
@dataclass
class CalibrationSolverConfig:
    """标定算法配置"""
    # 标定类型
    calibration_type: str = "eye_in_hand"  # "eye_in_hand" 或 "eye_to_hand"
    # ... 其他参数
```

#### 1.2 创建头部相机配置文件
- 文件：`head_camera_config.yaml`
- 配置了 D435i 相机参数
- 设置标定类型为 `eye_to_hand`
- 使用独立的数据目录：`calibration_data_head_camera`

### 2. 标定求解器更新

#### 2.1 修改 `calibration_solver.py`
更新了 `solve_hand_eye_calibration()` 方法以支持两种标定类型：

**Eye-in-Hand 标定**：
```python
if calibration_type == "eye_in_hand":
    R_cam2gripper, t_cam2gripper = cv2.calibrateHandEye(
        self.R_gripper2base,
        self.t_gripper2base,
        self.R_target2cam,
        self.t_target2cam,
        method=self.config.calibration_solver.method
    )
    # 返回 T_end_to_cam
```

**Eye-to-Hand 标定**：
```python
elif calibration_type == "eye_to_hand":
    R_cam2world, t_cam2world, _, _ = cv2.calibrateRobotWorldHandEye(
        R_world2cam=self.R_target2cam,
        t_world2cam=self.t_target2cam,
        R_base2gripper=R_base2gripper,
        t_base2gripper=t_base2gripper,
        method=self.config.calibration_solver.method
    )
    # 返回 T_base_to_cam
```

#### 2.2 更新 `save_results()` 方法
- 根据标定类型保存不同的结果键名
- Eye-in-Hand: `T_end_to_cam`
- Eye-to-Hand: `T_base_to_cam`
- 在 JSON 结果中添加 `calibration_type` 字段

### 3. 文档创建

#### 3.1 `HEAD_CAMERA_CALIBRATION_GUIDE.md`
- 详细说明两种标定方式的区别
- 硬件设置要求
- 代码修改方案
- 常见问题解答

#### 3.2 `HEAD_CAMERA_USAGE.md`
- 快速开始指南
- 详细的标定步骤
- 坐标转换示例代码
- 质量检查清单

---

## 🔧 使用方法

### 头部相机标定流程

```bash
# 1. 数据采集（标定板安装在机械臂末端）
cd /home/ilex/Dev/VIST/calibration
python3 data_collection.py --config head_camera_config.yaml

# 2. 标定计算
python3 calibration_solver.py --config head_camera_config.yaml

# 3. 结果验证
python3 calibration_error_analysis.py --config head_camera_config.yaml
```

### 手内相机标定流程（保持不变）

```bash
# 1. 数据采集（标定板固定不动）
cd /home/ilex/Dev/VIST/calibration
python3 data_collection.py --config calibration_config_template.yaml

# 2. 标定计算
python3 calibration_solver.py --config calibration_config_template.yaml

# 3. 结果验证
python3 calibration_error_analysis.py --config calibration_config_template.yaml
```

---

## 📁 文件结构

```
calibration/
├── config.py                           # ✅ 已更新：添加 calibration_type
├── calibration_solver.py               # ✅ 已更新：支持两种标定类型
├── data_collection.py                  # ✅ 无需修改：自动适配配置
├── calibration_error_analysis.py       # ✅ 无需修改：自动适配配置
│
├── calibration_config_template.yaml    # 手内相机配置（D405）
├── head_camera_config.yaml             # ✅ 新建：头部相机配置（D435i）
│
├── CALIBRATION_WORKFLOW.md             # 手眼标定完整工作流程
├── HEAD_CAMERA_CALIBRATION_GUIDE.md    # ✅ 新建：头部相机标定指南
├── HEAD_CAMERA_USAGE.md                # ✅ 新建：头部相机使用指南
│
├── calibration_data/                   # 手内相机数据目录
│   ├── images/
│   ├── hand_eye_result.json            # T_end_to_cam
│   └── ...
│
└── calibration_data_head_camera/       # ✅ 新建：头部相机数据目录
    ├── images/
    ├── eye_to_hand_result.json         # T_base_to_cam
    └── ...
```

---

## 🎯 关键区别总结

| 特性 | 手内相机 (Eye-in-Hand) | 头部相机 (Eye-to-Hand) |
|------|----------------------|----------------------|
| **相机型号** | RealSense D405 | RealSense D435i |
| **相机位置** | 机械臂末端 | 固定在头部 |
| **标定板位置** | 固定不动 | 安装在末端 |
| **标定类型** | `eye_in_hand` | `eye_to_hand` |
| **OpenCV 函数** | `cv2.calibrateHandEye()` | `cv2.calibrateRobotWorldHandEye()` |
| **配置文件** | `calibration_config_template.yaml` | `head_camera_config.yaml` |
| **数据目录** | `calibration_data/` | `calibration_data_head_camera/` |
| **结果矩阵** | `T_end_to_cam` | `T_base_to_cam` |
| **结果文件** | `hand_eye_result.json` | `eye_to_hand_result.json` |

---

## ✨ 系统特点

### 1. 统一的代码库
- 同一套代码支持两种标定类型
- 通过配置文件区分标定类型
- 无需维护两套独立的代码

### 2. 独立的数据管理
- 两种标定使用不同的数据目录
- 避免数据混淆
- 可以同时保留两种标定结果

### 3. 自动适配
- `data_collection.py` 自动适配配置
- `calibration_error_analysis.py` 自动适配配置
- 只需修改配置文件即可切换标定类型

### 4. 完整的文档
- 详细的使用指南
- 清晰的对比说明
- 常见问题解答

---

## 🔄 后续工作建议

### 1. 系统集成
完成两个相机的标定后，可以在 VIST 系统中同时使用：
- 手内相机：近距离精密操作
- 头部相机：全局视野观察

### 2. 联调测试
建议创建测试脚本验证标定精度：
```python
def test_head_camera_calibration():
    # 1. 在头部相机中检测目标
    target_pos_cam = detect_target_in_head_camera()

    # 2. 转换到基座坐标系
    target_pos_base = camera_to_base(target_pos_cam)

    # 3. 控制机器人移动到目标
    robot.move_to(target_pos_base)

    # 4. 测量实际误差
    actual_pos = robot.get_position()
    error = np.linalg.norm(actual_pos - target_pos_base)

    print(f"定位误差: {error*1000:.2f} mm")
```

### 3. 多相机融合
如果需要同时使用两个相机：
```python
class DualCameraSystem:
    def __init__(self):
        # 加载手内相机标定
        self.T_end_to_cam_hand = load_calibration('hand_eye_result.json')

        # 加载头部相机标定
        self.T_base_to_cam_head = load_calibration('eye_to_hand_result.json')

    def get_target_from_hand_camera(self):
        # 使用手内相机检测
        pass

    def get_target_from_head_camera(self):
        # 使用头部相机检测
        pass
```

---

## 📝 注意事项

### 1. 硬件安装
- ⚠️ 头部相机标定时，标定板**必须**安装在机械臂末端
- ⚠️ 不能像手内相机那样把标定板固定在桌面

### 2. 配置文件
- ⚠️ 确保使用正确的配置文件
- ⚠️ 检查 `calibration_type` 参数设置正确

### 3. 数据目录
- ⚠️ 两种标定使用不同的数据目录
- ⚠️ 避免覆盖已有的标定数据

---

## 🎉 总结

成功实现了头部相机（D435i）的 Eye-to-Hand 标定系统：

✅ 配置系统支持两种标定类型
✅ 标定求解器支持两种标定算法
✅ 创建了独立的配置文件
✅ 编写了完整的使用文档
✅ 保持了与手内相机标定的兼容性

现在可以为头部相机进行标定了！

**最后更新**: 2026-02-10
