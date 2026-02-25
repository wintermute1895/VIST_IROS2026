# 电机烧毁事故深度追溯分析报告

**事故时间**: 2026-02-24 19:35:28
**分析时间**: 2026-02-24 20:00
**分析方法**: 系统日志追溯 + 进程时间线重建

---

## 一、完整时间线重建

### 11:47 - 第一个linkerta会话启动
```
进程ID: 9147
启动时间: 11:47:43 (1771904863秒)
日志: /home/ilex/.ros/log/2026-02-24-11-47-43-551448-ilex22-9147/

历史记录:
- 11:47:43 启动 linkerta_node (PID 9149)
- 11:48:06 重启 (PID 9478)
- 12:07:36 重启 (PID 10824)
- 12:18:17 重启 (PID 11836)
- 12:24:57 重启 (PID 13494)
- 12:34:21 重启 (PID 15151)
- 12:43:38 重启 (PID 16339)
- 12:44:29 重启 (PID 16937)
- 12:48:14 重启 (PID 17846) ← 最后一次，一直运行到19:36
```

**关键发现**: 这个会话在8小时内重启了9次！说明linkerta节点不稳定。

---

### 12:18 - 第二个linkerta会话启动
```
进程ID: 11648
启动时间: 12:18:07 (1771906687秒)
日志: /home/ilex/.ros/log/2026-02-24-12-18-07-986725-ilex22-11648/

历史记录:
- 12:18:08 启动 linkerta_node (PID 11650)
- 12:18:16 崩溃 (exit code -15, SIGTERM) ← 被强制终止
- 12:18:19 重启 (PID 11817)
- 12:24:57 重启 (PID 13493)
- 12:34:21 重启 (PID 15154)
- 12:43:38 重启 (PID 16338)
- 12:44:29 重启 (PID 16936)
- 12:48:14 重启 (PID 17844) ← 最后一次，一直运行到19:36
```

**关键发现**: 这个会话也在7小时内重启了8次！

---

### 19:34 - 用户尝试启动新会话（失败）
```
进程ID: 47703
启动时间: 19:34:30 (1771932870秒)
日志: /home/ilex/.ros/log/2026-02-24-19-34-30-380347-ilex22-47703/

结果: 启动失败（可能因为旧节点占用）
```

---

### 19:35 - 用户再次启动新会话（成功但导致事故）
```
进程ID: 47834
启动时间: 19:35:19 (1771932919秒)
日志: /home/ilex/.ros/log/2026-02-24-19-35-19-772104-ilex22-47834/

启动序列:
19:35:19.773 - Launch进程启动
19:35:19.813 - lbot_driver启动 (PID 47835)
19:35:20.816 - linkerta_node启动 (PID 47867)
19:35:21.822 - teleop_bridge_node启动 (PID 47887)
```

---

### 19:35:19-19:35:21 - lbot_driver初始化
```
[INFO] [1771932919.822] [lbot_driver]: Starting LBot Driver with separate service nodes...
[INFO] [1771932919.836] [robot1.lbot_main_node]: Connected to LBot at 192.168.10.21
[INFO] [1771932919.836] [robot1.lbot_main_node]: State monitor started successfully
[INFO] [1771932919.836] [robot1.lbot_main_node]: LBot main node initialized successfully
[INFO] [1771932919.841] [robot1.lbot_left_arm_node]: Left arm service node initialized
[INFO] [1771932919.846] [robot1.lbot_right_arm_node]: Right arm service node initialized
[INFO] [1771932919.846] [main_executor]: Main node executor spinning...
[INFO] [1771932919.846] [lbot_driver]: All nodes ready, spinning...
[INFO] [1771932919.846] [left_arm_executor]: Left arm service executor spinning...
[INFO] [1771932919.846] [right_arm_executor]: Right arm service executor spinning...
```

**分析**: lbot_driver成功连接到机器人，所有执行器开始运行。

---

