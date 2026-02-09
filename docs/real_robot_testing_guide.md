"""
VIST 几何映射法集成分析与真机测试准备清单

作者: VIST Project
日期: 2026-02-07
"""

# ============================================================================
# 1. VIST 在几何映射法中的作用分析
# ============================================================================

## 1.1 当前集成状态

✅ **VIST 已经完全集成几何求解器**

工作流程：
```
人体关键点 → 几何求解器 → 目标关节角度 → VIST 卡尔曼滤波 → 平滑输出
    (肩肘腕)      (解析解)      (q_decoupled)    (状态估计)     (q_filtered)
```

关键代码位置：
- `vist_kalman_filter.py:780-784` - 几何解析模式选择
- `vist_kalman_filter.py:418-420` - 调用几何求解器
- `vist_kalman_filter.py:426` - 计算增量 Δθ = q_decoupled - q_current

## 1.2 VIST 的三重作用

### 作用 1: 状态估计与平滑
- **输入**: 几何求解器的目标角度（可能有抖动）
- **输出**: 平滑的关节角度轨迹
- **方法**: 卡尔曼滤波融合过程模型和观测模型

### 作用 2: 意图检测与自适应
- **精密模式** (α→1): 靠近目标时，增大几何解的权重（磁吸效果）
- **自由模式** (α→0): 远离目标时，降低几何解的权重（去噪效果）
- **实现**: `vist_kalman_filter.py:213-250` - detect_intent()

### 作用 3: 双观测融合
- **人类指令观测**: 几何解析解（高置信度，R=1e-4）
- **虚拟引导观测**: 微分 IK（低置信度，R=1e2）
- **融合策略**: `vist_kalman_filter.py:201-210` - 臂部关节完全信任几何解

## 1.3 融合效果验证

当前配置（`system_config.yaml:129-138`）：
```yaml
geometric_solver:
  enabled: true
  trust_weight: 2.0  # 几何解的信任权重
```

融合机制：
1. **过程噪声调整**: Q_arm *= (1.0 / trust_weight) = 0.5
   - 降低臂部关节的过程噪声，增强几何解的影响
2. **观测噪声调整**: R_human[0:4] = 1e-4, R_virtual[0:4] = 1e2
   - 臂部关节完全信任几何解，基本忽略微分 IK

# ============================================================================
# 2. 真机测试前的准备清单
# ============================================================================

## 2.1 通信测试

### 测试 1: UDP 连接测试
```bash
# 启动 UDP 接收测试
python scripts/test_udp_connection.py
```

需要验证：
- [ ] UDP 端口 6001 可以正常绑定
- [ ] 可以接收来自视觉节点的数据包
- [ ] 数据包格式正确（7 个关节角度）
- [ ] 数据包频率稳定（50Hz）

### 测试 2: 数据格式验证
```python
# 检查数据包结构
import struct
data = b'...'  # 从 UDP 接收的数据
joint_angles = struct.unpack('7f', data)  # 7 个 float
print(f"关节角度: {joint_angles}")
```

需要验证：
- [ ] 数据包大小 = 28 字节（7 * 4）
- [ ] 每个关节角度在合理范围内
- [ ] 没有 NaN 或 Inf 值

## 2.2 安全限制

### 限制 1: 速度限制
当前配置（`system_config.yaml:107-108`）：
```yaml
max_joint_velocity: 0.8      # rad/s
max_joint_acceleration: 2.0  # rad/s^2
```

建议真机测试时：
```yaml
max_joint_velocity: 0.3      # rad/s (降低到 30%)
max_joint_acceleration: 0.5  # rad/s^2 (降低到 25%)
```

实现位置：需要在控制节点添加速度限制器

### 限制 2: 关节限位检查
当前配置（`system_config.yaml:18-25`）：
```yaml
joint_limits:
  - [-7, 7]      # Joint 0-3: 肩部和肘部（仿真用，真机需要调整）
  - [-3.14, 3.14]  # Joint 4-6: 腕部
```

真机测试前需要：
- [ ] 从机器人手册获取真实关节限位
- [ ] 更新配置文件中的 joint_limits
- [ ] 添加软限位（在硬限位前 10% 停止）

### 限制 3: 工作空间限制
当前配置（`system_config.yaml:266`）：
```yaml
max_distance_from_shoulder: 0.7  # meters
```

建议真机测试时：
```yaml
max_distance_from_shoulder: 0.5  # meters (缩小工作空间)
```

## 2.3 紧急停止机制

### 方案 1: 键盘紧急停止
```python
import keyboard

def emergency_stop():
    """按 ESC 键紧急停止"""
    if keyboard.is_pressed('esc'):
        print("🚨 紧急停止！")
        # 发送零速度命令
        send_zero_velocity()
        sys.exit(0)
```

### 方案 2: 数据超时保护
当前配置（`system_config.yaml:263`）：
```yaml
max_data_timeout: 50  # frames (1秒 @ 50Hz)
```

实现逻辑：
```python
if frames_without_data > max_data_timeout:
    print("⚠️ 数据超时，停止运动")
    send_zero_velocity()
```

