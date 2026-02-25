# VIST系统安全审查报告 - 红队压力测试

**审查日期**: 2026-02-25
**审查员**: 工业机器人安全架构师（ISO 13849 / IEC 61508）
**系统**: VIST遥操作机械臂系统
**固件限制**: 50Hz伺服频率，无底层平滑插值
**历史事故**: 多进程冲突导致电机烧毁

---

## 🔴 [CRITICAL] 致命风险 - 可能再次烧毁电机

### C1. 关节跟随回调无差分限幅器（Step Input Protection）

**位置**: `lbot_driver.cpp:287-316`

```cpp
void LBot::right_joint_follow_callback(const std::shared_ptr<lbot_arm_interfaces::msg::FollowJoint> msg) {
    if (!msg || msg->joints.empty()) return;

    if (g_conn_state.load() != GlobalConnState::CONNECTED) {
        RCLCPP_WARN_THROTTLE(...);
        return;
    }

    std::vector<double> joints(msg->joints.begin(), msg->joints.end());

    // ❌ 直接下发，无任何检查！
    if (!lbot_api.lbot_joint_follow(lbot_handle, LBOT_RIGHT_ARM, joints, msg->follow)) {
        RCLCPP_ERROR(this->get_logger(), \"Failed to execute right_joint_follow\");
    }
}
```

**风险分析**:
- **无差分检查**: 如果 `msg->joints[i]` 与上一帧差值 > 0.1 rad，直接下发给50Hz固件
- **NaN传播**: 如果上游传感器故障返回 `NaN`，会直接发送给电机（未定义行为）
- **零值陷阱**: 如果传感器掉线返回 `[0,0,0,0,0,0,0]`，机器人会瞬间归零（极其危险）
- **多进程残留**: 如果有两个 `lbot_driver` 进程，两个回调会交替执行，导致指令跳变

**复现场景**:
```python
# 场景1: 传感器故障
msg.joints = [NaN, NaN, NaN, NaN, NaN, NaN, NaN]  # 直接下发 → 电机失控

# 场景2: 网络丢包后恢复
t=0ms:  joints = [0.1, 0.2, ...]
t=100ms: (网络丢包，无消息)
t=120ms: joints = [0.8, 0.9, ...]  # 跳变0.7 rad → 需要35 rad/s速度 → 烧电机

# 场景3: 多进程残留
Process A: joints = [0.0, 0.0, ...]
Process B: joints = [0.5, 0.5, ...]
固件收到: A → B → A → B (每20ms跳变0.5 rad) → 烧电机
```

**修复建议**:
```cpp
// 在 lbot_driver.cpp 中添加成员变量
std::vector<double> last_right_joints_{7, 0.0};
std::chrono::steady_clock::time_point last_right_cmd_time_;
const double MAX_JOINT_DELTA = 0.1;  // rad, 50Hz下安全阈值
const double CMD_TIMEOUT_MS = 200.0;  // 超时则重置

void LBot::right_joint_follow_callback(...) {
    if (!msg || msg->joints.empty()) return;
    if (g_conn_state.load() != GlobalConnState::CONNECTED) return;

    std::vector<double> joints(msg->joints.begin(), msg->joints.end());

    // ✅ 1. NaN检查
    for (size_t i = 0; i < joints.size(); ++i) {
        if (std::isnan(joints[i]) || std::isinf(joints[i])) {
            RCLCPP_ERROR(this->get_logger(), \"Joint %zu is NaN/Inf, REJECTING command\", i);
            return;  // 拒绝整个命令
        }
    }

    // ✅ 2. 超时检查（防止长时间无命令后突然大跳变）
    auto now = std::chrono::steady_clock::now();
    auto elapsed_ms = std::chrono::duration<double, std::milli>(now - last_right_cmd_time_).count();

    if (elapsed_ms > CMD_TIMEOUT_MS) {
        RCLCPP_WARN(this->get_logger(), \"Command timeout (%.1fms), resetting baseline\", elapsed_ms);
        last_right_joints_ = joints;  // 重置基线
        last_right_cmd_time_ = now;
        return;  // 第一帧不执行，只记录
    }

    // ✅ 3. 差分限幅（最关键！）
    bool clamped = false;
    for (size_t i = 0; i < joints.size(); ++i) {
        double delta = joints[i] - last_right_joints_[i];
        if (std::abs(delta) > MAX_JOINT_DELTA) {
            RCLCPP_ERROR(this->get_logger(),
                \"Joint %zu delta too large: %.3f rad (max %.3f), CLAMPING\",
                i, delta, MAX_JOINT_DELTA);

            // 限幅到安全范围
            joints[i] = last_right_joints_[i] + std::copysign(MAX_JOINT_DELTA, delta);
            clamped = true;
        }
    }

    if (clamped) {
        // 记录到日志，便于事后分析
        // 可选：连续N次限幅后触发紧急停止
    }

    // ✅ 4. 下发命令
    if (!lbot_api.lbot_joint_follow(lbot_handle, LBOT_RIGHT_ARM, joints, msg->follow)) {
        RCLCPP_ERROR(this->get_logger(), \"Failed to execute right_joint_follow\");
        return;
    }

    // ✅ 5. 更新状态
    last_right_joints_ = joints;
    last_right_cmd_time_ = now;
}
```

