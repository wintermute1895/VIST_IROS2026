# 多线程架构与通信优化方案

**日期**: 2026-02-18
**目标**: 使用成熟的工业方案优化VIST系统性能

---

## 🧵 多线程架构（最优配置）

### 线程配置

你的系统应该运行**4个线程**：

```
┌─────────────────────────────────────────────────────────┐
│                    主线程（Main）                        │
│  - 初始化系统                                            │
│  - 启动子线程                                            │
│  - 等待Ctrl+C                                           │
│  - 清理资源                                              │
└─────────────────────────────────────────────────────────┘
                          │
        ┌─────────────────┼─────────────────┬──────────────┐
        │                 │                 │              │
        ▼                 ▼                 ▼              ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│ 视觉线程      │  │ 控制线程      │  │ 可视化线程    │  │ 统计线程      │
│ (30Hz)       │  │ (100Hz)      │  │ (10Hz)       │  │ (1Hz)        │
│              │  │              │  │              │  │              │
│ UDP接收      │  │ VIST处理     │  │ 渲染显示     │  │ 性能监控     │
│ 关键点数据   │  │ 命令发送     │  │              │  │              │
└──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘
        │                 ▲                                    │
        └─────────────────┘                                    │
          deque(maxlen=1)                                      │
          + threading.Lock                                     │
                                                               │
                                    打印性能统计 ◄──────────────┘
```

### 线程详细说明

#### 1. 视觉线程（Vision Thread）- 30Hz
**职责**:
- 接收UDP数据包（人体关键点）
- 解析数据（MessagePack）
- 更新共享队列

**频率**: 30Hz（33ms/帧）
**优先级**: 中等
**为什么30Hz**: MediaPipe手部检测的典型输出频率

```python
def vision_thread(self):
    frame_time = 1.0 / 30.0  # 30Hz
    while self.running:
        loop_start = time.time()

        # 接收UDP数据
        keypoints = self.robot.receive_keypoints()

        if keypoints is not None:
            # 线程安全更新
            with self.keypoints_lock:
                self.keypoints_queue.clear()
                self.keypoints_queue.append(keypoints)

        # 精确定时
        elapsed = time.time() - loop_start
        if elapsed < frame_time:
            time.sleep(frame_time - elapsed)
```

---

#### 2. 控制线程（Control Thread）- 100Hz
**职责**:
- 读取最新关键点数据
- VIST算法处理（IK + 滤波 + 安全检查）
- 发送命令到机器人

**频率**: 100Hz（10ms/帧）
**优先级**: 最高
**为什么100Hz**: 受`move_joint()`限制，这是最优频率

```python
def control_thread(self):
    frame_time = 1.0 / 100.0  # 100Hz = 10ms
    last_keypoints = None

    while self.running:
        loop_start = time.time()

        # 读取最新数据
        with self.keypoints_lock:
            keypoints = self.keypoints_queue[0] if self.keypoints_queue else None

        if keypoints:
            last_keypoints = keypoints
            q_safe, success, _ = self.controller.process(keypoints)
            if success:
                self.robot.send_command(q_safe)
        elif last_keypoints:
            # 使用上一帧数据继续控制
            q_safe, success, _ = self.controller.process(last_keypoints)
            if success:
                self.robot.send_command(q_safe)

        # 精确定时
        elapsed = time.time() - loop_start
        if elapsed < frame_time:
            time.sleep(frame_time - elapsed)
```

---

#### 3. 可视化线程（Visualization Thread）- 10Hz（可选）
**职责**:
- 更新3D可视化
- 渲染机器人状态

**频率**: 10Hz（100ms/帧）
**优先级**: 最低
**为什么10Hz**: 人眼感知足够，不影响控制

```python
def visualization_thread(self):
    frame_time = 1.0 / 10.0  # 10Hz
    while self.running:
        loop_start = time.time()

        if self.visualizer:
            self.visualizer.update(self.controller.q_current)

        elapsed = time.time() - loop_start
        if elapsed < frame_time:
            time.sleep(frame_time - elapsed)
```

