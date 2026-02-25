# 8点会议准备材料 - VIST项目实验设计与数据整理

**会议时间**: 2026-02-24 08:00
**准备时间**: 2026-02-24 19:52 (剩余约12小时)

---

## 一、现有数据资产盘点

### 1.1 数据概况
- **数据文件总数**: 21个JSON文件（最近7天）
- **主要数据类型**:
  - 外骨骼遥操数据 (exo_arm)
  - 视觉控制数据 (vision_control)
  - 对比分析数据 (vision_vs_exo_comparison)
  - 时间同步验证数据

### 1.2 已有性能指标

#### 外骨骼遥操数据 (data/vision_vs_exo_comparison/exo_arm/)
```json
{
  "频率": 241.75 Hz,
  "平均速度": 6.85e-13 rad/s,
  "最大速度": 0.613 rad/s,
  "RMS速度": 0.130 rad/s,
  "最大加速度": 8.43 rad/s²,
  "RMS加速度": 2.15 rad/s²,
  "最大Jerk": 616.71 rad/s³,
  "RMS Jerk": 170.13 rad/s³,
  "样本数": 4470,
  "时长": 18.49秒
}
```

**关键发现**:
- ✅ 频率稳定在~242Hz（接近目标250Hz）
- ⚠️ Jerk值较高（RMS=170），说明存在高频震颤
- ⚠️ 最大Jerk达到616，存在突变

### 1.3 数据质量问题
根据之前的系统分析，现有数据存在：
1. **高频震颤未滤波** - 直接透传导致数据熵高
2. **多节点冲突风险** - 发现过4个重复节点同时运行
3. **缺少手指数据** - 之前未采集数据手套信息

---

## 二、论文实验需求分析

### 2.1 核心Research Questions

根据你的论文，需要验证5个RQ：

| RQ | 问题 | 需要的实验 | 需要的指标 |
|----|------|-----------|-----------|
| RQ1 | 控制性能与流形收敛 | 多任务精密装配 | 成功率(SR)、完成时间(CT)、归一化Jerk(NJ) |
| RQ2 | 容差灵敏度 | 不同间隙的插入任务 | 不同容差下的成功率曲线 |
| RQ3 | 交互平滑性与认知负荷 | 对比实验 | NASA-TLX问卷、Jerk指标 |
| RQ4 | 意图因子消融分析 | 消融实验 | 各组件对稳定性的贡献 |
| RQ5 | 数据质量量化 | 数据统计分析 | DTW距离、PCA能量占比、PSD频谱、SPARC |

### 2.2 实验任务设计

#### 任务1: USB插入（线流形约束）
- **目标**: 验证一维流形约束
- **指标**: SR, CT, NJ
- **对比方案**: AnyTeleop, One-Euro, TSC, VIST

#### 任务2: 积木堆叠（面流形约束）
- **目标**: 验证二维流形约束
- **指标**: SR, CT, NJ
- **对比方案**: 同上

#### 任务3: 3D打印件插入（容差测试）
- **目标**: 验证容差灵敏度
- **间隙**: 0.5mm, 1.0mm, 2.0mm
- **指标**: 不同容差下的SR

#### 任务4: 数据质量分析
- **目标**: 验证物理正则化效果
- **指标**:
  - DTW距离（轨迹一致性）
  - PCA能量占比（零空间投影）
  - PSD功率谱（高频抑制）
  - SPARC平滑度

---

## 三、新实验设计方案（外骨骼+数据手套）

### 3.1 系统配置

#### 硬件组成
```
LinkerArm A7 (7-DoF) - 机器人臂
  ↓
Linkerta外骨骼 - 臂控制 (~250Hz)
  +
LinkerHand L10 - 手指控制 (10关节, ~30Hz)
  ↓
RealSense D435i/D405 - 视觉反馈
```

#### 数据采集Topics
```python
# 臂控制
/right_arm_joint_control      # 外骨骼原始 ~250Hz
/robot1/right_arm/joint_follow # 跟随命令 ~250Hz
/robot1/right_arm/joint_states # 真机反馈 ~50Hz

# 手指控制
/cb_left_hand_control_cmd     # 手指命令 ~30Hz
/cb_left_hand_state           # 手指反馈 ~40Hz

# 视觉
/camera/color/image_raw       # RGB ~30Hz
/camera/depth/image_rect_raw  # 深度 ~30Hz
```

