# LBot机械臂API详解：move_joint和joint_follow

## 一、API概述

LBot机械臂提供了两个关键的运动控制方法：
1. **`lbot_move_joint`** - 关节空间运动（点到点运动）
2. **`lbot_joint_follow`** - 关节跟随控制（遥操作专用）

---

## 二、lbot_move_joint - 关节空间运动

### 2.1 函数签名

```c
bool lbot_move_joint(
    lbot_handle_t handle,      // 机械臂句柄
    lbot_arm_t arm,            // 机械臂选择：LBOT_LEFT_ARM 或 LBOT_RIGHT_ARM
    const double joints[7],    // 7个关节的目标角度（弧度）
    double speed,              // 运动速度（rad/s）
    double accel,              // 加速度（rad/s²）
    bool block                 // 是否阻塞执行
);
```

### 2.2 输入参数详解

#### handle
- **类型**：`lbot_handle_t`（整数句柄）
- **说明**：通过`lbot_init("192.168.10.21")`获得
- **有效值**：> 0

#### arm
- **类型**：`lbot_arm_t`（枚举）
- **可选值**：
  - `LBOT_LEFT_ARM` - 左臂
  - `LBOT_RIGHT_ARM` - 右臂

#### joints[7]
- **类型**：`double`数组，7个元素
- **单位**：弧度（rad）
- **说明**：7个关节的目标角度
- **示例**：
  ```c
  double joints[7] = {0.0, -0.5, 0.0, 1.57, 0.0, 0.5, 0.0};
  ```

#### speed
- **类型**：`double`
- **单位**：rad/s（弧度/秒）
- **范围**：0.0 ~ 20.0
- **建议**：从0.0 ~ 2.0开始使用，逐步提高
- **说明**：关节运动的最大速度

#### accel
- **类型**：`double`
- **单位**：rad/s²（弧度/秒²）
- **范围**：0.0 ~ 20.0
- **建议**：从0.0 ~ 2.0开始使用，逐步提高
- **说明**：关节运动的加速度

#### block
- **类型**：`bool`
- **说明**：
  - `true` - 阻塞执行，等待运动完成后返回
  - `false` - 非阻塞，立即返回

### 2.3 输出

#### 返回值
- **类型**：`bool`
- **说明**：
  - `true` - 指令发送成功
  - `false` - 发送失败（可通过`lbot_get_last_error()`获取错误信息）

### 2.4 底层实现机制

#### 控制流程
```
1. 客户端调用lbot_move_joint()
   ↓
2. 通过TCP连接发送指令到机械臂控制器
   ↓
3. 控制器接收指令并解析
   ↓
4. 控制器进行轨迹规划：
   - 计算从当前位置到目标位置的轨迹
   - 应用速度和加速度限制
   - 生成插值点
   ↓
5. 控制器以固定频率（通常1kHz）发送指令到电机驱动器
   ↓
6. 电机驱动器执行位置控制
   ↓
7. 如果block=true，等待运动完成后返回
   如果block=false，立即返回
```

#### 插值机制
- **插值类型**：关节空间插值（Joint Space Interpolation）
- **插值算法**：五次多项式或S曲线
- **控制频率**：控制器内部通常为1kHz
- **特点**：
  - 每个关节独立插值
  - 保证速度和加速度限制
  - 轨迹平滑，无突变

### 2.5 使用示例

```cpp
// 初始化连接
lbot_handle_t handle = lbot_init("192.168.10.21");

// 定义目标关节角度
double target_joints[7] = {0.0, -0.5, 0.0, 1.57, 0.0, 0.5, 0.0};

// 执行运动（阻塞模式）
bool success = lbot_move_joint(
    handle,
    LBOT_LEFT_ARM,
    target_joints,
    0.5,    // 速度: 0.5 rad/s
    0.2,    // 加速度: 0.2 rad/s²
    true    // 阻塞执行
);

if (success) {
    printf("运动完成\n");
} else {
    printf("运动失败: %s\n", lbot_get_last_error(handle));
}
```

### 2.6 性能特性

