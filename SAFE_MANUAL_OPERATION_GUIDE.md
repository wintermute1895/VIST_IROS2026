# 外骨骼遥操安全启动手册 - 手动分步执行

**⚠️ 重要**: 电机烧毁事故后的安全强化版本
**原则**: 每一步手动执行，清楚知道每个命令的作用，绝不运行后台进程

---

## 🛑 安全第一原则

1. **每次只运行一个命令**
2. **每个命令都要理解它的作用**
3. **绝不使用自动化脚本**
4. **每个节点都要能随时Ctrl+C停止**
5. **发现异常立即停止所有进程**

---

## 📋 启动前安全检查清单

### 第一步：检查是否有残留进程（最重要！）

```bash
# 检查linkerta进程
pgrep -af linkerta

# 检查lbot进程
pgrep -af lbot

# 如果有任何输出，说明有残留进程！必须清理！
```

**如果发现残留进程**:
```bash
# 查看进程详情
ps aux | grep linkerta
ps aux | grep lbot

# 手动杀死进程（记录PID）
kill -9 <PID>

# 再次确认已清理
pgrep -af linkerta
pgrep -af lbot
# 应该无输出
```

---

### 第二步：检查硬件连接

```bash
# 检查机械臂网络连接
ping -c 3 192.168.10.21

# 检查外骨骼USB连接
ls /dev/ttyUSB* 2>/dev/null || ls /dev/ttyACM* 2>/dev/null

# 检查CAN总线（如果使用数据手套）
ip link show can0 2>/dev/null
```

**预期结果**:
- ping成功，延迟<5ms
- 看到USB设备（如/dev/ttyUSB0）
- can0状态为UP（如果使用手套）

---

### 第三步：检查机械臂状态

```bash
# 进入SDK目录
cd /home/ilex/Dev/VIST/external_sdk/arm_teleop

# 加载ROS2环境
source /opt/ros/humble/setup.bash
source install/setup.bash

# 手动启动机械臂驱动（仅此一个进程）
ros2 run lbot_driver lbot_driver --ros-args -p arm_ip:=192.168.10.21
```

**观察输出**:
- 看到"Connected to robot"
- 看到joint_states发布（~50Hz）
- **没有任何错误信息**

**如果正常，按Ctrl+C停止**

---

## 🚀 安全启动流程（分步执行）

### 终端1: 机械臂驱动（从臂）

```bash
# 进入SDK目录
cd /home/ilex/Dev/VIST/external_sdk/arm_teleop
source /opt/ros/humble/setup.bash
source install/setup.bash

# 启动机械臂驱动
ros2 run lbot_driver lbot_driver --ros-args \
    -r __ns:=/robot1 \
    -p arm_ip:=192.168.10.21

# 观察输出，确认连接成功
# 看到 "Connected to robot at 192.168.10.21"
# 看到 "Publishing joint states at ~50Hz"
```

**这个终端保持运行，不要关闭**

---

### 终端2: 检查机械臂状态

```bash
# 新开一个终端
source /opt/ros/humble/setup.bash

# 检查话题列表
ros2 topic list | grep robot1

# 应该看到:
# /robot1/right_arm/joint_states
# /robot1/right_arm/joint_follow
# /robot1/left_arm/joint_states
# /robot1/left_arm/joint_follow

# 检查joint_states频率
ros2 topic hz /robot1/right_arm/joint_states

# 应该看到 ~50Hz

# 检查joint_states内容
ros2 topic echo /robot1/right_arm/joint_states --once

# 应该看到7个关节的位置数据
```

**确认一切正常后，继续下一步**

---

### 终端3: 外骨骼驱动（主臂）

```bash
# 新开一个终端
cd /home/ilex/Dev/VIST/external_sdk/arm_teleop
source /opt/ros/humble/setup.bash
source install/setup.bash

# 启动外骨骼驱动
ros2 run linkerta linkerta_node

# 观察输出，确认连接成功
# 看到 "Linkerta connected"
# 看到 "Publishing at ~230Hz"
```