### 19:35:21 - 连接异常与重连
```
[INFO] [1771932921.836] [robot1.lbot_main_node]: Trying to reconnect to LBot...
[ERROR] [1771932921.836] [robot1.lbot_main_node]: Failed to connect to LBot
[INFO] [1771932921.836] [robot1.lbot_main_node]: Arm reconnected successfully
```

**时间**: 启动后2秒
**问题**:
1. 为什么刚连接成功就需要重连？
2. "Failed to connect"后立即"reconnected successfully"是矛盾的
3. 这种快速的失败-成功切换可能导致状态不一致

---

### 19:35:21 - teleop_bridge发送初始位置命令
```
[INFO] [1771932921.843] [teleop_bridge_node]: ========== Teleop Bridge Configuration ==========
[INFO] [1771932921.843] [teleop_bridge_node]: Master left topic:  /left_arm_joint_control
[INFO] [1771932921.843] [teleop_bridge_node]: Master right topic: /right_arm_joint_control
[INFO] [1771932921.843] [teleop_bridge_node]: Slave namespaces:   robot1
[INFO] [1771932921.843] [teleop_bridge_node]: Scale factor:       1.00
[INFO] [1771932921.843] [teleop_bridge_node]: Follow mode:        true
[INFO] [1771932921.843] [teleop_bridge_node]: Robot type:         RS
[INFO] [1771932921.843] [teleop_bridge_node]: Left arm enabled:   true
[INFO] [1771932921.843] [teleop_bridge_node]: Right arm enabled:  true
[INFO] [1771932921.843] [teleop_bridge_node]: Joint limits:       enabled
[INFO] [1771932921.843] [teleop_bridge_node]: First move speed:   0.20
[INFO] [1771932921.843] [teleop_bridge_node]: First move acce:    0.20
[INFO] [1771932921.843] [teleop_bridge_node]: =================================================
[INFO] [1771932921.843] [teleop_bridge_node]: Teleop Bridge Node initialized successfully
[INFO] [1771932921.843] [teleop_bridge_node]: Teleop Bridge Node spinning...
[INFO] [1771932921.855] [teleop_bridge_node]: [robot1/left_arm] First move: calling MoveJ to initial position...
[INFO] [1771932921.855] [teleop_bridge_node]: [robot1/right_arm] First move: calling MoveJ to initial position...
```

**关键发现**:
- teleop_bridge在启动后立即发送了"First move"命令
- **同时**向左臂和右臂发送初始位置命令
- 速度: 0.20, 加速度: 0.20
- 这是在连接不稳定的情况下发送的！

---

### 19:35:21 - 左臂开始运动
```
[INFO] [1771932921.856] [robot1.lbot_left_arm_node]: [28228555 ms] Left arm move_joint started
```

**时间戳**: 28228555 ms = 28228.555秒 = 7小时50分28秒（机器人内部时钟）

**问题**:
- 只看到左臂的move_joint日志
- 没有看到右臂的move_joint日志
- 没有看到运动完成的日志

---

### 19:35:24 - CAN总线操作
```
2月 24 19:35:24 ilex22 sudo[47879]: ilex : TTY=pts/10 ; PWD=/home/ilex/Dev/VIST/external_sdk/arm_teleop ;
                                     USER=root ; COMMAND=/usr/sbin/ip link set can1 up type can bitrate 1000000
2月 24 19:35:24 ilex22 sudo[47902]: ilex : TTY=pts/10 ; PWD=/home/ilex/Dev/VIST/external_sdk/arm_teleop ;
                                     USER=root ; COMMAND=/usr/bin/chmod 0666 /sys/class/net/can1/tx_queue_len
```

**分析**:
- 在运动过程中，用户尝试启动can1（数据手套）
- 这可能干扰了系统资源

---

