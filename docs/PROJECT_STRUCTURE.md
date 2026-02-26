# VIST项目文件架构

**Vision-based Intent-aware State estimation (VIST)**

最后更新: 2026-02-26

---

## 📁 项目根目录结构

```
VIST/
├── calibration/              # 标定数据和脚本
├── config/                   # 系统配置文件
├── data/                     # 实验数据和分析结果
├── docs/                     # 项目文档
├── external_sdk/             # 外部SDK和驱动
├── patches/                  # 补丁文件
├── ros2_ws/                  # ROS2工作空间
├── scripts/                  # 启动和工具脚本
├── src/                      # 源代码（ROS2包）
├── tests/                    # 测试代码
└── web/                      # Web界面（可选）
```

---

## 📂 详细目录说明

### 1. `/calibration` - 标定数据

```
calibration/
├── calibration_data/
│   ├── aruco_detection_analysis/  # ArUco标记检测分析
│   ├── camera_intrinsics/         # 相机内参标定
│   └── images/                    # 标定图像
└── [标定脚本]
```

**用途**: 存储相机标定、手眼标定等数据

---

### 2. `/config` - 配置文件

```
config/
├── meshes/                   # 3D模型文件
│   ├── arm/                  # 机械臂模型
│   └── hand/                 # 灵巧手模型
├── urdf/                     # URDF机器人描述文件
├── vist_filter_config.yaml   # VIST滤波器配置 ⭐
└── [其他配置文件]
```

**关键文件**:
- `vist_filter_config.yaml` - 滤波器类型和参数配置

---

### 3. `/data` - 数据目录

```
data/
├── experiments/              # 实验数据 ⭐
│   └── peg_in_hole_YYYYMMDD_HHMMSS/
│       ├── metadata.yaml     # 实验元数据
│       └── rosbag2_*.db3     # ROS2 bag数据
├── ablation_experiments/     # 消融实验数据
├── analysis/                 # 分析结果
├── analysis_plots/           # 分析图表
├── archive/                  # 归档数据
├── collection/               # 数据采集
└── training/                 # 训练数据
```

**用途**:
- 存储所有实验录制的rosbag数据
- 分析结果和可视化图表
- 训练数据集

---

### 4. `/docs` - 文档目录 ⭐

```
docs/
├── BEGINNER_TUTORIAL.md          # 👶 新手教程
├── ENVIRONMENT_SETUP.md          # 🚀 环境配置
├── FINAL_STARTUP_GUIDE.md        # ⭐ 启动指南
├── MONITORING_AND_RECORDING.md   # 监控与采集
├── MODULE_TEST_GUIDE.md          # 模块测试
├── NODE_REFERENCE.md             # 节点参考
├── WORKFLOW_ANALYSIS.md          # 工作流程分析
├── README.md                     # 文档索引
├── ARCHITECTURE.md               # 系统架构
├── DATA_FORMAT.md                # 数据格式
└── archive/                      # 归档文档
```

**重要文档**:
- `BEGINNER_TUTORIAL.md` - 新手必读
- `FINAL_STARTUP_GUIDE.md` - 系统启动
- `WORKFLOW_ANALYSIS.md` - 工作流程

---

### 5. `/external_sdk` - 外部SDK

```
external_sdk/
├── arm_teleop/               # 外骨骼和机械臂驱动 ⭐
│   └── src/
│       ├── linkerta/         # Linkerta外骨骼
│       │   ├── config/
│       │   │   └── lta.yaml  # 外骨骼配置
│       │   └── src/
│       │       └── main_ros2.cpp
│       ├── lbot_driver/      # LBot机械臂驱动
│       ├── lbot_teleop/      # 遥操作桥接
│       │   └── config/
│       │       └── teleop_bridge_params.yaml  # 桥接配置 ⭐
│       └── lbot_demo/
│
├── linkerhand-ros2-sdk/      # 灵巧手ROS2 SDK ⭐
│   └── linker_hand_ros2_sdk/
│       └── LinkerHand/
│           └── config/
│               └── setting.yaml  # 灵巧手配置
│
├── linkerhand-ros-teleop/    # 数据手套SDK
│   └── linkertelopsdk/
│
├── linkerhand-python-sdk/    # 灵巧手Python SDK
├── linkerarm/                # 机械臂SDK
└── dex_retargeting/          # 灵巧操作重定向
```

**关键配置**:
- `arm_teleop/src/linkerta/config/lta.yaml` - 外骨骼CAN配置
- `arm_teleop/src/lbot_teleop/config/teleop_bridge_params.yaml` - 关节映射
- `linkerhand-ros2-sdk/.../config/setting.yaml` - 灵巧手配置

---

### 6. `/scripts` - 脚本目录 ⭐

