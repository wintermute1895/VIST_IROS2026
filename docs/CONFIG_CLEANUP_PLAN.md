# 配置文件整理方案

## 当前配置文件分析

### 主要配置文件
1. **system_config.yaml** (496行, 20K)
   - 包含: robot_model, robot, coordinate_transform, control, vist_kalman, filtering, network, vision, safety, hardware, visualization, enhanced_features
   - 问题: 太大，包含所有配置，难以维护

2. **system_config_paper.yaml** (15K)
   - 论文版本的系统配置
   - 建议: 保留作为参考，或者删除（如果与system_config.yaml重复）

3. **experiment_config.yaml** (5.1K)
   - 新创建的统一实验配置
   - 用途: 实验模式切换（vision_vist, exo_arm_vist等）

### 专用配置文件
4. **ablation_config.yaml** (4.4K)
   - 消融实验配置
   - 用途: 对比不同滤波器性能
   - 建议: 保留

5. **hand_config.yaml** (1.2K)
   - 手部重定向配置
   - 建议: 保留

6. **task.yaml** (650B)
   - 任务目标定义
   - 建议: 保留

7. **tcp_calibration.yaml** (1.7K)
   - TCP偏移标定
   - 建议: 保留

8. **vist_damping_compensation.yaml** (1.9K)
   - VIST阻尼补偿
   - 建议: 合并到主配置或删除

9. **vist_intent_detection.yaml** (1.9K)
   - VIST意图检测
   - 建议: 合并到主配置或删除

10. **temp_sensitivity_config.yaml** (3.6K)
    - 临时敏感性配置
    - 建议: 删除（临时文件）

### 机器人模型文件
11. **lkls73_o2_dual_arm_description.urdf** (24K)
    - 机器人URDF模型
    - 建议: 保留

12. **lkls73_o2_dual_arm_description.csv** (14K)
    - 机器人描述CSV
    - 建议: 检查是否使用，不使用则删除

13. **meshes/** 和 **meshes.zip** (11M)
    - 3D模型文件
    - 建议: 保留meshes/目录，删除meshes.zip（已解压）

## 整理方案

### 方案A: 拆分system_config.yaml（推荐）

将大的system_config.yaml拆分为多个模块化配置文件：

```
config/
├── core/                          # 核心配置
│   ├── robot_model.yaml          # 机器人模型参数
│   ├── robot_hardware.yaml       # 机器人硬件参数
│   └── coordinate_transform.yaml # 坐标系转换
│
├── control/                       # 控制配置
│   ├── control_params.yaml       # 控制参数
│   ├── vist_kalman.yaml          # VIST卡尔曼滤波
│   └── filtering.yaml            # 滤波器配置
│
├── perception/                    # 感知配置
│   ├── vision.yaml               # 视觉配置
│   └── hand_retargeting.yaml    # 手部重定向（原hand_config.yaml）
│
├── safety/                        # 安全配置
│   └── safety_limits.yaml        # 安全限制
│
├── experiments/                   # 实验配置
│   ├── experiment_modes.yaml     # 实验模式（原experiment_config.yaml）
│   ├── ablation.yaml             # 消融实验（原ablation_config.yaml）
│   └── task_definitions.yaml    # 任务定义（原task.yaml）
│
├── calibration/                   # 标定配置
│   └── tcp_calibration.yaml      # TCP标定
│
├── models/                        # 机器人模型
│   ├── lkls73_o2_dual_arm.urdf
│   └── meshes/
│
└── master_config.yaml             # 主配置文件（引用其他配置）
```

### 方案B: 保持现状，仅清理（简单）

保留主要配置文件，删除临时和重复文件：

**保留:**
- system_config.yaml（主配置）
- experiment_config.yaml（实验模式）
- ablation_config.yaml（消融实验）
- hand_config.yaml（手部配置）
- task.yaml（任务定义）
- tcp_calibration.yaml（TCP标定）
- lkls73_o2_dual_arm_description.urdf（机器人模型）
- meshes/（3D模型）

**删除:**
- system_config_paper.yaml（重复）
- temp_sensitivity_config.yaml（临时文件）
- vist_damping_compensation.yaml（已合并到system_config）
- vist_intent_detection.yaml（已合并到system_config）
- lkls73_o2_dual_arm_description.csv（不使用）
- meshes.zip（已解压）

## 推荐方案：方案B + 部分拆分

1. **立即清理**（删除无用文件）
2. **逐步拆分**（将system_config.yaml拆分为模块）

### 第一步：清理无用文件

```bash
# 删除临时和重复文件
rm config/temp_sensitivity_config.yaml
rm config/system_config_paper.yaml  # 或者重命名为 system_config_paper.yaml.bak
rm config/vist_damping_compensation.yaml  # 如果已合并
rm config/vist_intent_detection.yaml      # 如果已合并
rm config/lkls73_o2_dual_arm_description.csv  # 如果不使用
rm config/meshes.zip  # 已解压
```

### 第二步：拆分system_config.yaml

创建模块化配置结构，但保留system_config.yaml作为向后兼容：

```yaml
# config/master_config.yaml（新的主配置）
includes:
  - core/robot_model.yaml
  - core/robot_hardware.yaml
  - control/control_params.yaml
  - control/vist_kalman.yaml
  - perception/vision.yaml
  - safety/safety_limits.yaml
```

### 第三步：更新代码

修改配置加载器，支持模块化配置：

```python
# src/config/config_loader.py
class ConfigLoader:
    def load_config(self, config_path):
        # 支持includes字段，自动加载多个配置文件
        # 支持向后兼容，仍然可以加载单个system_config.yaml
```

## 配置文件用途总结

| 文件名 | 用途 | 状态 | 建议 |
|--------|------|------|------|
| system_config.yaml | 主系统配置 | 使用中 | 拆分 |
| system_config_paper.yaml | 论文版本配置 | 重复 | 删除/备份 |
| experiment_config.yaml | 实验模式配置 | 使用中 | 保留 |
| ablation_config.yaml | 消融实验配置 | 使用中 | 保留 |
| hand_config.yaml | 手部重定向配置 | 使用中 | 保留 |
| task.yaml | 任务定义 | 使用中 | 保留 |
| tcp_calibration.yaml | TCP标定 | 使用中 | 保留 |
| temp_sensitivity_config.yaml | 临时配置 | 临时 | 删除 |
| vist_damping_compensation.yaml | 阻尼补偿 | 可能重复 | 检查后删除 |
| vist_intent_detection.yaml | 意图检测 | 可能重复 | 检查后删除 |
| lkls73_o2_dual_arm_description.urdf | 机器人模型 | 使用中 | 保留 |
| lkls73_o2_dual_arm_description.csv | 机器人描述 | 不确定 | 检查后决定 |
| meshes/ | 3D模型 | 使用中 | 保留 |
| meshes.zip | 压缩包 | 已解压 | 删除 |

## 下一步行动

### 立即执行（清理）
1. 删除明确无用的文件
2. 备份可能有用的文件

### 后续执行（拆分）
1. 创建模块化目录结构
2. 拆分system_config.yaml
3. 更新配置加载器
4. 测试配置加载

---

**准备好开始清理了吗？**
