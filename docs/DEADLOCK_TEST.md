# VIST 死锁测试指南

## 目的

诊断机械臂抖动的根本原因：
- **外部输入问题**（遥操臂信号脏、α跳变）
- **算法内部问题**（卡尔曼增益过大、自激震荡）

## 测试原理

**死锁测试**通过以下方式隔离问题：

1. **锁定 α=1.0**（全约束模式）
2. **观测值=当前状态**（不接受外部输入）
3. **系统变成"自己跟自己玩"**

这样可以排除外部干扰，只测试算法内部稳定性。

## 使用方法

### 方法1: 手动修改代码（推荐）

1. **编辑文件**:
   ```bash
   vim ros2_ws/src/core/vist_kalman_filter.py
   ```

2. **找到 update() 方法**（约第546行）

3. **取消注释测试代码**（约第560-570行）:
   ```python
   # 找到这些行并取消注释：
   # ENABLE_DEADLOCK_TEST = True
   # if ENABLE_DEADLOCK_TEST:
   #     alpha = 1.0
   #     shadow_joints = self.state[:self.n_joints]
   #     print(f"[DEADLOCK TEST] α={alpha:.3f}, using internal state as observation")
   #     self.alpha = alpha
   #     self.alpha_smoothed = alpha
   ```

   改为：
   ```python
   ENABLE_DEADLOCK_TEST = True
   if ENABLE_DEADLOCK_TEST:
       alpha = 1.0
       shadow_joints = self.state[:self.n_joints]
       print(f"[DEADLOCK TEST] α={alpha:.3f}, using internal state as observation")
       self.alpha = alpha
       self.alpha_smoothed = alpha
   ```

4. **重启节点**:
   ```bash
   pkill -f vist_filter_node
   source ros2_ws/install/setup.bash
   python3 ros2_ws/src/nodes/vist_filter_node.py \
       --ros-args --params-file config/baseline_filters_config.yaml &
   ```

5. **观察日志**:
   ```bash
   # 查看测试输出
   ros2 topic echo /rosout | grep DEADLOCK

   # 或查看节点日志
   tail -f /tmp/vist_deadlock_test.log | grep DEADLOCK
   ```

### 方法2: 使用脚本（自动）

```bash
# 启用死锁测试
./deadlock_test.sh enable

# 禁用死锁测试（恢复正常）
./deadlock_test.sh disable
```

## 诊断结果

### 情况A: 机械臂不抖了 ✅

**结论**: 抖动来自**外部输入**或**α跳变**

**可能原因**:
1. 遥操臂信号太脏（高频噪声）
2. α在0和1之间疯狂跳变（意图切换震荡）
3. 虚拟引导计算不稳定
4. 输入数据采样率不稳定

**解决方案**:
```yaml
# 方案1: 增加α平滑
intent_detection:
  intent_smoothing: 0.95  # 从0.7增加到0.95

# 方案2: 增加输入滤波
filtering:
  enable_mapper_filter: true
  oneeuro_min_cutoff: 0.02  # 降低截止频率

# 方案3: 放宽约束方差（减少α的影响）
task_covariance:
  cons_variance_xyz: [0.2, 0.2, 1.0]  # 从0.01增加到0.2
```

**进一步诊断**:
```bash
# 查看α的实时变化
ros2 topic echo /vist_intent_factors

# 如果α在疯狂跳变（0.2 → 0.9 → 0.3 → 0.8...）
# 说明意图检测逻辑有问题
```

---

### 情况B: 机械臂还在抖 ❌

**结论**: 抖动来自**算法内部**

**可能原因**:
1. **卡尔曼增益过大**（自激震荡）
2. **约束方差过紧**（0.01太小，导致过度约束）
3. **过程噪声设置不当**
4. **观测噪声过小**（过度信任观测）

**解决方案**:

```yaml
# 方案1: 放宽约束方差（最重要！）
task_covariance:
  cons_variance_xyz: [0.1, 0.1, 1.0]  # 从0.01增加到0.1

# 方案2: 增加过程噪声
process_model:
  position_variance: 1e-3  # 从1e-4增加到1e-3
  velocity_variance: 1e-2  # 从1e-3增加到1e-2

# 方案3: 增加观测噪声（降低卡尔曼增益）
observation_model:
  human_base_variance: 1e-1  # 从1e-2增加到1e-1
  virtual_base_variance: 1e-3  # 从1e-4增加到1e-3
```

**理论分析**:

当 α=1.0 且观测值=当前状态时：
```
观测: z = x (观测值等于状态)
预测: x_pred = F @ x
更新: x_new = x_pred + K @ (z - H @ x_pred)
     = x_pred + K @ (x - x_pred)
```

如果卡尔曼增益 K 过大：
- K → 1: x_new = x（完全信任观测）
- K → 0: x_new = x_pred（完全信任预测）

当 K 在中间值且约束方差很小时，系统可能产生**自激震荡**。

---

## 验证方法

### 1. 检查α是否锁定

```bash
ros2 topic echo /vist_intent_factors
```

应该看到：
```
data: [1.0, 0.0, 0.0, 0.0]
      [α,   α_geo, α_vel, α_alignment]
```

α应该恒定为1.0。

### 2. 检查观测值

在代码中添加打印：
```python
if ENABLE_DEADLOCK_TEST:
    print(f"[DEADLOCK] shadow_joints: {shadow_joints}")
    print(f"[DEADLOCK] state: {self.state[:self.n_joints]}")
```

两者应该相同。

### 3. 观察机械臂行为

- **不抖**: 外部输入问题
- **还抖**: 算法内部问题

---

## 测试完成后

**记得禁用测试模式！**

```bash
# 方法1: 手动注释代码
# 将 ENABLE_DEADLOCK_TEST = True 改为 False

# 方法2: 使用脚本
./deadlock_test.sh disable

# 方法3: 恢复备份
cp ros2_ws/src/core/vist_kalman_filter.py.backup_deadlock \
   ros2_ws/src/core/vist_kalman_filter.py
```

---

## 理论背景

### 为什么这个测试有效？

**正常模式**:
```
输入: 遥操臂信号（可能有噪声）
     ↓
  意图检测（α可能跳变）
     ↓
  卡尔曼滤波（融合多源信息）
     ↓
  输出: 滤波后的关节角度
```

**死锁测试模式**:
```
输入: 内部状态（无外部噪声）
     ↓
  意图检测（α锁定为1.0）
     ↓
  卡尔曼滤波（只处理内部状态）
     ↓
  输出: 应该稳定不变
```

如果死锁模式下还抖动，说明卡尔曼滤波器在"自己跟自己玩"的过程中产生了震荡。

### 自激震荡的数学原理

卡尔曼滤波器的更新方程：
```
K = P_pred @ H^T @ inv(H @ P_pred @ H^T + R)
x_new = x_pred + K @ (z - H @ x_pred)
```

当：
1. R很小（约束方差0.01很小）
2. z = x（观测值=当前状态）
3. 系统处于高增益状态

可能导致：
```
x(k+1) = x(k) + K @ noise
```

如果 K 过大，微小的数值误差会被放大，产生震荡。

---

## 相关文件

- 测试代码: [ros2_ws/src/core/vist_kalman_filter.py](../ros2_ws/src/core/vist_kalman_filter.py) (第560-570行)
- 自动脚本: [deadlock_test.sh](../deadlock_test.sh)
- 参数修复: [fix_shaking.sh](../fix_shaking.sh)
