# VIST 感知模块开发 FAQ

## ❓ 常见问题解答

### Q1: 用不用单独开一个分支做手眼标定？

**答案：不需要**

**理由**：
- 手眼标定是**一次性的配置工作**，不是功能开发
- 标定结果保存在配置文件中（`config/camera_calibration.yaml`）
- 可以在当前分支（`feature/vision-perception`）完成
- 标定完成后，配置文件会随代码一起合并到 main

**建议流程**：
```bash
# 在当前分支完成标定
git checkout feature/vision-perception

# 运行标定程序
python scripts/calibrate_cameras.py

# 标定结果自动保存到配置文件
# config/camera_calibration.yaml

# 提交配置文件
git add config/camera_calibration.yaml
git commit -m "chore: 添加相机标定结果"
```

---

### Q2: 我可以通过几何解析法确定 USB 位置吗？

**答案：可以，但有条件**

**方案对比**：

| 方案 | 优点 | 缺点 | 适用场景 |
|------|------|------|---------|
| **几何解析法** | 简单、快速 | 需要固定位置、精度依赖测量 | USB 插口位置固定 |
| **AprilTag 标记** | 精度高、实时 | 需要贴标记 | 快速原型、测试 |
| **YOLO 检测** | 通用、鲁棒 | 需要训练模型 | 生产环境 |

**几何解析法实现**：

```python
# 方案 1: 手动测量 USB 插口位置
# 1. 使用卷尺测量 USB 插口相对于机器人基座的位置
# 2. 记录坐标（x, y, z）
# 3. 保存到配置文件

# config/system_config.yaml
target_detection:
  detector_type: 'manual'
  target_position: [0.35, 0.0, 0.45]  # 手动测量的坐标

# 方案 2: 使用机器人示教
# 1. 手动移动机器人末端到 USB 插口位置
# 2. 记录当前末端位置
# 3. 保存为目标位置

def teach_target_position(robot):
    """示教目标位置"""
    input("将机器人末端移动到 USB 插口位置，按回车继续...")
    current_pos = robot.get_end_effector_position()
    print(f"目标位置: {current_pos}")
    return current_pos
```

**精度评估**：
- 手动测量：±10-20mm（取决于测量工具）
- 机器人示教：±5-10mm（取决于机器人重复精度）
- AprilTag：±2-5mm（取决于相机分辨率）
- YOLO：±3-7mm（取决于模型质量）

**结论**：
- **初期测试**：使用几何解析法（手动测量或示教）
- **正式使用**：使用 AprilTag 或 YOLO

---

### Q3: 精度能达到多少？是否需要融合图像分割和目标检测？

**精度分析**：

```
总体精度 = 手眼标定精度 + 目标检测精度 + 机器人重复精度

示例计算：
- 手眼标定：±2mm
- AprilTag 检测：±3mm
- 机器人重复精度：±1mm
- 总体精度：±√(2² + 3² + 1²) ≈ ±3.7mm
```

**USB 插入精度要求**：
- USB Type-A 插口宽度：约 12mm
- 所需精度：±5mm（足够插入）
- **结论**：AprilTag 方案精度足够 ✅

**是否需要图像分割和目标检测？**

**阶段 1（当前）：不需要**
- 使用 AprilTag 标记即可
- 精度足够、实现简单
- 适合快速原型和数据采集

**阶段 2（未来）：可选**
- 训练 YOLO 模型检测 USB 插口
- 使用图像分割精确定位插口边缘
- 提高鲁棒性（不需要标记）

**推荐方案**：
```python
# 阶段 1: AprilTag（2天内完成）
detector = create_target_detector('apriltag', marker_id=0)

# 阶段 2: YOLO（2-3周后）
detector = create_target_detector('yolo', model_path='usb_detector.pt')

# 阶段 3: 融合（可选）
# 使用 AprilTag 提供粗略位置
# 使用 YOLO 精确定位
# 使用图像分割提取插口轮廓
```

---

### Q4: 感知模块有哪些必要的代码？

**核心代码**（已完成）：

```
src/perception/
├── __init__.py                    # 模块初始化 ✅
└── target_detector.py             # 目标检测器 ✅
    ├── ITargetDetector            # 抽象接口 ✅
    ├── ManualTargetDetector       # 手动指定 ✅
    ├── AprilTagDetector           # AprilTag 检测 🔨（需要完善）
    └── YOLOTargetDetector         # YOLO 检测 ⏳（未来）
```

**辅助代码**（需要添加）：

