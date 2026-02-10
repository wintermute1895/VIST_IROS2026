# VIST 性能优化方案

## 1. 李代数（Lie Algebra）加速

### 1.1 为什么使用李代数？

**当前问题**：
- 旋转矩阵 R ∈ SO(3) 有约束（正交性、行列式=1）
- 卡尔曼滤波中直接对 R 进行线性运算会破坏约束
- 需要频繁进行正交化（计算昂贵）

**李代数解决方案**：
- 使用李代数 so(3) 表示旋转（无约束的 3D 向量）
- 在李代数空间进行线性运算（卡尔曼滤波）
- 通过指数映射 exp: so(3) → SO(3) 转回旋转矩阵

### 1.2 Pinocchio 中的李代数支持

Pinocchio 已经内置了李群/李代数支持：

```python
import pinocchio as pin

# 1. SE(3) 李群（刚体变换）
M = pin.SE3.Random()  # 随机刚体变换

# 2. 李代数 se(3)（6D 向量：平移速度 + 角速度）
v = pin.Motion.Random()  # 6D 速度向量

# 3. 指数映射：se(3) → SE(3)
M_from_v = pin.exp(v)

# 4. 对数映射：SE(3) → se(3)
v_from_M = pin.log(M)

# 5. 李代数上的插值（比旋转矩阵插值更高效）
M1 = pin.SE3.Random()
M2 = pin.SE3.Random()
alpha = 0.5
M_interp = M1.act(pin.exp(alpha * pin.log(M1.actInv(M2))))
```

### 1.3 在 VIST 中应用李代数

#### 应用 1: 卡尔曼滤波状态表示

**当前实现**（`vist_kalman_filter.py`）：
```python
# 状态向量: [θ, θ̇] ∈ R^14
x = np.concatenate([q, q_dot])
```

**李代数优化**：
```python
# 状态向量: [q_joints, ξ] ∈ R^(n+6)
# q_joints: 关节角度
# ξ ∈ se(3): 末端速度（李代数表示）

# 优点：
# 1. 避免旋转矩阵约束
# 2. 速度表示更自然
# 3. 卡尔曼滤波线性运算有效
```

#### 应用 2: 旋转插值

**当前实现**（可能存在的问题）：
```python
# 线性插值旋转矩阵（错误！）
R_interp = (1 - alpha) * R1 + alpha * R2  # 破坏正交性
```

**李代数优化**：
```python
# 在 SO(3) 上的正确插值（SLERP）
def slerp_rotation(R1, R2, alpha):
    """使用李代数进行旋转插值"""
    # 1. 计算相对旋转
    R_rel = R1.T @ R2

    # 2. 转换到李代数（轴角表示）
    omega = pin.log3(R_rel)  # ∈ so(3)

    # 3. 在李代数空间插值
    omega_interp = alpha * omega

    # 4. 转回 SO(3)
    R_rel_interp = pin.exp3(omega_interp)

    return R1 @ R_rel_interp
```

#### 应用 3: 速度计算

**当前实现**：
```python
# 数值微分（噪声大）
v = (pos_new - pos_old) / dt
```

**李代数优化**：
```python
# 使用李代数计算速度
def compute_velocity_lie(M_old, M_new, dt):
    """使用李代数计算刚体速度"""
    # M_old, M_new ∈ SE(3)

    # 1. 计算相对变换
    M_rel = M_old.actInv(M_new)

    # 2. 转换到李代数
    v = pin.log(M_rel)  # ∈ se(3)

    # 3. 除以时间得到速度
    return v / dt
```

### 1.4 实现建议

