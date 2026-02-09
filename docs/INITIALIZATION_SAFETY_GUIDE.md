# 机器人初始化安全检查指南

## 概述

为了防止电机损坏（如J1烧毁事件），我们实现了一个全面的初始化安全检查系统。

## 问题回顾：J1电机损坏事件

### 事故经过
1. 用户运行真机测试脚本
2. 在enable_arm()时，J1电机立即：
   - 过热
   - 发出异响
   - 冒烟
3. 用户立即停止，但J1已损坏（手动转动阻塞、有异响）

### 根本原因
SDK配置了 **custom_gripper** 工具坐标系（10cm偏移），当enable时：
- SDK认为末端应该在"夹爪中心"
- 实际末端在"手腕位置"
- SDK命令J1移动来补偿10cm偏移
- J1被命令到不可达位置，电机卡死，过流，冒烟

## 安全检查系统

### 自动检查项目

1. **工具坐标系检查**
   - 要求用户确认已切换到 Arm_Tip (0, 0, 0)
   - 防止工具偏移导致的位置错误

2. **关节位置检查**
   - 要求用户确认机械臂处于安全姿态
   - 确保无关节在极限位置

3. **SDK配置检查**
   - 验证控制频率 ≤15 Hz
   - 验证电机速度 ≤0.3 rad/s
   - 验证电机加速度 ≤0.5 rad/s²

4. **电机健康检查**
   - 要求用户确认所有电机冷却
   - 确认无异响、无卡顿
   - 确认无烧焦味

### 使用方法

#### 方法1：自动使用（推荐）

安全检查已集成到 `RealArmDriver.connect()` 中，默认启用：

```python
from src.robot.arm_driver import RealArmDriver

# 创建驱动
driver = RealArmDriver(ip="192.168.10.21", arm_side="right", config=config)

# 连接（自动执行安全检查）
success = driver.connect()  # use_safety_checks=True (默认)
```

#### 方法2：手动调用

如果需要更细粒度的控制：

```python
from src.robot.arm_driver import RealArmDriver
from src.robot.safety_checks import InitializationSafetyChecker, safe_enable_arm

# 创建驱动
driver = RealArmDriver(ip="192.168.10.21", arm_side="right", config=config)

# 仅连接，不使能
driver.robot.connect(timeout=10.0)

# 执行安全检查
checker = InitializationSafetyChecker(config)
is_safe, warnings = checker.check_all(driver)

if is_safe:
    # 安全使能
    safe_enable_arm(driver, config)
else:
    print("安全检查失败，拒绝使能")
```

#### 方法3：跳过安全检查（不推荐）

仅用于调试或紧急情况：

```python
# ⚠️ 危险：跳过安全检查
success = driver.connect(use_safety_checks=False)
```

## 安全检查流程

### 1. 工具坐标系确认

```
1️⃣ 检查工具坐标系配置...
   ⚠️  无法自动检测工具坐标系配置
   请手动确认：
   1. 打开SDK Web界面
   2. 进入'可用工具坐标系'页面
   3. 确认当前使用的是 'Arm_Tip' (0, 0, 0)
   4. 如果不是，请点击 'Arm_Tip' 旁边的'切换到此工具'

   ✋ 请确认已切换到 Arm_Tip (输入 'yes' 继续):
```

**重要**：必须确认工具坐标系为 Arm_Tip，否则拒绝使能。

### 2. 机械臂姿态确认

```
2️⃣ 检查当前关节位置...
   ℹ️  Enable之前无法读取关节状态
   请手动确认：
   1. 机械臂是否处于自然下垂姿态？
   2. 各关节是否在正常范围内（无极限位置）？
   3. 是否有关节被卡住或阻塞？

   ✋ 请确认机械臂姿态安全 (输入 'yes' 继续):
```

### 3. 配置参数检查

```
3️⃣ 检查SDK配置一致性...
   ✅ SDK配置检查通过
      - 控制频率: 10 Hz
      - 电机速度: 0.1 rad/s
      - 电机加速度: 0.1 rad/s²
```

如果参数超出安全范围，会显示警告。

### 4. 电机健康确认

```
4️⃣ 检查电机健康状态...
   ℹ️  电机健康检查
   请手动确认：
   1. 所有电机是否冷却（温度正常）？
   2. 是否有电机发出异响？
   3. 手动转动各关节，是否有卡顿或阻塞？
   4. 是否有烧焦味道？

   ✋ 请确认所有电机健康 (输入 'yes' 继续):
```

**重要**：如果J1已损坏，必须回答 'no'，系统会拒绝使能。

### 5. 最终确认

```
⚠️  最终确认
即将使能机械臂。使能后：
  - 电机将通电并保持当前位置
  - 如果配置错误，可能导致电机损坏
  - 请确保紧急停止按钮可用

✋ 确认使能机械臂？(输入 'ENABLE' 继续):
```

必须输入 **'ENABLE'**（全大写）才能继续。

### 6. 使能后检查

```
🔍 使能后检查...
   请观察：
   1. 是否有电机发出异响？
   2. 是否有电机过热？
   3. 机械臂是否保持稳定？

✋ 使能后状态正常？(输入 'yes' 继续):
```

如果发现异常，立即断开连接。

## 安全参数建议

### 保守参数（推荐用于初次测试）

```yaml
control:
  frequency: 5  # Hz - 非常保守

hardware:
  move_joint_speed: 0.05   # rad/s - 非常慢
  move_joint_accel: 0.05   # rad/s² - 非常慢
```

### 标准参数（正常使用）

```yaml
control:
  frequency: 10  # Hz

hardware:
  move_joint_speed: 0.1    # rad/s
  move_joint_accel: 0.1    # rad/s²
```

### 激进参数（仅在确认安全后使用）

```yaml
control:
  frequency: 15  # Hz

hardware:
  move_joint_speed: 0.3    # rad/s
  move_joint_accel: 0.3    # rad/s²
```

## 故障排除

### Q: 安全检查一直失败怎么办？

A: 检查以下项目：
1. 是否切换到 Arm_Tip 工具坐标系？
2. 机械臂姿态是否安全？
3. 是否有损坏的电机（如J1）？
4. 配置参数是否过高？

### Q: 如何在J1损坏的情况下测试其他关节？

A:
1. 在电机健康检查时回答 'no'
2. 系统会拒绝使能
3. 需要先维修J1，或者修改代码跳过J1

### Q: 紧急情况下如何快速使能？

A: 不推荐，但如果必须：
```python
driver.connect(use_safety_checks=False)
```

## 预防措施总结

1. **始终使用 Arm_Tip 工具坐标系**（除非你完全理解工具偏移的影响）
2. **使用保守的控制参数**（频率≤10Hz，速度≤0.1 rad/s）
3. **enable前确认机械臂姿态安全**
4. **enable后立即观察电机状态**
5. **准备好紧急停止按钮**
6. **定期检查电机健康**

## 相关文件

- `src/robot/safety_checks.py` - 安全检查模块
- `src/robot/arm_driver.py` - 驱动（集成了安全检查）
- `config/system_config.yaml` - 配置文件
- `docs/MOTOR_DAMAGE_INCIDENT_REPORT.md` - J1损坏事件报告（本文档）
