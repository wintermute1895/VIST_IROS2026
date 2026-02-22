# 真机控制参数优化建议

## 当前问题
1. 控制频率太低（10 Hz），导致响应慢、有颤动
2. 速度限制太严格（0.1 rad/s），51%的帧被限制
3. 大量时间浪费在sleep（96ms/帧）

## 优化方案

### 方案1：保守提升（推荐先试这个）
```yaml
control:
  frequency: 15  # Hz (从10提高到15)
  dt: 0.0667     # 1/15
  max_joint_velocity: 0.3      # rad/s (从0.1提高到0.3)
  max_joint_acceleration: 0.5  # rad/s² (从0.2提高到0.5)

hardware:
  move_joint_speed: 0.2   # rad/s (从0.1提高到0.2)
  move_joint_accel: 0.2   # rad/s² (从0.1提高到0.2)
```

**预期效果**：
- 响应更快，颤动减少
- 速度限制触发率从51%降到~20%
- 电机负载适中

### 方案2：激进提升（如果方案1效果好）
```yaml
control:
  frequency: 20  # Hz
  dt: 0.05       # 1/20
  max_joint_velocity: 0.5      # rad/s
  max_joint_acceleration: 0.8  # rad/s²

hardware:
  move_joint_speed: 0.3   # rad/s
  move_joint_accel: 0.3   # rad/s²
```

## 关于 move_joint 的轨迹规划

**block=False 模式**（当前使用）：
- 非阻塞，立即返回
- 新命令会打断旧轨迹
- 适合高频控制

**关键**：
- speed 和 accel 参数控制轨迹的平滑度
- 不是控制频率的限制
- 可以在高频率下使用较低的 speed/accel 来保证平滑

## 为什么可以提高频率

1. **处理能力充足**：
   - 当前循环只需 3.75 ms
   - 20 Hz 需要 50 ms/帧
   - 有 46 ms 的余量

2. **block=False 模式**：
   - 不等待轨迹完成
   - 可以高频发送命令

3. **硬件支持**：
   - 电机控制器可以处理更高频率
   - 只要 speed/accel 合理，不会过载

## 测试步骤

1. 先试方案1（15 Hz + 0.3 rad/s）
2. 观察：
   - 运动是否更流畅
   - 电机温度是否正常
   - 速度限制触发率
3. 如果效果好且电机不热，再试方案2
4. 记录每次测试的性能数据

## 注意事项

- 逐步提高，不要一次改太多
- 每次测试后检查电机温度
- 观察安全限制触发率
- 如果电机发热，降低参数