**优先级 1: 旋转插值**（立即可做）
```python
# src/utils/lie_algebra.py
import pinocchio as pin
import numpy as np

def slerp_SE3(M1: pin.SE3, M2: pin.SE3, alpha: float) -> pin.SE3:
    """
    在 SE(3) 上进行球面线性插值

    Args:
        M1, M2: 两个刚体变换
        alpha: 插值参数 [0, 1]

    Returns:
        插值后的变换
    """
    M_rel = M1.actInv(M2)
    v = pin.log(M_rel)
    return M1.act(pin.exp(alpha * v))

def slerp_rotation(R1: np.ndarray, R2: np.ndarray, alpha: float) -> np.ndarray:
    """
    在 SO(3) 上进行球面线性插值

    Args:
        R1, R2: 两个旋转矩阵 (3x3)
        alpha: 插值参数 [0, 1]

    Returns:
        插值后的旋转矩阵
    """
    R_rel = R1.T @ R2
    omega = pin.log3(R_rel)
    R_rel_interp = pin.exp3(alpha * omega)
    return R1 @ R_rel_interp
```

**优先级 2: 卡尔曼滤波状态表示**（中期）
- 需要重构 `VISTKalmanFilter`
- 状态向量改为 [q_joints, ξ]
- 观测模型需要调整

**优先级 3: 速度估计**（中期）
- 使用李代数计算末端速度
- 替代数值微分

### 1.5 预期收益

| 优化项 | 计算加速 | 精度提升 | 实现难度 |
|--------|----------|----------|----------|
| 旋转插值 | 10-20% | 显著 | 低 |
| 速度计算 | 5-10% | 中等 | 低 |
| 卡尔曼滤波 | 20-30% | 显著 | 高 |

---

## 2. 计算加速工具

### 2.1 Numba JIT 编译

**原理**：将 Python 代码即时编译为机器码

**应用场景**：
- 卡尔曼滤波的矩阵运算
- 运动映射的向量计算
- IK 求解的迭代循环

**示例**：
```python
from numba import jit
import numpy as np

@jit(nopython=True, cache=True)
def kalman_predict(x, P, F, Q):
    """
    卡尔曼预测步骤（Numba 加速）

    加速比: 10-50x
    """
    x_pred = F @ x
    P_pred = F @ P @ F.T + Q
    return x_pred, P_pred

@jit(nopython=True, cache=True)
def kalman_update(x_pred, P_pred, z, H, R):
    """
    卡尔曼更新步骤（Numba 加速）

    加速比: 10-50x
    """
    y = z - H @ x_pred
    S = H @ P_pred @ H.T + R
    K = P_pred @ H.T @ np.linalg.inv(S)
    x = x_pred + K @ y
    P = (np.eye(len(x)) - K @ H) @ P_pred
    return x, P, K
```

**实现步骤**：
1. 安装 Numba: `pip install numba`
2. 识别热点函数（使用 cProfile）
3. 添加 `@jit` 装饰器
4. 测试性能提升

**注意事项**：
- Numba 不支持所有 NumPy 函数
- 不支持 Pinocchio（C++ 库）
- 适合纯 NumPy 计算

### 2.2 CuPy GPU 加速

**原理**：使用 GPU 并行计算矩阵运算

**应用场景**：
- 大规模矩阵运算（如果状态维度很高）
- 批量 IK 求解
- 图像处理（目标检测）

**示例**：
```python
import cupy as cp

# 将 NumPy 数组转换为 CuPy 数组（GPU）
x_gpu = cp.asarray(x)
P_gpu = cp.asarray(P)

# GPU 上的矩阵运算
x_pred_gpu = F_gpu @ x_gpu
P_pred_gpu = F_gpu @ P_gpu @ F_gpu.T + Q_gpu

# 转回 CPU
x_pred = cp.asnumpy(x_pred_gpu)
```

**实现步骤**：
1. 安装 CuPy: `pip install cupy-cuda12x`（根据 CUDA 版本）
2. 修改 `VISTKalmanFilter` 支持 GPU
3. 测试性能提升

**注意事项**：
- 需要 NVIDIA GPU
- CPU-GPU 数据传输有开销
- 只有大规模计算才值得

**建议**：
- 当前 7-DoF 机器人不需要 GPU
- 如果扩展到多机器人或高维状态，再考虑

### 2.3 Cython 编译