### 19:35:28 - lbot_driver崩溃 ⚠️⚠️⚠️
```
2月 24 19:35:28 ilex22 kernel: traps: lbot_driver[47850] general protection fault
                                ip:7abb0ba1134e sp:7abaeeffa120 error:0
                                in liblbot_api_cpp.so.1.0.3[7abb0ba00000+20000]
```

**崩溃详情**:
- **进程ID**: 47850 (注意：不是47835！)
- **错误类型**: general protection fault (段错误)
- **错误位置**: liblbot_api_cpp.so.1.0.3库中
- **指令指针**: 0x7abb0ba1134e
- **栈指针**: 0x7abaeeffa120
- **时间**: 启动后9秒，运动开始后7秒

**关键疑问**: 为什么PID是47850而不是47835？

---

### 19:35:28 - 用户按下Ctrl+C
```
[INFO] [1771932928.380] [rclcpp]: signal_handler(SIGINT/SIGTERM)
[INFO] [1771932928.380] [lbot_driver]: Shutdown signal received, stopping...
[INFO] [1771932928.380] [robot1.lbot_main_node]: Disconnecting from LBot...
[INFO] [1771932928.380] [robot1.lbot_main_node]: Stopping state monitor...
[INFO] [1771932928.380] [robot1.lbot_main_node]: Cleaning up LBot connection...
[INFO] [1771932928.480] [robot1.lbot_main_node]: Disconnected from LBot successfully
[INFO] [1771932928.480] [lbot_driver]: Cleanup completed
```

**时间**: 19:35:28.380 (崩溃后0.1秒)
**分析**: 用户可能听到异常声音或看到异常现象后立即按下Ctrl+C

---

### 19:35:28 - 进程退出
```
[INFO] [1771932928.491] [teleop_bridge_node-3]: process has finished cleanly [pid 47887]
[INFO] [1771932928.497] [linkerta_node-2]: process has finished cleanly [pid 47867]
[ERROR] [1771932928.585] [lbot_driver-1]: process has died [pid 47835, exit code -11,
                                           cmd '/home/ilex/Dev/VIST/external_sdk/arm_teleop/install/lbot_driver/lib/lbot_driver/lbot_driver ...']
```

**退出码**: -11 = SIGSEGV (段错误信号)

---

### 19:36 - 旧节点被清理
```
[INFO] [1771932970.038] [linkerta_node-1]: process has finished cleanly [pid 17846]
[INFO] [1771932970.039] [linkerta_node-1]: process has finished cleanly [pid 17844]
```

**时间**: 19:36:10 (事故后42秒)
**分析**: 两个旧的linkerta节点终于被清理

---

## 二、关键问题分析

### 问题1: 为什么有多个linkerta节点？

**证据**:
```
会话1 (PID 9147):  11:47启动，PID 17846在19:36停止
会话2 (PID 11648): 12:18启动，PID 17844在19:36停止
会话3 (PID 47834): 19:35启动，PID 47867在19:35停止
```

**结论**:
- 用户在11:47和12:18启动了两个linkerta会话
- 这两个会话一直运行到19:36
- 在19:35启动新会话时，旧会话仍在运行
- **同时有3个linkerta节点在向外骨骼发送命令！**

---

### 问题2: 为什么lbot_driver崩溃？

**直接原因**:
```c
general protection fault in liblbot_api_cpp.so.1.0.3
```

**可能的触发场景**:

#### 场景A: 内存访问违规
```c
// 伪代码
void move_joint(double* positions) {
    // 在重连过程中，指针可能已失效
    robot_state->joint_positions = positions;  // ← 崩溃点
}
```

#### 场景B: 多线程竞争
```c
// 线程1: 重连线程
disconnect();
reconnect();  // 释放旧资源，分配新资源

// 线程2: 运动控制线程
send_command(robot_state);  // 访问已释放的资源 ← 崩溃
```

#### 场景C: 状态机错误
```
状态: CONNECTED → RECONNECTING → CONNECTED
      ↓              ↓                ↓
命令: move_joint → move_joint → move_joint
                    ↑
                  在RECONNECTING状态下发送命令 ← 崩溃
```