| 特性 | 说明 |
|------|------|
| 控制频率 | 控制器内部1kHz，TCP通信不需要高频 |
| 延迟 | 网络延迟 + 轨迹规划时间（通常<50ms） |
| 精度 | 高精度，完整轨迹规划 |
| 平滑性 | 非常平滑，五次多项式插值 |
| 适用场景 | 点到点运动，预定义轨迹 |

---

## 三、lbot_joint_follow - 关节跟随控制

### 3.1 函数签名

```c
bool lbot_joint_follow(
    lbot_handle_t handle,      // 机械臂句柄
    lbot_arm_t arm,            // 机械臂选择
    const double joints[7],    // 7个关节的目标角度（弧度）
    bool follow                // 跟随模式标志
);
```

### 3.2 输入参数详解

#### handle
- **类型**：`lbot_handle_t`
- **说明**：机械臂连接句柄

#### arm
- **类型**：`lbot_arm_t`
- **可选值**：`LBOT_LEFT_ARM` 或 `LBOT_RIGHT_ARM`

#### joints[7]
- **类型**：`double`数组，7个元素
- **单位**：弧度（rad）
- **说明**：7个关节的目标角度
- **更新频率**：建议30Hz以上

#### follow
- **类型**：`bool`
- **说明**：
  - `true` - **高跟随模式**（低延迟，实时映射关节角度）
  - `false` - **低跟随模式**（有延迟，但轨迹平滑处理）

### 3.3 输出

#### 返回值
- **类型**：`bool`
- **说明**：
  - `true` - 指令发送成功
  - `false` - 发送失败

### 3.4 底层实现机制

#### 高跟随模式（follow=true）

```
1. 客户端以高频率（30Hz+）调用lbot_joint_follow()
   ↓
2. 每次调用立即通过TCP发送目标角度到控制器
   ↓
3. 控制器接收目标角度
   ↓
4. 控制器进行最小插值处理：
   - 从当前位置到目标位置的直接插值
   - 插值点数量少（低延迟）
   - 可能有轻微抖动
   ↓
5. 控制器以1kHz频率发送指令到电机
   ↓
6. 电机驱动器执行位置控制
```

**特点**：
- ✅ 延迟最低（<20ms）
- ✅ 实时响应
- ⚠️ 可能有轻微抖动
- ⚠️ 需要高频率输入（30Hz+）

#### 低跟随模式（follow=false）

```
1. 客户端以高频率调用lbot_joint_follow()
   ↓
2. 每次调用发送目标角度到控制器
   ↓
3. 控制器接收目标角度
   ↓
4. 控制器进行平滑处理：
   - 使用滤波器平滑轨迹
   - 应用速度和加速度限制
   - 生成更多插值点
   ↓
5. 控制器以1kHz频率发送指令到电机
   ↓
6. 电机驱动器执行位置控制
```

**特点**：
- ✅ 轨迹平滑
- ✅ 无抖动
- ⚠️ 延迟较高（50-100ms）
- ⚠️ 响应稍慢

### 3.5 控制频率需求

#### 推荐频率
- **最低频率**：10Hz（基本可用）
- **推荐频率**：30Hz（良好体验）
- **最佳频率**：50-100Hz（最佳体验）

#### 频率影响

| 频率 | 延迟 | 平滑性 | 跟踪精度 | 适用场景 |
|------|------|--------|---------|---------|
| 10Hz | 高 | 差 | 低 | 不推荐 |
| 30Hz | 中 | 好 | 中 | 推荐（baseline） |
| 50Hz | 低 | 很好 | 高 | 推荐 |
| 100Hz | 很低 | 优秀 | 很高 | 最佳 |

### 3.6 电机控制插值

#### 控制器内部插值
- **插值频率**：1kHz（固定）
- **插值算法**：
  - 高跟随模式：线性插值或最小插值
  - 低跟随模式：五次多项式或S曲线
- **插值点数**：
  - 高跟随模式：少（例如10-20个点）
  - 低跟随模式：多（例如50-100个点）

#### 从输入到电机的完整流程

```
输入频率: 30Hz (每33ms一次)
    ↓
TCP传输: ~5-10ms
    ↓
控制器接收: <1ms
    ↓
轨迹规划/插值: 1-5ms
    ↓
生成1kHz控制指令
    ↓
电机驱动器: 1kHz位置控制
    ↓
电机执行
```

