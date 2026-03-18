# 双臂遥操作系统使用指南

## 📋 系统架构

```
┌──────────────────┐         ┌──────────────────┐
│ 左臂外骨骼驱动    │         │ 右臂外骨骼驱动    │
│ /left_arm_joint  │         │ /right_arm_joint │
│ _control         │         │ _control         │
└────────┬─────────┘         └────────┬─────────┘
         │                            │
         ▼                            ▼
┌──────────────────┐         ┌──────────────────┐
│ 左臂滤波节点      │         │ 右臂滤波节点      │
│ (VIST/OneEuro)   │         │ (VIST/OneEuro)   │
└────────┬─────────┘         └────────┬─────────┘
         │                            │
         ▼                            ▼
┌──────────────────┐         ┌──────────────────┐
│ /filtered_left   │         │ /filtered_right  │
│ _joint_control   │         │ _joint_control   │
└────────┬─────────┘         └────────┬─────────┘
         │                            │
         └────────┬───────────────────┘
                  │
                  ▼
         ┌────────────────┐
         │ 双臂可视化节点  │
         │ (Meshcat)      │
         └────────────────┘
```

## 🚀 快速开始

### 方法1：使用测试脚本（推荐）

```bash
# 进入项目目录
cd /home/ilex/Dev/VIST

# 运行测试脚本
./test_dual_arm.sh

# 选择选项7：完整测试（滤波+可视化）
```

### 方法2：手动启动

#### 终端1：启动左臂滤波节点
```bash
cd /home/ilex/Dev/VIST
conda activate robot_env
python3 ros2_ws/src/nodes/vist_filter_node.py --ros-args \
    --params-file config/baseline_filters_config.yaml \
    -p arm_side:=left
```

#### 终端2：启动右臂滤波节点
```bash
cd /home/ilex/Dev/VIST
conda activate robot_env
python3 ros2_ws/src/nodes/vist_filter_node.py --ros-args \
    --params-file config/baseline_filters_config.yaml \
    -p arm_side:=right
```

#### 终端3：启动双臂可视化
```bash
cd /home/ilex/Dev/VIST
conda activate robot_env
python3 visualize_dual_arm_realtime.py
```

#### 终端4：查看话题（可选）
```bash
# 查看所有话题
ros2 topic list

# 监听左臂滤波输出
ros2 topic echo /filtered_left_joint_control

# 监听右臂滤波输出
ros2 topic echo /filtered_right_joint_control
```

### 方法3：使用Launch文件

```bash
cd /home/ilex/Dev/VIST
conda activate robot_env
ros2 launch ros2_ws/launch/dual_arm_teleop.launch.py
```

## 📊 话题说明

### 输入话题（外骨骼驱动发布）
- `/left_arm_joint_control` - 左臂外骨骼关节角度
- `/right_arm_joint_control` - 右臂外骨骼关节角度

### 输出话题（滤波节点发布）
- `/filtered_left_joint_control` - 左臂滤波后的关节角度
- `/filtered_right_joint_control` - 右臂滤波后的关节角度

### 监控话题
- `/vist_intent_factors` - VIST意图因子
- `/vist_diagnostics` - VIST诊断数据
- `/vist_performance` - 性能指标

## 🔧 配置参数

编辑 `config/baseline_filters_config.yaml`:

```yaml
/vist_filter_node:
  ros__parameters:
    # 话题配置
    exo_left_topic: '/left_arm_joint_control'
    exo_right_topic: '/right_arm_joint_control'
    filtered_left_topic: '/filtered_left_joint_control'
    filtered_right_topic: '/filtered_right_joint_control'

    # 控制参数
    output_freq_hz: 80.0
    arm_side: 'left'  # 启动时通过参数覆盖

    # 滤波器类型
    filter_type: 'oneeuro'  # 可选: gello, oneeuro, vist, fsm, apf
```

## 🎥 录制演示视频

