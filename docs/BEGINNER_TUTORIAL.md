# VIST系统新手启动教程

**欢迎！** 这是一份面向零基础新手的完整启动指南。我们会一步一步教你如何启动VIST系统并进行实验。

**预计时间**: 30-45分钟（首次启动）

---

## 📋 开始之前

### 你需要准备什么？

1. ✅ 已经按照 [ENVIRONMENT_SETUP.md](ENVIRONMENT_SETUP.md) 配置好环境
2. ✅ 所有硬件设备已连接：
   - 相机（USB）
   - 外骨骼（CAN1）
   - 数据手套（USB）
   - 灵巧手（CAN0）
   - 机械臂（网络线）
3. ✅ 电脑已开机并登录

### 你会学到什么？

- 如何打开多个终端
- 如何启动每个系统组件
- 如何验证系统是否正常工作
- 如何开始数据采集
- 遇到问题如何解决

---

## 🚀 第一步：准备工作

### 1.1 打开第一个终端

**操作**:
- 按 `Ctrl + Alt + T` 打开终端
- 或者点击屏幕左上角的"活动"，搜索"终端"

**你会看到**:
```
(base) ilex@ilex22:~$
```

这是你的命令行提示符，表示终端已经准备好接收命令了。

<thinking>
我需要创建一个非常详细的、逐步的教程，包括每一步的预期输出和可能的错误。让我继续编写。
</thinking>

### 1.2 启动CAN接口（重要！）

**为什么要做这个？**
外骨骼和灵巧手需要通过CAN接口通信。如果不启动CAN接口，它们将无法工作。

**操作**:
在终端中输入以下命令（一次一行）：

```bash
sudo ip link set can0 up type can bitrate 1000000
```

**会发生什么**:
- 系统会要求你输入密码
- 输入密码时屏幕上不会显示任何字符（这是正常的！）
- 按回车

然后输入：

```bash
sudo ip link set can1 up type can bitrate 1000000
```

**验证是否成功**:
```bash
ip link show can0
ip link show can1
```

**你应该看到**:
```
can0: <NOARP,UP,LOWER_UP,ECHO> mtu 16 qdisc pfifo_fast state UP
    can state ERROR-ACTIVE
```

✅ 如果看到 `state UP` 和 `ERROR-ACTIVE`，说明成功了！

❌ 如果看到 `state DOWN`，说明启动失败，请重新运行上面的命令。

---

## 📹 第二步：启动相机（终端1）

### 2.1 保持当前终端打开

这个终端将用于运行相机节点。

### 2.2 进入项目目录

**操作**:
```bash
cd ~/Dev/VIST
```

**解释**: 这个命令让你进入VIST项目的目录。

### 2.3 加载ROS2环境

**操作**:
```bash
source /opt/ros/humble/setup.bash
source install/setup.bash
```

**解释**: 这两个命令告诉系统在哪里找到ROS2和VIST的程序。

**你会看到**: 命令执行后没有任何输出，这是正常的！

### 2.4 启动相机

**操作**:
```bash
./scripts/start_camera.sh
```

**你会看到**:
```
========================================
可选: 数据采集相机
========================================
启动数据采集相机...

相机配置:
  序列号: 348122071157
  分辨率: 848x480
  帧率: 30 fps

[INFO] 相机初始化成功
[INFO] RealSense相机节点已启动
```

✅ **成功标志**: 看到 "相机初始化成功" 和 "RealSense相机节点已启动"

❌ **如果出错**:
- 检查相机USB线是否插好
- 尝试拔掉相机USB线，等5秒，再插回去
- 重新运行启动命令

### 2.5 验证相机是否工作

**打开一个新终端** (按 `Ctrl + Shift + T` 或点击终端菜单 → 新建标签页)

在新终端中输入：
```bash
ros2 topic hz /camera/color/image_raw
```

**你会看到**:
```
average rate: 12.345
    min: 0.078s max: 0.085s std dev: 0.00234s window: 13
```

✅ **成功标志**: 看到 `average rate: 12-15` 左右的数字

**关闭这个验证终端**: 按 `Ctrl + C`，然后关闭这个标签页

---

## 🦾 第三步：启动外骨骼（终端2）

### 3.1 打开新终端

**操作**: 按 `Ctrl + Shift + T` 打开新的终端标签页

### 3.2 进入项目并加载环境

**操作**:
```bash
cd ~/Dev/VIST
source /opt/ros/humble/setup.bash
cd external_sdk/arm_teleop
source install/setup.bash
cd ~/Dev/VIST
source install/setup.bash
```

**解释**: 外骨骼需要加载两个工作空间的环境。

### 3.3 启动外骨骼

**操作**:
```bash
./scripts/start_left_arm_teleop.sh
```

**你会看到**:
```
========================================
左臂外骨骼遥操
========================================
CAN接口: can1

calibration : 0
CAN channel : can1
baudrate : 1000000

（然后会持续输出关节数据）
 0 : 0.9  |  OK
 1 : 1.3  |  OK
 2 : -12.4  |  OK
 ...
```

