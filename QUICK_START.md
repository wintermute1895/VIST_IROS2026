# VIST 快速启动参考
# Quick Start Reference

## 启动前检查 ✓

```bash
cd /home/ilex/Dev/VIST
./scripts/validate_startup_config.sh
```

## 4 个终端启动命令

### Terminal 1 - 外骨骼
```bash
./scripts/start_1_exoskeleton.sh
```

### Terminal 2 - 滤波器
```bash
cd /home/ilex/Dev/VIST && ./scripts/start_2_filter.sh one_euro
```

### Terminal 3 - 机械臂驱动
```bash
cd /home/ilex/Dev/VIST && ./scripts/start_3_robot_driver.sh
```

### Terminal 4 - 遥操作桥接
```bash
cd /home/ilex/Dev/VIST && ./scripts/start_4_teleop_bridge.sh
```

## 数据采集

```bash
cd /home/ilex/Dev/VIST
./scripts/collect_right_arm_data.sh exp1_one_euro 30
```

## 滤波器类型

- `./scripts/start_2_filter.sh none` - 无滤波
- `./scripts/start_2_filter.sh ema 0.3` - EMA 滤波
- `./scripts/start_2_filter.sh one_euro 1.0 0.007` - One-Euro 滤波
- `./scripts/start_2_filter.sh vist_kalman` - VIST Kalman 滤波

## 重要提醒

1. ✓ 启动前运行验证脚本
2. ✓ 按顺序启动 4 个终端
3. ✓ 在 web 控制器手动使能机械臂
4. ✓ 确认工作空间安全
5. ✓ 急停按钮在手边

## 故障排除

**机械臂不动？**
```bash
# 检查数据流
ros2 topic hz /filtered_right_joint_control

# 检查连接
ros2 topic info /right_arm/joint_follow
```

**话题碰撞？**
```bash
# 停止所有节点，然后重新启动
ros2 node list
```

---

详细文档: [docs/STARTUP_GUIDE_SIMPLE.md](docs/STARTUP_GUIDE_SIMPLE.md)