**原理**：将 Python 代码编译为 C 扩展

**应用场景**：
- 性能关键的循环
- 需要与 C/C++ 库交互

**示例**：
```cython
# motion_mapper_fast.pyx
import numpy as np
cimport numpy as np
cimport cython

@cython.boundscheck(False)
@cython.wraparound(False)
def compute_target_position(
    np.ndarray[np.float64_t, ndim=1] shoulder,
    np.ndarray[np.float64_t, ndim=1] elbow,
    np.ndarray[np.float64_t, ndim=1] wrist,
    double scale
):
    """
    快速计算目标位置（Cython 加速）

    加速比: 5-10x
    """
    cdef np.ndarray[np.float64_t, ndim=1] upper_arm = elbow - shoulder
    cdef np.ndarray[np.float64_t, ndim=1] forearm = wrist - elbow

    # ... 计算逻辑

    return target_pos
```

**建议**：
- 实现复杂度高
- 维护成本高
- 优先考虑 Numba

---

## 3. 通信优化

### 3.1 ZeroMQ（推荐）

**优势**：
- 比 UDP/TCP 更高效
- 内置消息队列
- 支持多种通信模式（REQ-REP, PUB-SUB, PUSH-PULL）
- 自动重连
- 跨语言支持

**示例**：
```python
import zmq

# 服务端（VIST 控制器）
context = zmq.Context()
socket = context.socket(zmq.REP)
socket.bind("tcp://*:5555")

while True:
    # 接收关节角度请求
    message = socket.recv_json()

    # 处理
    q_safe = process(message['keypoints'])

    # 发送响应
    socket.send_json({'q': q_safe.tolist()})

# 客户端（机器人）
context = zmq.Context()
socket = context.socket(zmq.REQ)
socket.connect("tcp://localhost:5555")

# 发送请求
socket.send_json({'keypoints': keypoints})

# 接收响应
response = socket.recv_json()
q = np.array(response['q'])
```

**实现步骤**：
1. 安装 ZeroMQ: `pip install pyzmq`
2. 创建 `src/communication/zmq_server.py`
3. 修改 `robot_interface.py` 使用 ZeroMQ
4. 测试延迟和稳定性

**预期收益**：
- 延迟降低 20-30%
- 稳定性提升（自动重连）
- 吞吐量提升 2-3x

### 3.2 共享内存（最快）

**原理**：进程间通过共享内存通信，避免网络开销

**应用场景**：
- 视觉和控制在同一台机器
- 需要极低延迟（<1ms）

**示例**：
```python
from multiprocessing import shared_memory
import numpy as np

# 创建共享内存
shm = shared_memory.SharedMemory(create=True, size=1024)

# 写入数据
arr = np.ndarray((7,), dtype=np.float64, buffer=shm.buf)
arr[:] = q_safe

# 读取数据（另一个进程）
shm = shared_memory.SharedMemory(name='vist_control')
arr = np.ndarray((7,), dtype=np.float64, buffer=shm.buf)
q = arr.copy()
```

**注意事项**：
- 需要同步机制（锁、信号量）
- 只适用于同一台机器
- 实现复杂度高

**建议**：
- 先尝试 ZeroMQ
- 如果延迟仍不满足，再考虑共享内存

### 3.3 Protocol Buffers（消息序列化）

**优势**：
- 比 JSON 更快（2-10x）
- 更紧凑（体积小 50-70%）
- 强类型检查

**示例**：
```protobuf
// vist_messages.proto
syntax = "proto3";

message JointCommand {
    repeated double q = 1;
    double timestamp = 2;
}

message KeypointsData {
    map<string, Vector3> keypoints = 1;
    double timestamp = 2;
}

message Vector3 {
    double x = 1;
    double y = 2;
    double z = 3;
}
```

