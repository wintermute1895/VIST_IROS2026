# 干运行测试指南（无真实机械臂）

本指南用于在没有真实机械臂的情况下测试数据采集系统，验证数据流和节点通信。

## 测试目标

1. 验证外骨骼数据采集正常
2. 验证滤波器处理正常
3. 验证相机数据采集正常
4. 验证数据手套和灵巧手通信正常（如果有硬件）
5. 验证数据采集脚本能正确录制所有话题

## 测试步骤

### 1. 启动外骨骼节点 (Terminal 1)

```bash
cd /home/ilex/Dev/VIST
./scripts/start_1_exoskeleton.sh
```

**预期结果：**
- 节点正常启动
- 发布话题 `/right_arm_joint_control`

**验证：**
```bash
# 新开一个终端
ros2 topic list | grep right_arm_joint_control
ros2 topic hz /right_arm_joint_control
ros2 topic echo /right_arm_joint_control --once
```

**可能遇到的问题：**
- USB 权限不足：`sudo chmod 777 /dev/ttyUSB*`
- 外骨骼未连接：检查 USB 连接
- 节点崩溃：检查日志，可能是配置文件错误

---

### 2. 启动滤波器节点 (Terminal 2)

```bash
cd /home/ilex/Dev/VIST
./scripts/start_2_filter.sh one_euro
```

**预期结果：**
- 节点正常启动
- 订阅话题 `/right_arm_joint_control`
- 发布话题 `/filtered_right_joint_control`

**验证：**
```bash
# 检查话题
ros2 topic list | grep filtered_right_joint_control
ros2 topic hz /filtered_right_joint_control

# 检查发布者数量（应该只有1个）
ros2 topic info /filtered_right_joint_control

# 对比原始数据和滤波后数据
ros2 topic echo /right_arm_joint_control --once
ros2 topic echo /filtered_right_joint_control --once
```

**可能遇到的问题：**
- 滤波器节点未启动：检查 Python 环境和依赖
- 话题碰撞：检查是否有多个滤波器节点在运行
- 滤波器参数错误：检查配置文件

---

### 3. 跳过机械臂驱动和遥操作桥接

**说明：**
- Terminal 3 (机械臂驱动) 需要真实硬件，跳过
- Terminal 4 (遥操作桥接) 依赖机械臂驱动，跳过

**注意：**
- 数据采集时，`/right_arm/joint_follow` 和 `/right_arm/joint_states` 话题不会存在
- 这是正常的，数据采集脚本会显示警告但继续采集其他话题

---

### 4. 启动相机节点 (Terminal 3)

```bash
cd /home/ilex/Dev/VIST
./scripts/start_camera.sh --with-viewer
```

**预期结果：**
- 相机节点正常启动
- 弹出实时画面窗口
- 发布话题：
  - `/camera/color/image_raw`
  - `/camera/depth/image_raw`
  - `/camera/color/camera_info`

**验证：**
```bash
# 检查相机话题
ros2 topic list | grep camera

# 检查相机频率
ros2 topic hz /camera/color/image_raw

# 检查相机信息
ros2 topic echo /camera/color/camera_info --once
```

**可能遇到的问题：**
- 相机未连接：检查 USB 连接
- 相机被占用：关闭其他使用相机的程序
- 序列号错误：检查相机序列号是否正确（348122071157）

---

### 5. 启动数据手套节点 (Terminal 4) - 可选

```bash
cd /home/ilex/Dev/VIST
./scripts/start_5_data_glove.sh
```

**预期结果：**
- 节点正常启动
- 发布话题 `/cb_right_hand_control_cmd`

**验证：**
```bash
ros2 topic list | grep cb_right_hand
ros2 topic hz /cb_right_hand_control_cmd
ros2 topic echo /cb_right_hand_control_cmd --once
```

**可能遇到的问题：**
- USB 设备未找到：检查手套连接
- 权限不足：脚本会自动设置权限
- 需要标定：使用 `./scripts/start_5_data_glove.sh true` 强制标定