### 方案 3: 异常检测
需要监控：
- [ ] 关节角度突变（> 30° / 帧）
- [ ] 关节速度超限
- [ ] 关节加速度超限
- [ ] 末端位置超出工作空间

## 2.4 数据记录与监控

### 记录内容
```python
log_data = {
    'timestamp': time.time(),
    'human_keypoints': {
        'shoulder': shoulder_pos,
        'elbow': elbow_pos,
        'wrist': wrist_pos
    },
    'robot_state': {
        'joint_angles': q_current,
        'joint_velocities': q_dot_current,
        'end_effector_pos': ee_pos
    },
    'control_output': {
        'target_angles': q_target,
        'filtered_angles': q_filtered
    },
    'safety_status': {
        'velocity_limited': False,
        'position_limited': False,
        'emergency_stop': False
    }
}
```

### 监控界面
建议使用 ROS rqt 或自定义 GUI：
- [ ] 实时显示关节角度曲线
- [ ] 实时显示关节速度曲线
- [ ] 显示末端位置轨迹
- [ ] 显示安全状态指示灯

## 2.5 渐进式测试流程

### 阶段 1: 静态测试（机器人不动）
1. 启动视觉节点，检查关键点检测
2. 启动映射节点，检查坐标转换
3. 启动控制节点，检查 IK 求解
4. **不发送命令到机器人**，只记录数据

验证：
- [ ] 关键点检测稳定
- [ ] 坐标转换正确
- [ ] IK 求解无异常
- [ ] 关节角度在合理范围内

### 阶段 2: 单关节测试
1. 只启用一个关节（如 Shoulder_Pitch）
2. 缓慢移动手臂，观察机器人响应
3. 检查运动方向是否正确
4. 检查运动幅度是否合理

验证：
- [ ] 运动方向正确（direction 参数）
- [ ] 运动幅度合理（无过冲）
- [ ] 速度平滑（无抖动）

### 阶段 3: 多关节测试
1. 逐步启用更多关节
2. 测试简单动作（如抬手、放下）
3. 测试复杂动作（如画圆、抓取）

验证：
- [ ] 多关节协调运动
- [ ] 无关节冲突
- [ ] 末端轨迹平滑

### 阶段 4: 全速测试
1. 逐步提高速度限制
2. 测试快速运动
3. 测试连续运动

验证：
- [ ] 高速运动稳定
- [ ] 无振荡
- [ ] 无超限

# ============================================================================
# 3. 灵巧手集成准备
# ============================================================================

## 3.1 灵巧手控制接口

需要确认：
- [ ] 灵巧手型号和通信协议（CAN/串口/以太网）
- [ ] 灵巧手控制命令格式
- [ ] 灵巧手状态反馈格式
- [ ] 灵巧手控制频率

## 3.2 手势识别集成

### 方案 1: MediaPipe 手势识别
```python
import mediapipe as mp

mp_hands = mp.solutions.hands
hands = mp_hands.Hands()

# 识别手势
results = hands.process(image)
if results.multi_hand_landmarks:
    hand_landmarks = results.multi_hand_landmarks[0]
    gesture = recognize_gesture(hand_landmarks)
    # 映射到灵巧手命令
    dexterous_hand_command = map_gesture_to_command(gesture)
```

### 方案 2: 关键点映射
```python
# 从手部关键点计算手指角度
finger_angles = calculate_finger_angles(hand_landmarks)

# 映射到灵巧手关节角度
dexterous_hand_angles = map_to_dexterous_hand(finger_angles)
```

## 3.3 集成架构

```
视觉节点 → 手臂控制 + 手部识别 → 机器人控制
   ↓           ↓            ↓
关键点    手臂关节角度  灵巧手命令
         (VIST 滤波)   (手势映射)
```

# ============================================================================
# 4. 推荐的测试脚本
# ============================================================================

## 4.1 创建安全控制节点

需要创建：`src/control/safe_robot_controller.py`

功能：
- 速度限制
- 加速度限制
- 关节限位检查
- 紧急停止
- 数据记录

## 4.2 创建监控界面

需要创建：`scripts/monitor_robot_state.py`

功能：
- 实时显示关节状态
- 实时显示末端位置
- 安全状态指示
- 数据记录回放

## 4.3 创建测试脚本

需要创建：`scripts/test_real_robot.py`

功能：
- 渐进式测试流程
- 自动化测试用例
- 测试报告生成

# ============================================================================
# 5. 总结
# ============================================================================

## 当前状态
✅ VIST 已完全集成几何求解器
✅ 仿真测试通过
✅ 配置系统完善

## 下一步
1. 创建安全控制节点（速度限制、紧急停止）
2. 创建监控界面（实时显示、数据记录）
3. 进行渐进式真机测试
4. 集成灵巧手控制

## 风险提示
⚠️ 真机测试前务必：
- 降低速度限制（30% 最大速度）
- 缩小工作空间（50cm 半径）
- 准备紧急停止按钮
- 有人在旁监护

## 预期效果
🎯 真机测试成功后：
- 手臂运动平滑自然
- 响应延迟 < 100ms
- 末端位置误差 < 2cm
- 无抖动、无振荡