**这个终端保持运行，不要关闭**

---

### 终端4: 检查外骨骼状态

```bash
# 新开一个终端
source /opt/ros/humble/setup.bash

# 检查话题列表
ros2 topic list | grep arm_joint_control

# 应该看到:
# /left_arm_joint_control
# /right_arm_joint_control

# 检查频率
ros2 topic hz /right_arm_joint_control

# 应该看到 ~230Hz

# 检查内容
ros2 topic echo /right_arm_joint_control --once

# 应该看到7个关节的位置数据
```

**⚠️ 重要检查**:
```bash
# 确认只有一个linkerta进程
pgrep -af linkerta | wc -l
# 应该输出: 1

# 如果输出>1，立即停止所有进程！
```

---

### 终端5: 桥接节点（连接外骨骼和机械臂）

```bash
# 新开一个终端
cd /home/ilex/Dev/VIST/external_sdk/arm_teleop
source /opt/ros/humble/setup.bash
source install/setup.bash

# 启动桥接节点
ros2 run lbot_teleop teleop_bridge_node --ros-args \
    -p master_left_topic:=/left_arm_joint_control \
    -p master_right_topic:=/right_arm_joint_control \
    -p slave_namespaces:="['robot1']"

# 观察输出
# 看到 "Subscribed to /right_arm_joint_control"
# 看到 "Publishing to /robot1/right_arm/joint_follow"
```

**这个终端保持运行，不要关闭**

---

### 终端6: 监控系统状态

```bash
# 新开一个终端
source /opt/ros/humble/setup.bash

# 实时监控joint_follow命令
ros2 topic echo /robot1/right_arm/joint_follow

# 观察:
# - 当你移动外骨骼时，应该看到数据更新
# - 数据应该是连续的，没有突变
# - 频率应该稳定
```

---

## 🎯 测试流程（极度谨慎）

### 第一次测试：静态保持

```bash
# 在终端6中监控
ros2 topic echo /robot1/right_arm/joint_follow

# 保持外骨骼完全静止
# 观察30秒

# 预期: 数据应该非常稳定，几乎不变
# 如果数据剧烈跳动，立即停止所有进程！
```

---

### 第二次测试：缓慢移动

```bash
# 继续在终端6中监控

# 非常缓慢地移动外骨骼（1秒移动1cm）
# 观察数据变化

# 预期: 数据应该平滑变化，没有突变
# 如果看到突然跳变（>0.1 rad），立即停止！
```

---

### 第三次测试：机械臂响应

```bash
# 在终端6中监控

# 缓慢移动外骨骼
# 同时观察机械臂是否跟随

# 预期: 机械臂应该平滑跟随，没有抖动
# 如果机械臂剧烈震动，立即按Ctrl+C停止所有终端！
```

---

## 🛑 紧急停止流程

### 发现异常时：

1. **立即按Ctrl+C停止所有终端**（按顺序）:
   - 终端5 (teleop_bridge) - 先停止命令发送
   - 终端3 (linkerta) - 停止外骨骼
   - 终端1 (lbot_driver) - 停止机械臂

2. **检查进程**:
   ```bash
   pgrep -af linkerta
   pgrep -af lbot
   ```

3. **如果还有残留进程，强制杀死**:
   ```bash
   pkill -9 -f linkerta
   pkill -9 -f lbot
   ```

4. **记录日志**:
   ```bash
   # 保存系统日志
   journalctl -xe > ~/emergency_stop_$(date +%Y%m%d_%H%M%S).log
   ```

---

## 📊 安全监控指标

### 实时监控命令

```bash
# 终端A: 监控进程数量
watch -n 1 'pgrep -af linkerta | wc -l'
# 应该始终显示: 1

# 终端B: 监控话题频率
watch -n 1 'ros2 topic hz /robot1/right_arm/joint_follow --window 10'
# 应该稳定在 ~230Hz

# 终端C: 监控关节速度
ros2 topic echo /robot1/right_arm/joint_states --field velocity
# 速度不应超过 1.0 rad/s
```

