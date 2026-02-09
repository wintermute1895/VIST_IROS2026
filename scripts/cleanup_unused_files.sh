#!/bin/bash
# 清理无用文件脚本

echo "🧹 开始清理无用文件..."

# 1. 删除备份文件
echo "📁 删除备份文件..."
find . -name "*.backup" -type f -delete
find . -name "*.bak" -type f -delete
find . -name "*~" -type f -delete

# 2. 删除项目根目录下的临时测试文件
echo "📁 删除临时测试文件..."
rm -f test_biomimetic_visualization.py
rm -f test_frequency_mismatch_simulation.py
rm -f test_geometric_arm_control.py
rm -f test_geometric_realtime.py
rm -f test_hierarchical_control.py
rm -f test_joint_mapping.py
rm -f test_motor_health.py
rm -f test_simulation_offset.py

# 3. 删除 Python 缓存
echo "📁 删除 Python 缓存..."
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null
find . -type f -name "*.pyc" -delete
find . -type f -name "*.pyo" -delete

# 4. 删除临时文件
echo "📁 删除临时文件..."
find . -type f -name ".DS_Store" -delete
find . -type f -name "Thumbs.db" -delete

echo "✅ 清理完成！"
echo ""
echo "📊 清理统计："
echo "   - 备份文件: 已删除"
echo "   - 临时测试文件: 已删除"
echo "   - Python 缓存: 已删除"
echo ""
echo "💡 提示：运行 'git status' 查看变更"
