# Phase 4: 控制节点配置化

## 目标

将控制节点（`vist_teleoperation.py`）中的所有硬编码参数替换为配置文件参数，完成整个系统的配置化重构。

## 当前问题

控制节点仍然使用大量硬编码参数：

```python
# 硬编码的参数
mapper = ArmMotionMapper(
    robot_shoulder_pos=[0.0, -0.096, 1.217],  # 应从配置文件读取
    arm_lengths={'upper': 0.2908, 'fore': 0.2366}
)

joint_limits = np.array([...])  # 应从配置文件读取
safety_monitor = SafetyMonitor(
    joint_limits,
    max_joint_velocity=0.8,  # 应从配置文件读取
    max_joint_acceleration=2.0
)

frequency = 50  # 应从配置文件读取
ik_gain = 0.9  # 应从配置文件读取
sock.bind(('0.0.0.0', 6001))  # 端口应从配置文件读取
```

## 实施方案

### 1. 导入配置加载器

```python
from src.config import get_config
```

### 2. 加载配置

```python
def main():
    # 加载统一配置
    config = get_config()

    # 仍然需要加载硬件配置（IP、侧别、自由度）
    config_path = os.path.join(project_root, "config", "hardware.yaml")
    with open(config_path, 'r') as f:
        hw_config = yaml.safe_load(f)
    arm_config = hw_config['arm']
```

### 3. 使用配置参数初始化组件

#### 运动映射器
```python
# 之前：硬编码
mapper = ArmMotionMapper(
    robot_shoulder_pos=[0.0, -0.096, 1.217],
    arm_lengths={'upper': 0.2908, 'fore': 0.2366}
)

# 之后：从配置文件读取
mapper = ArmMotionMapper()  # 自动从配置文件加载
```

#### 安全监控器
```python
# 之前：硬编码
joint_limits = np.array([...])
safety_monitor = SafetyMonitor(
    joint_limits,
    max_joint_velocity=0.8,
    max_joint_acceleration=2.0
)

# 之后：从配置文件读取
safety_monitor = SafetyMonitor(
    config.robot_joint_limits,
    max_joint_velocity=config.max_joint_velocity,
    max_joint_acceleration=config.max_joint_acceleration
)
```

#### 控制参数
```python
# 之前：硬编码
frequency = 50
ik_gain = 0.9
max_joint_velocity = 0.8
duration = 300.0

# 之后：从配置文件读取
frequency = config.control_frequency
ik_gain = config.ik_gain
max_joint_velocity = config.max_joint_velocity
duration = config.get('control', {}).get('duration', 300.0)
```

#### 网络参数
```python
# 之前：硬编码
sock.bind(('0.0.0.0', 6001))

# 之后：从配置文件读取
sock.bind((config.udp_host, config.udp_port))
```

#### 滤波器参数
```python
# 之前：硬编码
pos_filter = OneEuroFilter(min_cutoff=0.3, beta=0.005)

# 之后：从配置文件读取
pos_filter = OneEuroFilter(
    min_cutoff=config.filter_min_cutoff,
    beta=config.filter_beta
)
```

## 需要修改的代码位置

| 行号 | 原代码 | 修改后 |
|------|--------|--------|
| 73-76 | `mapper = ArmMotionMapper(robot_shoulder_pos=..., arm_lengths=...)` | `mapper = ArmMotionMapper()` |
| 82-90 | `joint_limits = np.array([...])` | `joint_limits = config.robot_joint_limits` |
| 91-95 | `SafetyMonitor(joint_limits, max_joint_velocity=0.8, ...)` | `SafetyMonitor(config.robot_joint_limits, max_joint_velocity=config.max_joint_velocity, ...)` |
| 112 | `sock.bind(('0.0.0.0', 6001))` | `sock.bind((config.udp_host, config.udp_port))` |
| 117-118 | `OneEuroFilter(min_cutoff=0.3, beta=0.005)` | `OneEuroFilter(min_cutoff=config.filter_min_cutoff, beta=config.filter_beta)` |
| 127 | `frequency = 50` | `frequency = config.control_frequency` |
| 129 | `max_joint_velocity = 0.8` | `max_joint_velocity = config.max_joint_velocity` |
| 133 | `ik_gain = 0.9` | `ik_gain = config.ik_gain` |

## 配置文件检查

确保 `config/system_config.yaml` 包含所有必要的参数：

```yaml
control:
  frequency: 50
  ik_gain: 0.9
  max_joint_velocity: 0.8
  max_joint_acceleration: 2.0
  duration: 300.0

network:
  udp_host: "0.0.0.0"
  udp_port: 6001

vision:
  filter_min_cutoff: 0.3
  filter_beta: 0.005
```

## 预期效果

1. **参数集中管理**：所有参数都在配置文件中，修改参数不需要改代码
2. **一致性**：所有节点都使用相同的配置系统
3. **可维护性**：新人只需要看配置文件就能理解系统参数
4. **向后兼容**：保留硬件配置文件（hardware.yaml）用于设备特定参数

## 测试验证

修改完成后，运行以下测试：

```bash
# 1. 语法检查
python3 -c "from scripts.vist_teleoperation import main; print('✅ 导入成功')"

# 2. 配置加载测试
python3 -c "from src.config import get_config; c = get_config(); print(f'✅ 配置加载成功: frequency={c.control_frequency}')"

# 3. 完整流程测试（需要硬件）
python3 scripts/vist_teleoperation.py
```

## 实施步骤

1. ✅ 创建本实施指南
2. ⏳ 修改 `vist_teleoperation.py`
3. ⏳ 测试修改后的代码
4. ⏳ 更新 `REFACTOR_COMPLETE.md`
5. ⏳ 提交 Git commit

## 注意事项

- 保留 `hardware.yaml` 的加载，因为它包含设备特定的配置（IP、侧别等）
- 确保所有配置参数都有默认值，避免配置文件缺失时崩溃
- 保持代码的向后兼容性