---

## ⚠️ 危险信号识别

### 立即停止的情况：

1. **进程数量异常**
   ```bash
   pgrep -af linkerta | wc -l
   # 如果 > 1，立即停止！
   ```

2. **数据突变**
   ```bash
   # 如果看到关节位置突然跳变 > 0.1 rad
   # 立即停止！
   ```

3. **频率异常**
   ```bash
   # 如果频率突然下降到 < 100Hz
   # 或者频率不稳定（波动 > 50Hz）
   # 立即停止！
   ```

4. **机械臂异常**
   - 听到异常声音（嗡嗡声、尖叫声）
   - 看到剧烈震动
   - 感觉到发热
   - **立即停止！**

---

## 🔧 故障排查

### 问题1: 连接失败

```bash
# 检查网络
ping 192.168.10.21

# 检查防火墙
sudo ufw status

# 检查机械臂电源
# 物理检查LED指示灯
```

---

### 问题2: 多进程残留

```bash
# 查看所有相关进程
ps aux | grep -E "linkerta|lbot"

# 记录PID
# 逐个杀死
kill -9 <PID1>
kill -9 <PID2>

# 确认清理完成
pgrep -af linkerta
pgrep -af lbot
```

---

### 问题3: 话题无数据

```bash
# 检查节点状态
ros2 node list

# 检查话题连接
ros2 topic info /robot1/right_arm/joint_follow

# 检查节点日志
ros2 node info /lbot_driver
```

---

## 📝 操作日志模板

### 每次启动都要记录：

```
日期: 2026-02-24
时间: 20:00
操作员: [姓名]

启动前检查:
[ ] 残留进程检查 - 通过
[ ] 硬件连接检查 - 通过
[ ] 机械臂状态检查 - 通过

启动流程:
[ ] 终端1: lbot_driver - 启动成功
[ ] 终端2: 状态检查 - 通过
[ ] 终端3: linkerta_node - 启动成功
[ ] 终端4: 状态检查 - 通过
[ ] 终端5: teleop_bridge - 启动成功
[ ] 终端6: 监控 - 正常

测试流程:
[ ] 静态保持测试 - 通过
[ ] 缓慢移动测试 - 通过
[ ] 机械臂响应测试 - 通过

异常记录:
无

停止时间: 20:30
总运行时长: 30分钟
```

---

## 🎓 理解每个命令

### ros2 run lbot_driver lbot_driver
- **作用**: 启动机械臂驱动节点
- **功能**: 连接到192.168.10.21的机械臂，接收控制命令，发送状态反馈
- **话题**: 订阅 `/robot1/right_arm/joint_follow`，发布 `/robot1/right_arm/joint_states`
- **风险**: 低（只是驱动，不主动发送命令）

### ros2 run linkerta linkerta_node
- **作用**: 启动外骨骼驱动节点
- **功能**: 读取外骨骼传感器数据，发布关节角度
- **话题**: 发布 `/right_arm_joint_control`
- **风险**: 低（只是读取，不控制机械臂）

### ros2 run lbot_teleop teleop_bridge_node
- **作用**: 启动桥接节点
- **功能**: 将外骨骼数据转发给机械臂
- **话题**: 订阅 `/right_arm_joint_control`，发布 `/robot1/right_arm/joint_follow`
- **风险**: ⚠️ 高（这个节点会让机械臂跟随外骨骼运动）

---

## 总结

**核心原则**:
1. ✅ 每个命令都手动执行
2. ✅ 每个终端都可以Ctrl+C停止
3. ✅ 每次启动前检查残留进程
4. ✅ 发现异常立即停止
5. ✅ 记录所有操作日志

**绝不**:
- ❌ 使用自动化脚本
- ❌ 后台运行进程
- ❌ 跳过安全检查
- ❌ 忽略异常信号

**记住**: 安全第一，宁可多花时间检查，也不要冒险！