---

#### 4. 统计线程（Stats Thread）- 1Hz（可选）
**职责**:
- 计算实际帧率
- 打印性能统计
- 监控系统健康

**频率**: 1Hz（1秒/次）
**优先级**: 最低

```python
def stats_thread(self):
    while self.running:
        time.sleep(1.0)

        # 计算帧率
        vision_fps = self.vision_frame_count / 1.0
        control_fps = self.control_frame_count / 1.0

        print(f"📊 视觉={vision_fps:.1f}Hz, 控制={control_fps:.1f}Hz")

        # 重置计数器
        self.vision_frame_count = 0
        self.control_frame_count = 0
```

---

## 📡 通信优化（成熟工业方案）

### 1. UDP通信优化

#### 数据包格式（标准方案）
```python
packet = {
    'seq': 12345,              # 序列号（检测丢包）
    'timestamp': 1234567890.123,  # 时间戳（检测延迟）
    'keypoints': {             # 实际数据
        'wrist': [x, y, z],
        'elbow': [x, y, z],
        ...
    }
}
```

#### 序列化方案：MessagePack（工业标准）
**为什么选MessagePack**:
- 比JSON快5-10倍
- 二进制格式，体积小30-50%
- 跨语言支持（Python, C++, JavaScript等）
- 无需schema定义（比Protobuf简单）

**安装**:
```bash
pip install msgpack
```

**发送端**:
```python
import msgpack
import socket
import time

class UDPSender:
    def __init__(self, host="127.0.0.1", port=6001):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.host = host
        self.port = port
        self.seq = 0

    def send(self, keypoints):
        packet = {
            'seq': self.seq,
            'timestamp': time.time(),
            'keypoints': keypoints
        }
        self.seq += 1

        data = msgpack.packb(packet)
        self.sock.sendto(data, (self.host, self.port))
```

**接收端**:
```python
import msgpack
import socket

class UDPReceiver:
    def __init__(self, host="0.0.0.0", port=6001):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((self.host, self.port))
        self.sock.setblocking(False)

        # 设置缓冲区（避免旧数据堆积）
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 65536)

        # 丢包统计
        self.last_seq = -1
        self.total_packets = 0
        self.lost_packets = 0

    def receive(self):
        try:
            data, addr = self.sock.recvfrom(65536)
            packet = msgpack.unpackb(data, raw=False)

            # 丢包检测
            seq = packet['seq']
            self.total_packets += 1

            if self.last_seq >= 0 and seq != self.last_seq + 1:
                lost = seq - self.last_seq - 1
                self.lost_packets += lost
                loss_rate = (self.lost_packets / self.total_packets) * 100
                print(f"⚠️ 丢包率: {loss_rate:.2f}%")

            self.last_seq = seq

            # 延迟检测
            latency = (time.time() - packet['timestamp']) * 1000
            if latency > 50:
                print(f"⚠️ 高延迟: {latency:.1f}ms")

            return packet['keypoints']

        except BlockingIOError:
            return None
```

---

### 2. TCP连接健康检查（标准方案）

#### 心跳检测机制
```python
class ConnectionHealthMonitor:
    def __init__(self, timeout=1.0):
        self.last_heartbeat = time.time()
        self.timeout = timeout
        self.alive = True

    def update(self):
        """收到数据时调用"""
        self.last_heartbeat = time.time()
        self.alive = True

    def check(self):
        """定期检查"""
        if time.time() - self.last_heartbeat > self.timeout:
            self.alive = False
            return False
        return True
```

#### 自动重连机制
```python
class AutoReconnect:
    def __init__(self, max_attempts=3, interval=5.0):
        self.max_attempts = max_attempts
        self.interval = interval
        self.attempts = 0

    def try_reconnect(self, connect_func):
        """尝试重连"""
        if self.attempts >= self.max_attempts:
            return False

        self.attempts += 1
        print(f"🔄 重连尝试 {self.attempts}/{self.max_attempts}")

        if connect_func():
            self.attempts = 0
            return True

        time.sleep(self.interval)
        return False
```

