# VIST 架构重构 - Phase 1 完成报告

## ✅ 已完成：配置化（Phase 1）

### 创建的文件

1. **`docs/ARCHITECTURE_REFACTOR.md`**
   - 完整的架构重构方案
   - 数据流图
   - 坐标系定义
   - 实施步骤

2. **`config/system_config.yaml`**
   - 统一的系统配置文件
   - 包含所有参数：机器人、控制、网络、视觉、安全
   - 清晰的注释和说明

3. **`src/config/config_loader.py`**
   - 配置加载器类 `VISTConfig`
   - 单例模式，全局访问
   - 类型转换（自动转为 numpy array）
   - 配置验证

4. **`src/config/__init__.py`**
   - 模块初始化文件

### 配置文件结构

```yaml
robot:           # 机器人参数（肩部位置、臂长、关节限位）
coordinate_transform:  # 坐标转换矩阵和说明
control:         # 控制参数（IK、速度、频率）
network:         # UDP 通信参数
vision:          # 相机参数
safety:          # 安全参数和调试选项
```

### 使用方法

```python
from src.config import get_config

# 获取配置实例（单例）
config = get_config()

# 访问参数
shoulder_pos = config.robot_shoulder_position  # numpy array
arm_lengths = config.robot_arm_lengths         # dict
rotation_matrix = config.rotation_matrix       # numpy array (3,3)
ik_gain = config.ik_gain                       # float
```

## 📋 下一步：Phase 2 - 视觉节点简化

### 目标
修改 `vision_node_depth.py`，移除坐标转换逻辑，只保留：
1. 动态归零（肩部为原点）
2. 深度融合（RealSense + MediaPipe）
3. 输出肩膀坐标系（X=上, Y=右, Z=前）

### 具体修改

#### 1. 简化 `mediapipe_to_robot_coords()` 方法
**当前**：做坐标转换（MediaPipe → 肩膀坐标系）
**修改后**：只做深度融合，不做坐标转换

```python
def mediapipe_to_shoulder_coords(self, mp_point, real_depth=None):
    """
    将 MediaPipe 坐标转换为肩膀坐标系（不做旋转，只做深度融合）

    输入：MediaPipe 世界坐标 [x, y, z]
    输出：肩膀坐标系 [x, y, z]
        - X: 向上
        - Y: 向右
        - Z: 向前（靠近相机）
    """
    x_mp, y_mp, z_mp = mp_point

    # 如果提供了真实深度，替换 Z 坐标
    if real_depth is not None:
        z_mp = -real_depth  # 取反，因为靠近相机为正

    # 直接返回，不做旋转转换
    return np.array([
        -y_mp * self.scale,  # X: 向上
        x_mp * self.scale,   # Y: 向右
        z_mp * self.scale    # Z: 向前
    ])
```

#### 2. 更新配置加载
在 `__init__()` 中使用配置文件：

```python
from src.config import get_config

def __init__(self, ...):
    config = get_config()
    self.scale = config.vision_scale
    self.width = config.vision_width
    self.height = config.vision_height
    # ...
```

#### 3. 移除调试代码
移除临时添加的调试输出（`_debug_counter`, `_depth_debug_counter`）

## 📋 Phase 3 - 映射节点职责明确

### 目标
修改 `motion_mapper.py`，统一坐标转换逻辑：
1. 从配置文件读取转换矩阵
2. 移除 `R_cam_to_base`（已废弃）
3. 清晰的输入输出说明

### 具体修改

#### 1. 使用配置文件
```python
from src.config import get_config

def __init__(self, ...):
    config = get_config()

    # 从配置文件读取参数
    self.P_base_shoulder = config.robot_shoulder_position
    self.L_upper = config.robot_arm_lengths['upper']
    self.L_fore = config.robot_arm_lengths['forearm']
    self.R_vision_to_robot = config.rotation_matrix
    self.alpha = config.filter_alpha
```

#### 2. 移除废弃代码
删除 `R_cam_to_base` 和相关方法：
- `set_calibration_matrix()`
- `_warn_if_not_identity()`

## 📋 Phase 4 - 控制节点配置化

### 目标
修改 `vist_teleoperation.py`，使用配置文件：

```python
from src.config import get_config

def main():
    config = get_config()

    # 使用配置参数
    mapper = ArmMotionMapper(
        robot_shoulder_pos=config.robot_shoulder_position,
        arm_lengths=config.robot_arm_lengths
    )
    mapper.set_filter_alpha(config.filter_alpha)

    safety_monitor = SafetyMonitor(
        config.robot_joint_limits,
        max_joint_velocity=config.max_joint_velocity,
        max_joint_acceleration=config.max_joint_acceleration
    )

    frequency = config.control_frequency
    ik_gain = config.ik_gain
    # ...
```

## 🎯 重构优势

### 1. 参数管理
- ✅ 所有参数集中在一个文件
- ✅ 修改参数不需要改代码
- ✅ 便于版本控制和团队协作

### 2. 职责清晰
- ✅ 视觉节点：只负责数据采集
- ✅ 映射节点：只负责坐标转换和映射
- ✅ 控制节点：只负责 IK 和控制

### 3. 可维护性
- ✅ 代码结构清晰
- ✅ 易于调试和测试
- ✅ 减少重复代码

### 4. 可扩展性
- ✅ 添加新参数只需修改配置文件
- ✅ 支持多套配置（开发/生产）
- ✅ 便于添加新功能

## 📝 实施建议

### 立即执行（高优先级）
1. ✅ Phase 1: 配置化（已完成）
2. Phase 2: 视觉节点简化
3. Phase 3: 映射节点职责明确
4. Phase 4: 控制节点配置化

### 后续优化（中优先级）
1. 添加配置验证（参数范围检查）
2. 支持多套配置文件（dev/prod）
3. 添加配置热重载功能

### 代码清理（低优先级）
1. 删除重复的测试脚本
2. 统一日志输出格式
3. 添加单元测试

## ⚠️ 注意事项

1. **向后兼容**：保留旧的参数接口，逐步迁移
2. **测试验证**：每个 Phase 完成后都要测试完整流程
3. **文档更新**：及时更新 README 和注释
4. **Git 提交**：每个 Phase 单独提交，便于回滚

## 🚀 开始实施

建议按顺序执行：
1. 先完成 Phase 2（视觉节点）
2. 再完成 Phase 3（映射节点）
3. 最后完成 Phase 4（控制节点）
4. 全面测试和验证

每个 Phase 完成后运行：
```bash
# 测试视觉输出
python3 scripts/test_coordinate_display.py

# 测试完整流程
python3 scripts/vist_teleoperation.py
```
