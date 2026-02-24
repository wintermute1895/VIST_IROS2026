#!/bin/bash
# 数据目录结构清理和重组脚本
# 功能：
# 1. 创建新的标准化目录结构
# 2. 迁移旧数据到archive
# 3. 为归档数据生成元数据
# 4. 更新.gitignore

set -e

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
RED='\033[0;31m'
NC='\033[0m'

# 项目根目录
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

echo -e "${CYAN}========================================${NC}"
echo -e "${CYAN}VIST 数据目录结构清理${NC}"
echo -e "${CYAN}========================================${NC}"
echo ""

# 步骤1: 创建新目录结构
echo -e "${YELLOW}步骤1: 创建新目录结构...${NC}"

mkdir -p data/collection
mkdir -p data/training
mkdir -p data/analysis
mkdir -p data/archive

echo -e "${GREEN}✓ 新目录结构已创建${NC}"
echo ""

# 步骤2: 迁移旧数据到archive
echo -e "${YELLOW}步骤2: 迁移旧数据到archive...${NC}"

# 迁移recordings
if [ -d "data/recordings" ]; then
    echo -e "  迁移 recordings/ -> archive/old_recordings/"
    mv data/recordings data/archive/old_recordings
    echo -e "${GREEN}  ✓ recordings 已迁移${NC}"
fi

# 迁移vision_recordings
if [ -d "data/vision_recordings" ]; then
    echo -e "  迁移 vision_recordings/ -> archive/old_vision_recordings/"
    mv data/vision_recordings data/archive/old_vision_recordings
    echo -e "${GREEN}  ✓ vision_recordings 已迁移${NC}"
fi

# 迁移vision_control_test_*
for dir in data/vision_control_test_*; do
    if [ -d "$dir" ]; then
        dirname=$(basename "$dir")
        echo -e "  迁移 $dirname -> archive/"
        mv "$dir" data/archive/
        echo -e "${GREEN}  ✓ $dirname 已迁移${NC}"
    fi
done

# 迁移test_publisher_exo_*
for dir in data/test_publisher_exo_*; do
    if [ -d "$dir" ]; then
        dirname=$(basename "$dir")
        echo -e "  迁移 $dirname -> archive/"
        mv "$dir" data/archive/
        echo -e "${GREEN}  ✓ $dirname 已迁移${NC}"
    fi
done

# 迁移test_new_analysis
if [ -d "data/test_new_analysis" ]; then
    echo -e "  迁移 test_new_analysis/ -> archive/"
    mv data/test_new_analysis data/archive/
    echo -e "${GREEN}  ✓ test_new_analysis 已迁移${NC}"
fi

echo ""

# 步骤3: 为归档数据生成元数据
echo -e "${YELLOW}步骤3: 为归档数据生成元数据...${NC}"

# 为old_recordings生成元数据
if [ -d "data/archive/old_recordings" ]; then
    echo -e "  为 old_recordings 生成元数据..."
    python3 scripts/generate_episode_metadata.py \
        data/archive/old_recordings \
        --batch \
        --task archived_recordings 2>/dev/null || echo -e "${YELLOW}  ⚠️  部分数据无法生成元数据${NC}"
fi

# 为old_vision_recordings生成元数据
if [ -d "data/archive/old_vision_recordings" ]; then
    echo -e "  为 old_vision_recordings 生成元数据..."
    python3 scripts/generate_episode_metadata.py \
        data/archive/old_vision_recordings \
        --batch \
        --task archived_vision_recordings 2>/dev/null || echo -e "${YELLOW}  ⚠️  部分数据无法生成元数据${NC}"
fi

echo -e "${GREEN}✓ 元数据生成完成${NC}"
echo ""

# 步骤4: 创建README文件
echo -e "${YELLOW}步骤4: 创建README文件...${NC}"

# collection/README.md
cat > data/collection/README.md << 'EOF'
# 数据采集目录

此目录存储原始采集数据，按任务和会话组织。