### 3.2 实验流程

#### Phase 1: 基线数据采集（无VIST）
```bash
# 任务: USB插入 x 20次
# 方案: AnyTeleop (Raw Teleop)
# 采集: 完整数据流（臂+手指+视觉）
# 时长: 每次约30-60秒
```

#### Phase 2: One-Euro滤波对比
```bash
# 任务: USB插入 x 20次
# 方案: One-Euro Filter
# 采集: 同上
```

#### Phase 3: 硬切换共享控制对比
```bash
# 任务: USB插入 x 20次
# 方案: TSC (Threshold-based Shared Control)
# 采集: 同上
```

#### Phase 4: VIST完整方案
```bash
# 任务: USB插入 x 20次
# 方案: VIST (Intent-driven AKF)
# 采集: 同上
```

#### Phase 5: 容差测试
```bash
# 任务: 3D打印件插入
# 间隙: 0.5mm, 1.0mm, 2.0mm
# 每个间隙 x 20次
# 方案: AnyTeleop vs VIST
```

#### Phase 6: 积木堆叠
```bash
# 任务: 精密堆叠 x 20次
# 方案: AnyTeleop vs VIST
```

### 3.3 数据分析流程

#### 实时指标计算
```python
# 每次实验后立即计算
- 成功/失败判定
- 完成时间
- 轨迹Jerk
- 频率统计
```

#### 离线深度分析
```python
# 批量分析
- DTW距离矩阵
- PCA主成分分析
- PSD频谱分析
- SPARC平滑度
- 条件熵计算
```

---

## 四、关键指标定义与计算方法

### 4.1 控制性能指标

#### 成功率 (Success Rate, SR)
```python
SR = (成功次数 / 总尝试次数) × 100%

# 成功判定标准:
# - USB插入: 完全插入且稳定
# - 积木堆叠: 堆叠稳定不倒塌
# - 3D打印件: 完全插入到底
```

#### 完成时间 (Completion Time, CT)
```python
CT = t_end - t_start  # 从接近目标到任务完成

# 统计量:
# - 平均值 (Mean CT)
# - 标准差 (Std CT)
# - 中位数 (Median CT)
```

#### 归一化Jerk (Normalized Jerk, NJ)
```python
# 对数无量纲加加速度 (Log-SPARC)
NJ = -∫ (d³x/dt³)² dt / (duration × max_velocity²)

# 物理意义: 运动平滑度
# 值越小越平滑
```

### 4.2 数据质量指标

#### DTW距离 (Dynamic Time Warping Distance)
```python
# 衡量轨迹一致性
DTW_dist = dtw(trajectory_i, trajectory_j)

# 统计量:
# - 平均DTW距离 (Mean DTW)
# - 标准差 (Std DTW)
# - 归一化DTW (Normalized DTW)

# 期望: VIST数据的DTW距离显著低于baseline
```

#### PCA能量占比 (Task-Axis PCA Ratio)
```python
# 主成分分析
pca = PCA(n_components=3)
pca.fit(velocity_data)

# 任务主轴能量占比
task_axis_ratio = pca.explained_variance_ratio_[0]

# 期望: VIST数据的主轴占比 > 95%
#      Baseline数据的主轴占比 < 70%
```

#### PSD功率谱 (Power Spectral Density)
```python
# 频域分析
freqs, psd = welch(velocity_signal, fs=250)

# 高频能量 (>5Hz)
high_freq_power = np.sum(psd[freqs > 5])

# 期望: VIST数据的高频能量显著降低
```

#### SPARC平滑度
```python
# Spectral Arc Length
SPARC = -∫ √(1 + (dP/df)²) df

# 期望: VIST数据的SPARC值更高（更平滑）
```

### 4.3 认知负荷指标

#### NASA-TLX问卷
```
6个维度（1-20分）:
1. 脑力需求 (Mental Demand)
2. 体力需求 (Physical Demand)
3. 时间压力 (Temporal Demand)
4. 努力程度 (Effort)
5. 表现水平 (Performance)
6. 挫败感 (Frustration)

加权总分 = Σ(维度分数 × 权重)
```

---

## 五、实验时间规划

### 5.1 数据采集时间估算

