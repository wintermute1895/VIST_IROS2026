# VIST 真机测试准备清单

## 📋 总体评估

**当前状态：** 🟡 **基本就绪，需要最终验证**

**距离真机测试：** 约 **1-2天** 的准备工作

---

## ✅ 已完成的工作

### 1. **核心算法层** ✅

| 组件 | 状态 | 文件 |
|------|------|------|
| VIST卡尔曼滤波器 | ✅ 完成 | `src/core/vist_kalman_filter.py` |
| 几何解析求解器 | ✅ 完成 | `src/core/geometric_arm_solver.py` |
| 运动映射器 | ✅ 完成 | `src/core/motion_mapper.py` |
| IK求解器 | ✅ 完成 | `src/core/ik_solver.py` |

### 2. **硬件驱动层** ✅

| 组件 | 状态 | 文件 |
|------|------|------|
| 真机驱动器 | ✅ 完成 | `src/robot/arm_driver.py` |
| SDK集成 | ✅ 完成 | `src/robot/sdk/linkerarm/` |
| 关节映射 | ✅ 完成 | URDF→SDK映射已配置 |
| 符号翻转 | ✅ 完成 | 关节方向已校准 |

### 3. **安全保障层** ✅

| 组件 | 状态 | 文件 |
|------|------|------|
| 安全控制器 | ✅ 完成 | `src/control/safe_robot_controller.py` |
| 速度限制 | ✅ 完成 | 0.3 rad/s (真机安全值) |
| 加速度限制 | ✅ 完成 | 0.8 rad/s² (真机安全值) |
| 关节限位检查 | ✅ 完成 | 从配置读取 |
| 紧急停止 | ✅ 完成 | Ctrl+C 支持 |

### 4. **视觉采集层** ✅

| 组件 | 状态 | 文件 |
|------|------|------|
| RealSense深度相机 | ✅ 完成 | `src/nodes/vision_node_depth.py` |
| MediaPipe姿态检测 | ✅ 完成 | 支持0.10.x版本 |
| 深度融合 | ✅ 完成 | RealSense + MediaPipe |
| UDP通信 | ✅ 完成 | 30Hz数据传输 |

### 5. **测试脚本** ✅

| 脚本 | 状态 | 文件 | 说明 |
|------|------|------|------|
| 分阶段安全测试 | ✅ 完成 | `tests/test_real_hardware.py` | 4个测试阶段 |
| 完整遥操作 | ✅ 完成 | `scripts/run_real_robot_vist.py` | VIST完整流程 |
| 重构版控制器 | ✅ 完成 | `scripts/run_real_robot_vist_refactored.py` | 模块化架构 |

---

## ⚠️ 需要完成的工作

### 1. **频率匹配优化** 🟡 部分完成

**当前状态：**
- ✅ 配置已调整（30Hz控制频率）
- ✅ `move_joint` 速度参数已优化（1.0 rad/s）
- ⚠️ VIST预测模式未实现（需要添加 `has_new_observation` 参数）

**需要做的：**
```python
# 修改 vist_kalman_filter.py 的 solve() 方法
def solve(self, target_pos=None, has_new_observation=True, ...):
    self.predict()  # 总是预测
    if has_new_observation and target_pos is not None:
        self.update(target_pos, ...)  # 只在有新数据时更新
    else:
        return self.state[:n_joints]  # 使用预测值
```

**优先级：** 🟡 中等（可以先用30Hz匹配测试，后续优化）

---

### 2. **通信保障** 🟡 基本完成

**已有机制：**
- ✅ UDP非阻塞接收
- ✅ 数据超时检测（`max_data_timeout`）
- ✅ JSON解析错误处理

**需要加强：**
- ⚠️ 网络延迟监控（建议添加）
- ⚠️ 数据包丢失统计（建议添加）
- ⚠️ 心跳机制（可选）

**建议添加：**
```python
# 在 robot_interface.py 中添加
class NetworkMonitor:
    def __init__(self):
        self.latency_history = deque(maxlen=100)
        self.packet_loss_count = 0

    def record_latency(self, send_time, receive_time):
        latency = (receive_time - send_time) * 1000  # ms
        self.latency_history.append(latency)

    def get_stats(self):
        if not self.latency_history:
            return None
        return {
            'avg_latency': np.mean(self.latency_history),
            'max_latency': np.max(self.latency_history),
            'packet_loss_rate': self.packet_loss_count / total_packets
        }
```

**优先级：** 🟢 低（当前机制已足够，可后续优化）

---

### 3. **配置验证** 🔴 必须完成

**需要验证的配置：**