### 准备工作
1. 启动双臂系统（使用上述任一方法）
2. 打开浏览器访问 Meshcat: http://127.0.0.1:7000/static/
3. 准备录屏软件（OBS Studio / SimpleScreenRecorder）

### 演示场景

#### 场景1：双臂独立运动
- 左臂画圆，右臂画方
- 展示独立控制能力

#### 场景2：双臂协同抓取
- 双臂同时接近目标
- 展示VIST滤波效果

#### 场景3：精密插入任务
- 左臂固定，右臂插入USB
- 展示意图检测和虚拟夹具

### 录制命令
```bash
# 使用SimpleScreenRecorder
simplescreenrecorder

# 或使用OBS Studio
obs
```

## 🐛 故障排查

### 问题1：话题没有数据
```bash
# 检查话题是否存在
ros2 topic list | grep arm

# 检查话题频率
ros2 topic hz /left_arm_joint_control
ros2 topic hz /right_arm_joint_control

# 手动发布测试数据
ros2 topic pub --once /left_arm_joint_control sensor_msgs/msg/JointState \
    "{position: [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]}"
```

### 问题2：可视化不更新
```bash
# 检查滤波节点是否运行
ps aux | grep vist_filter_node

# 检查可视化节点日志
# 查看终端输出，应该显示更新频率

# 重启可视化节点
pkill -f visualize_dual_arm
python3 visualize_dual_arm_realtime.py
```

### 问题3：关节方向错误
- 检查 `vist_filter_node.py` 中的关节方向修正代码
- 检查 `visualize_dual_arm_realtime.py` 中的关节方向修正代码
- 确保两者一致

## 📝 开发笔记

### 为什么使用双节点而不是单节点双实例？

**优点**：
- ✅ 零代码修改（最小侵入）
- ✅ 完全独立，互不干扰
- ✅ 符合ROS2设计哲学（单一职责原则）
- ✅ 易于调试和监控

**ROS2设计哲学**：
- 一个节点做一件事，做好它
- 通过话题通信，而不是共享状态
- 模块化、可组合、可扩展

### 代码修改总结

**修改的文件**：
1. `ros2_ws/launch/dual_arm_teleop.launch.py` - 新建
2. `visualize_dual_arm_realtime.py` - 新建
3. `test_dual_arm.sh` - 新建
4. `DUAL_ARM_README.md` - 新建（本文件）

**未修改的文件**：
- `ros2_ws/src/nodes/vist_filter_node.py` - 无需修改
- `ros2_ws/src/core/vist_kalman_filter.py` - 无需修改
- `ros2_ws/src/core/ik_solver.py` - 无需修改
- `config/baseline_filters_config.yaml` - 已有双臂配置

### 关键设计决策

1. **双节点实例 vs 单节点双滤波器**
   - 选择：双节点实例
   - 原因：零侵入、易维护、符合ROS2哲学

2. **是否需要桥接节点**
   - 选择：不需要
   - 原因：滤波节点已处理单位转换

3. **可视化方案**
   - 选择：单个可视化节点订阅双臂话题
   - 原因：统一显示，便于观察协同运动

## 🎓 学习资源

### ROS2基础
- [ROS2官方教程](https://docs.ros.org/en/humble/Tutorials.html)
- [ROS2节点概念](https://docs.ros.org/en/humble/Tutorials/Beginner-CLI-Tools/Understanding-ROS2-Nodes/Understanding-ROS2-Nodes.html)
- [ROS2话题概念](https://docs.ros.org/en/humble/Tutorials/Beginner-CLI-Tools/Understanding-ROS2-Topics/Understanding-ROS2-Topics.html)

### Python进阶
- [Python多线程](https://docs.python.org/3/library/threading.html)
- [Python类型注解](https://docs.python.org/3/library/typing.html)

### 机器人学
- 《Programming Robots with ROS》
- 《Modern Robotics》

## 📞 联系方式

如有问题，请提交Issue或联系VIST团队。

---

**版本**: v1.0
**日期**: 2026-03-17
**作者**: VIST Team