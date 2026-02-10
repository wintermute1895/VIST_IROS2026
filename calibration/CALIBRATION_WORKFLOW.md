# 手眼标定完整工作流程

## 📋 概述

本文档详细说明手眼标定的完整流程，从准备工作到系统集成。手眼标定是 VIST 系统的**前置步骤**，必须先完成标定才能进行后续的视觉伺服任务。

---

## 🎯 工作流程总览

```
1. 准备阶段
   ├── 硬件准备（标定板、相机、机器人）
   ├── 配置文件准备
   └── 环境检查

2. 数据采集阶段
   ├── 运行 data_collection.py
   ├── 移动机器人到不同位姿
   └── 采集 15-20 组数据

3. 标定计算阶段
   ├── 运行 calibration_solver.py
   ├── 计算手眼变换矩阵
   └── 保存标定结果

4. 结果验证阶段
   ├── 运行 calibration_error_analysis.py
   ├── 检查重投影误差
   └── 评估标定质量

5. 系统集成阶段
   ├── 将标定结果集成到 VIST 系统
   ├── 进行联调测试
   └── 验证实际任务性能
```

---

## 📝 详细步骤

### 阶段 1: 准备工作

#### 1.1 硬件准备

**必需硬件**：
- ✅ LinkerArm 机械臂（已连接并通电）
- ✅ RealSense D405 相机（已安装在机械臂末端）
- ✅ ChArUco 标定板（5x7，方格 25mm，标记 18mm）
- ✅ 标定板固定支架（保持标定板稳定）

**硬件检查**：
```bash
# 检查机器人连接
ping 192.168.10.21

# 检查相机连接
rs-enumerate-devices

# 测试相机画面
realsense-viewer
```

**标定板测量**：
- 使用卡尺精确测量标定板的实际尺寸
- 记录方格边长（square_size）和标记边长（marker_size）
- 这是标定精度的关键！

#### 1.2 配置文件准备

**生成配置文件模板**：
```bash
cd /home/ilex/Dev/VIST/calibration
python3 -c "from config import generate_config_template; generate_config_template('my_calibration.yaml')"
```

**修改配置文件** (`my_calibration.yaml`):
```yaml
robot:
  tcp_host: "192.168.10.21"  # 修改为实际机器人 IP
  arm_side: "right"           # 使用右臂

camera:
  width: 640
  height: 480
  fps: 30
  use_auto_intrinsics: true   # 自动从相机读取内参

charuco_board:
  rows: 5
  cols: 7
  square_size: 0.025          # ⚠️ 必须精确测量！（米）
  marker_size: 0.018          # ⚠️ 必须精确测量！（米）

data_collection:
  min_samples: 15             # 最少采集 15 组
  recommended_samples: 20     # 推荐 20 组
  min_position_change: 0.02   # 位置变化阈值 2cm
  min_rotation_change: 0.1    # 旋转变化阈值

storage:
  data_dir: "calibration_data"  # 数据保存目录
```

#### 1.3 环境检查

```bash
# 检查 Python 环境
python3 --version  # 需要 Python 3.8+

# 检查依赖库
python3 -c "import cv2; print(f'OpenCV: {cv2.__version__}')"  # 需要 4.8.0+
python3 -c "import pyrealsense2; print('RealSense SDK: OK')"
python3 -c "import numpy; print('NumPy: OK')"

# 检查 SDK 路径
ls src/robot/sdk/linkerarm/lbot  # 应该能看到 lbot 模块
```

---

### 阶段 2: 数据采集

#### 2.1 启动数据采集程序

```bash
cd /home/ilex/Dev/VIST/calibration
python3 data_collection.py --config my_calibration.yaml
```

**程序界面说明**：
- 窗口显示相机实时画面
- 绿色文字：检测到标定板，显示当前采集数量
- 橙色文字：未检测到标定板或位姿变化不足
- 按 `s` 键：保存当前样本
- 按 `q` 键：退出程序

#### 2.2 采集数据的要点

**位姿多样性**：
- 需要采集 15-20 组不同位姿的数据
- 每组数据的位姿应该有明显差异（位置变化 > 2cm 或旋转变化 > 0.1）

**推荐的采集策略**：
```
1. 正面观察（5 组）
   - 距离标定板 30-50cm
   - 相机正对标定板
   - 在不同高度和左右位置采集

2. 倾斜观察（5 组）
   - 相机倾斜 15-30 度
   - 从不同角度观察标定板
   - 保证标定板完全可见

3. 侧面观察（5 组）
   - 相机倾斜 30-45 度
   - 从侧面观察标定板
   - 增加位姿多样性

4. 近距离观察（5 组）
   - 距离标定板 20-30cm
   - 标定板充满画面
   - 提高标定精度
```