---

### 6. 启动灵巧手节点 (Terminal 5) - 可选

```bash
cd /home/ilex/Dev/VIST
./scripts/start_6_dexterous_hand.sh
```

**预期结果：**
- CAN 端口激活
- 节点正常启动
- 订阅话题 `/cb_right_hand_control_cmd`
- 发布话题 `/cb_right_hand_state`

**验证：**
```bash
# 检查 CAN 端口
ip -details link show can0

# 检查话题
ros2 topic list | grep cb_right_hand
ros2 topic hz /cb_right_hand_state
```

**可能遇到的问题：**
- CAN 端口未激活：脚本会自动激活
- 灵巧手未连接：检查 CAN 连接
- 权限不足：需要 sudo 权限激活 CAN

---

## 数据采集测试

### 检查所有话题状态

在开始采集前，检查所有话题是否正常：

```bash
# 列出所有话题
ros2 topic list

# 检查关键话题的发布频率
ros2 topic hz /right_arm_joint_control
ros2 topic hz /filtered_right_joint_control
ros2 topic hz /camera/color/image_raw
ros2 topic hz /cb_right_hand_control_cmd  # 如果启动了手套
ros2 topic hz /cb_right_hand_state        # 如果启动了灵巧手
```

### 开始数据采集

```bash
cd /home/ilex/Dev/VIST
./scripts/collect_right_arm_data.sh test_dry_run 10
```

**预期输出：**
```
[INFO] 实验名称: test_dry_run
[INFO] 采集时长: 10秒
[INFO] 保存目录: /home/ilex/Dev/VIST/data/exp_right_arm_only_20260225
[INFO] 相机录制: 启用
[INFO] 手部控制录制: 启用
[INFO] 检查话题连接...
[INFO] ✓ /right_arm_joint_control
[INFO] ✓ /filtered_right_joint_control
[WARN] ✗ /right_arm/joint_follow (未找到，将在采集时等待)
[WARN] ✗ /right_arm/joint_states (未找到，将在采集时等待)
[INFO] 检查相机话题...
[INFO] ✓ 相机话题: /camera/color/image_raw
[INFO] ✓ 相机话题: /camera/depth/image_raw
[INFO] ✓ 相机话题: /camera/color/camera_info
[INFO] 检查手部控制话题...
[INFO] ✓ 手部话题: /cb_right_hand_control_cmd
[INFO] ✓ 手部话题: /cb_right_hand_state
[INFO] 开始采集！
```

**注意：**
- `/right_arm/joint_follow` 和 `/right_arm/joint_states` 未找到是正常的（没有机械臂驱动）
- 数据采集会继续进行，只录制存在的话题

### 验证采集的数据

```bash
# 查看数据文件
cd /home/ilex/Dev/VIST/data/exp_right_arm_only_20260225
ls -lh test_dry_run/

# 查看数据包信息
ros2 bag info test_dry_run

# 预期输出应该包含：
# - /right_arm_joint_control
# - /filtered_right_joint_control
# - /camera/color/image_raw
# - /camera/depth/image_raw
# - /camera/color/camera_info
# - /cb_right_hand_control_cmd (如果启动了手套)
# - /cb_right_hand_state (如果启动了灵巧手)
```

---

## 预期问题和解决方案

### 问题 1：外骨骼数据频率不稳定

**现象：**
```bash
ros2 topic hz /right_arm_joint_control
# 输出频率波动很大，或者很低
```

**可能原因：**
- USB 连接不稳定
- 外骨骼电量不足
- 系统负载过高

**解决方案：**
- 更换 USB 线或 USB 口
- 给外骨骼充电
- 关闭其他占用 CPU 的程序

---

### 问题 2：滤波器延迟过大

**现象：**
```bash
# 原始数据和滤波后数据的时间戳差异很大
ros2 topic echo /right_arm_joint_control --once
ros2 topic echo /filtered_right_joint_control --once
```