✅ **成功标志**: 看到关节数据持续输出，每行都显示 "OK"

❌ **如果出错**:
- 检查CAN1接口是否启动（回到第一步）
- 检查外骨骼的电源是否打开
- 检查CAN线是否插好

**测试**: 轻轻移动外骨骼的关节，你应该看到数字在变化

---

## 🔄 第四步：启动滤波器（终端3）

### 4.1 打开新终端

**操作**: 按 `Ctrl + Shift + T`

### 4.2 启动滤波器

**操作**:
```bash
cd ~/Dev/VIST
source /opt/ros/humble/setup.bash
source install/setup.bash
./scripts/start_filter.sh
```

**你会看到**:
```
========================================
启动滤波器
========================================
输入: /left_arm_joint_control
输出: /filtered_joint_states
滤波类型: one_euro

[INFO] 滤波器节点已启动
```

✅ **成功标志**: 看到 "滤波器节点已启动"

**这个节点不会显示数据**，它在后台默默工作。

---

## 🧤 第五步：启动数据手套（终端4）

### 5.1 打开新终端

**操作**: 按 `Ctrl + Shift + T`

### 5.2 启动数据手套

**操作**:
```bash
cd ~/Dev/VIST
source /opt/ros/humble/setup.bash
source install/setup.bash
bash scripts/start_5_data_glove.sh
```

**你会看到**:
```
========================================
Terminal 5: 数据手套驱动
========================================
检查手套 USB 连接...
找到 USB 设备: /dev/ttyUSB0

[INFO] 已搜索到左部力反馈手套,版本号1.2.12
[INFO] 标定数据加载成功
```

✅ **成功标志**: 看到 "已搜索到左部力反馈手套" 和 "标定数据加载成功"

❌ **如果出错**:
- 检查数据手套USB线是否插好
- 检查数据手套电源是否打开
- 尝试拔掉USB线，等5秒，再插回去

---

## 🤚 第六步：启动灵巧手（终端5）

### 6.1 打开新终端

**操作**: 按 `Ctrl + Shift + T`

### 6.2 启动灵巧手

**操作**:
```bash
cd ~/Dev/VIST
source /opt/ros/humble/setup.bash
source install/setup.bash
./scripts/start_6_dexterous_hand.sh
```

**你会看到**:
```
========================================
Terminal 6: 灵巧手驱动
========================================
检查 CAN 端口...
CAN 端口已经激活

启动灵巧手驱动...
手部: left
CAN 端口: can0
触觉传感器: false

（灵巧手初始化信息）
```

✅ **成功标志**: 看到 "CAN 端口已经激活" 和灵巧手初始化信息

**测试**: 移动数据手套的手指，观察灵巧手是否跟随运动

---

## 🤖 第七步：启动机械臂驱动（终端6）

### 7.1 打开新终端

**操作**: 按 `Ctrl + Shift + T`

### 7.2 启动机械臂驱动

**操作**:
```bash
cd ~/Dev/VIST/external_sdk/arm_teleop
source /opt/ros/humble/setup.bash
source install/setup.bash
ros2 launch lbot_driver lbot_start_driver.launch.py
```

**你会看到**:
```
[INFO] [lbot_driver]: Starting LBot Driver...
[INFO] [robot1.lbot_main_node]: Connected to LBot at 192.168.10.21
[INFO] [robot1.lbot_main_node]: State monitor started successfully
[INFO] [lbot_driver]: All nodes ready, spinning...
```

✅ **成功标志**: 看到 "Connected to LBot" 和 "All nodes ready"

❌ **如果出错**:
- 检查网络线是否插好
- 检查机械臂电源是否打开
- 用 `ping 192.168.10.21` 测试网络连接

---

## 🔗 第八步：启动遥操桥接（终端7）

### 8.1 打开新终端

**操作**: 按 `Ctrl + Shift + T`

### 8.2 启动遥操桥接

**操作**:
```bash
cd ~/Dev/VIST
./scripts/start_teleop_bridge.sh
```

**你会看到**:
```
========================================
遥操桥接节点
========================================
启动遥操桥接节点...
输入: /filtered_joint_states
输出: /robot1/left_arm/joint_follow

[INFO] 遥操桥接节点已启动
```

✅ **成功标志**: 看到 "遥操桥接节点已启动"

**重要测试**:
1. **确保机械臂急停按钮已按下**（安全第一！）
2. 轻轻移动外骨骼
3. 观察终端输出，应该看到数据在流动

---

## 🎉 恭喜！系统已经启动完成！

现在你有7个终端在运行：
1. 📹 相机
2. 🦾 外骨骼
3. 🔄 滤波器
4. 🧤 数据手套
5. 🤚 灵巧手
6. 🤖 机械臂驱动
7. 🔗 遥操桥接

---

## ✅ 系统验证

### 验证1：检查所有节点

**打开一个新终端**，输入：
```bash
ros2 node list
```

**你应该看到**:
```
/realsense_camera_node
/linkerta_node
/unified_filter_node
/handretarget_node
/linker_hand_advanced_l10
/robot1.lbot_main_node
/teleop_bridge_node
```

