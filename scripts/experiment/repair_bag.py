#!/usr/bin/env python3
"""
ROS2 Bag 数据库修复工具
用于修复因强制终止而损坏的 rosbag2 数据库
"""

import os
import sys
import sqlite3
from pathlib import Path

# 颜色定义
GREEN = '\033[0;32m'
YELLOW = '\033[1;33m'
RED = '\033[0;31m'
BLUE = '\033[0;34m'
NC = '\033[0m'


def check_database(db_path: str) -> bool:
    """
    检查数据库是否损坏

    Args:
        db_path: 数据库文件路径

    Returns:
        True 如果数据库正常，False 如果损坏
    """
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # 尝试执行完整性检查
        cursor.execute("PRAGMA integrity_check")
        result = cursor.fetchone()

        conn.close()

        if result and result[0] == 'ok':
            return True
        else:
            print(f"{RED}数据库完整性检查失败: {result}{NC}")
            return False
    except sqlite3.DatabaseError as e:
        print(f"{RED}数据库错误: {e}{NC}")
        return False
    except Exception as e:
        print(f"{RED}检查失败: {e}{NC}")
        return False


def repair_database(db_path: str) -> bool:
    """
    尝试修复数据库

    Args:
        db_path: 数据库文件路径

    Returns:
        True 如果修复成功，False 如果失败
    """
    backup_path = f"{db_path}.backup"

    try:
        # 创建备份
        print(f"{YELLOW}创建备份: {backup_path}{NC}")
        import shutil
        shutil.copy2(db_path, backup_path)

        # 尝试修复
        print(f"{YELLOW}尝试修复数据库...{NC}")

        # 方法 1: 使用 sqlite3 的 dump 和 restore
        conn = sqlite3.connect(db_path)

        # 导出到临时文件
        temp_sql = f"{db_path}.sql"
        with open(temp_sql, 'w') as f:
            for line in conn.iterdump():
                f.write(f'{line}\n')
        conn.close()

        # 删除原数据库
        os.remove(db_path)

        # 从 SQL 重建
        conn = sqlite3.connect(db_path)
        with open(temp_sql, 'r') as f:
            conn.executescript(f.read())
        conn.close()

        # 删除临时文件
        os.remove(temp_sql)

        print(f"{GREEN}✓ 数据库修复完成{NC}")
        return True

    except Exception as e:
        print(f"{RED}修复失败: {e}{NC}")

        # 恢复备份
        if os.path.exists(backup_path):
            print(f"{YELLOW}恢复备份...{NC}")
            shutil.copy2(backup_path, db_path)

        return False


def main():
    """主函数"""
    if len(sys.argv) < 2:
        print(f"{BLUE}ROS2 Bag 数据库修复工具{NC}")
        print()
        print("用法:")
        print(f"  {sys.argv[0]} <bag_directory>")
        print()
        print("示例:")
        print(f"  {sys.argv[0]} data/experiments/experiment_20260227_142235")
        sys.exit(1)

    bag_dir = sys.argv[1]

    if not os.path.isdir(bag_dir):
        print(f"{RED}错误: 目录不存在: {bag_dir}{NC}")
        sys.exit(1)

    print(f"{BLUE}========================================{NC}")
    print(f"{BLUE}ROS2 Bag 数据库修复工具{NC}")
    print(f"{BLUE}========================================{NC}")
    print()
    print(f"Bag 目录: {bag_dir}")
    print()

    # 查找数据库文件
    db_files = list(Path(bag_dir).glob("*.db3"))

    if not db_files:
        print(f"{RED}错误: 未找到数据库文件 (*.db3){NC}")
        sys.exit(1)

    print(f"找到 {len(db_files)} 个数据库文件:")
    for db_file in db_files:
        print(f"  - {db_file.name}")
    print()

    # 检查和修复每个数据库
    all_ok = True
    for db_file in db_files:
        print(f"{YELLOW}检查: {db_file.name}{NC}")

        if check_database(str(db_file)):
            print(f"{GREEN}✓ 数据库正常{NC}")
        else:
            print(f"{RED}✗ 数据库损坏{NC}")
            all_ok = False

            # 询问是否修复
            response = input(f"{YELLOW}是否尝试修复？[y/N]: {NC}").strip().lower()
            if response in ['y', 'yes']:
                if repair_database(str(db_file)):
                    # 再次检查
                    if check_database(str(db_file)):
                        print(f"{GREEN}✓ 修复成功，数据库现在正常{NC}")
                    else:
                        print(f"{RED}✗ 修复后数据库仍有问题{NC}")
                else:
                    print(f"{RED}✗ 修复失败{NC}")
        print()

    print(f"{BLUE}========================================{NC}")
    if all_ok:
        print(f"{GREEN}所有数据库都正常{NC}")
    else:
        print(f"{YELLOW}部分数据库有问题{NC}")
    print(f"{BLUE}========================================{NC}")


if __name__ == '__main__':
    main()