```yaml
# config/system_config.yaml

# ✅ 已配置
robot:
  shoulder_position: [0.0, -0.17, 1.217]  # 需要真机验证
  arm_lengths:
    upper: 0.2908    # 需要真机测量验证
    forearm: 0.2366  # 需要真机测量验证
  joint_directions: [-1, 1, -1, 1, 1, 1, 1]  # 需要真机验证
  joint_offsets: [-1.57, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]  # 需要真机验证

# ⚠️ 需要确认
hardware:
  robot_ip: "192.168.1.183"  # 确认真机IP
  arm_side: "right"          # 确认使用哪个手臂
  move_joint_speed: 1.0      # 真机测试后可能需要调整
  move_joint_accel: 2.0      # 真机测试后可能需要调整

# ⚠️ 需要确认
control:
  frequency: 30  # Hz - 已调整为30Hz
  max_joint_velocity: 0.3      # rad/s - 真机安全值
  max_joint_acceleration: 0.8  # rad/s² - 真机安全值
```

**验证步骤：**
1. 运行 `test_real_hardware.py` 阶段1（连接测试）
2. 检查读取的关节角度是否合理
3. 运行阶段2（单关节测试），验证关节方向
4. 如果方向错误，调整 `joint_directions` 配置

**优先级：** 🔴 **高（必须在真机测试前完成）**

---

### 4. **安全检查清单** 🔴 必须完成

**物理安全：**
- [ ] 机器人周围无障碍物（至少1米安全距离）
- [ ] 紧急停止按钮可用且测试过
- [ ] 电源开关位置已确认
- [ ] 有人在旁监控（至少2人）
- [ ] 准备好软垫/防护措施

**软件安全：**
- [ ] 速度限制已设置（0.3 rad/s）
- [ ] 加速度限制已设置（0.8 rad/s²）
- [ ] 关节限位已配置
- [ ] 紧急停止功能已测试（Ctrl+C）
- [ ] 数据记录已启用（用于事故分析）

**测试流程安全：**
- [ ] 从最小幅度开始（±5°）
- [ ] 逐步增加运动范围
- [ ] 每个阶段需要人工确认
- [ ] 发现异常立即停止

**优先级：** 🔴 **最高（生命安全）**

---

### 5. **数据记录与监控** 🟡 建议添加

**当前状态：**
- ✅ 安全控制器有数据记录功能
- ⚠️ 实时监控界面缺失

**建议添加：**
```python
# 实时监控显示
class RealtimeMonitor:
    def __init__(self):
        self.start_time = time.time()

    def print_status(self, q_current, q_target, safety_status):
        """每秒打印一次状态"""
        print(f"\r时间: {time.time() - self.start_time:.1f}s | "
              f"关节误差: {np.linalg.norm(q_target - q_current):.3f} rad | "
              f"速度限制: {safety_status['velocity_limited']} | "
              f"加速度限制: {safety_status['acceleration_limited']}",
              end='')
```

**优先级：** 🟢 低（可后续添加）

---

## 🚀 真机测试流程

### **阶段0：准备工作（1小时）**

1. **硬件检查**
   ```bash
   # 检查机器人连接
   ping 192.168.1.183

   # 检查相机连接
   rs-enumerate-devices
   ```

2. **配置验证**
   ```bash
   # 检查配置文件
   cat config/system_config.yaml | grep -A 5 "hardware:"
   ```

3. **安全检查**
   - 清理机器人周围区域
   - 测试紧急停止按钮
   - 准备防护措施

---

### **阶段1：连接测试（10分钟）**

```bash
# 运行连接测试
python3 tests/test_real_hardware.py
# 只运行阶段1，验证连接和状态读取
```

**预期结果：**
- ✅ 连接成功
- ✅ 能读取关节角度
- ✅ 关节角度值合理（不全为0）

**如果失败：**
- 检查IP地址配置
- 检查SDK是否正确安装
- 检查机器人是否上电

---

### **阶段2：单关节测试（20分钟）**

```bash
# 继续运行 test_real_hardware.py
# 运行阶段2，测试单关节小幅运动
```

**预期结果：**
- ✅ 关节能正常运动
- ✅ 运动方向正确
- ✅ 能回到零位

**如果方向错误：**
1. 记录哪个关节方向错误
2. 修改 `config/system_config.yaml` 中的 `joint_directions`
3. 重新测试

---

### **阶段3：IK验证测试（30分钟）**

```bash
# 继续运行 test_real_hardware.py
# 运行阶段3，测试IK求解器
```

**预期结果：**
- ✅ IK求解成功
- ✅ 机器人能到达目标位置
- ✅ 位置误差 < 5mm

**如果失败：**
- 检查肩部位置配置
- 检查臂长参数
- 检查关节限位

---

### **阶段4：完整回路测试（1小时）**

```bash
# 继续运行 test_real_hardware.py
# 运行阶段4，测试完整控制回路
```

**预期结果：**
- ✅ 能跟踪圆周轨迹
- ✅ IK成功率 > 95%
- ✅ 运动平滑无抖动

---

### **阶段5：视觉遥操作测试（2小时）**

```bash
# Terminal 1: 启动视觉节点
python3 src/nodes/vision_node_depth.py

# Terminal 2: 启动真机控制
python3 scripts/run_real_robot_vist.py
```

