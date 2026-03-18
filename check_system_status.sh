#!/bin/bash
# 系统状态检查脚本

echo "=========================================="
echo "  双臂遥操作系统状态检查"
echo "=========================================="
echo ""

# 1. 检查ROS2节点
echo "1. ROS2节点状态:"
echo "----------------------------------------"
ros2 node list 2>/dev/null | while read node; do
    echo "  ✓ $node"
done
echo ""

# 2. 检查话题
echo "2. 关键话题状态:"
echo "----------------------------------------"
TOPICS=(
    "/left_arm_joint_control"
    "/right_arm_joint_control"
    "/filtered_left_joint_control"
    "/filtered_right_joint_control"
)

for topic in "${TOPICS[@]}"; do
    if ros2 topic list 2>/dev/null | grep -q "^${topic}$"; then
        # 检查发布者数量
        PUB_COUNT=$(ros2 topic info "$topic" 2>/dev/null | grep "Publisher count:" | awk '{print $3}')
        SUB_COUNT=$(ros2 topic info "$topic" 2>/dev/null | grep "Subscription count:" | awk '{print $3}')
        echo "  ✓ $topic"
        echo "    发布者: $PUB_COUNT | 订阅者: $SUB_COUNT"
    else
        echo "  ✗ $topic (不存在)"
    fi
done
echo ""

# 3. 检查话题频率
echo "3. 话题频率检查 (采样3秒):"
echo "----------------------------------------"
for topic in "${TOPICS[@]}"; do
    if ros2 topic list 2>/dev/null | grep -q "^${topic}$"; then
        echo -n "  $topic: "
        HZ=$(timeout 3 ros2 topic hz "$topic" 2>&1 | grep "average rate" | awk '{print $3}')
        if [ -n "$HZ" ]; then
            echo "${HZ} Hz"
        else
            echo "无数据"
        fi
    fi
done
echo ""

# 4. 检查数据流
echo "4. 数据流检查:"
echo "----------------------------------------"
echo "  LinkerTA → 原始数据:"
for topic in "/left_arm_joint_control" "/right_arm_joint_control"; do
    if ros2 topic list 2>/dev/null | grep -q "^${topic}$"; then
        DATA=$(timeout 1 ros2 topic echo "$topic" --once 2>/dev/null | grep "position:" | head -1)
        if [ -n "$DATA" ]; then
            echo "    ✓ $topic 有数据"
        else
            echo "    ✗ $topic 无数据"
        fi
    fi
done

echo ""
echo "  滤波节点 → 滤波数据:"
for topic in "/filtered_left_joint_control" "/filtered_right_joint_control"; do
    if ros2 topic list 2>/dev/null | grep -q "^${topic}$"; then
        DATA=$(timeout 1 ros2 topic echo "$topic" --once 2>/dev/null | grep "position:" | head -1)
        if [ -n "$DATA" ]; then
            echo "    ✓ $topic 有数据"
        else
            echo "    ✗ $topic 无数据"
        fi
    fi
done
echo ""

# 5. 系统健康评分
echo "=========================================="
echo "  系统健康评分"
echo "=========================================="

SCORE=0
MAX_SCORE=0

# LinkerTA节点
MAX_SCORE=$((MAX_SCORE + 10))
if ros2 node list 2>/dev/null | grep -q "linkerta_node"; then
    SCORE=$((SCORE + 10))
    echo "  ✓ LinkerTA节点运行 (+10)"
else
    echo "  ✗ LinkerTA节点未运行 (0)"
fi

# 滤波节点
MAX_SCORE=$((MAX_SCORE + 20))
FILTER_COUNT=$(ros2 node list 2>/dev/null | grep -c "vist_filter_node")
if [ "$FILTER_COUNT" -eq 2 ]; then
    SCORE=$((SCORE + 20))
    echo "  ✓ 双臂滤波节点运行 (+20)"
elif [ "$FILTER_COUNT" -eq 1 ]; then
    SCORE=$((SCORE + 10))
    echo "  ⚠️  只有一个滤波节点 (+10)"
else
    echo "  ✗ 滤波节点未运行 (0)"
fi

# 话题存在
MAX_SCORE=$((MAX_SCORE + 20))
TOPIC_COUNT=0
for topic in "${TOPICS[@]}"; do
    if ros2 topic list 2>/dev/null | grep -q "^${topic}$"; then
        TOPIC_COUNT=$((TOPIC_COUNT + 1))
    fi
done
TOPIC_SCORE=$((TOPIC_COUNT * 5))
SCORE=$((SCORE + TOPIC_SCORE))
echo "  ✓ 话题存在: $TOPIC_COUNT/4 (+$TOPIC_SCORE)"

# 数据流通
MAX_SCORE=$((MAX_SCORE + 20))
DATA_COUNT=0
for topic in "${TOPICS[@]}"; do
    if ros2 topic list 2>/dev/null | grep -q "^${topic}$"; then
        DATA=$(timeout 1 ros2 topic echo "$topic" --once 2>/dev/null | grep "position:")
        if [ -n "$DATA" ]; then
            DATA_COUNT=$((DATA_COUNT + 1))
        fi
    fi
done
DATA_SCORE=$((DATA_COUNT * 5))
SCORE=$((SCORE + DATA_SCORE))
echo "  ✓ 数据流通: $DATA_COUNT/4 (+$DATA_SCORE)"

# 频率正常
MAX_SCORE=$((MAX_SCORE + 30))
FREQ_SCORE=0
for topic in "${TOPICS[@]}"; do
    if ros2 topic list 2>/dev/null | grep -q "^${topic}$"; then
        HZ=$(timeout 3 ros2 topic hz "$topic" 2>&1 | grep "average rate" | awk '{print $3}')
        if [ -n "$HZ" ]; then
            # 检查频率是否在70-90Hz范围内
            HZ_INT=$(echo "$HZ" | cut -d. -f1)
            if [ "$HZ_INT" -ge 70 ] && [ "$HZ_INT" -le 90 ]; then
                FREQ_SCORE=$((FREQ_SCORE + 7))
            fi
        fi
    fi
done
SCORE=$((SCORE + FREQ_SCORE))
echo "  ✓ 频率正常: (+$FREQ_SCORE)"

echo ""
echo "总分: $SCORE / $MAX_SCORE"
PERCENTAGE=$((SCORE * 100 / MAX_SCORE))
echo "健康度: $PERCENTAGE%"

if [ "$PERCENTAGE" -ge 90 ]; then
    echo "状态: 🟢 优秀"
elif [ "$PERCENTAGE" -ge 70 ]; then
    echo "状态: 🟡 良好"
elif [ "$PERCENTAGE" -ge 50 ]; then
    echo "状态: 🟠 一般"
else
    echo "状态: 🔴 需要修复"
fi

echo "=========================================="