```python
import vist_messages_pb2

# 序列化
cmd = vist_messages_pb2.JointCommand()
cmd.q.extend(q_safe.tolist())
cmd.timestamp = time.time()
data = cmd.SerializeToString()

# 反序列化
cmd = vist_messages_pb2.JointCommand()
cmd.ParseFromString(data)
q = np.array(cmd.q)
```

**实现步骤**：
1. 安装 protobuf: `pip install protobuf`
2. 定义消息格式（.proto 文件）
3. 编译生成 Python 代码
4. 替换 JSON 序列化

**预期收益**：
- 序列化速度提升 2-10x
- 网络带宽降低 50-70%

---

## 4. 实时性优化

### 4.1 实时 Linux（PREEMPT_RT）

**原理**：将 Linux 内核改造为实时系统

**优势**：
- 确定性延迟（<100μs）
- 优先级调度
- 避免抖动

**实现步骤**：
1. 安装 PREEMPT_RT 补丁内核
2. 配置实时优先级
3. 禁用不必要的服务

**适用场景**：
- 需要硬实时保证
- 控制频率 >200Hz

**建议**：
- 当前 30Hz 控制频率不需要
- 如果提升到 100Hz+，再考虑

### 4.2 进程优先级调整

**原理**：提高 VIST 进程的调度优先级

**示例**：
```python
import os

# 设置实时优先级
os.sched_setscheduler(0, os.SCHED_FIFO, os.sched_param(99))

# 或使用 nice 值
os.nice(-20)  # 最高优先级
```

**注意事项**：
- 需要 root 权限
- 可能影响系统稳定性

### 4.3 CPU 亲和性（CPU Affinity）

**原理**：将进程绑定到特定 CPU 核心，避免上下文切换

**示例**：
```python
import os

# 绑定到 CPU 核心 2 和 3
os.sched_setaffinity(0, {2, 3})
```

**预期收益**：
- 减少缓存失效
- 降低延迟抖动

---

## 5. 并发优化

### 5.1 多线程架构

**设计**：
```
Thread 1: 视觉感知 (30 Hz)
    ↓ Queue (线程安全)
Thread 2: VIST 控制 (100 Hz)
    ↓ Queue (线程安全)
Thread 3: 机器人通信 (200 Hz)
```

**示例**：
```python
import threading
import queue

# 创建队列
keypoints_queue = queue.Queue(maxsize=1)
command_queue = queue.Queue(maxsize=1)

# 视觉线程
def vision_thread():
    while True:
        keypoints = detect_pose()
        try:
            keypoints_queue.put_nowait(keypoints)
        except queue.Full:
            pass  # 丢弃旧数据

# 控制线程
def control_thread():
    while True:
        keypoints = keypoints_queue.get()
        q_safe = vist_controller.process(keypoints)
        try:
            command_queue.put_nowait(q_safe)
        except queue.Full:
            pass

# 通信线程
def communication_thread():
    while True:
        q_safe = command_queue.get()
        robot.send_command(q_safe)

# 启动线程
threading.Thread(target=vision_thread, daemon=True).start()
threading.Thread(target=control_thread, daemon=True).start()
threading.Thread(target=communication_thread, daemon=True).start()
```

**预期收益**：
- 控制频率提升 3-5x
- 系统响应更快

### 5.2 异步 IO（asyncio）

**适用场景**：
- 网络通信密集
- 多个 IO 操作

**示例**：
```python
import asyncio

async def vision_loop():
    while True:
        keypoints = await detect_pose_async()
        await keypoints_queue.put(keypoints)

async def control_loop():
    while True:
        keypoints = await keypoints_queue.get()
        q_safe = await vist_controller.process_async(keypoints)
        await command_queue.put(q_safe)

# 运行事件循环
asyncio.run(asyncio.gather(
    vision_loop(),
    control_loop(),
    communication_loop()
))
```

**建议**：
- 先尝试多线程
- 如果 IO 密集，再考虑 asyncio

---

## 6. 优化优先级矩阵

