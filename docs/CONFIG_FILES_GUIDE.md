# 配置文件说明 - 整理后

## 当前配置文件（5个YAML文件）

### 1. system_config.yaml (20K, 496行)
**用途**: 主系统配置文件，包含所有核心参数

**包含模块**:
- `robot_model`: 机器人模型参数（URDF文件名、末端执行器等）
- `robot`: 机器人硬件参数（肩部位置、臂长、关节限位、方向、偏移等）
- `coordinate_transform`: 坐标系转换（旋转矩阵、TCP偏移）
- `control`: 控制参数（频率、插值、轨迹规划等）
- `vist_kalman`: VIST卡尔曼滤波参数
- `filtering`: 滤波器配置
- `network`: 网络配置
- `vision`: 视觉配置
- `safety`: 安全限制
- `hardware`: 硬件配置
- `visualization`: 可视化配置
- `enhanced_features`: 增强功能

**使用场景**: 所有实验的基础配置

### 2. experiment_config.yaml (5.1K)
**用途**: 实验模式配置，用于切换不同的实验模式

**支持模式**:
- `vision_vist`: 纯视觉 + VIST算法
- `exo_arm_vist`: 外骨骼臂 + VIST算法
- `exo_arm_baseline`: 外骨骼臂 + 基线滤波
- `exo_full`: 外骨骼臂 + 数据手套（完整遥操作）

**配置项**:
- 实验模式选择
- 臂控制配置（外骨骼/视觉）
- 手控制配置（手套/视觉/无）
- VIST算法参数
- 基线滤波器参数
- 安全配置
- 数据记录配置

**使用场景**: 快速切换实验模式

### 3. ablation_config.yaml (4.4K)
**用途**: 消融实验配置，用于对比不同滤波器性能

**配置项**:
- 滤波器类型选择（VIST/低通/One Euro/无滤波）
- 各滤波器参数
- 实验对比设置

**使用场景**: 消融实验和性能对比

### 4. hand_config.yaml (1.2K)
**用途**: 手部重定向配置

**配置项**:
- 手部重定向参数
- 关节映射
- 手部模型配置

**使用场景**: 视觉手部控制

### 5. tcp_calibration.yaml (1.7K)
**用途**: TCP（Tool Center Point）偏移标定

**配置项**:
- TCP偏移值（位置和姿态）
- 不同工具的TCP配置

**使用场景**: 工具末端标定

## 机器人模型文件

### 6. lkls73_o2_dual_arm_description.urdf (24K)
**用途**: 机器人URDF模型文件

### 7. lkls73_o2_dual_arm_description.csv (14K)
**用途**: 机器人描述CSV文件

### 8. meshes/ 目录
**用途**: 3D模型文件（STL格式）

### 9. meshes.zip (11M)
**用途**: 3D模型压缩包（已解压，可删除）

## 备份文件

### 10. system_config_paper.yaml.bak (15K)
**用途**: 论文版本的系统配置（已备份）

## 配置文件使用指南

### 基本使用

#### 1. 视觉遥操作实验
```python
from src.config.config_loader import ConfigLoader

# 加载主配置
config = ConfigLoader.load("config/system_config.yaml")

# 加载实验配置
exp_config = ConfigLoader.load("config/experiment_config.yaml")
exp_config['experiment']['mode'] = 'vision_vist'
```

#### 2. 外骨骼遥操作实验
```python
# 修改实验配置
exp_config['experiment']['mode'] = 'exo_arm_vist'
exp_config['arm']['control_type'] = 'exoskeleton'
exp_config['arm']['use_vist'] = True
```

#### 3. 消融实验
```python
# 加载消融配置
ablation_config = ConfigLoader.load("config/ablation_config.yaml")
ablation_config['filter_type'] = 'low_pass'  # 或 'one_euro', 'none'
```

### 配置优先级

当多个配置文件有重叠时，优先级为：
1. 实验配置（experiment_config.yaml）- 最高优先级
2. 消融配置（ablation_config.yaml）
3. 主配置（system_config.yaml）- 默认值

### 配置文件关系

```
system_config.yaml (基础配置)
    ↓
experiment_config.yaml (实验模式)
    ↓
ablation_config.yaml (消融实验，可选)
    ↓
hand_config.yaml (手部配置，可选)
    ↓
tcp_calibration.yaml (TCP标定，可选)
```

## 未来优化建议

### 短期（保持现状）
- ✅ 已删除临时配置文件
- ✅ 已备份重复配置文件
- ✅ 配置文件数量精简到5个核心文件

### 中期（模块化拆分）
如果system_config.yaml变得难以维护，可以拆分为：
```
config/
├── core/
│   ├── robot_model.yaml
│   ├── robot_hardware.yaml
│   └── coordinate_transform.yaml
├── control/
│   ├── control_params.yaml
│   └── vist_kalman.yaml
├── perception/
│   └── vision.yaml
└── master_config.yaml (引用其他配置)
```

### 长期（配置管理系统）
- 实现配置继承和覆盖机制
- 支持环境变量和命令行参数
- 配置验证和类型检查
- 配置版本管理

## 配置文件维护规范

1. **不要直接修改system_config.yaml**
   - 使用experiment_config.yaml覆盖参数
   - 保持system_config.yaml作为默认值

2. **实验参数放在experiment_config.yaml**
   - 实验模式
   - 临时参数调整
   - 特定实验的配置

3. **消融实验使用ablation_config.yaml**
   - 滤波器对比
   - 算法性能评估

4. **提交前检查**
   - 不要提交临时修改的配置
   - 使用.gitignore忽略实验配置
   - 保持默认配置的稳定性

---

**配置文件整理完成！**
- 删除: 0个（保留所有必要文件）
- 备份: 1个（system_config_paper.yaml）
- 保留: 5个核心YAML + 3个模型文件