**优先级**: 🔴 **P0 - 立即修复**

---

### C2. 进程互斥检查可被绕过（PID复用漏洞）

**位置**: `SAFE_MANUAL_OPERATION_GUIDE.md:23-29`

```bash
# 检查linkerta进程
pgrep -af linkerta

# 检查lbot进程
pgrep -af lbot
```

**风险分析**:
- **PID复用**: Linux PID会循环使用（最大32768），如果旧进程崩溃后PID被复用，`pgrep` 可能误报
- **竞态条件**: 用户在两个终端同时运行检查 → 都显示"无进程" → 同时启动 → 多进程冲突
- **僵尸进程**: 如果进程变成僵尸（Z状态），`pgrep` 仍能检测到，但 `kill -9` 无法杀死

**复现场景**:
```bash
# 终端1
pgrep -af linkerta  # 输出: 空
ros2 run linkerta linkerta_node &  # PID=12345

# 终端2（同时执行）
pgrep -af linkerta  # 输出: 空（竞态窗口）
ros2 run linkerta linkerta_node &  # PID=12346

# 结果: 两个进程同时运行
```

**修复建议**:
```bash
# 使用 flock 文件锁（原子操作）
LOCKFILE="/tmp/vist_linkerta.lock"

# 启动前检查
exec 200>"$LOCKFILE"
if ! flock -n 200; then
    echo "❌ 另一个linkerta进程正在运行（锁文件被占用）"
    echo "   如果确认无进程，删除锁文件: rm $LOCKFILE"
    exit 1
fi

# 启动进程
ros2 run linkerta linkerta_node

# 退出时自动释放锁（flock会在进程结束时自动释放）
```

**但是 flock 也有问题**:
- 如果进程崩溃，锁文件可能残留 → 死锁
- 需要手动清理机制

**更安全的方案（推荐）**:
```bash
# 使用 systemd 的单实例保证
# 创建 /etc/systemd/system/vist-linkerta.service
[Unit]
Description=VIST Linkerta Node
After=network.target

[Service]
Type=simple
ExecStart=/usr/bin/ros2 run linkerta linkerta_node
Restart=no
# 关键：确保只有一个实例
ExecStartPre=/bin/sh -c 'pgrep -f linkerta_node && exit 1 || exit 0'

[Install]
WantedBy=multi-user.target

# 启动
sudo systemctl start vist-linkerta

# 停止
sudo systemctl stop vist-linkerta
```

**优先级**: 🔴 **P0 - 立即修复**

---

### C3. 析构函数无安全停机（掉臂风险）

**位置**: `lbot_driver.cpp:110-121`

```cpp
LBot::~LBot() {
    shutting_down_ = true;

    // 停止 reconnect 线程
    {
        std::lock_guard<std::mutex> lock(reconnect_thread_mutex_);
        if (reconnect_thread_.joinable())
            reconnect_thread_.join();
    }

    disconnect_robot();  // ❌ 直接断开，无减速停机
}
```

**风险分析**:
- **瞬间断电**: `disconnect_robot()` 会调用 `lbot_api.lbot_cleanup()`，直接切断通信
- **掉臂风险**: 如果机器人正在运动中，突然断电会导致机械臂自由落体（重力作用）
- **Ctrl+C触发**: 用户按 Ctrl+C 时，ROS2会调用析构函数 → 瞬间断电