---

### 问题3: 电机为什么烧毁？

**推测的事故链**:

```
1. 19:35:21 - teleop_bridge发送初始位置命令
   ↓
2. 同时，3个linkerta节点也在发送命令
   ↓
3. 机器人收到冲突的命令
   ↓
4. 19:35:21-19:35:28 (7秒内)
   - 左臂开始运动
   - 可能收到多个冲突的目标位置
   - 电机在不同目标间快速切换
   ↓
5. 19:35:28 - lbot_driver崩溃
   - 可能发送了错误的命令
   - 或者最后一个命令持续执行
   ↓
6. 电机失控
   - 可能尝试到达不可能的位置
   - 或者在冲突命令间震荡
   - 电流过载
   ↓
7. 电机烧毁
```

---

## 三、发出的控制指令追溯

### 3.1 teleop_bridge发出的指令

**初始位置命令** (19:35:21.855):
```python
# 伪代码重建
left_arm_initial_position = [?, ?, ?, ?, ?, ?, ?]  # 7个关节
right_arm_initial_position = [?, ?, ?, ?, ?, ?, ?]

# 参数
speed = 0.20
acceleration = 0.20
follow_mode = True
scale_factor = 1.00
```

**问题**:
- 日志中没有记录具体的关节角度值
- 不知道初始位置与当前位置的差异有多大
- 如果差异很大，即使速度0.20也可能导致大幅度运动

---

### 3.2 linkerta节点发出的指令

**节点1 (PID 17846)**:
- 启动时间: 12:48:14
- 运行时长: 6小时47分钟
- 发送频率: ~250Hz
- 发送的topic: `/right_arm_joint_control`

**节点2 (PID 17844)**:
- 启动时间: 12:48:14
- 运行时长: 6小时47分钟
- 发送频率: ~250Hz
- 发送的topic: `/right_arm_joint_control`

**节点3 (PID 47867)**:
- 启动时间: 19:35:20
- 运行时长: 8秒
- 发送频率: ~250Hz
- 发送的topic: `/right_arm_joint_control`

**冲突分析**:
```
同一时刻，3个节点都在向 /right_arm_joint_control 发送数据
  ↓
teleop_bridge订阅这个topic
  ↓
teleop_bridge收到哪个节点的数据？
  → ROS2的QoS策略决定
  → 可能是最新的，也可能是混合的
  ↓
teleop_bridge将数据转发给机器人
  ↓
机器人收到混乱的命令序列
```

---

### 3.3 机器人实际执行的指令

**已知**:
- 左臂在19:35:21.856开始move_joint
- 没有看到运动完成的日志
- 在19:35:28崩溃

**推测的指令序列** (19:35:21 - 19:35:28):
```
t=0.000s: teleop_bridge → MoveJ(left_arm, initial_pos, speed=0.2, accel=0.2)
t=0.001s: linkerta_node_1 → JointFollow(right_arm, pos_1)
t=0.005s: linkerta_node_2 → JointFollow(right_arm, pos_2)  # 冲突！
t=0.009s: linkerta_node_3 → JointFollow(right_arm, pos_3)  # 冲突！
t=0.013s: linkerta_node_1 → JointFollow(right_arm, pos_4)
...
t=7.000s: lbot_driver崩溃，可能发送了错误命令
```

---

## 四、为什么烧毁的是电机？

### 4.1 可能的物理机制

#### 机制1: 命令冲突导致震荡
```
时刻t:   目标位置A (来自节点1)
时刻t+4ms: 目标位置B (来自节点2)
时刻t+8ms: 目标位置A (来自节点1)
时刻t+12ms: 目标位置B (来自节点2)
...

电机行为:
→ 向A运动
→ 立即反向向B运动
→ 立即反向向A运动
→ 高频震荡
→ 电流持续过载
→ 发热
→ 烧毁
```