**注意事项**：
- ⚠️ 确保标定板在画面中完全可见
- ⚠️ 避免标定板反光或过曝
- ⚠️ 保持标定板静止（固定在支架上）
- ⚠️ 每次采集后移动机器人到新位姿

#### 2.3 数据采集完成

采集完成后，数据保存在 `calibration_data/` 目录：
```
calibration_data/
├── images/
│   ├── sample_0.png
│   ├── sample_1.png
│   └── ...
├── hand_eye_robot_poses.npy  # 机器人位姿数据
└── metadata.json              # 元数据
```

---

### 阶段 3: 标定计算

#### 3.1 运行标定求解器

```bash
cd /home/ilex/Dev/VIST/calibration
python3 calibration_solver.py --config my_calibration.yaml
```

**程序输出**：
```
正在加载配置...
正在加载数据...
检测到 20 组数据
正在检测 ChArUco 角点...
样本 0: 检测到 24 个角点 ✓
样本 1: 检测到 26 个角点 ✓
...
有效样本数: 20/20
正在计算手眼标定...
标定方法: TSAI (cv2.CALIB_HAND_EYE_TSAI)
标定完成！
保存结果到: calibration_data/hand_eye_result.json
```

#### 3.2 标定结果文件

**hand_eye_result.json**：
```json
{
  "T_end_to_cam": [
    [0.659, -0.746, 0.100, -0.146],
    [0.752, 0.651, -0.100, -0.338],
    [0.010, 0.141, 0.990, 0.526],
    [0.0, 0.0, 0.0, 1.0]
  ],
  "rotation_matrix": [...],
  "translation_vector": [-0.146, -0.338, 0.526],
  "valid_samples": 20,
  "calibration_method": "0"
}
```

**T_end_to_cam** 是手眼变换矩阵：
- 描述相机坐标系相对于机械臂末端坐标系的位姿
- 4x4 齐次变换矩阵
- 这是后续系统集成的关键参数

---

### 阶段 4: 结果验证

#### 4.1 运行误差分析

```bash
cd /home/ilex/Dev/VIST/calibration
python3 calibration_error_analysis.py --config my_calibration.yaml
```

**程序输出**：
```
正在加载标定结果...
正在分析标定误差...

=== 标定质量评估 ===
平均重投影误差: 1.23 像素
最大重投影误差: 2.45 像素
最小重投影误差: 0.67 像素

质量评级: 优秀 ✓
- 优秀 (< 1.0 px): 12 个样本
- 良好 (< 2.0 px): 6 个样本
- 可接受 (< 5.0 px): 2 个样本
- 不合格 (>= 5.0 px): 0 个样本

保存统计数据到: calibration_data/calibration_error_stats.json
```

#### 4.2 质量评估标准

**重投影误差**：
- **优秀**: < 1.0 像素
- **良好**: 1.0 - 2.0 像素
- **可接受**: 2.0 - 5.0 像素
- **不合格**: > 5.0 像素

**如果误差过大**：
1. 检查标定板尺寸是否测量准确
2. 检查相机内参是否正确
3. 重新采集数据（增加位姿多样性）
4. 尝试不同的标定方法

#### 4.3 可视化验证（可选）

```bash
cd /home/ilex/Dev/VIST/calibration
python3 visual_verification.py --config my_calibration.yaml
```

这会显示每个样本的重投影结果：
- 绿色点：检测到的角点
- 红色点：重投影的角点
- 两者越接近，标定质量越好

---

### 阶段 5: 系统集成

#### 5.1 标定完成后的下一步

**标定结果的用途**：
- 手眼变换矩阵 `T_end_to_cam` 用于坐标系转换
- 将相机坐标系中的目标位置转换到机器人坐标系
- 这是视觉伺服的基础

**系统集成步骤**：

1. **集成到 VIST 系统**：
   ```python
   # 在 VIST 系统中加载标定结果
   import json
   import numpy as np

   # 加载手眼变换矩阵
   with open('calibration_data/hand_eye_result.json', 'r') as f:
       calib_result = json.load(f)

   T_end_to_cam = np.array(calib_result['T_end_to_cam'])

   # 使用变换矩阵进行坐标转换
   def camera_to_robot(point_in_camera):
       """将相机坐标系中的点转换到机器人坐标系"""
       # point_in_camera: [x, y, z] 在相机坐标系中
       point_homo = np.append(point_in_camera, 1.0)  # 齐次坐标
       point_in_end = T_end_to_cam @ point_homo
       return point_in_end[:3]
   ```

2. **联调测试**：
   - 在相机画面中检测目标（如 AprilTag）
   - 使用手眼变换矩阵将目标位置转换到机器人坐标系
   - 控制机器人移动到目标位置
   - 验证实际到达位置与预期位置的误差

