# 右臂数据采集快速指南
# Quick Start Guide for Right Arm Data Collection

## 一、准备工作（5分钟）

### 1. 硬件检查
```bash
# 检查机械臂连接
ping 192.168.1.18

# 检查外骨骼连接
ros2 topic list | grep linkerta
```

### 2. 安全确认
- [ ] 急停按钮在手边
- [ ] 工作空间清空
- [ ] 机械臂状态正常

## 二、启动节点（3个终端）

### Terminal 1: 外骨骼数据源
```bash
cd /home/ilex/Dev/VIST

# 启动linkerta（只发布右臂）
ros2 run linkerta linkerta_node --ros-args \
  -p publish_left:=false \
  -p publish_right:=true
```

### Terminal 2: 滤波节点（根据实验切换）
```bash
cd /home/ilex/Dev/VIST

# 实验0: 无滤波
./scripts/start_right_arm_filter.sh none

# 实验1: EMA (alpha=0.3)
./scripts/start_right_arm_filter.sh ema 0.3

# 实验2: EMA (alpha=0.5)
./scripts/start_right_arm_filter.sh ema 0.5

# 实验3: One-Euro (标准)
./scripts/start_right_arm_filter.sh one_euro 1.0 0.007

# 实验4: One-Euro (高响应)
./scripts/start_right_arm_filter.sh one_euro 2.0 0.01
```

### Terminal 3: Teleop Bridge
```bash
cd /home/ilex/Dev/VIST/external_sdk/arm_teleop

# 启动teleop_bridge（订阅滤波后的话题）
ros2 run lbot_teleop teleop_bridge_node --ros-args \
  --params-file src/lbot_teleop/config/teleop_bridge_params.yaml \
  -p master_right_topic:=/filtered_right_joint_control \
  -p master_left_topic:=/left_arm_disabled
```

## 三、数据采集（每个实验30秒）

### Terminal 4: 数据采集
```bash
cd /home/ilex/Dev/VIST

# 实验0: 无滤波基线
./scripts/collect_right_arm_data.sh exp0_no_filter 30

# 实验1: EMA alpha=0.3
./scripts/collect_right_arm_data.sh exp1_ema_alpha03 30

# 实验2: EMA alpha=0.5
./scripts/collect_right_arm_data.sh exp2_ema_alpha05 30

# 实验3: One-Euro 标准
./scripts/collect_right_arm_data.sh exp3_oneeuro_standard 30

# 实验4: One-Euro 高响应
./scripts/collect_right_arm_data.sh exp4_oneeuro_highresp 30
```

### 测试动作序列（30秒）
1. **前后移动** (0-5秒): 手臂前后推拉
2. **左右移动** (5-10秒): 手臂左右摆动
3. **上下移动** (10-15秒): 手臂上下运动
4. **旋转运动** (15-20秒): 手腕旋转
5. **组合运动** (20-30秒): 自由组合动作

## 四、实验流程（每个实验约2分钟）

### 实验0: 无滤波基线
```bash
# Terminal 2: 启动无滤波节点
./scripts/start_right_arm_filter.sh none

# 等待节点启动（5秒）

# Terminal 4: 采集数据
./scripts/collect_right_arm_data.sh exp0_no_filter 30

# 执行测试动作...

# 完成后停止Terminal 2的滤波节点 (Ctrl+C)
```

### 实验1-4: 重复上述流程
每次实验：
1. 停止上一个滤波节点 (Ctrl+C)
2. 启动新的滤波节点（不同参数）
3. 等待5秒
4. 开始数据采集
5. 执行相同的测试动作

## 五、监控（可选，Terminal 5）

```bash
cd /home/ilex/Dev/VIST

# 实时监控系统健康
python3 scripts/monitor_system_health.py
```

检查项：
- 频率应该在 70-90 Hz
- 发布者数量应该为 1
- 无错误或警告

## 六、数据验证

### 检查采集的数据
```bash
cd /home/ilex/Dev/VIST/data/exp_right_arm_only_$(date +%Y%m%d)

# 列出所有实验
ls -lh

# 查看某个实验的信息
ros2 bag info exp0_no_filter
```

### 预期结果
每个实验应该包含：
- 约30秒的数据
- 5个话题的记录
- 文件大小约 10-50 MB

## 七、快速分析（实验后）

```bash
cd /home/ilex/Dev/VIST

# 分析所有实验数据
python3 scripts/analyze_filter_ablation.py

# 生成对比图表
# 输出: data/exp_right_arm_only_YYYYMMDD/analysis_report.pdf
```

## 八、故障排查

### 问题1: 滤波节点启动失败
```bash
# 检查Python路径
which python3

# 检查依赖
pip3 list | grep numpy
```

### 问题2: 话题未连接
```bash
# 检查话题列表
ros2 topic list

# 检查话题频率
ros2 topic hz /filtered_right_joint_control
```

### 问题3: 发布者数量异常
```bash
# 检查发布者
ros2 topic info /filtered_right_joint_control

# 如果有多个发布者，查找并停止多余的节点
ros2 node list
```

### 问题4: 机械臂运动异常
1. **立即按下急停**
2. 停止所有节点
3. 检查日志
4. 重新启动

## 九、完整实验时间表

| 时间 | 任务 | 终端 |
|-----|------|------|
| 0:00 | 启动linkerta | T1 |
| 0:30 | 启动teleop_bridge | T3 |
| 1:00 | 启动monitor（可选） | T5 |
| 1:30 | 实验0: 无滤波 | T2, T4 |
| 3:30 | 实验1: EMA 0.3 | T2, T4 |
| 5:30 | 实验2: EMA 0.5 | T2, T4 |
| 7:30 | 实验3: One-Euro标准 | T2, T4 |
| 9:30 | 实验4: One-Euro高响应 | T2, T4 |
| 11:30 | 停止所有节点 | 所有 |
| 12:00 | 数据验证 | T4 |

**总时长**: 约12分钟

## 十、安全检查清单

### 测试前
- [ ] 急停按钮可用
- [ ] 工作空间清空
- [ ] 机械臂状态正常
- [ ] 外骨骼校准完成
- [ ] 所有节点配置正确

### 测试中
- [ ] 监控频率正常（80Hz）
- [ ] 只有1个发布者
- [ ] 运动平滑无异常
- [ ] 无错误日志

### 测试后
- [ ] 数据已保存
- [ ] 所有节点已停止
- [ ] 机械臂回到安全位置
- [ ] 记录实验日志

---

**重要提示**:
- 首次测试时保持低速运动
- 如有任何异常立即按下急停
- 每个实验使用相同的测试动作以确保可比性

更新日期: 2026-02-25