✅ 如果看到这7个节点，说明所有组件都在运行！

### 验证2：测试数据手套→灵巧手

1. 移动数据手套的手指
2. 观察灵巧手是否跟随运动

✅ 如果灵巧手跟随运动，说明这条数据链路正常！

### 验证3：测试外骨骼→机械臂（急停状态）

**重要**: 确保机械臂急停按钮已按下！

1. 移动外骨骼的关节
2. 观察终端2（外骨骼）的数据是否变化
3. 观察终端3（滤波器）是否有输出
4. 观察终端7（遥操桥接）是否有输出

✅ 如果所有终端都有数据流动，说明数据链路正常！

**注意**: 因为急停按钮按下，机械臂不会实际运动，但数据应该在流动。

---

## 📊 第九步：开始数据采集（可选）

### 9.1 打开新终端（终端8）

**操作**: 按 `Ctrl + Shift + T`

### 9.2 启动数据采集

**操作**:
```bash
cd ~/Dev/VIST
source /opt/ros/humble/setup.bash
source install/setup.bash
./scripts/record_experiment.sh my_first_experiment
```

**你会看到**:
```
=== VIST数据采集 ===

实验名称: my_first_experiment
输出目录: /home/ilex/Dev/VIST/data/experiments/my_first_experiment_20260226_051047

将记录以下topic:
  - /camera/color/image_raw
  - /left_arm_joint_control
  - /filtered_joint_states
  ...

开始录制... (按Ctrl+C停止)
```

### 9.3 进行实验

现在你可以：
1. 移动外骨骼
2. 移动数据手套
3. 系统会自动记录所有数据

### 9.4 停止录制

**操作**: 按 `Ctrl + C`

**你会看到**:
```
录制完成！
数据保存在: /home/ilex/Dev/VIST/data/experiments/my_first_experiment_20260226_051047
```

✅ 数据已保存！你可以在 `~/Dev/VIST/data/experiments/` 目录中找到它。

---

## 🛑 如何关闭系统

**重要**: 按照相反的顺序关闭节点！

1. 终端8: 数据采集 - 按 `Ctrl + C`
2. 终端7: 遥操桥接 - 按 `Ctrl + C`
3. 终端6: 机械臂驱动 - 按 `Ctrl + C`
4. 终端5: 灵巧手 - 按 `Ctrl + C`
5. 终端4: 数据手套 - 按 `Ctrl + C`
6. 终端3: 滤波器 - 按 `Ctrl + C`
7. 终端2: 外骨骼 - 按 `Ctrl + C`
8. 终端1: 相机 - 按 `Ctrl + C`

然后关闭所有终端窗口。

---

## ❓ 常见问题

### Q1: 我按了命令但什么都没发生？

**A**: 检查：
- 是否按了回车键？
- 是否在正确的目录？（用 `pwd` 命令查看当前目录）
- 是否source了环境？

### Q2: 提示"Permission denied"？

**A**:
- 如果是CAN接口，需要用 `sudo` 命令
- 如果是脚本，检查是否有执行权限：`chmod +x scripts/*.sh`

### Q3: 提示"Package not found"？

**A**:
- 检查是否source了环境：
  ```bash
  source /opt/ros/humble/setup.bash
  source ~/Dev/VIST/install/setup.bash
  ```

### Q4: 相机/手套/灵巧手找不到设备？

**A**:
1. 拔掉USB线
2. 等待5秒
3. 重新插入
4. 重新运行启动命令

### Q5: 机械臂连接失败？

**A**:
1. 检查网络线是否插好
2. 测试连接：`ping 192.168.10.21`
3. 检查机械臂电源是否打开

### Q6: 终端太多了，记不住哪个是哪个？

**A**:
- 每个终端的标题栏会显示正在运行的程序名称
- 或者在每个终端的第一行输出中查看节点名称

---

## 📚 下一步学习

恭喜你完成了第一次启动！接下来你可以：

1. **学习监控系统** - 阅读 [MONITORING_AND_RECORDING.md](MONITORING_AND_RECORDING.md)
2. **了解节点详情** - 阅读 [NODE_REFERENCE.md](NODE_REFERENCE.md)
3. **进行真实实验** - 松开机械臂急停，进行实际的遥操作

---

## 💡 小贴士

1. **使用tmux**: 如果你熟悉tmux，可以用它管理多个终端，更方便
2. **保存终端布局**: 记住每个终端的位置，下次启动会更快
3. **检查清单**: 每次启动前，用本文档的检查清单确保所有步骤都完成了
4. **记录问题**: 如果遇到问题，记下错误信息，方便排查

---

## 🎓 总结

你已经学会了：
- ✅ 如何启动CAN接口
- ✅ 如何按顺序启动7个系统组件
- ✅ 如何验证系统是否正常工作
- ✅ 如何进行数据采集
- ✅ 如何安全地关闭系统

**记住**: 熟能生巧！多启动几次，你就会越来越熟练。

**祝你实验顺利！** 🚀

---

最后更新: 2026-02-26