3. **精度验证**：
   ```python
   # 测试脚本示例
   def test_calibration_accuracy():
       # 1. 在相机中检测目标
       target_pos_camera = detect_target()  # [x, y, z] in camera frame

       # 2. 转换到机器人坐标系
       target_pos_robot = camera_to_robot(target_pos_camera)

       # 3. 控制机器人移动
       robot.move_to(target_pos_robot)

       # 4. 测量实际误差
       actual_pos = robot.get_position()
       error = np.linalg.norm(actual_pos - target_pos_robot)

       print(f"定位误差: {error*1000:.2f} mm")

       # 期望误差 < 5mm
       return error < 0.005
   ```

#### 5.2 集成到 VIST 完整工作流程

标定完成后，就可以运行 VIST 系统的完整工作流程了：

**参考文档**：
- [VIST_COMPLETE_WORKFLOW.md](../docs/VIST_COMPLETE_WORKFLOW.md) - VIST 系统完整工作流程
- 包括人类主导接近、算法主导对齐、自动插入等阶段

**VIST 系统使用标定结果**：
```python
# VIST 系统中的坐标转换
class VISTSystem:
    def __init__(self, calibration_file):
        # 加载手眼标定结果
        with open(calibration_file, 'r') as f:
            calib = json.load(f)
        self.T_end_to_cam = np.array(calib['T_end_to_cam'])

    def detect_and_track_target(self):
        # 1. 在相机中检测目标（USB 插孔）
        target_pos_cam = self.detect_usb_port()

        # 2. 转换到机器人末端坐标系
        target_pos_end = self.transform_camera_to_end(target_pos_cam)

        # 3. 转换到机器人基座坐标系
        T_base_to_end = self.robot.get_forward_kinematics()
        target_pos_base = T_base_to_end @ target_pos_end

        # 4. 生成运动指令
        return target_pos_base

    def transform_camera_to_end(self, point_cam):
        """使用手眼标定结果进行坐标转换"""
        point_homo = np.append(point_cam, 1.0)
        point_end = self.T_end_to_cam @ point_homo
        return point_end[:3]
```

---

## 🔧 常见问题

### Q1: 标定误差很大怎么办？

**可能原因**：
1. 标定板尺寸测量不准确
2. 采集的位姿多样性不足
3. 标定板检测质量差（反光、模糊）
4. 相机内参不准确

**解决方法**：
1. 重新精确测量标定板尺寸
2. 重新采集数据，增加位姿多样性
3. 改善光照条件，避免反光
4. 检查相机内参，必要时手动标定相机

### Q2: 采集数据时检测不到标定板？

**可能原因**：
1. 标定板不在相机视野内
2. 标定板距离太远或太近
3. 光照条件差
4. 标定板反光或模糊

**解决方法**：
1. 调整机器人位姿，确保标定板完全可见
2. 调整距离到 30-50cm
3. 改善光照，避免强光直射
4. 使用哑光标定板，避免反光

### Q3: 系统集成后定位误差大？

**可能原因**：
1. 手眼标定误差大
2. 机器人运动学误差
3. 相机畸变未校正
4. 目标检测误差

**解决方法**：
1. 重新进行手眼标定，提高标定精度
2. 检查机器人运动学参数
3. 进行相机畸变标定
4. 优化目标检测算法

### Q4: 需要多久重新标定一次？

**重新标定的情况**：
- 相机安装位置发生变化
- 相机或机器人更换
- 标定精度明显下降
- 系统长时间未使用（建议每月验证一次）

---

## 📊 标定质量检查清单

在进行系统集成前，请确认：

- [ ] 采集了至少 15 组数据
- [ ] 位姿具有足够多样性（不同距离、角度）
- [ ] 所有样本都成功检测到标定板
- [ ] 平均重投影误差 < 2.0 像素
- [ ] 没有样本的误差 > 5.0 像素
- [ ] 标定结果文件已保存
- [ ] 已进行可视化验证
- [ ] 已进行实际定位测试

---

## 🎯 总结

**手眼标定工作流程**：
```
准备 → 采集 → 计算 → 验证 → 集成
```

**关键要点**：
1. 精确测量标定板尺寸（最重要！）
2. 采集多样化的位姿数据（15-20 组）
3. 验证标定质量（重投影误差 < 2.0 px）
4. 集成到 VIST 系统进行联调测试

**下一步**：
- 完成手眼标定后，参考 [VIST_COMPLETE_WORKFLOW.md](../docs/VIST_COMPLETE_WORKFLOW.md) 进行系统集成
- 进行 VIST 系统的完整功能测试
- 验证 USB 插入任务的实际性能

**最后更新**: 2026-02-10
