#!/bin/bash
# 运行完整性能指标分析的包装脚本
# 自动加载必要的ROS2环境

# 加载ROS2环境
source /opt/ros/humble/setup.bash

# 加载lbot_arm_interfaces
if [ -f "external_sdk/arm_teleop/install/setup.bash" ]; then
    source external_sdk/arm_teleop/install/setup.bash
fi

# 运行分析脚本
python3 scripts/analyze_all_metrics.py "$@"