| 优化项 | 收益 | 成本 | 优先级 | 建议时机 |
|--------|------|------|--------|----------|
| 李代数旋转插值 | 高 | 低 | ⭐⭐⭐⭐⭐ | 立即 |
| ZeroMQ 通信 | 高 | 低 | ⭐⭐⭐⭐⭐ | 本周 |
| Numba JIT | 高 | 中 | ⭐⭐⭐⭐ | 瓶颈明确后 |
| Protocol Buffers | 中 | 中 | ⭐⭐⭐ | 带宽不足时 |
| 多线程架构 | 高 | 高 | ⭐⭐⭐ | 频率不足时 |
| 李代数卡尔曼 | 高 | 高 | ⭐⭐ | 精度不足时 |
| CuPy GPU | 中 | 高 | ⭐ | 大规模计算 |
| 实时 Linux | 中 | 高 | ⭐ | 硬实时需求 |
| 共享内存 | 高 | 高 | ⭐ | 极低延迟 |

---

## 7. 推荐实施路径

### 阶段 1: 立即可做（本周）

1. **李代数旋转插值**
   - 创建 `src/utils/lie_algebra.py`
   - 实现 `slerp_rotation()` 和 `slerp_SE3()`
   - 在运动映射中使用

2. **ZeroMQ 通信**
   - 安装 pyzmq
   - 创建 `src/communication/zmq_server.py`
   - 测试延迟和稳定性

**预期收益**: 延迟降低 30%，精度提升 10%

### 阶段 2: 实验期间（1-2周）

3. **性能分析**
   - 使用 cProfile 识别瓶颈
   - 确定是否需要 Numba

4. **Numba JIT**（如果需要）
   - 为热点函数添加 @jit
   - 测试加速效果

**预期收益**: 计算速度提升 2-3x

### 阶段 3: 论文后（可选）

5. **多线程架构**
   - 重构为多线程
   - 提升控制频率到 100Hz+

6. **李代数卡尔曼滤波**
   - 重构状态表示
   - 提升精度和稳定性

**预期收益**: 系统性能提升 5-10x

---

## 8. 注意事项

1. **过早优化是万恶之源**
   - 先让系统跑起来
   - 用 cProfile 找瓶颈
   - 针对性优化

2. **测量优化效果**
   - 优化前后都要测量
   - 使用相同的测试数据
   - 记录延迟、吞吐量、CPU 使用率

3. **保持代码可读性**
   - 优化不应牺牲可维护性
   - 添加注释说明优化原理
   - 保留未优化版本作为参考

4. **渐进式优化**
   - 一次只优化一个模块
   - 确保功能正确
   - 避免引入新 bug

---

## 9. 性能基准测试

创建性能测试脚本：

```python
# tests/test_performance.py
import time
import numpy as np
from src.control.vist_controller import VISTController

def benchmark_control_loop(controller, n_iterations=1000):
    """测试控制循环性能"""
    keypoints = generate_test_keypoints()

    times = []
    for _ in range(n_iterations):
        start = time.perf_counter()
        q_safe, success, _ = controller.process(keypoints)
        end = time.perf_counter()
        times.append(end - start)

    times = np.array(times)
    print(f"平均延迟: {times.mean()*1000:.2f} ms")
    print(f"最大延迟: {times.max()*1000:.2f} ms")
    print(f"99% 延迟: {np.percentile(times, 99)*1000:.2f} ms")
    print(f"控制频率: {1/times.mean():.1f} Hz")

if __name__ == "__main__":
    config = load_config()
    controller = VISTController(config)
    benchmark_control_loop(controller)
```

---

## 10. 总结

**立即实施**（本周）:
1. ✅ 李代数旋转插值（精度提升）
2. ✅ ZeroMQ 通信（延迟降低）

**中期实施**（实验期间）:
3. 性能分析 + Numba JIT（速度提升）
4. Protocol Buffers（带宽优化）

**长期实施**（论文后）:
5. 多线程架构（频率提升）
6. 李代数卡尔曼滤波（精度提升）

**关键原则**: 测量 → 优化 → 验证 → 迭代