### 3.7 使用示例

#### 基本使用（ROS2）

```cpp
// 在ROS2节点中订阅遥操臂数据
void joint_callback(const sensor_msgs::msg::JointState::SharedPtr msg) {
    if (msg->position.size() != 7) return;

    // 转换为double数组
    double joints[7];
    for (size_t i = 0; i < 7; ++i) {
        joints[i] = msg->position[i];
    }

    // 调用joint_follow（高跟随模式）
    bool success = lbot_joint_follow(
        handle,
        LBOT_LEFT_ARM,
        joints,
        true  // 高跟随模式
    );

    if (!success) {
        RCLCPP_ERROR(logger, "Joint follow failed");
    }
}

// 订阅遥操臂话题（30Hz）
auto sub = node->create_subscription<sensor_msgs::msg::JointState>(
    "/left_arm_joint_control", 10, joint_callback);
```

#### 高级使用（带频率控制）

```cpp
class TeleopController {
private:
    rclcpp::TimerBase::SharedPtr timer_;
    double current_joints_[7];

public:
    TeleopController() {
        // 创建30Hz定时器
        timer_ = node->create_wall_timer(
            std::chrono::milliseconds(33),  // 30Hz
            std::bind(&TeleopController::control_loop, this)
        );
    }

    void control_loop() {
        // 发送当前关节角度
        bool success = lbot_joint_follow(
            handle_,
            LBOT_LEFT_ARM,
            current_joints_,
            true  // 高跟随模式
        );

        if (!success) {
            RCLCPP_WARN_THROTTLE(logger_, clock_, 1000,
                "Joint follow failed");
        }
    }

    void update_joints(const double joints[7]) {
        std::copy(joints, joints + 7, current_joints_);
    }
};
```

### 3.8 性能特性

| 特性 | 高跟随模式 | 低跟随模式 |
|------|-----------|-----------|
| 延迟 | <20ms | 50-100ms |
| 平滑性 | 中等 | 优秀 |
| 抖动 | 可能有 | 无 |
| 响应速度 | 快 | 中等 |
| 适用场景 | 精确遥操作 | 平滑遥操作 |

---

## 四、输入输出可见性

### 4.1 输入数据可见性

#### 通过ROS2话题查看

```bash
# 查看遥操臂输入（主臂）
ros2 topic echo /left_arm_joint_control

# 输出示例：
# header:
#   stamp:
#     sec: 1234567890
#     nanosec: 123456789
# position: [0.0, -0.5, 0.0, 1.57, 0.0, 0.5, 0.0]
# velocity: []
# effort: []

# 查看发送到机械臂的指令
ros2 topic echo /robot1/left_arm/joint_follow

# 输出示例：
# joints: [0.0, -0.5, 0.0, 1.57, 0.0, 0.5, 0.0]
# follow: true
```

#### 通过性能监控工具查看

```bash
# 启动性能监控
bash scripts/start_performance_monitor_advanced.sh

# 实时显示：
# - 频率: 30.02 Hz
# - 延迟: 15.3 ms
# - 速度: 0.125 rad/s
# - 加速度: 0.032 rad/s²
# - Jerk: 0.008 rad/s³
```

### 4.2 输出数据可见性

#### 通过ROS2话题查看机械臂状态

```bash
# 查看机械臂当前状态
ros2 topic echo /robot1/joint_states

# 输出示例：
# header:
#   stamp:
#     sec: 1234567890
#     nanosec: 123456789
# name: ['joint1', 'joint2', 'joint3', 'joint4', 'joint5', 'joint6', 'joint7']
# position: [0.001, -0.498, 0.002, 1.568, -0.001, 0.502, 0.001]
# velocity: [0.01, 0.02, 0.01, 0.03, 0.01, 0.02, 0.01]
# effort: [0.5, 1.2, 0.8, 1.5, 0.6, 0.9, 0.4]
```

#### 通过API查看状态

```cpp
// 获取当前机器人状态
lbot_full_state_t state;
if (lbot_get_current_state(handle, &state)) {
    printf("Left arm joints:\n");
    for (int i = 0; i < 7; ++i) {
        printf("  Joint %d: %.4f rad\n", i, state.left_arm.joints[i]);
    }
}
```