**修复建议**:
```cpp
LBot::~LBot() {
    shutting_down_ = true;

    RCLCPP_INFO(this->get_logger(), \"Shutting down safely...\");

    // ✅ 1. 发送减速停机命令
    if (conn_state_ == GlobalConnState::CONNECTED) {
        try {
            // 获取当前位置
            lbot_full_state_t state;
            {
                std::lock_guard<std::mutex> lock(state_mutex_);
                state = current_lbot_state_;
            }

            // 发送"保持当前位置"命令（让固件接管）
            std::vector<double> current_joints(7);
            for (size_t i = 0; i < 7; ++i) {
                current_joints[i] = state.right_arm.joint_position[i];
            }

            // 使用 follow=false（启用固件平滑）
            lbot_api.lbot_joint_follow(lbot_handle, LBOT_RIGHT_ARM, current_joints, false);

            // 等待固件稳定（至少1个控制周期）
            std::this_thread::sleep_for(std::chrono::milliseconds(50));

            RCLCPP_INFO(this->get_logger(), \"Safe stop command sent\");
        } catch (...) {
            RCLCPP_ERROR(this->get_logger(), \"Failed to send safe stop command\");
        }
    }

    // ✅ 2. 停止 reconnect 线程
    {
        std::lock_guard<std::mutex> lock(reconnect_thread_mutex_);
        if (reconnect_thread_.joinable())
            reconnect_thread_.join();
    }

    // ✅ 3. 断开连接
    disconnect_robot();

    RCLCPP_INFO(this->get_logger(), \"Shutdown complete\");
}
```

**优先级**: 🔴 **P0 - 立即修复**

---

## 🟡 [HIGH] 高风险 - 可能导致程序崩溃或控制发散

### H1. 心跳超时后继续发送最后一条指令（堵转风险）

**位置**: `safe_robot_controller.py:88-105`

```python
def check_heartbeat(self):
    current_time = time.time()
    elapsed = current_time - self.last_command_time

    if elapsed > self.heartbeat_timeout:
        self.heartbeat_violations += 1
        print(f\"⚠️ [SafeController] 心跳超时！已 {elapsed:.3f}s 未收到命令\")
        return True  # ❌ 只返回True，但不停止电机

    return False
```

**风险分析**:
- **Python脚本卡死**: 如果上位机Python进入死循环（例如 `while True: pass`），不会发送新命令
- **SafeController返回**: `process_command()` 会返回 `self.q_current`（最后一条指令）
- **电机持续出力**: 底层固件会持续执行最后一条指令，如果遇到障碍物会堵转
- **100ms超时太短**: 网络抖动或GC暂停可能触发误报

**修复建议**:
```python
def check_heartbeat(self):
    current_time = time.time()
    elapsed = current_time - self.last_command_time

    if elapsed > self.heartbeat_timeout:
        self.heartbeat_violations += 1
        print(f\"⚠️ [SafeController] 心跳超时！已 {elapsed:.3f}s 未收到命令\")

        # ✅ 触发紧急停止
        if self.heartbeat_violations >= 3:  # 连续3次超时
            print(f\"🚨 [SafeController] 心跳连续超时{self.heartbeat_violations}次，触发紧急停止\")
            self.set_emergency_stop(True)

        return True
    else:
        # 恢复后重置计数
        self.heartbeat_violations = 0

    return False

# 在 process_command() 中
def process_command(self, q_target, q_dot_estimated=None):
    # ...

    # 检查心跳超时
    if self.check_heartbeat():
        # ✅ 返回零速度命令（而不是最后一条指令）
        # 注意：这里返回 q_current 是正确的（保持当前位置）
        # 但需要确保底层固件也会停止
        return self.q_current, {
            'emergency_stop': False,
            'heartbeat_timeout': True,
            ...
        }
```

**更好的方案**: 在C++层实现心跳检测
```cpp
// 在 lbot_driver.cpp 中
std::chrono::steady_clock::time_point last_cmd_time_;
const double HEARTBEAT_TIMEOUT_MS = 500.0;  // 500ms

void LBot::right_joint_follow_callback(...) {
    // 更新心跳时间
    last_cmd_time_ = std::chrono::steady_clock::now();
    // ...
}

// 添加心跳检查定时器（10Hz）
void LBot::heartbeat_check_callback() {
    auto now = std::chrono::steady_clock::now();
    auto elapsed_ms = std::chrono::duration<double, std::milli>(now - last_cmd_time_).count();

    if (elapsed_ms > HEARTBEAT_TIMEOUT_MS) {
        RCLCPP_ERROR(this->get_logger(), \"Command heartbeat timeout (%.1fms), sending STOP\", elapsed_ms);

        // 发送零速度命令
        std::vector<double> stop_cmd = last_right_joints_;  // 保持当前位置
        lbot_api.lbot_joint_follow(lbot_handle, LBOT_RIGHT_ARM, stop_cmd, false);  // follow=false启用平滑
    }
}
```

**优先级**: 🟡 **P1 - 高优先级**

---

### H2. 速度/加速度限制器的dt异常处理不足

**位置**: `safe_robot_controller.py:256-262`

