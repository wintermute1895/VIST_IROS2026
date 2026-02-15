# VIST 配置指南

本文档说明如何在不同的配置组合之间切换,以进行实验对比分析。

## 配置文件概览

### 1. system_config.yaml (Baseline配置)
**用途**: 现有的sigmoid实现,作为baseline

**特点**:
- α计算方法: Sigmoid函数
- 李代数: 默认关闭
- 多源融合: 标准卡尔曼滤波

**适用场景**:
- 快速原型验证
- 与现有实验结果对比
- 作为baseline参考

### 2. system_config_paper.yaml (论文框架配置)
**用途**: 完全匹配论文框架的实现

**特点**:
- α计算方法: 指数衰减 + 反比例
- 李代数: 默认启用
- 多源融合: 标准卡尔曼滤波 (信息滤波器形式数学等价)

**适用场景**:
- 论文实验验证
- 与论文公式完全一致
- 最终发表使用

## 配置切换方法

### 方法1: 修改代码中的配置文件路径

在 `src/config/config_loader.py` 中修改默认配置文件:

```python
# Baseline配置
config = VISTConfig(config_file="config/system_config.yaml")

# 论文框架配置
config = VISTConfig(config_file="config/system_config_paper.yaml")
```

### 方法2: 通过环境变量切换

```bash
# 使用baseline配置
export VIST_CONFIG="config/system_config.yaml"
python scripts/run_real_robot_vist_refactored.py

# 使用论文框架配置
export VIST_CONFIG="config/system_config_paper.yaml"
python scripts/run_real_robot_vist_refactored.py
```

### 方法3: 命令行参数

```bash
# 使用baseline配置
python scripts/run_real_robot_vist_refactored.py --config config/system_config.yaml

# 使用论文框架配置
python scripts/run_real_robot_vist_refactored.py --config config/system_config_paper.yaml
```

## 关键配置参数对比

| 参数 | Baseline (sigmoid) | 论文框架 (paper) |
|------|-------------------|-----------------|
| **α计算方法** | `alpha_computation_method: "sigmoid"` | `alpha_computation_method: "paper"` |
| **距离项** | Sigmoid: `1/(1+exp(-k*(d_th-d)))` | 指数衰减: `exp(-d²/(2σ_d²))` |
| **速度项** | Sigmoid: `1/(1+exp(-k*(v_th-v)))` | 反比例: `1/(1+β_v·v)` |
| **方向项** | 余弦相似度 (通用) | 余弦相似度 (通用) |
| **李代数** | `use_orientation_control: false` | `use_orientation_control: true` |
| **融合方法** | `fusion_method: "standard"` | `fusion_method: "standard"` |

## 实验对比建议

### 实验1: α计算方法对比
**目的**: 验证sigmoid vs 指数衰减+反比例的效果差异

**步骤**:
1. 使用 `system_config.yaml` 运行实验,记录结果
2. 使用 `system_config_paper.yaml` 运行实验,记录结果
3. 对比: 成功率、完成时间、轨迹平滑度、α轨迹

**预期**:
- 两种方法在数学上等价,性能应该接近
- 论文方法的α轨迹可能更符合物理直觉

### 实验2: 李代数效果验证
**目的**: 验证李代数对姿态控制的影响

**步骤**:
1. 修改 `system_config.yaml`: `use_orientation_control: true`
2. 运行实验,对比启用/禁用李代数的效果

**预期**:
- 启用李代数后,姿态控制更精确
- 避免欧拉角奇异性问题

### 实验3: 参数敏感性分析
**目的**: 验证α权重的敏感性

**步骤**:
1. 修改 `alpha_weights` 参数
2. 测试不同权重组合: (0.3, 0.3, 0.4), (0.33, 0.33, 0.33), (0.2, 0.2, 0.6)
3. 记录性能变化

**预期**:
- 验证权重设计的合理性
- 为论文的参数敏感性分析提供数据

## 配置参数详解

### α计算参数 (论文方法)

```yaml
# 距离项: α_dist = exp(-d²/(2σ_d²))
sigma_d: 0.1  # 距离敏感度标准差
# 说明: σ_d越小,对距离越敏感
# 推荐值: 0.05-0.15米

# 速度项: α_vel = 1/(1+β_v·v)
beta_v: 20.0  # 速度系数
# 说明: β_v越大,对速度越敏感
# 推荐值: 10-30

# α权重
alpha_weights:
  distance: 0.3   # 距离权重
  velocity: 0.3   # 速度权重
  alignment: 0.4  # 对齐权重
# 说明: 对齐权重最高,因为方向是最强的意图信号
```

### α计算参数 (Sigmoid方法)

```yaml
# 距离项: α_dist = 1/(1+exp(-k*(d_th-d)))
distance_threshold: 0.1  # 距离阈值
sigmoid_k: 10.0          # 陡峭度
# 说明: k越大,sigmoid越陡峭,转换越快

# 速度项: α_vel = 1/(1+exp(-k*(v_th-v)))
velocity_threshold: 0.05  # 速度阈值
# 说明: 速度低于此值时,α_vel开始增大
```

## 故障排查

### 问题1: 配置文件未生效
**症状**: 修改配置后,系统行为没有变化

**解决**:
1. 检查配置文件路径是否正确
2. 确认配置加载器是否读取了正确的文件
3. 重启程序,确保配置重新加载

### 问题2: α值异常
**症状**: α始终为0或1,没有平滑过渡

**解决**:
1. 检查 `sigma_d` 和 `beta_v` 参数是否合理
2. 检查 `intent_smoothing` 是否过大(>0.95)
3. 打印α的三个组件,定位问题

### 问题3: 李代数报错
**症状**: 启用 `use_orientation_control` 后报错

**解决**:
1. 确认pinocchio版本支持 `log3` 函数
2. 检查旋转矩阵是否有效(正交性)
3. 查看错误日志,定位具体问题

## 最佳实践

1. **先用baseline验证**: 确保系统基本功能正常
2. **逐步切换**: 一次只改变一个配置项,便于定位问题
3. **记录实验**: 每次实验记录配置文件版本和结果
4. **版本控制**: 使用git管理配置文件的不同版本
5. **文档同步**: 修改配置后,及时更新文档

## 论文写作建议

在论文中描述实现时:

```
实现中,我们提供了两种α计算方法:
1. Sigmoid方法 (baseline): 使用sigmoid函数作为smooth_step的实现
2. 论文方法: 使用指数衰减和反比例函数,物理意义更直观

两种方法在数学上等价(都是平滑的单调函数),实验表明性能接近。
论文中的公式采用方法2,因为其物理解释更清晰。
```

## 参考资料

- [VIST论文框架](PAPER_FRAMEWORK_ALPHA_CENTERED.md)
- [李代数集成指南](LIE_ALGEBRA_INTEGRATION_GUIDE.md)
- [性能优化指南](PERFORMANCE_OPTIMIZATION.md)