### 4.3 数据流可视化

#### 使用rqt_plot实时绘图

```bash
# 绘制关节角度
rqt_plot /left_arm_joint_control/position[0]:position[1]:position[2]

# 绘制跟踪误差
rqt_plot /robot1/joint_states/position[0] /left_arm_joint_control/position[0]
```

#### 使用性能监控工具生成图表

```bash
# 记录数据
bash scripts/start_performance_monitor_advanced.sh

# 操作完成后分析
ros2 run performance_monitor analyze_performance performance_log_advanced.csv

# 生成图表：
# - performance_log_advanced_plot.png
# - 包含频率、延迟、速度、加速度、Jerk的时间序列图
```

---

## 五、两种方法对比

| 特性 | move_joint | joint_follow |
|------|-----------|-------------|
| **用途** | 点到点运动 | 实时遥操作 |
| **输入频率** | 单次调用 | 30Hz+ |
| **阻塞模式** | 支持 | 不支持（总是非阻塞） |
| **速度控制** | 显式指定 | 隐式（由输入频率决定） |
| **加速度控制** | 显式指定 | 隐式（由控制器处理） |
| **轨迹规划** | 完整规划 | 最小规划（高跟随）或平滑处理（低跟随） |
| **延迟** | 中等（50ms） | 低（<20ms，高跟随）或中等（50-100ms，低跟随） |
| **平滑性** | 优秀 | 中等（高跟随）或优秀（低跟随） |
| **精度** | 高 | 中等 |
| **适用场景** | 预定义轨迹、自动化任务 | 遥操作、实时控制 |

---

## 六、最佳实践

### 6.1 使用move_joint的场景

```cpp
// 场景1：移动到预定义位置
double home_position[7] = {0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0};
lbot_move_joint(handle, LBOT_LEFT_ARM, home_position, 0.5, 0.2, true);

// 场景2：执行一系列动作
double positions[][7] = {
    {0.0, -0.5, 0.0, 1.57, 0.0, 0.5, 0.0},
    {0.5, -0.3, 0.2, 1.2, 0.1, 0.3, 0.0},
    {0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0}
};
for (int i = 0; i < 3; ++i) {
    lbot_move_joint(handle, LBOT_LEFT_ARM, positions[i], 0.5, 0.2, true);
}
```

### 6.2 使用joint_follow的场景

```cpp
// 场景：遥操作
// 在ROS2回调中，30Hz频率
void teleop_callback(const sensor_msgs::msg::JointState::SharedPtr msg) {
    double joints[7];
    for (size_t i = 0; i < 7; ++i) {
        joints[i] = msg->position[i];
    }

    // 使用高跟随模式获得最低延迟
    lbot_joint_follow(handle, LBOT_LEFT_ARM, joints, true);
}
```

### 6.3 频率控制建议

```cpp
// 推荐：使用定时器确保稳定频率
class TeleopNode : public rclcpp::Node {
    rclcpp::TimerBase::SharedPtr timer_;

    TeleopNode() {
        // 30Hz定时器
        timer_ = create_wall_timer(
            std::chrono::milliseconds(33),
            std::bind(&TeleopNode::control_loop, this)
        );
    }

    void control_loop() {
        // 每33ms执行一次
        lbot_joint_follow(handle_, arm_, current_joints_, true);
    }
};
```

---

## 七、总结

### move_joint
- ✅ 适合预定义轨迹
- ✅ 完整的轨迹规划
- ✅ 高精度、高平滑性
- ⚠️ 不适合实时遥操作

### joint_follow
- ✅ 专为遥操作设计
- ✅ 低延迟（高跟随模式）
- ✅ 实时响应
- ⚠️ 需要高频率输入（30Hz+）
- ⚠️ 可能有轻微抖动（高跟随模式）

### 推荐配置（baseline系统）
- **控制频率**：30Hz
- **跟随模式**：高跟随（follow=true）
- **网络**：有线以太网
- **延迟目标**：<20ms

输入输出都可以通过ROS2话题和性能监控工具实时查看和记录！
