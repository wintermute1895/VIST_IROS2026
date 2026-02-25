# MuJoCo 双臂仿真文档

## 概述

本项目实现了基于 MuJoCo 的双臂机器人遥操作仿真系统，支持通过电脑摄像头和 MediaPipe 进行实时双臂姿态检测和控制。

## 系统架构

```
电脑摄像头 → MediaPipe 双臂姿态检测 → VIST 算法 → MuJoCo 双臂仿真
```

### 核心组件

1. **视觉检测** (`DualArmWebcamVisionNode`)
   - 使用 MediaPipe Pose 检测双臂关键点
   - 自动镜像翻转（镜像模式）
   - 实时计算肩、肘、腕位置

2. **运动映射** (`ArmMotionMapper`)
   - 将人体关键点转换为机器人坐标系
   - 支持左右臂独立肩部位置配置
   - One Euro Filter 平滑滤波

3. **逆运动学求解** (`GeometricArmSolver`)
   - 几何解析法求解 7-DOF 臂部配置
   - 支持左右臂镜像对称
   - 基于大臂轴线的正确 q3 (Shoulder Yaw) 计算

4. **MuJoCo 驱动** (`DualArmMuJoCoDriver`)
   - 双臂独立控制
   - 运动学位置控制（无重力）
   - 实时可视化

## 文件结构

```
VIST-feature-exo-hand-integration/
├── scripts/
│   ├── run_mujoco_dual_arm_demo.py    # 双臂仿真主程序
│   ├── run_mujoco_demo.py             # 单臂仿真演示
│   └── run_mujoco_simulation.py       # 基础仿真脚本
├── src/
│   ├── robot/
│   │   └── mujoco_arm_driver.py       # MuJoCo 驱动封装
│   ├── core/
│   │   ├── geometric_arm_solver.py    # 几何解析 IK 求解器
│   │   ├── motion_mapper.py           # 运动映射器
│   │   └── vist_controller.py         # VIST 控制器
│   └── config/
│       └── config_loader.py           # 配置加载器
├── config/
│   ├── system_config.yaml             # 系统配置文件
│   └── urdf/
│       └── lkls73_o2_dual_arm_description.urdf  # 双臂机器人模型
└── docs/
    └── MUJOCO_SIMULATION.md           # 本文档
```

## 安装依赖

```bash
# 安装 MuJoCo 3.4.0+
pip install mujoco>=3.4.0

# 安装 MediaPipe
pip install mediapipe

# 安装其他依赖
pip install numpy scipy opencv-python pinocchio
```

## 运行仿真

### 双臂仿真（推荐）

```bash
# 使用 GLFW 渲染（推荐）
MUJOCO_GL=glfw LD_PRELOAD=/usr/lib/x86_64-linux-gnu/libstdc++.so.6 \
    python3 scripts/run_mujoco_dual_arm_demo.py

# 或使用 EGL 渲染（无头模式）
MUJOCO_GL=egl python3 scripts/run_mujoco_dual_arm_demo.py
```

### 参数说明

```bash
python3 scripts/run_mujoco_dual_arm_demo.py \
    --camera 0              # 摄像头 ID（默认 0）
    --no-viewer             # 禁用 MuJoCo 可视化
    --duration 300.0        # 运行时长（秒，默认 300）
```

## 配置说明

### 双臂肩部位置配置

在 `config/system_config.yaml` 中配置左右臂肩部位置：

```yaml
robot:
  shoulder_positions:
    left: [0.0, 0.17, 1.217]   # 左肩位置 [x, y, z]
    right: [0.0, -0.17, 1.217]  # 右肩位置 [x, y, z]
```

### 视觉缩放因子

```yaml
vision:
  scale: 2.5  # 视觉缩放因子（调整映射范围）
```

### 关节方向配置

```yaml
robot:
  joint_directions: [-1, 1, -1, 1, 1, 1, 1]  # 右臂关节方向
  # 左臂会自动镜像 Joint 1 (Shoulder_Roll)
```

## 操作说明

1. **启动程序**：运行上述命令启动仿真
2. **站在摄像头前**：确保全身可见
3. **举起双臂**：系统会自动检测并控制仿真机器人
4. **映射关系**：
   - 现实左臂（物理右侧）→ 仿真右臂
   - 现实右臂（物理左侧）→ 仿真左臂