```
scripts/
├── startup/                  # 启动脚本
│   └── start_vist_filter.sh  # VIST滤波器启动
│
├── experiment/               # 实验脚本
│   └── collect_experiment.sh # 数据采集 ⭐
│
├── analysis/                 # 分析脚本
│   ├── analyzers/            # 分析器模块
│   ├── cli/                  # 命令行接口
│   ├── core/                 # 核心功能
│   ├── analyze_all_metrics.py
│   └── analyze_timestamp_sync.py
│
├── calibration/              # 标定脚本
├── tools/                    # 工具脚本
├── archive/                  # 归档脚本
│
├── start_camera.sh           # 相机启动 ⭐
├── start_left_arm_teleop.sh  # 外骨骼启动 ⭐
├── start_6_dexterous_hand.sh # 灵巧手启动 ⭐
├── start_filter.sh           # 滤波器启动
├── start_teleop_bridge.sh    # 遥操桥接启动 ⭐
├── start_robot_driver.sh     # 机械臂驱动启动
├── start_hand_keyboard.sh    # 键盘控制启动
├── record_experiment.sh      # 数据录制
├── package_project.sh        # 项目打包
└── hand_control.py           # 手部控制脚本
```

**核心启动脚本**（按启动顺序）:
1. `start_camera.sh`
2. `startup/start_vist_filter.sh`
3. `start_6_dexterous_hand.sh`
4. `start_left_arm_teleop.sh`
5. `start_robot_driver.sh`
6. `start_teleop_bridge.sh`
7. `start_hand_keyboard.sh`
8. `experiment/collect_experiment.sh`

---

### 7. `/src` - 源代码目录 ⭐

```
src/
├── camera_manager/           # 相机管理包 ⭐
│   ├── camera_manager/
│   │   └── realsense_camera_node.py  # 相机节点
│   ├── config/
│   └── launch/
│
├── nodes/                    # ROS2节点
│   ├── vist_filter_node.py   # VIST滤波器节点 ⭐
│   └── unified_filter_node.py
│
├── control/                  # 控制模块
│   └── filters/              # 滤波器实现
│
├── perception/               # 感知模块
├── robot/                    # 机器人模块
│   ├── arm/                  # 机械臂
│   └── hand/                 # 灵巧手
│
├── performance_monitor/      # 性能监控包
│   └── performance_monitor/
│
├── communication/            # 通信模块
├── core/                     # 核心功能
├── interfaces/               # 接口定义
├── monitoring/               # 监控模块
├── config/                   # 配置模块
└── utils/                    # 工具函数
```

**关键节点**:
- `camera_manager/camera_manager/realsense_camera_node.py` - 相机节点
- `nodes/vist_filter_node.py` - VIST滤波器节点

---

### 8. `/tests` - 测试目录

```
tests/
├── engineering_pitfalls/     # 工程陷阱测试
└── sensitivity_analysis/     # 灵敏度分析
```

---

### 9. `/web` - Web界面（可选）

```
web/
├── backend/                  # 后端服务
└── frontend/                 # 前端界面
    └── src/
```

**用途**: 可选的Web监控界面

---

## 🔑 关键文件索引

### 配置文件

| 文件 | 用途 | 位置 |
|------|------|------|
| `lta.yaml` | 外骨骼配置 | `external_sdk/arm_teleop/src/linkerta/config/` |
| `teleop_bridge_params.yaml` | 遥操桥接配置 | `external_sdk/arm_teleop/src/lbot_teleop/config/` |
| `setting.yaml` | 灵巧手配置 | `external_sdk/linkerhand-ros2-sdk/.../config/` |
| `vist_filter_config.yaml` | 滤波器配置 | `config/` |

### 启动脚本

| 脚本 | 功能 | 位置 |
|------|------|------|
| `start_camera.sh` | 启动相机 | `scripts/` |
| `start_vist_filter.sh` | 启动滤波器 | `scripts/startup/` |
| `start_6_dexterous_hand.sh` | 启动灵巧手 | `scripts/` |
| `start_left_arm_teleop.sh` | 启动外骨骼 | `scripts/` |
| `start_teleop_bridge.sh` | 启动遥操桥接 | `scripts/` |
| `collect_experiment.sh` | 数据采集 | `scripts/experiment/` |

### 源代码

| 文件 | 功能 | 位置 |
|------|------|------|
| `realsense_camera_node.py` | 相机节点 | `src/camera_manager/camera_manager/` |
| `vist_filter_node.py` | 滤波器节点 | `src/nodes/` |
| `main_ros2.cpp` | 外骨骼节点 | `external_sdk/arm_teleop/src/linkerta/src/` |
| `hand_control.py` | 手部控制 | `scripts/` |

### 文档

| 文档 | 用途 | 位置 |
|------|------|------|
| `BEGINNER_TUTORIAL.md` | 新手教程 | `docs/` |
| `FINAL_STARTUP_GUIDE.md` | 启动指南 | `docs/` |
| `WORKFLOW_ANALYSIS.md` | 工作流程 | `docs/` |
| `NODE_REFERENCE.md` | 节点参考 | `docs/` |

