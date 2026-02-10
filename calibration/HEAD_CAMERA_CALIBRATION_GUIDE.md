# 头部相机标定指南 (Eye-to-Hand Calibration)

## 📋 概述

本文档说明如何为头部相机（固定安装的相机）进行标定。这与手内相机标定（Eye-in-Hand）有本质区别。

---

## 🔍 两种标定方式的对比

| 特性 | 手眼标定 (Eye-in-Hand) | 眼到手标定 (Eye-to-Hand) |
|------|----------------------|------------------------|
| **相机位置** | 安装在机械臂末端 | 固定在外部（头部/基座） |
| **标定板位置** | 固定不动 | 安装在机械臂末端 |
| **运动方式** | 机械臂带相机移动 | 机械臂带标定板移动 |
| **标定目标** | `T_end_to_cam` | `T_base_to_cam` |
| **OpenCV 函数** | `cv2.calibrateHandEye()` | `cv2.calibrateRobotWorldHandEye()` |
| **你的情况** | ✅ 已完成 | ❓ 需要进行 |

---

## ⚠️ 重要区别

### 当前代码的局限性

你当前的标定系统是为 **Eye-in-Hand（手眼标定）** 设计的：
- 假设相机安装在机械臂末端
- 标定板固定不动
- 使用 `cv2.calibrateHandEye()` 函数

### 头部相机需要的改动

对于头部相机（Eye-to-Hand），需要：
1. **硬件设置不同**：标定板需要安装在机械臂末端
2. **数据采集不同**：固定相机观察移动的标定板
3. **标定算法不同**：使用 `cv2.calibrateRobotWorldHandEye()`
4. **输出结果不同**：得到 `T_base_to_cam`（相机相对于机器人基座）

---

## 🛠️ 实现方案

### 方案 1: 修改现有代码（推荐）

在配置中添加标定类型参数，让同一套代码支持两种标定。

#### 1.1 修改配置文件

在 `config.py` 的 `CalibrationSolverConfig` 中添加：

```python
@dataclass
class CalibrationSolverConfig:
    """标定算法配置"""
    # 标定类型
    calibration_type: str = "eye_in_hand"  # "eye_in_hand" 或 "eye_to_hand"

    # 手眼标定方法
    method: int = cv2.CALIB_HAND_EYE_TSAI

    # ... 其他参数
```

#### 1.2 修改标定求解器

在 `calibration_solver.py` 中添加对两种标定类型的支持：

```python
def solve_calibration(self):
    """执行标定计算"""

    if self.config.calibration_solver.calibration_type == "eye_in_hand":
        # 手眼标定 (Eye-in-Hand)
        R_cam2gripper, t_cam2gripper = cv2.calibrateHandEye(
            R_gripper2base=self.R_gripper2base,
            t_gripper2base=self.t_gripper2base,
            R_target2cam=self.R_target2cam,
            t_target2cam=self.t_target2cam,
            method=self.config.calibration_solver.method
        )

        # 构建变换矩阵 T_end_to_cam
        T_end_to_cam = np.eye(4)
        T_end_to_cam[:3, :3] = R_cam2gripper
        T_end_to_cam[:3, 3] = t_cam2gripper.flatten()

        return T_end_to_cam

    elif self.config.calibration_solver.calibration_type == "eye_to_hand":
        # 眼到手标定 (Eye-to-Hand)
        R_cam2world, t_cam2world, R_gripper2base, t_gripper2base = cv2.calibrateRobotWorldHandEye(
            R_world2cam=self.R_target2cam,  # 标定板到相机的旋转
            t_world2cam=self.t_target2cam,  # 标定板到相机的平移
            R_base2gripper=self.R_gripper2base,  # 基座到末端的旋转
            t_base2gripper=self.t_gripper2base,  # 基座到末端的平移
            method=self.config.calibration_solver.method
        )

        # 构建变换矩阵 T_base_to_cam
        T_base_to_cam = np.eye(4)
        T_base_to_cam[:3, :3] = R_cam2world
        T_base_to_cam[:3, 3] = t_cam2world.flatten()

        return T_base_to_cam

    else:
        raise ValueError(f"不支持的标定类型: {self.config.calibration_solver.calibration_type}")
```

---

### 方案 2: 创建独立的头部相机标定脚本

如果你不想修改现有代码，可以创建一个新的标定脚本专门用于头部相机。

---

## 📝 头部相机标定步骤

### 步骤 1: 硬件准备

**关键区别**：
- ❌ 不要把标定板固定在桌面上
- ✅ 把标定板安装在机械臂末端（夹持器上）
- ✅ 头部相机固定不动

**安装方式**：
```
方式 1: 使用夹持器夹住标定板
方式 2: 使用 3D 打印支架将标定板固定在末端法兰
方式 3: 使用胶带临时固定（不推荐，可能不稳定）
```

### 步骤 2: 配置文件准备

创建头部相机的配置文件 `head_camera_calibration.yaml`：