5. **退出**：按 `q` 键退出

## 技术细节

### 几何解析 IK 算法

本项目使用三阶段几何解析法求解 7-DOF 逆运动学：

#### 第一阶段：臂部配置（q1-q4）

给定肩、肘、腕三点位置，计算前 4 个关节角度：

- **q1 (Shoulder Pitch)**：肩→肘向量在 XZ 平面的投影角度
- **q2 (Shoulder Roll)**：肩→肘向量偏离 XZ 平面的角度
- **q3 (Shoulder Yaw)**：大臂绕自身轴线的旋转角度
  - 将小臂向量投影到垂直于大臂轴线的平面
  - 测量相对参考方向（X 轴投影）的有符号角度
  - 使用叉积确定旋转方向
- **q4 (Elbow Pitch)**：肩→肘和肘→腕两向量的夹角

#### 第二阶段：腕部姿态（q5-q7）

使用正运动学计算腕基座姿态，与目标末端姿态做相对旋转，分解为欧拉角。

### 左右臂镜像处理

1. **肩部位置**：左右臂使用不同的肩部位置（Y 坐标相反）
2. **关节方向**：左臂的 Shoulder_Roll (J1) 方向取反
3. **q3 镜像**：左臂的 Shoulder_Yaw (q3) 取反

### 工作空间限制

系统会检查目标位置是否超出机器人工作空间：

```python
max_reach = upper_arm_length + forearm_length  # 0.5274m
workspace_limit = max_reach * 0.98  # 0.517m (98% 安全裕度)
```

如果目标超出工作空间，控制器会返回失败，不更新关节角度。

## 常见问题

### Q1: 左臂不动或频繁失败

**原因**：工作空间检查失败，目标位置超出机器人可达范围。

**解决方案**：
1. 检查 `config/system_config.yaml` 中左臂肩部位置是否正确
2. 确认 `ArmMotionMapper` 使用了正确的肩部位置（已修复）
3. 调整 `vision.scale` 参数（减小缩放因子）

### Q2: 左臂小臂方向不对

**原因**：q3 (Shoulder Yaw) 计算方法不正确。

**解决方案**：已使用基于大臂轴线的正确投影法（最新版本已修复）。

### Q3: EGL 初始化失败

**错误信息**：`EGL: Failed to initialize EGL`

**解决方案**：
```bash
# 使用 GLFW 渲染
MUJOCO_GL=glfw LD_PRELOAD=/usr/lib/x86_64-linux-gnu/libstdc++.so.6 \
    python3 scripts/run_mujoco_dual_arm_demo.py
```

### Q4: libstdc++ 版本不兼容

**错误信息**：`GLIBCXX_3.4.29' not found`

**解决方案**：
```bash
# 预加载系统的 libstdc++
LD_PRELOAD=/usr/lib/x86_64-linux-gnu/libstdc++.so.6 python3 scripts/...
```

## 性能优化

1. **降低 MediaPipe 复杂度**：`model_complexity=0`（已设置）
2. **调整控制频率**：修改 `config.control_dt`（默认 0.05s = 20Hz）
3. **禁用可视化**：使用 `--no-viewer` 参数

## 开发者信息

### 关键修复历史

1. **2026-02-25**：修复左臂工作空间检查失败问题
   - 原因：`ArmMotionMapper` 使用全局配置的肩部位置
   - 修复：传入控制器配置的肩部位置

2. **2026-02-25**：重写 q3 (Shoulder Yaw) 计算
   - 原因：固定坐标系无法正确表示大臂自旋
   - 修复：基于大臂轴线的投影法

3. **2026-02-25**：添加左臂镜像支持
   - 自动检测左右臂（基于末端执行器名称）
   - 关节方向和 q3 符号自动镜像

## 参考资料

- [MuJoCo Documentation](https://mujoco.readthedocs.io/)
- [MediaPipe Pose](https://google.github.io/mediapipe/solutions/pose.html)
- [Pinocchio IK Solver](https://stack-of-tasks.github.io/pinocchio/)

## 许可证

本项目遵循原 VIST 项目的许可证。