## 目录结构

```
collection/
├── task_name/                  # 任务名称
│   ├── session_YYYYMMDD_HHMMSS/
│   │   ├── episode_000000/
│   │   │   ├── rosbag/
│   │   │   ├── metadata.json
│   │   │   ├── sync_validation_report.json
│   │   │   └── quality_report.json
│   │   ├── episode_000001/
│   │   └── session_manifest.json
│   └── all_episodes/           # 符号链接
```

## 使用方法

### 创建新任务
```bash
python scripts/episode_manager.py create-task \
    --name task_name \
    --config config/task_config.yaml
```

### 录制数据
```bash
python scripts/episode_manager.py interactive \
    --session session_YYYYMMDD_HHMMSS
```

### 验证数据
```bash
python scripts/episode_manager.py validate \
    --episode episode_000000
```
EOF

# training/README.md
cat > data/training/README.md << 'EOF'
# 训练数据目录

此目录存储转换后的训练数据（HDF5格式）。

## 目录结构

```
training/
├── task_name/
│   ├── episode_000000.hdf5
│   ├── episode_000001.hdf5
│   └── dataset_manifest.json
```

## 使用方法

### 转换数据
```bash
python scripts/episode_manager.py convert \
    --session session_YYYYMMDD_HHMMSS \
    --quality-threshold B \
    --format hdf5
```
EOF

# analysis/README.md
cat > data/analysis/README.md << 'EOF'
# 分析结果目录

此目录存储数据分析结果和可视化图表。

## 目录结构

```
analysis/
├── task_name/
│   ├── session_YYYYMMDD_HHMMSS/
│   │   ├── frequency_analysis.png
│   │   ├── trajectory_comparison.png
│   │   └── analysis_report.json
│   └── comparison_reports/
```

## 使用方法

### 分析Episode
```bash
python scripts/analyze_episode.py \
    --episode data/collection/task_name/session_*/episode_000000
```
EOF

# archive/README.md
cat > data/archive/README.md << 'EOF'
# 归档数据目录

此目录存储旧的、已废弃的或测试数据。

## 内容

- `old_recordings/` - 旧的配置化录制数据
- `old_vision_recordings/` - 旧的视觉录制数据
- `vision_control_test_*/` - 视觉控制测试数据
- `test_publisher_exo_*/` - 测试数据

## 注意

归档数据仅供参考，不建议用于训练。
如需使用，请先验证数据质量。
EOF

echo -e "${GREEN}✓ README文件已创建${NC}"
echo ""

# 步骤5: 更新.gitignore
echo -e "${YELLOW}步骤5: 更新.gitignore...${NC}"

# 检查是否需要添加data目录规则
if ! grep -q "^# Data directories" .gitignore 2>/dev/null; then
    cat >> .gitignore << 'EOF'

# Data directories
data/collection/
data/training/
data/analysis/
data/archive/
EOF
    echo -e "${GREEN}✓ .gitignore已更新${NC}"
else
    echo -e "${YELLOW}  .gitignore已包含data目录规则${NC}"
fi

echo ""

# 步骤6: 显示清理结果
echo -e "${YELLOW}步骤6: 清理结果统计...${NC}"

echo -e "\n${CYAN}新目录结构:${NC}"
tree -L 2 -d data/ 2>/dev/null || find data -maxdepth 2 -type d | sort

echo ""
echo -e "${CYAN}归档数据统计:${NC}"
if [ -d "data/archive" ]; then
    echo -e "  归档目录数: $(find data/archive -maxdepth 1 -type d | wc -l)"
    echo -e "  归档数据大小: $(du -sh data/archive 2>/dev/null | cut -f1)"
fi

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}数据目录清理完成！${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${CYAN}下一步:${NC}"
echo "  1. 查看新目录结构: tree data/"
echo "  2. 查看归档数据: ls -lh data/archive/"
echo "  3. 开始使用新的录制流程: python scripts/episode_manager.py create-task"
echo ""
