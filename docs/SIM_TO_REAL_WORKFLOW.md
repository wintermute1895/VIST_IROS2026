# 🔄 录制数据 → 仿真验证 → 真机部署工作流程

## 概述

这是一个安全且高效的开发流程，可以在不使用真实硬件的情况下验证算法：

```
1. 录制真实视觉数据 → 2. 仿真环境验证 → 3. 真机部署
   (record_vision_data)    (simulate_full_flow)   (run_real_robot)
```

---

## 🎯 完整工作流程

### Step 1: 录制真实视觉数据

首先，录制一组标准的遥操作动作：

```bash
# 终端 1: 启动视觉节点
cd /home/ilex/Dev/VIST
python src/nodes/vision_node_depth.py

# 终端 2: 录制数据（60秒）
python scripts/record_vision_data.py data/recordings/test_sequence.jsonl --duration 60

# 现在站在摄像头前，做标准的遥操作动作
# 例如：孔轴装配、物体抓取等
```

**录制建议**：
- 包含完整的任务流程（接近 → 对齐 → 插入）
- 动作要自然、平滑
- 避免过快或过慢的运动
- 确保手部始终在摄像头视野内

### Step 2: 在仿真环境中验证

使用录制的数据在仿真环境中测试算法：

```bash
# 终端 1: 启动仿真环境（MeshCat 可视化）
python scripts/simulate_full_flow.py

# 终端 2: 回放录制的数据
python scripts/playback_vision_data.py data/recordings/test_sequence.jsonl

# 你会在浏览器中看到机器人的实时运动
# 打开 http://127.0.0.1:7000/static/ 查看可视化
```

**仿真验证内容**：
- ✅ 运动学是否正确（关节角度合理）
- ✅ 轨迹是否平滑（无突变）
- ✅ 是否触发安全限制（速度/加速度）
- ✅ 末端位置是否准确跟踪目标

### Step 3: 调试和优化

如果仿真中发现问题，可以快速迭代：

```bash
# 修改配置文件
vim config/system_config.yaml

# 重新运行仿真（使用相同的录制数据）
python scripts/simulate_full_flow.py &
python scripts/playback_vision_data.py data/recordings/test_sequence.jsonl

# 对比不同配置的效果
```

**常见调试场景**：
- 调整卡尔曼滤波参数（Q, R）
- 调整速度/加速度限制
- 调整意图因子参数
- 测试不同的 IK 策略

### Step 4: 真机部署

仿真验证通过后，部署到真机：

```bash
# 终端 1: 启动视觉节点
python src/nodes/vision_node_depth.py

# 终端 2: 启动真机控制器
python scripts/run_real_robot_vist_refactored.py --duration 60

# 现在可以安全地进行真机遥操作
```

---

## 🔬 消融实验工作流程

对于消融实验，可以使用相同的录制数据在仿真和真机上对比：

### 仿真环境消融实验

```bash
# 1. 录制标准测试数据
python scripts/record_vision_data.py data/recordings/ablation_standard.jsonl --duration 60

# 2. 在仿真中测试不同配置
for config in config/ablation_*.yaml; do
    echo "Testing $config in simulation"
    export VIST_CONFIG=$config
    python scripts/simulate_full_flow.py &
    sleep 2
    python scripts/playback_vision_data.py data/recordings/ablation_standard.jsonl
    wait
done
```

### 真机消融实验

仿真验证通过后，在真机上运行相同的实验：

```bash
# 使用自动化脚本
python scripts/run_ablation_study.py --config config/ablation_config.yaml
```

---

## 📊 对比分析

### 仿真 vs 真机对比

使用诊断脚本对比仿真和真机的差异：

```bash
# 运行诊断脚本
python scripts/diagnose_sim_vs_real.py

# 查看对比报告
cat logs/sim_vs_real_comparison.json | jq .
```

**关键对比指标**：
- 关节角度差异
- 末端位置误差
- 速度/加速度分布
- 安全限制触发率

---

## 🎮 实时可视化

### MeshCat 可视化界面

仿真环境使用 MeshCat 提供实时 3D 可视化：

```bash
# 启动仿真后，在浏览器中打开
http://127.0.0.1:7000/static/

# 可视化元素：
# - 机器人本体（实时关节状态）
# - 红色球：目标末端位置
# - 绿色球：目标肘部位置
# - 蓝色线：末端运动轨迹
```

**交互功能**：
- 鼠标拖动：旋转视角
- 滚轮：缩放
- 右键拖动：平移

---

## 🔧 高级用法

### 1. 循环回放（长时间测试）

```bash
# 在仿真中循环播放，测试系统稳定性
python scripts/simulate_full_flow.py &
python scripts/playback_vision_data.py data/recordings/test_sequence.jsonl --loop
```

### 2. 加速回放（快速验证）