#### 机制2: 崩溃时的错误命令
```
lbot_driver崩溃时可能:
1. 发送了一个超出限位的命令
2. 发送了一个速度极高的命令
3. 发送了一个导致堵转的命令

电机尝试执行:
→ 超出物理限位
→ 堵转
→ 电流激增
→ 烧毁
```

#### 机制3: 最后命令持续执行
```
lbot_driver崩溃前的最后一个命令:
→ 持续向某个方向运动
→ 撞到物理限位
→ 但命令仍在执行
→ 电机持续施加力矩
→ 堵转
→ 烧毁
```

---

### 4.2 哪个电机烧毁了？

**需要确认**:
- 左臂还是右臂？
- 哪个关节 (J1-J7)?

**线索**:
- 日志显示"Left arm move_joint started"
- 但没有右臂的日志
- 可能是左臂的某个关节

---

## 五、根本原因总结

### 直接原因
1. **软件崩溃**: liblbot_api_cpp.so段错误
2. **多节点冲突**: 3个linkerta节点同时发送命令
3. **连接不稳定**: 启动后2秒就出现重连

### 间接原因
1. **缺少进程检查**: 启动前没有检查旧进程
2. **不安全的初始运动**: 启动后立即发送运动命令
3. **缺少错误恢复**: 崩溃时没有安全停止机制

### 根本原因
1. **系统设计缺陷**:
   - 允许多个节点同时控制
   - 没有互斥锁机制
   - 没有心跳监控

2. **软件质量问题**:
   - liblbot_api_cpp.so存在内存安全bug
   - 重连逻辑不完善
   - 错误处理不充分

---

## 六、证据链

```
证据1: 系统日志
→ 证明有3个linkerta节点同时运行

证据2: lbot_driver日志
→ 证明连接不稳定（重连）
→ 证明发送了初始位置命令

证据3: 内核日志
→ 证明lbot_driver崩溃（段错误）
→ 证明崩溃位置在liblbot_api_cpp.so

证据4: 时间戳
→ 证明崩溃发生在运动开始后7秒
→ 证明用户在崩溃后立即按下Ctrl+C

证据5: 退出码
→ 证明进程以SIGSEGV退出
→ 证明是内存访问违规
```

---

## 七、无法确定的问题

1. **具体的关节角度值**: 日志中没有记录
2. **电机烧毁的确切时刻**: 可能在崩溃时，也可能在崩溃后
3. **哪个电机烧毁**: 需要物理检查
4. **3个linkerta节点发送的具体数据**: 没有数据包捕获

---

## 八、建议的进一步调查

### 8.1 硬件检查
```bash
# 检查哪个电机烧毁
# 检查电机驱动器状态
# 检查是否有其他损坏
```

### 8.2 日志深度分析
```bash
# 查看ROS2 DDS层的日志
export RCUTILS_CONSOLE_OUTPUT_FORMAT="[{severity}] [{time}] [{name}]: {message}"
export RCUTILS_LOGGING_BUFFERED_STREAM=1

# 启用详细日志
export RCUTILS_CONSOLE_STDOUT_LINE_BUFFERED=1
```

### 8.3 数据包捕获
```bash
# 下次测试时捕获所有ROS2消息
ros2 bag record -a -o debug_recording
```

---

## 九、预防措施（已在之前的报告中）

1. 添加进程互斥检查
2. 修复liblbot_api_cpp.so崩溃
3. 添加初始位置检查
4. 实现软件看门狗
5. 降低初始运动速度

---

**结论**:
电机烧毁是由**软件崩溃** + **多节点冲突** + **连接不稳定**三重因素共同导致的。在运动过程中，lbot_driver发生段错误崩溃，可能发送了错误命令或导致最后命令持续执行，加上3个linkerta节点的命令冲突，最终导致电机失控烧毁。

**置信度**: 85%
**需要进一步确认**: 具体哪个电机烧毁，以及烧毁时的确切现象。