---

## 📊 数据流与文件关系

```
配置文件 → 启动脚本 → ROS2节点 → Topic通信 → 数据采集

config/vist_filter_config.yaml
    ↓
scripts/startup/start_vist_filter.sh
    ↓
src/nodes/vist_filter_node.py
    ↓
/filtered_left_joint_control (Topic)
    ↓
scripts/experiment/collect_experiment.sh
    ↓
data/experiments/peg_in_hole_*/
```

---

## 🔧 工作空间结构

### 主工作空间 (`~/Dev/VIST`)

```
~/Dev/VIST/
├── src/                      # 源代码
├── build/                    # 编译输出（gitignore）
├── install/                  # 安装目录（gitignore）
└── log/                      # 日志（gitignore）
```

### 外骨骼工作空间 (`external_sdk/arm_teleop`)

```
external_sdk/arm_teleop/
├── src/                      # 源代码
├── build/                    # 编译输出
├── install/                  # 安装目录
└── log/                      # 日志
```

### 灵巧手工作空间 (`external_sdk/linkerhand-ros2-sdk`)

```
external_sdk/linkerhand-ros2-sdk/
├── linker_hand_ros2_sdk/     # 源代码
├── build/                    # 编译输出
├── install/                  # 安装目录
└── log/                      # 日志
```

---

## 📦 ROS2包列表

### 主工作空间包

1. **camera_manager** - 相机管理
2. **performance_monitor** - 性能监控
3. **[其他自定义包]**

### 外骨骼工作空间包

1. **linkerta** - 外骨骼驱动
2. **lbot_driver** - 机械臂驱动
3. **lbot_teleop** - 遥操作桥接
4. **lbot_demo** - 演示程序
5. **lbot_arm_interfaces** - 接口定义

### 灵巧手工作空间包

1. **linker_hand_ros2_sdk** - 灵巧手SDK

---

## 🗂️ 数据组织

### 实验数据结构

```
data/experiments/
└── peg_in_hole_20260226_203434/
    ├── metadata.yaml         # 实验元数据
    ├── rosbag2_*.db3        # 数据库文件
    └── metadata.yaml        # rosbag元数据
```

### 分析结果结构

```
data/analysis/
└── peg_in_hole_20260226_203434/
    ├── metrics.json          # 性能指标
    ├── plots/                # 可视化图表
    └── report.md             # 分析报告
```

---

## 🚀 快速导航

### 我想...

**配置系统**:
- 外骨骼CAN接口 → `external_sdk/arm_teleop/src/linkerta/config/lta.yaml`
- 关节方向映射 → `external_sdk/arm_teleop/src/lbot_teleop/config/teleop_bridge_params.yaml`
- 滤波器类型 → `config/vist_filter_config.yaml`

**启动系统**:
- 查看启动顺序 → `docs/WORKFLOW_ANALYSIS.md`
- 新手教程 → `docs/BEGINNER_TUTORIAL.md`
- 启动脚本 → `scripts/start_*.sh`

**查看源码**:
- 相机节点 → `src/camera_manager/camera_manager/realsense_camera_node.py`
- 滤波器节点 → `src/nodes/vist_filter_node.py`
- 外骨骼节点 → `external_sdk/arm_teleop/src/linkerta/src/main_ros2.cpp`

**分析数据**:
- 实验数据 → `data/experiments/`
- 分析脚本 → `scripts/analysis/`
- 分析结果 → `data/analysis/`

---

## 📝 文件命名规范

### 脚本命名

- `start_*.sh` - 启动脚本
- `stop_*.sh` - 停止脚本
- `test_*.sh` - 测试脚本
- `analyze_*.py` - 分析脚本

### 数据命名

- `实验类型_YYYYMMDD_HHMMSS/` - 实验数据目录
- `metadata.yaml` - 元数据文件
- `rosbag2_*.db3` - ROS2 bag数据库

### 配置命名

- `*_config.yaml` - 配置文件
- `*_params.yaml` - 参数文件
- `*.launch.py` - Launch文件

---

## 🔍 查找文件技巧

### 查找配置文件

```bash
find ~/Dev/VIST -name "*.yaml" -o -name "*.yml"
```

### 查找启动脚本

```bash
find ~/Dev/VIST/scripts -name "start_*.sh"
```

### 查找Python节点

```bash
find ~/Dev/VIST/src -name "*_node.py"
```

### 查找C++节点

```bash
find ~/Dev/VIST/external_sdk -name "main*.cpp"
```

---

## 📚 相关文档

- [WORKFLOW_ANALYSIS.md](WORKFLOW_ANALYSIS.md) - 工作流程分析
- [NODE_REFERENCE.md](NODE_REFERENCE.md) - 节点参考手册
- [FINAL_STARTUP_GUIDE.md](FINAL_STARTUP_GUIDE.md) - 启动指南

---

最后更新: 2026-02-26