---

## 🔧 线程同步（标准方案）

### 数据传递：deque + Lock
```python
from collections import deque
import threading

# 共享数据结构
keypoints_queue = deque(maxlen=1)  # 只保留最新数据
keypoints_lock = threading.Lock()

# 写入（视觉线程）
with keypoints_lock:
    keypoints_queue.clear()
    keypoints_queue.append(new_data)

# 读取（控制线程）
with keypoints_lock:
    data = keypoints_queue[0] if keypoints_queue else None
```

**为什么用deque(maxlen=1)**:
- 自动丢弃旧数据，避免延迟累积
- O(1)时间复杂度
- 线程安全（配合Lock）

---

## 📊 性能预期

| 指标 | 当前（串行） | 优化后（多线程） | 提升 |
|------|-------------|----------------|------|
| 控制频率 | 37Hz | 100Hz | 2.7倍 |
| 响应延迟 | 27ms | 10ms | 2.7倍 |
| UDP解析 | 10-20ms | 1-2ms | 10倍 |
| 丢包检测 | ❌ | ✅ | - |
| 连接监控 | ❌ | ✅ | - |
| CPU利用率 | 单核 | 多核 | 3倍 |

---

## 🚀 实施步骤

### 第1步：创建多线程控制器（3小时）

1. 创建文件：`src/control/threaded_vist_controller.py`
2. 复制文档中的完整代码（已在SDK_ARCHITECTURE_AND_IMPROVEMENTS.md中）
3. 测试基本功能

### 第2步：优化UDP通信（1小时）

1. 安装MessagePack：`pip install msgpack`
2. 修改发送端（视觉节点）：添加序列号和时间戳
3. 修改接收端（`src/communication/udp_receiver.py`）：使用MessagePack解析
4. 测试丢包检测

### 第3步：添加连接监控（1小时）

1. 在`src/robot/arm_driver.py`中添加心跳检测
2. 实现自动重连逻辑
3. 测试断网恢复

### 第4步：集成测试（1小时）

1. 修改主程序使用多线程控制器
2. 运行完整测试
3. 观察性能统计
4. 调优参数

---

## ✅ 验收标准

运行系统后，应该看到：

```
🚀 准备启动多线程遥操作控制
================================================================================

⚠️  安全提示：
   1. 确保机器人周围无障碍物
   2. 确保紧急停止按钮可用
   3. 确保视觉节点正在运行
   4. 按 Ctrl+C 可随时停止

⏱️  10 秒后开始遥操作
   🚀 开始遥操作！

🎥 视觉线程启动
🤖 控制线程启动
📊 可视化线程启动

✅ 所有线程已启动
   - 视觉线程: 运行中
   - 控制线程: 运行中
   - 可视化线程: 运行中

📊 性能统计: 视觉=29.8Hz, 控制=98.5Hz
📊 性能统计: 视觉=30.1Hz, 控制=99.2Hz
📊 性能统计: 视觉=29.9Hz, 控制=100.1Hz
```

**成功指标**:
- ✅ 视觉线程稳定在29-31Hz
- ✅ 控制线程稳定在95-105Hz
- ✅ 无丢包或丢包率<1%
- ✅ 延迟<15ms
- ✅ 机器人响应流畅，无卡顿

---

## 📝 总结

这套方案使用的都是**成熟的工业标准**：

1. **多线程架构**: 生产者-消费者模式（经典并发模式）
2. **UDP优化**: 序列号+时间戳（网络协议标准）
3. **序列化**: MessagePack（工业标准，广泛应用）
4. **线程同步**: deque+Lock（Python标准库）
5. **心跳检测**: 定期检查+自动重连（网络编程标准）

**无需创新，直接使用即可达到最优性能。**