```yaml
# 标定类型配置
calibration_solver:
  calibration_type: "eye_to_hand"  # ⚠️ 关键：设置为 eye_to_hand
  method: 0  # TSAI 方法

# 相机配置（头部相机）
camera:
  camera_type: "realsense_d405_head"  # 头部相机
  width: 640
  height: 480
  fps: 30
  use_auto_intrinsics: true

# 机器人配置
robot:
  tcp_host: "192.168.10.21"
  arm_side: "right"  # 或 "left"

# 标定板配置（与手内相机相同）
charuco_board:
  rows: 5
  cols: 7
  square_size: 0.025  # 25mm
  marker_size: 0.018  # 18mm

# 数据采集配置
data_collection:
  min_samples: 15
  recommended_samples: 20

# 存储配置
storage:
  data_dir: "calibration_data_head_camera"  # 使用不同的目录
```

### 步骤 3: 数据采集

**注意事项**：
1. 确保头部相机能看到标定板
2. 移动机械臂（带着标定板）到不同位置
3. 标定板应该始终在相机视野内
4. 采集 15-20 组不同位姿的数据

**采集策略**：
```
1. 中心位置（5 组）
   - 标定板在相机正前方
   - 距离 50-80cm
   - 不同高度

2. 左侧位置（5 组）
   - 标定板向左移动
   - 保持在视野内

3. 右侧位置（5 组）
   - 标定板向右移动
   - 保持在视野内

4. 倾斜位置（5 组）
   - 改变标定板姿态
   - 增加旋转多样性
```

**运行数据采集**：
```bash
cd /home/ilex/Dev/VIST/calibration
python3 data_collection.py --config head_camera_calibration.yaml
```

### 步骤 4: 标定计算

```bash
python3 calibration_solver.py --config head_camera_calibration.yaml
```

**输出结果**：
- `T_base_to_cam`：相机相对于机器人基座的变换矩阵
- 保存在 `calibration_data_head_camera/hand_eye_result.json`

### 步骤 5: 结果验证

```bash
python3 calibration_error_analysis.py --config head_camera_calibration.yaml
```

---

## 🔧 代码修改清单

如果你选择方案 1（修改现有代码），需要修改以下文件：

### 1. `config.py`
- [ ] 在 `CalibrationSolverConfig` 中添加 `calibration_type` 参数

### 2. `calibration_solver.py`
- [ ] 添加对 `eye_to_hand` 标定类型的支持
- [ ] 使用 `cv2.calibrateRobotWorldHandEye()` 函数
- [ ] 正确处理输入输出矩阵

### 3. `data_collection.py`
- [ ] 可选：添加提示信息，说明当前是哪种标定类型
- [ ] 可选：根据标定类型显示不同的操作指南

---

## 📊 两种标定结果的使用

### 手眼标定结果 (Eye-in-Hand)
```python
# T_end_to_cam: 相机相对于末端的变换
# 用途：将相机坐标系中的点转换到末端坐标系

def camera_to_end(point_cam, T_end_to_cam):
    point_homo = np.append(point_cam, 1.0)
    point_end = T_end_to_cam @ point_homo
    return point_end[:3]

# 进一步转换到基座坐标系
def camera_to_base(point_cam, T_end_to_cam, T_base_to_end):
    point_end = camera_to_end(point_cam, T_end_to_cam)
    point_homo = np.append(point_end, 1.0)
    point_base = T_base_to_end @ point_homo
    return point_base[:3]
```

### 眼到手标定结果 (Eye-to-Hand)
```python
# T_base_to_cam: 相机相对于基座的变换
# 用途：将相机坐标系中的点直接转换到基座坐标系

def camera_to_base(point_cam, T_base_to_cam):
    point_homo = np.append(point_cam, 1.0)
    point_base = T_base_to_cam @ point_homo
    return point_base[:3]
```

---

## ❓ 常见问题

### Q1: 可以用同一个标定板吗？
**A**: 可以！标定板的尺寸参数保持不变即可。

### Q2: 需要重新标定相机内参吗？
**A**: 如果是不同的相机，需要使用该相机的内参。如果启用了 `use_auto_intrinsics: true`，会自动从相机读取。

### Q3: 标定板怎么固定在机械臂末端？
**A**:
- 最简单：用夹持器夹住
- 最稳定：3D 打印一个固定支架
- 临时方案：用胶带固定（注意稳定性）

### Q4: 两个相机可以同时使用吗？
**A**: 可以！完成两个相机的标定后：
- 手内相机：用于近距离精密操作
- 头部相机：用于全局视野和远距离观察

### Q5: 标定精度要求一样吗？
**A**: 是的，重投影误差标准相同：
- 优秀: < 1.0 像素
- 良好: < 2.0 像素
- 可接受: < 5.0 像素

---

## 🎯 总结

**关键区别**：
1. **硬件设置**：标定板安装在机械臂末端（不是固定在桌面）
2. **标定类型**：配置中设置 `calibration_type: "eye_to_hand"`
3. **标定算法**：使用 `cv2.calibrateRobotWorldHandEye()`
4. **输出结果**：得到 `T_base_to_cam`（不是 `T_end_to_cam`）

**不是简单地换相机参数**，而是需要：
- ✅ 改变硬件安装方式
- ✅ 修改标定类型配置
- ✅ 使用不同的标定算法
- ✅ 理解不同的坐标系关系

**最后更新**: 2026-02-10