| 实验阶段 | 任务数 | 单次时长 | 总时长 |
|---------|--------|---------|--------|
| Phase 1 (Baseline) | 20 | 1分钟 | 20分钟 |
| Phase 2 (One-Euro) | 20 | 1分钟 | 20分钟 |
| Phase 3 (TSC) | 20 | 1分钟 | 20分钟 |
| Phase 4 (VIST) | 20 | 1分钟 | 20分钟 |
| Phase 5 (容差测试) | 60 | 1分钟 | 60分钟 |
| Phase 6 (积木堆叠) | 40 | 1分钟 | 40分钟 |
| **总计** | **180** | - | **180分钟 (3小时)** |

### 5.2 数据分析时间估算

| 分析任务 | 估算时长 |
|---------|---------|
| 实时指标计算 | 自动（实验中） |
| DTW距离计算 | 30分钟 |
| PCA分析 | 20分钟 |
| PSD频谱分析 | 20分钟 |
| SPARC计算 | 20分钟 |
| 统计检验 | 30分钟 |
| 可视化 | 60分钟 |
| **总计** | **180分钟 (3小时)** |

---

## 六、安全注意事项（基于电机烧毁事故）

### 6.1 启动前检查清单
```bash
# 1. 清理旧进程
pkill -f "linkerta_node"
pkill -f "lbot_driver"
sleep 2

# 2. 验证清理成功
if pgrep -f "linkerta_node"; then
    echo "错误: 仍有旧进程运行！"
    exit 1
fi

# 3. 检查机器人连接
ping -c 1 192.168.10.21

# 4. 检查CAN总线
ip link show can0

# 5. 检查相机
rs-enumerate-devices
```

### 6.2 运行时监控
```python
# 监控项:
- 电机电流（如果可用）
- 关节速度（不超过安全阈值）
- 关节加速度（不超过安全阈值）
- 软件崩溃检测
- 连接状态监控
```

### 6.3 紧急停止协议
```
1. 物理急停按钮（如果有）
2. Ctrl+C停止所有ROS2节点
3. 断开机器人电源
4. 记录日志和状态
```

---

## 七、会议讨论要点

### 7.1 现状总结
- ✅ 已完成数据管理标准化（Phase 1-3）
- ✅ 已完成外骨骼+数据手套集成
- ✅ 已完成系统安全分析
- ⚠️ 发生电机烧毁事故（已分析根因）
- ⚠️ 现有数据质量不足（高频震颤未处理）

### 7.2 需要讨论的问题
1. **实验优先级**: 先做哪些实验？
2. **时间安排**: 何时开始数据采集？
3. **人力分配**: 需要几个操作员？
4. **硬件修复**: 电机更换进度？
5. **安全措施**: 是否需要额外的安全设备？
6. **论文思路**: 是否需要调整实验设计？

### 7.3 预期产出
- [ ] 完整的对比实验数据（4个方案 × 3个任务）
- [ ] 容差灵敏度曲线
- [ ] 数据质量统计分析
- [ ] NASA-TLX认知负荷评估
- [ ] 消融实验结果
- [ ] 论文图表和表格

---

## 八、下一步行动计划

### 立即行动（会议前）
1. ✅ 整理现有数据和指标
2. ✅ 准备实验设计方案
3. ⏳ 准备会议PPT大纲
4. ⏳ 重新梳理论文思路

### 会议后行动
1. 根据讨论结果调整实验方案
2. 修复硬件问题
3. 实施安全改进措施
4. 开始数据采集
5. 实时分析和调整

---

## 附录：快速参考

### A. 数据采集命令
```bash
# 完整测试（臂+手指+视觉）
cd ~/Dev/VIST
./scripts/test_exo_teleop_pipeline.sh 60 "usb_insertion_baseline"

# 仅臂控制测试
ros2 bag record \
    /right_arm_joint_control \
    /robot1/right_arm/joint_follow \
    /robot1/right_arm/joint_states \
    -o data/collection/test
```

### B. 数据分析命令
```bash
# 频率分析
python3 scripts/analyze_episode.py data/collection/<episode>

# 时间同步验证
python3 scripts/validate_time_sync.py data/collection/<episode>/rosbag
```

### C. 关键文件位置
```
- 实验数据: data/collection/
- 分析脚本: scripts/analysis/
- 配置文件: config/
- 文档: docs/
- 事故报告: MOTOR_FAILURE_ROOT_CAUSE_ANALYSIS.md
```

---

**准备人**: Claude
**准备时间**: 2026-02-24 19:52
**文档版本**: v1.0