# VIST: Vision-based Intent-aware State Teleoperation

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python](https://img.shields.io/badge/Python-3.10-blue.svg)](https://www.python.org/)
[![Status](https://img.shields.io/badge/Status-Research-red.svg)]()

**VIST** 是一个针对 **IROS 2026** 研发的高精度机器人视觉遥操作框架。

本项目旨在解决低成本视觉传感器（如 WebCam/RealSense）在遥操作中存在的**高噪声**与**丢失高频细节**的问题。通过引入 **意图感知（Intent-aware）** 机制，系统能够实时评估操作者的运动意图（快速接近 vs 精细调节），并自适应地调整状态估计器的卡尔曼增益，从而实现了在保持低延迟的同时，彻底消除生理性抖动。

## ✨ 核心特性 (Key Features)

* **🧠 意图自适应状态估计 (Intent-Adaptive Estimation)**
    * 基于操作速度与上下文的意图推断算法。
    * 动态调节卡尔曼滤波观测噪声协方差矩阵 ($R$)，实现“动静自如”的控制手感。
* **🦾 平滑逆运动学求解 (Smooth IK)**
    * 集成 `Pink` 求解器与二次规划 (QP)，在满足关节限位的同时生成连续的关节速度。
    * 基于 `Pinocchio` 的高效率动力学计算。
* **🔌 模块化工程架构**
    * **解耦设计**：视觉采集、状态估计、运动控制、可视化显示完全分离。
    * **网络透传**：基于 UDP 通信，支持远程部署（如边缘端采集，云端计算）。

## 🛠️ 安装指南 (Installation)

本项目推荐使用 **Conda** 进行环境管理，以确保 Pinocchio 等数学库的兼容性。

### 1. 克隆仓库
```bash
git clone [https://github.com/wintermute1895/VIST.git](https://github.com/wintermute1895/VIST.git)
cd VIST

```

### 2. 配置环境

我们提供了一键安装脚本。请确保系统已安装 Anaconda 或 Miniconda。

```bash
# 创建并安装依赖
mamba env create -f environment.yaml

# 激活环境
mamba activate vist_env

```

### 3. 初始化配置

项目不直接上传具体的硬件配置文件。你需要根据模板生成自己的配置：

```bash
# 复制配置模板
cp config/settings_template.yaml config/settings.yaml

# (可选) 如果需要修改 IP 或端口，请编辑 config/settings.yaml

```

## 🚀 快速开始 (Quick Start)

请按照以下顺序启动三个终端窗口：

### 终端 1：启动可视化服务器 (Visualization)

启动 MeshCat 服务器，用于实时查看机器人姿态与意图识别结果。

```bash
python -m src.robot.viz_server

```

*启动后，请在浏览器访问终端提示的 URL (通常是 `http://127.0.0.1:7000`)。*

### 终端 2：启动视觉采集 (Vision Source)

连接你的 RealSense 或使用电脑自带摄像头，捕捉人体动作。

```bash
python scripts/run_vision.py

```

### 终端 3：启动核心控制器 (VIST Controller)

运行核心算法，接收视觉数据，进行意图滤波并解算 IK。

```bash
python scripts/run_arm.py

```

## 📂 项目结构 (Structure)

```text
VIST/
├── config/                 # 机器人 URDF、SRDF 及参数配置文件
├── docs/                   # 文档与演示资源
├── scripts/                # 启动脚本 (用户入口)
│   ├── run_vision.py       # 视觉捕捉节点
│   └── run_arm.py          # 机械臂控制节点 (包含 IK)
├── src/                    # 源代码核心
│   ├── core/               # 核心算法 (Estimator, Solver)
│   │   └── estimator.py    # [核心] 自适应卡尔曼滤波器实现
│   ├── robot/              # 机器人驱动与可视化接口
│   └── utils/              # 通用工具 (Math, Filter, Socket)
├── environment.yaml        # Conda 环境依赖表
└── README.md               # 项目说明书

```

## 📝 理论背景 (Theoretical Background)

系统的核心状态方程如下：

其中，观测噪声  是意图因子  的函数：
$$ R(\alpha) = \alpha \cdot R_{base} $$
当检测到**精细操作意图**时，，滤波器倾向于信任内部预测模型，从而抑制视觉抖动。

## 🤝 贡献与协作 (Collaboration)

1. **提交代码**：请切出新的 `feature/xxx` 分支进行开发，禁止直接推送到 `main`。
2. **Pull Request**：合并代码前请确保通过本地测试，并邀请 Owner 进行 Code Review。

## 📄 引用 (Citation)


## 📄 License

本项目采用 [MIT License](https://www.google.com/search?q=LICENSE) 开源。
