#!/bin/bash
# 启动 rqt 并正确 source 工作空间环境

echo "=== 启动 rqt (已 source 工作空间) ==="

# Source 工作空间
source /home/ilex/Dev/VIST/ros2_ws/install/setup.bash

# 启动 rqt
echo "启动 rqt..."
rqt