**预期结果：**
- ✅ 机器人能跟随手部运动
- ✅ 延迟 < 100ms
- ✅ 运动平滑自然

---

## 📊 关键指标

### **性能指标**

| 指标 | 目标值 | 当前配置 | 验证方法 |
|------|--------|---------|---------|
| 控制频率 | 30 Hz | 30 Hz | 测量实际帧率 |
| 视觉延迟 | < 50 ms | 待测 | 时间戳对比 |
| IK成功率 | > 95% | 待测 | 统计成功次数 |
| 位置精度 | < 5 mm | 待测 | 测量末端误差 |
| 关节速度 | < 0.3 rad/s | 0.3 rad/s | 安全控制器监控 |

### **安全指标**

| 指标 | 限制值 | 当前配置 | 状态 |
|------|--------|---------|------|
| 最大速度 | 0.3 rad/s | 0.3 rad/s | ✅ |
| 最大加速度 | 0.8 rad/s² | 0.8 rad/s² | ✅ |
| 紧急停止响应 | < 100 ms | 待测 | ⚠️ |
| 数据超时检测 | 5 帧 | 5 帧 | ✅ |

---

## 🔧 故障排查指南

### **问题1：连接失败**

**症状：** `connect()` 返回 False

**可能原因：**
1. IP地址错误
2. 机器人未上电
3. 网络不通
4. SDK未正确安装

**解决方法：**
```bash
# 1. 检查网络
ping 192.168.1.183

# 2. 检查SDK
python3 -c "from lbot import LbotRobot; print('SDK OK')"

# 3. 检查配置
grep "robot_ip" config/system_config.yaml
```

---

### **问题2：关节方向错误**

**症状：** 发送正值，关节反向运动

**解决方法：**
1. 记录错误的关节索引
2. 修改 `config/system_config.yaml`:
   ```yaml
   joint_directions:
     - -1  # 如果Joint 0方向错误，改为-1
     - 1
     # ...
   ```
3. 重新测试

---

### **问题3：运动抖动**

**症状：** 机器人运动不平滑，有抖动

**可能原因：**
1. 速度参数太高
2. 视觉数据噪声大
3. IK求解不稳定

**解决方法：**
```yaml
# 降低速度
hardware:
  move_joint_speed: 0.5  # 从1.0降到0.5
  move_joint_accel: 1.0  # 从2.0降到1.0

# 增强滤波
filtering:
  oneeuro_min_cutoff: 0.05  # 从0.1降到0.05
```

---

### **问题4：IK求解失败**

**症状：** IK成功率低，频繁失败

**可能原因：**
1. 目标位置超出工作空间
2. 肩部位置配置错误
3. 臂长参数错误

**解决方法：**
1. 检查目标位置是否可达
2. 用卷尺测量真实臂长
3. 调整配置参数

---

## 📝 总结

### **当前状态评估**

| 方面 | 完成度 | 说明 |
|------|--------|------|
| **核心算法** | 100% | ✅ VIST框架完整 |
| **硬件驱动** | 100% | ✅ SDK集成完成 |
| **安全保障** | 100% | ✅ 安全机制完备 |
| **测试脚本** | 100% | ✅ 分阶段测试完整 |
| **配置验证** | 70% | ⚠️ 需要真机验证 |
| **频率匹配** | 80% | ⚠️ 预测模式待完善 |
| **通信保障** | 90% | ✅ 基本机制完备 |

### **距离真机测试还有多远？**

**答案：1-2天**

**必须完成的工作（1天）：**
1. 🔴 配置验证（运行 `test_real_hardware.py` 阶段1-2）
2. 🔴 安全检查清单（物理准备）
3. 🟡 频率匹配优化（可选，建议完成）

**可选的优化工作（1天）：**
1. 🟢 网络监控增强
2. 🟢 实时监控界面
3. 🟢 数据记录完善

### **建议的测试时间表**

**第1天（准备）：**
- 上午：配置验证 + 安全检查
- 下午：阶段1-2测试（连接 + 单关节）

**第2天（测试）：**
- 上午：阶段3-4测试（IK + 完整回路）
- 下午：阶段5测试（视觉遥操作）

---

## ✅ 最终检查清单

在开始真机测试前，请确认：

- [ ] 已阅读完整的安全检查清单
- [ ] 机器人周围已清理干净
- [ ] 紧急停止按钮已测试
- [ ] 至少2人在场监控
- [ ] 配置文件已检查
- [ ] 测试脚本已准备好
- [ ] 数据记录已启用
- [ ] 已了解故障排查方法
- [ ] 已准备好防护措施
- [ ] 心理准备充分（第一次真机测试会紧张）

**记住：安全第一！宁可慢一点，也不要冒险！**

---

**文档版本：** v1.0
**最后更新：** 2026-02-09
**作者：** VIST Project Team