```
src/perception/
├── camera_manager.py              # 相机管理 🔨
│   ├── RealSenseCamera            # RealSense 相机封装
│   └── CameraCalibration          # 标定数据加载
│
├── coordinate_transform.py        # 坐标转换 🔨
│   ├── transform_camera_to_base   # 相机 → 基座
│   └── transform_camera_to_ee     # 相机 → 末端
│
└── hand_eye_calibration.py        # 手眼标定工具 🔨
    ├── calibrate_eye_to_base      # 全局相机标定
    └── calibrate_eye_in_hand      # 手腕相机标定
```

**配置文件**（需要添加）：

```
config/
└── camera_calibration.yaml        # 相机标定结果 🔨
    ├── global_camera              # 全局相机
    │   ├── intrinsics             # 内参
    │   └── extrinsics             # 外参（T_base_camera）
    └── wrist_camera               # 手腕相机
        ├── intrinsics             # 内参
        └── extrinsics             # 外参（T_ee_camera）
```

---

### Q5: 现在合并进来的代码哪些可以删掉？

**可以删除的文件**：

```bash
# 1. 备份文件
src/nodes/vision_node_depth.py.backup  # 删除 ✅

# 2. 旧的接口文件（如果不再使用）
# 注意：vision_node_depth.py 还在使用（MediaPipe 人体姿态检测）
# 暂时保留，等新的 MediaPipe 接口实现后再删除

# 3. 临时测试文件
test_*.py  # 项目根目录下的临时测试文件（可选）
```

**清理命令**：

```bash
# 删除备份文件
rm src/nodes/vision_node_depth.py.backup

# 删除临时测试文件（可选）
rm test_biomimetic_visualization.py
rm test_frequency_mismatch_simulation.py
rm test_geometric_arm_control.py
rm test_geometric_realtime.py
rm test_hierarchical_control.py
rm test_joint_mapping.py
rm test_motor_health.py
rm test_simulation_offset.py

# 提交清理
git add -A
git commit -m "chore: 清理无用文件"
```

**需要保留的文件**：

```bash
# 人体姿态检测（还在使用）
src/nodes/vision_node_depth.py  # 保留 ✅
src/nodes/mediapipe_compat.py   # 保留 ✅

# 核心模块（已完成）
src/core/motion_mapper.py       # 保留 ✅
src/core/vist_kalman_filter.py  # 保留 ✅
src/core/ik_solver.py            # 保留 ✅

# 新的感知模块（本次开发）
src/perception/                  # 保留 ✅
src/interfaces/                  # 保留 ✅
```

---

## 🚀 推荐实施方案

### 方案 A: 快速原型（2天）

**目标**：快速验证 VIST 流程

**步骤**：
1. **Day 1 上午**：使用几何解析法（手动测量 USB 位置）
2. **Day 1 下午**：集成测试（人体姿态 + 手动目标 + VIST）
3. **Day 2 上午**：USB 插入实验
4. **Day 2 下午**：记录数据、调整参数

**优点**：
- 快速验证算法
- 不需要标定
- 适合论文实验

**缺点**：
- 精度较低（±10mm）
- 不适合生产环境

---

### 方案 B: 标准流程（3-4天）

**目标**：完整的感知模块

**步骤**：
1. **Day 1**：手眼标定（全局相机 + 手腕相机）
2. **Day 2**：实现 AprilTag 检测器
3. **Day 3**：集成测试 + USB 插入实验
4. **Day 4**：优化和文档

**优点**：
- 精度高（±3-5mm）
- 可重复使用
- 适合生产环境

**缺点**：
- 需要更多时间
- 需要标定设备

---

### 方案 C: 混合方案（推荐）

**目标**：快速验证 + 高精度

**步骤**：
1. **Day 1 上午**：几何解析法快速验证
2. **Day 1 下午**：手眼标定（只标定一个相机）
3. **Day 2 上午**：实现 AprilTag 检测器
4. **Day 2 下午**：集成测试 + USB 插入实验

**优点**：
- 快速验证算法（Day 1 上午）
- 高精度实验（Day 2）
- 时间可控

---

## 📝 总结

| 问题 | 答案 |
|------|------|
| 手眼标定次数 | 2次（全局相机 + 手腕相机） |
| 是否需要单独分支 | 不需要，在当前分支完成 |
| 内参标定 | RealSense 有出厂内参，可直接使用 |
| 外参标定 | 需要，使用 easy_handeye 或手动标定 |
| AprilTag vs ArUco | 都可以，AprilTag 精度更高 |
| 几何解析法 | 可以，适合快速原型（±10mm） |
| 精度 | AprilTag: ±3-5mm，足够 USB 插入 |
| 图像分割/目标检测 | 初期不需要，后期可选 |
| 必要代码 | 目标检测器（已完成）+ 相机管理（需添加） |
| 可删除代码 | 备份文件、临时测试文件 |

---

**推荐方案**：混合方案（2天完成基础功能）

**最后更新**: 2026-02-09