**可能原因：**
- 滤波器参数设置不当
- 系统负载过高
- 滤波器节点性能问题

**解决方案：**
- 调整滤波器参数（降低 min_cutoff，增加 beta）
- 检查 CPU 使用率
- 使用更简单的滤波器（如 EMA）

---

### 问题 3：相机数据丢帧

**现象：**
```bash
ros2 topic hz /camera/color/image_raw
# 输出频率低于 30Hz
```

**可能原因：**
- USB 带宽不足
- 相机配置错误
- 系统负载过高

**解决方案：**
- 使用 USB 3.0 接口
- 降低相机分辨率或帧率
- 关闭深度图像采集（只采集 RGB）

---

### 问题 4：数据采集文件过大

**现象：**
```bash
du -sh test_dry_run/
# 输出文件大小超过预期（例如 10 秒数据 > 1GB）
```

**可能原因：**
- 相机数据占用空间大（RGB + 深度图像）
- 采集频率过高

**解决方案：**
- 暂时不采集深度图像（修改脚本，只采集 RGB）
- 降低相机分辨率
- 使用压缩话题（需要修改节点）

---

### 问题 5：话题碰撞

**现象：**
```bash
ros2 topic info /filtered_right_joint_control
# Publisher count: 2 (应该是 1)
```

**可能原因：**
- 有多个滤波器节点在运行
- 之前的节点没有正确关闭

**解决方案：**
```bash
# 查找所有 ROS2 节点
ros2 node list

# 杀死所有 ROS2 进程
pkill -9 ros2

# 重新启动节点
```

---

## 测试检查清单

完成以下检查，确保系统正常：

### 节点启动检查
- [ ] 外骨骼节点正常启动
- [ ] 滤波器节点正常启动
- [ ] 相机节点正常启动（如果有相机）
- [ ] 数据手套节点正常启动（如果有手套）
- [ ] 灵巧手节点正常启动（如果有灵巧手）

### 话题检查
- [ ] `/right_arm_joint_control` 正常发布（频率 > 50Hz）
- [ ] `/filtered_right_joint_control` 正常发布（频率 > 50Hz）
- [ ] `/camera/color/image_raw` 正常发布（频率 ~30Hz）
- [ ] `/cb_right_hand_control_cmd` 正常发布（如果启动了手套）
- [ ] `/cb_right_hand_state` 正常发布（如果启动了灵巧手）

### 数据质量检查
- [ ] 外骨骼数据无明显跳变
- [ ] 滤波后数据平滑
- [ ] 相机图像清晰，无花屏
- [ ] 手部控制数据合理

### 数据采集检查
- [ ] 数据采集脚本正常启动
- [ ] 所有存在的话题都被录制
- [ ] 数据文件大小合理
- [ ] 可以使用 `ros2 bag info` 查看数据包信息

---

## 下一步

完成干运行测试后：

1. **分析采集的数据**
   - 使用 `ros2 bag play` 回放数据
   - 检查数据质量和完整性
   - 验证滤波器效果

2. **准备真机测试**
   - 连接真实机械臂
   - 启动机械臂驱动和遥操作桥接
   - 进行完整的数据采集

3. **离线分析**
   - 提取数据进行滤波器性能分析
   - 比较不同滤波器的效果
   - 准备消融实验

---

## 故障排查命令汇总

```bash
# 检查所有 ROS2 节点
ros2 node list

# 检查所有话题
ros2 topic list

# 检查话题发布频率
ros2 topic hz <topic_name>

# 查看话题内容
ros2 topic echo <topic_name> --once

# 查看话题信息（发布者、订阅者数量）
ros2 topic info <topic_name>

# 杀死所有 ROS2 进程
pkill -9 ros2

# 检查 USB 设备
ls /dev/ttyUSB*

# 检查相机设备
rs-enumerate-devices

# 检查 CAN 端口
ip -details link show can0

# 查看数据包信息
ros2 bag info <bag_directory>

# 回放数据包
ros2 bag play <bag_directory>
```