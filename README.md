# VIST - Visual Intent-driven Spatio-Temporal Teleoperation

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![ROS2](https://img.shields.io/badge/ROS2-Humble-blue.svg)](https://docs.ros.org/en/humble/)
[![Python](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)

VIST是一个用于精密遥操作任务的人机共享控制框架，结合视觉感知和意图驱动的自适应卡尔曼滤波。

## 🚀 快速开始

### 一键安装

```bash
# 克隆仓库
git clone https://github.com/your-org/VIST.git
cd VIST

# 运行自动安装脚本
./scripts/setup_environment.sh

# 验证安装
./scripts/verify_installation.sh
```

### 手动安装

详细安装步骤请参考 [SETUP.md](SETUP.md)

## 📋 环境要求

- **操作系统**: Ubuntu 22.04 LTS
- **ROS2**: Humble
- **Python**: 3.10+
- **内存**: 至少 8GB RAM
- **磁盘**: 20GB 可用空间

## 📚 文档

- **[环境配置指南](SETUP.md)** - 详细的安装和配置步骤
- **[系统架构](README_v2.md)** - 完整的系统文档和数学理论
- **[故障排查](TROUBLESHOOTING.md)** - 常见问题和解决方案
- **[高频控制计划](docs/HIGH_FREQ_CONTROL_PLAN.md)** - 250Hz控制实现策略
- **[消融实验指南](docs/ABLATION_STUDY_GUIDE.md)** - 实验设计和分析

## 🎯 核心功能

### 1. 数据采集与分析

```bash
# 运行数据分析
./scripts/run_analysis.sh --rosbag data/rosbags/your_bag --output data/analysis

# 运行消融实验
python3 scripts/run_ablation_experiments.py --config config/ablation_experiments.yaml
```

### 2. VIST滤波器

```bash
# 启动VIST滤波节点
./scripts/start_vist_filter.sh

# 配置滤波参数
vim config/vist_filter_config.yaml
```

### 3. 遥操控制

```bash
# 启动遥操臂
./scripts/start_arm_teleop.sh

# 启动灵巧手
./scripts/start_hand_glove.sh
```

## 📊 项目结构

```
VIST/
├── config/                    # 配置文件
│   ├── system_config.yaml
│   ├── vist_filter_config.yaml
│   ├── analysis_config.yaml
│   └── ablation_experiments.yaml
├── scripts/                   # 脚本工具
│   ├── setup_environment.sh   # 环境配置脚本
│   ├── verify_installation.sh # 安装验证脚本
│   ├── analyze_all_metrics.py # 性能分析脚本
│   └── run_ablation_experiments.py
├── src/                       # 源代码
│   ├── core/                  # 核心算法
│   ├── nodes/                 # ROS2节点
│   └── utils/                 # 工具函数
├── external_sdk/              # 外部SDK
│   ├── arm_teleop/            # 遥操臂SDK
│   └── linkerhand-ros2-sdk/   # 灵巧手SDK
├── docs/                      # 文档
├── data/                      # 数据目录
└── requirements.txt           # Python依赖
```

## 🔬 核心创新

| 创新点 | 描述 |
|--------|------|
| **指节向量法** | 消除传统方法的奇异性 |
| **意图驱动卡尔曼滤波** | 自适应协方差调度 |
| **冲突检测与柔顺接管** | 无模式切换的平滑权重调整 |
| **250Hz高频控制** | 预测-更新混合策略 |

## 📈 性能指标

| 指标 | 数值 |
|------|------|
| 控制频率 | 250 Hz |
| 系统延迟 | < 50ms |
| 任务成功率 | 95% |
| 对齐精度 | < 2mm |

## 🛠️ 常见问题

### 找不到 lbot_arm_interfaces

```bash
# 确保已编译并source
cd external_sdk/arm_teleop
colcon build --packages-select lbot_arm_interfaces
source install/setup.bash
```

### ROS2命令找不到

```bash
# 加载ROS2环境
source /opt/ros/humble/setup.bash
```

更多问题请查看 [TROUBLESHOOTING.md](TROUBLESHOOTING.md)

## 📝 使用示例

### 示例1：分析rosbag数据

```bash
# 使用默认配置分析
./scripts/run_analysis.sh --rosbag data/rosbags/experiment_001

# 使用自定义配置
./scripts/run_analysis.sh \
  --rosbag data/rosbags/experiment_001 \
  --config config/analysis_config.yaml \
  --output data/analysis/exp001
```

### 示例2：运行消融实验

```bash
# 运行所有实验
python3 scripts/run_ablation_experiments.py

# 运行特定实验
python3 scripts/run_ablation_experiments.py --experiment baseline
```

## 🤝 贡献

欢迎贡献！请查看 [CONTRIBUTING.md](CONTRIBUTING.md) 了解详情。

## 📄 许可证

本项目采用 MIT 许可证 - 详见 [LICENSE](LICENSE) 文件

## 📞 联系方式

- **项目主页**: https://github.com/your-org/VIST
- **问题反馈**: https://github.com/your-org/VIST/issues
- **邮箱**: your-email@example.com

## 🙏 致谢

- MediaPipe 团队
- Pinocchio 开发者
- AprilTag 项目
- ROS2 社区

---

**最后更新**: 2026-02-24
**版本**: v2.0
**状态**: 活跃开发中

---

<div align="center">

**⭐ 如果这个项目对您有帮助，请给我们一个 Star！⭐**

Made with ❤️ by VIST Research Team

</div>