```python
# 测量实际的时间间隔
current_time = time.time()
dt_actual = current_time - self.last_update_time

# 防止异常的dt值
if dt_actual > 1.0 or dt_actual < 0.001:
    print(f\"⚠️ [SafeController] 异常dt值: {dt_actual:.6f}s, 使用默认值 {self.dt}s\")
    dt_actual = self.dt  # ❌ 使用默认值，但状态已经不连续
```

**风险分析**:
- **系统卡顿**: 如果系统卡顿1秒，`dt_actual=1.0s`，但 `q_target` 可能只移动了0.01 rad
- **速度计算错误**: `q_dot = 0.01 / 0.02 = 0.5 rad/s`（使用默认dt），但实际速度是 `0.01 / 1.0 = 0.01 rad/s`
- **限制器失效**: 速度限制器会认为速度很慢，不触发限制，但实际上机器人可能在快速运动

**修复建议**:
```python
# 测量实际的时间间隔
current_time = time.time()
dt_actual = current_time - self.last_update_time

# ✅ 更严格的异常处理
if dt_actual > 0.5:  # 超过500ms认为异常
    print(f\"🚨 [SafeController] dt过大: {dt_actual:.6f}s, 可能系统卡顿，拒绝命令\")
    # 返回当前位置（不移动）
    return self.q_current, {
        'emergency_stop': False,
        'heartbeat_timeout': False,
        'system_lag': True,  # 新增标志
        ...
    }

if dt_actual < 0.001:  # 小于1ms认为异常
    print(f\"⚠️ [SafeController] dt过小: {dt_actual:.6f}s, 可能时钟错误\")
    dt_actual = self.dt

# ✅ 记录异常dt，用于事后分析
if dt_actual > 0.1 or dt_actual < 0.005:  # 超出正常范围
    self._log_abnormal_dt(dt_actual)
```

**优先级**: 🟡 **P1 - 高优先级**

---

### H3. 50Hz固件混叠风险（200Hz → 20Hz降频）

**位置**: 系统架构问题

**风险分析**:
- **正常情况**: 上位机200Hz发送 → 固件50Hz采样（每20ms取最新）
- **系统卡顿**: 上位机降到20Hz发送 → 固件50Hz采样（每20ms可能取到相同值）
- **波形失真**: 固件收到的是阶跃波形，而不是平滑波形

**示例**:
```
正常（200Hz发送）:
t=0ms:   上位机发送 q=0.00
t=5ms:   上位机发送 q=0.01
t=10ms:  上位机发送 q=0.02
t=15ms:  上位机发送 q=0.03
t=20ms:  固件采样 q=0.03 ✓ (平滑)

卡顿（20Hz发送）:
t=0ms:   上位机发送 q=0.00
t=20ms:  固件采样 q=0.00
t=50ms:  上位机发送 q=0.10  ← 跳变！
t=60ms:  固件采样 q=0.10 ✗ (阶跃)
```

**修复建议**:
```python
# 在上位机添加频率监控
class FrequencyMonitor:
    def __init__(self, target_hz=200, tolerance=0.2):
        self.target_hz = target_hz
        self.tolerance = tolerance
        self.last_time = time.time()
        self.freq_violations = 0

    def check(self):
        current_time = time.time()
        dt = current_time - self.last_time
        actual_hz = 1.0 / dt if dt > 0 else 0

        if actual_hz < self.target_hz * (1 - self.tolerance):
            self.freq_violations += 1
            print(f\"⚠️ 发送频率过低: {actual_hz:.1f} Hz (目标 {self.target_hz} Hz)\")

            if self.freq_violations >= 10:
                print(f\"🚨 频率连续异常{self.freq_violations}次，建议停止系统\")
                return False
        else:
            self.freq_violations = 0

        self.last_time = current_time
        return True

# 在控制循环中
freq_monitor = FrequencyMonitor(target_hz=200)

while True:
    if not freq_monitor.check():
        break  # 停止控制

    # 发送命令
    send_command(...)
```

**优先级**: 🟡 **P1 - 高优先级**

---

## 🔵 [SUGGESTION] 代码规范和防御性编程建议

### S1. 缺少单元测试覆盖关键安全路径