```bash
# 2倍速回放，快速验证算法
python scripts/simulate_full_flow.py &
python scripts/playback_vision_data.py data/recordings/test_sequence.jsonl --speed 2.0
```

### 3. 分段测试

```bash
# 只测试插入阶段（跳过前100帧）
python scripts/simulate_full_flow.py &
python scripts/playback_vision_data.py data/recordings/test_sequence.jsonl --start 100
```

### 4. 对比不同滤波器

```bash
# 测试 No Filter
export VIST_CONFIG=config/ablation_no_filter.yaml
python scripts/simulate_full_flow.py &
python scripts/playback_vision_data.py data/recordings/test_sequence.jsonl

# 测试 VIST (完整版)
export VIST_CONFIG=config/system_config.yaml
python scripts/simulate_full_flow.py &
python scripts/playback_vision_data.py data/recordings/test_sequence.jsonl
```

---

## 📈 性能监控

### 仿真环境性能日志

仿真环境也会生成性能日志：

```bash
# 查看仿真性能
cat logs/simulation_performance_*.json | jq .

# 关键指标：
# - IK 求解时间
# - 卡尔曼滤波时间
# - 安全检查时间
# - 可视化帧率
```

### 对比仿真和真机性能

```bash
# 仿真性能
cat logs/simulation_performance_*.json | jq '.ik_solve_time'

# 真机性能
cat logs/performance_*.json | jq '.ik_solve_time'

# 对比差异
python scripts/compare_sim_real_performance.py
```

---

## ⚠️ 注意事项

### 仿真的局限性

仿真环境**无法完全模拟**以下真机特性：

1. **硬件延迟**：
   - 真机有通信延迟（UDP、串口）
   - 电机响应延迟
   - 传感器采样延迟

2. **物理接触**：
   - 仿真中没有碰撞检测
   - 无法模拟插入时的接触力
   - 无法模拟摩擦和阻力

3. **传感器噪声**：
   - 仿真中的关节角度是理想值
   - 真机有编码器噪声和漂移

4. **动力学效应**：
   - 仿真中没有惯性和重力补偿
   - 真机有机械柔性和振动

### 建议的验证策略

1. **仿真验证**（快速迭代）：
   - 算法逻辑正确性
   - 参数敏感性分析
   - 消融实验对比

2. **真机验证**（最终测试）：
   - 实际任务成功率
   - 系统鲁棒性
   - 安全性验证

---

## 🎯 典型使用场景

### 场景 1: 开发新算法

```bash
# 1. 录制一组标准数据
python scripts/record_vision_data.py data/dev_test.jsonl --duration 30

# 2. 在仿真中快速迭代（修改代码 → 测试 → 修改 → 测试）
while true; do
    python scripts/simulate_full_flow.py &
    python scripts/playback_vision_data.py data/dev_test.jsonl
    read -p "Continue? (y/n) " answer
    [[ $answer != "y" ]] && break
done

# 3. 仿真验证通过后，真机测试
python scripts/run_real_robot_vist_refactored.py --duration 60
```

### 场景 2: 调试问题

```bash
# 1. 在真机上复现问题并录制
python scripts/record_vision_data.py data/bug_reproduction.jsonl --duration 30

# 2. 在仿真中重现问题
python scripts/simulate_full_flow.py &
python scripts/playback_vision_data.py data/bug_reproduction.jsonl

# 3. 在仿真中调试和修复
# （可以添加断点、打印调试信息）

# 4. 修复后在真机上验证
python scripts/run_real_robot_vist_refactored.py --duration 60
```

### 场景 3: 论文实验

```bash
# 1. 录制标准测试数据集
python scripts/record_vision_data.py data/paper_dataset.jsonl --duration 120

# 2. 在仿真中进行消融实验（快速）
python scripts/run_ablation_study.py --use-simulation

# 3. 在真机上验证关键结果
python scripts/run_ablation_study.py --use-real-robot
```

---

## 📚 相关文件

- [simulate_full_flow.py](../scripts/simulate_full_flow.py) - 全流程仿真环境
- [record_vision_data.py](../scripts/record_vision_data.py) - 数据录制工具
- [playback_vision_data.py](../scripts/playback_vision_data.py) - 数据回放工具
- [run_real_robot_vist_refactored.py](../scripts/run_real_robot_vist_refactored.py) - 真机控制器
- [diagnose_sim_vs_real.py](../scripts/diagnose_sim_vs_real.py) - 仿真真机对比

---

## 🚀 快速开始

最简单的测试流程：

```bash
# 1. 录制
python scripts/record_vision_data.py data/test.jsonl --duration 30

# 2. 仿真验证
python scripts/simulate_full_flow.py &
python scripts/playback_vision_data.py data/test.jsonl

# 3. 真机部署（仿真验证通过后）
python scripts/run_real_robot_vist_refactored.py --duration 60
```

---

**作者**: VIST Project
**日期**: 2026-02-22