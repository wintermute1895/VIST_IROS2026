#!/bin/bash
# 项目清理脚本
# 删除临时分析文档、测试文件、演示脚本和数据文件

echo "🗑️  开始清理项目..."

# 1. 删除临时分析文档
echo "删除临时分析文档..."
rm -f docs/ARCHITECTURE_ANALYSIS_FOR_GEMINI.md
rm -f docs/GEMINI_REVIEW_RESPONSE.md
rm -f docs/COMMUNICATION_AND_CONCURRENCY_ANALYSIS.md
rm -f docs/SDK_ARCHITECTURE_AND_IMPROVEMENTS.md
rm -f docs/ARCHITECTURE_FIX_SUMMARY.md
rm -f docs/CODE_ARCHITECTURE_VERIFICATION.md
rm -f docs/SOFTWARE_ENGINEERING_AUDIT_REPORT.md
rm -f docs/PROJECT_CLEANUP_GUIDE.md
rm -f docs/IK_ANALYSIS_CORRECTION.md
rm -f docs/LIE_ALGEBRA_CODE_REVIEW.md

# 2. 删除测试文件
echo "删除测试文件..."
rm -f test_se3_distance_fix.py
rm -f test_velocity_lie.py

# 3. 删除演示脚本
echo "删除演示脚本..."
rm -f scripts/animate_robot_usb_insertion.py
rm -f scripts/animate_robot_usb_insertion_v2.py
rm -f scripts/animate_vist_filtering.py
rm -f scripts/simulate_peg_in_hole_task.py
rm -f scripts/visualize_vist_manifold_constraint.py
rm -f scripts/verify_correct_q_matrix.py

# 4. 删除数据文件
echo "删除数据文件..."
rm -f peg_in_hole_vist_filtering.npz
rm -f robot_usb_insertion_animation.gif
rm -f vist_trajectory_animation.gif
rm -f vist_manifold_constraint.mp4
rm -rf data/experiments/

# 5. 删除错误放置的文件
echo "删除错误放置的文件..."
rm -f docs/correct_Q_matrix_design.py

# 6. 删除清理脚本本身（可选）
# rm -f clean_project.py

echo "✅ 清理完成！"
echo ""
echo "保留的重要文件："
echo "  - 核心代码: src/control/threaded_vist_controller.py"
echo "  - 运行脚本: scripts/run_threaded_vist.py"
echo "  - 重要文档: docs/MULTITHREADING_IMPLEMENTATION_SUMMARY.md"
echo "  - 重要文档: docs/THREADING_AND_COMMUNICATION_OPTIMIZATION.md"
echo "  - 重要文档: docs/ROBOT_API_USAGE_AND_READINESS_CHECK.md"
echo ""
echo "下一步："
echo "  1. 检查修改的文件: git diff"
echo "  2. 提交核心代码: git add src/control/threaded_vist_controller.py ..."
echo "  3. 创建提交: git commit -m 'feat: 多线程优化'"