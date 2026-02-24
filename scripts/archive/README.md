# 归档的录制脚本

这些脚本已被废弃，保留仅供参考。

## 废弃原因

### collect_data.sh
- 功能已被 record_configurable.sh 覆盖
- 输出目录不明确
- 缺少配置化支持

### collect_vision_data.sh
- 输出目录 vision_experiments/ 不存在
- 与 record_vision_only.sh 功能重复
- 未集成到新的数据管理系统

### record_vision_only.sh
- 与 quick_record.sh 功能重复
- 都输出到 vision_recordings/
- quick_record.sh 更简洁

## 新的录制脚本

请使用以下脚本：

1. **scripts/record_data.sh** - 主要录制脚本（增强版record_configurable.sh）
   - 集成Episode管理器
   - 自动质量验证
   - 统一输出到 data/collection/

2. **scripts/quick_record.sh** - 快速测试录制
   - 简化版本
   - 用于快速测试

3. **scripts/episode_manager.py** - Episode管理器
   - 任务管理
   - 自动编号
   - 质量验证

## 迁移指南

如果你之前使用这些脚本，请迁移到新的脚本：

### 从 collect_data.sh 迁移
```bash
# 旧方式
bash scripts/collect_data.sh

# 新方式
python scripts/episode_manager.py create-task --name my_task --config config/task_config.yaml
python scripts/episode_manager.py interactive --session session_YYYYMMDD_HHMMSS
```

### 从 collect_vision_data.sh 迁移
```bash
# 旧方式
bash scripts/collect_vision_data.sh

# 新方式
bash scripts/quick_record.sh 30
```

### 从 record_vision_only.sh 迁移
```bash
# 旧方式
bash scripts/record_vision_only.sh

# 新方式
bash scripts/quick_record.sh 30
```
