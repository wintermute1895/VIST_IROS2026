# VIST系统文档索引

## 🎓 新手必读

### 0. [BEGINNER_TUTORIAL.md](BEGINNER_TUTORIAL.md) 👶
**新手启动教程** - 手把手教你从零开始启动系统

包含:
- 每一步的详细解释
- 预期看到什么
- 如何验证是否成功
- 常见问题解答
- 完整的检查清单

### 1. [ENVIRONMENT_SETUP.md](ENVIRONMENT_SETUP.md) 🚀
**环境配置指南** - 在Ubuntu 22.04上从零开始配置VIST系统

包含:
- ROS2 Humble安装
- 依赖安装
- 工作空间构建
- 硬件配置
- 权限设置
- 验证步骤

---

## 主要文档

### 2. [FINAL_STARTUP_GUIDE.md](FINAL_STARTUP_GUIDE.md) ⭐
**完整的系统启动指南** - 按顺序启动所有节点的详细步骤

包含:
- 9个终端的启动命令
- 硬件准备
- 系统验证
- 常见问题解决

### 3. [MONITORING_AND_RECORDING.md](MONITORING_AND_RECORDING.md)
**监控与数据采集指南** - 系统监控和rosbag数据采集

包含:
- 频率监控
- Topic验证
- 数据采集脚本
- 数据回放

### 4. [MODULE_TEST_GUIDE.md](MODULE_TEST_GUIDE.md)
**模块测试记录** - 各个模块的测试结果和配置

### 5. [NODE_REFERENCE.md](NODE_REFERENCE.md)
**节点参考手册** - 所有ROS2节点的详细信息

包含:
- 节点源码位置
- 输入输出Topic
- 参数配置
- 调试技巧

---

## 其他文档

### 技术文档
- [ARCHITECTURE.md](ARCHITECTURE.md) - 系统架构
- [DATA_FORMAT.md](DATA_FORMAT.md) - 数据格式说明
- [lbot_api_move_joint_and_joint_follow.md](lbot_api_move_joint_and_joint_follow.md) - 机械臂API

### 相机相关
- [CAMERA_SETUP.md](CAMERA_SETUP.md) - 相机设置
- [CAMERA_ASSIGNMENT.md](CAMERA_ASSIGNMENT.md) - 相机分配

### 归档文档
过时的文档已移至 `archive/` 目录

---

## 快速开始

**如果你是新手**:
1. 阅读 [BEGINNER_TUTORIAL.md](BEGINNER_TUTORIAL.md) 👶 - 手把手教程
2. 按照教程一步一步操作
3. 完成第一次启动和数据采集

**如果你已经熟悉系统**:
1. 阅读 [FINAL_STARTUP_GUIDE.md](FINAL_STARTUP_GUIDE.md) ⭐ - 快速启动
2. 按照指南启动9个终端
3. 验证系统功能
4. 开始数据采集

---

最后更新: 2026-02-26