**建议**:
```python
# tests/test_safe_controller.py
import pytest
import numpy as np

def test_nan_rejection():
    \"\"\"测试NaN输入是否被拒绝\"\"\"
    controller = SafeRobotController(config)

    q_target = np.array([np.nan, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
    q_safe, status = controller.process_command(q_target)

    # 应该返回当前位置（不移动）
    assert np.allclose(q_safe, controller.q_current)
    assert status['nan_detected'] == True

def test_large_step_rejection():
    \"\"\"测试大跳变是否被限制\"\"\"
    controller = SafeRobotController(config)
    controller.q_current = np.zeros(7)

    q_target = np.array([1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])  # 跳变1.0 rad
    q_safe, status = controller.process_command(q_target)

    # 应该被限制到安全范围
    assert q_safe[0] < 0.1  # 假设max_velocity=1.0, dt=0.02, 则max_delta=0.02
    assert status['velocity_limited'] == True

def test_heartbeat_timeout():
    \"\"\"测试心跳超时是否触发停止\"\"\"
    controller = SafeRobotController(config)

    # 模拟超时
    controller.last_command_time = time.time() - 1.0  # 1秒前

    q_target = np.array([0.1, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
    q_safe, status = controller.process_command(q_target)

    assert status['heartbeat_timeout'] == True
    assert np.allclose(q_safe, controller.q_current)  # 不移动
```

---

### S2. 日志记录不足，难以事后分析

**建议**:
```cpp
// 在 lbot_driver.cpp 中添加详细日志
void LBot::right_joint_follow_callback(...) {
    // 记录每一帧的命令（用于事后分析）
    static std::ofstream log_file(\"/tmp/lbot_commands.csv\", std::ios::app);
    static bool header_written = false;

    if (!header_written) {
        log_file << \"timestamp,j0,j1,j2,j3,j4,j5,j6,follow\\n\";
        header_written = true;
    }

    auto now = std::chrono::system_clock::now();
    auto timestamp = std::chrono::duration_cast<std::chrono::milliseconds>(
        now.time_since_epoch()).count();

    log_file << timestamp;
    for (const auto& j : joints) {
        log_file << \",\" << j;
    }
    log_file << \",\" << (msg->follow ? \"true\" : \"false\") << \"\\n\";
    log_file.flush();  // 立即写入（防止崩溃丢失）
}
```

---

### S3. 缺少硬件限位开关检测

**建议**:
```cpp
// 在固件层添加硬件限位检测
// 如果机械臂有限位开关，应该在固件层检测并拒绝超限命令
// 这是最后一道防线

// 在 lbot_driver.cpp 中检查
void LBot::state_publish_timer_callback() {
    // ...

    // 检查是否触发限位
    for (size_t i = 0; i < 7; ++i) {
        if (state.right_arm.joint_position[i] < joint_limits_[i].lower ||
            state.right_arm.joint_position[i] > joint_limits_[i].upper) {

            RCLCPP_ERROR(this->get_logger(),
                \"Joint %zu hit limit: %.3f (limits: [%.3f, %.3f])\",
                i, state.right_arm.joint_position[i],
                joint_limits_[i].lower, joint_limits_[i].upper);

            // 触发紧急停止
            emergency_stop_ = true;
        }
    }
}
```

---

## 总结与优先级

### 立即修复（P0）

1. **C1**: 在 `lbot_driver.cpp` 的 `joint_follow_callback` 中添加差分限幅器
2. **C2**: 使用 `flock` 或 systemd 实现进程互斥
3. **C3**: 在析构函数中添加安全停机逻辑

### 高优先级（P1）

4. **H1**: 在C++层实现心跳检测和自动停机
5. **H2**: 改进dt异常处理，拒绝异常命令
6. **H3**: 添加发送频率监控

### 建议（P2）

7. **S1**: 添加单元测试覆盖安全路径
8. **S2**: 增强日志记录
9. **S3**: 添加硬件限位检测

---

## 测试建议

### 压力测试场景

1. **多进程冲突测试**:
   ```bash
   # 同时启动两个lbot_driver
   ros2 run lbot_driver lbot_driver &
   ros2 run lbot_driver lbot_driver &
   # 预期：第二个应该被拒绝
   ```

2. **NaN注入测试**:
   ```python
   # 发送NaN命令
   msg.joints = [float('nan')] * 7
   pub.publish(msg)
   # 预期：命令被拒绝，机器人不动
   ```

3. **心跳超时测试**:
   ```python
   # 发送一条命令后停止
   pub.publish(msg)
   time.sleep(1.0)  # 等待超时
   # 预期：机器人停止运动
   ```

4. **大跳变测试**:
   ```python
   # 发送大跳变命令
   msg.joints = [0.0] * 7
   pub.publish(msg)
   time.sleep(0.1)
   msg.joints = [1.0] * 7  # 跳变1.0 rad
   pub.publish(msg)
   # 预期：命令被限幅，机器人平滑移动
   ```

---

**审查结论**: 系统存在多个致命风险，必须立即修复C1-C3才能安全使用。