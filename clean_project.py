#!/usr/bin/env python3
"""
VIST Project Cleanup Script
安全清理项目中的临时文件和调试产物

使用方法：
    python clean_project.py              # Dry run（只显示，不删除）
    python clean_project.py --delete     # 实际删除（需要确认）
"""

import os
import sys
from pathlib import Path
from typing import List, Dict, Tuple
import argparse


# ============================================================================
# 配置区域 - 可根据项目需求调整
# ============================================================================

# 要删除的文件模式（按类别组织）
PATTERNS_TO_DELETE = {
    'visualizations': [
        '*.png', '*.jpg', '*.jpeg', '*.gif',
        '*.mp4', '*.avi', '*.mov'
    ],
    'data_logs': [
        '*.npy', '*.npz', '*.csv', '*.pkl', '*.pickle'
    ],
    'python_cache': [
        '__pycache__', '*.pyc', '*.pyo', '*.pyd'
    ],
    'temp_scripts': [
        'test_tmp_*.py', 'debug_*.py', 'draft_*.py',
        'temp_*.py', 'tmp_*.py', 'scratch_*.py'
    ],
    'system_junk': [
        '.DS_Store', 'Thumbs.db', 'desktop.ini'
    ],
    'experiment_data': [
        'data/experiments/*',  # 实验数据目录
    ]
}

# 排除的目录（这些目录下的文件不会被删除）
EXCLUDE_DIRS = {
    'assets',      # README 插图
    'docs',        # 文档图片
    'config',      # 配置文件
    'weights',     # 模型权重
    '.git',        # Git 仓库
    'venv',        # 虚拟环境
    'env',
    '.venv',
    'node_modules',
}

# 特殊保护的文件模式（即使匹配删除规则也不删）
PROTECTED_PATTERNS = [
    'config/*.yaml',
    'config/*.yml',
    'weights/*.pth',
    'weights/*.pt',
    'docs/*.png',      # 文档中的图片
    'docs/*.jpg',
    'assets/*.png',    # 资源图片
    'assets/*.jpg',
]


# ============================================================================
# 核心功能
# ============================================================================

def get_file_size(path: Path) -> int:
    """获取文件大小（字节）"""
    try:
        if path.is_file():
            return path.stat().st_size
        elif path.is_dir():
            return sum(f.stat().st_size for f in path.rglob('*') if f.is_file())
        return 0
    except (OSError, PermissionError):
        return 0


def format_size(size_bytes: int) -> str:
    """格式化文件大小"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} TB"


def is_protected(file_path: Path, project_root: Path) -> bool:
    """检查文件是否受保护"""
    try:
        rel_path = file_path.relative_to(project_root)
    except ValueError:
        return True  # 不在项目目录内，保护

    # 检查是否在排除目录中
    for exclude_dir in EXCLUDE_DIRS:
        if exclude_dir in rel_path.parts:
            return True

    # 检查是否匹配保护模式
    for pattern in PROTECTED_PATTERNS:
        if rel_path.match(pattern):
            return True

    return False


def find_junk_files(project_root: Path) -> Dict[str, List[Tuple[Path, int]]]:
    """
    扫描项目目录，找出所有匹配删除规则的文件

    返回：{类别: [(文件路径, 文件大小), ...]}
    """
    junk_files = {category: [] for category in PATTERNS_TO_DELETE.keys()}

    print(f"🔍 正在扫描项目目录: {project_root}")
    print(f"📁 排除的目录: {', '.join(EXCLUDE_DIRS)}\n")

    for category, patterns in PATTERNS_TO_DELETE.items():
        for pattern in patterns:
            # 处理 __pycache__ 目录
            if pattern == '__pycache__':
                for pycache_dir in project_root.rglob('__pycache__'):
                    if not is_protected(pycache_dir, project_root):
                        size = get_file_size(pycache_dir)
                        junk_files[category].append((pycache_dir, size))
            else:
                # 处理文件模式
                for file_path in project_root.rglob(pattern):
                    if not is_protected(file_path, project_root):
                        size = get_file_size(file_path)
                        junk_files[category].append((file_path, size))

    return junk_files


def print_summary(junk_files: Dict[str, List[Tuple[Path, int]]], project_root: Path):
    """打印扫描结果摘要"""
    total_files = 0
    total_size = 0

    print("=" * 80)
    print("📊 扫描结果摘要")
    print("=" * 80)

    for category, files in junk_files.items():
        if not files:
            continue

        category_size = sum(size for _, size in files)
        total_files += len(files)
        total_size += category_size

        # 类别标题
        category_names = {
            'visualizations': '🖼️  可视化文件',
            'data_logs': '📊 数据日志',
            'python_cache': '🐍 Python 缓存',
            'temp_scripts': '📝 临时脚本',
            'system_junk': '🗑️  系统垃圾',
            'experiment_data': '🧪 实验数据'
        }
        print(f"\n{category_names.get(category, category)}:")
        print(f"  数量: {len(files)} 个文件/目录")
        print(f"  大小: {format_size(category_size)}")

        # 显示前 5 个文件作为示例
        for file_path, size in files[:5]:
            try:
                rel_path = file_path.relative_to(project_root)
                print(f"    - {rel_path} ({format_size(size)})")
            except ValueError:
                print(f"    - {file_path} ({format_size(size)})")

        if len(files) > 5:
            print(f"    ... 还有 {len(files) - 5} 个文件")

    print("\n" + "=" * 80)
    print(f"✅ 总计: {total_files} 个文件/目录，占用 {format_size(total_size)} 空间")
    print("=" * 80)

    return total_files, total_size


def delete_files(junk_files: Dict[str, List[Tuple[Path, int]]], dry_run: bool = True):
    """删除文件（或 dry run）"""
    deleted_count = 0
    deleted_size = 0
    failed_files = []

    for category, files in junk_files.items():
        for file_path, size in files:
            try:
                if dry_run:
                    # Dry run 模式：只显示，不删除
                    deleted_count += 1
                    deleted_size += size
                else:
                    # 实际删除
                    if file_path.is_dir():
                        import shutil
                        shutil.rmtree(file_path)
                    else:
                        file_path.unlink()
                    deleted_count += 1
                    deleted_size += size
                    print(f"✓ 已删除: {file_path}")
            except Exception as e:
                failed_files.append((file_path, str(e)))
                print(f"✗ 删除失败: {file_path} - {e}")

    return deleted_count, deleted_size, failed_files


def main():
    parser = argparse.ArgumentParser(
        description='VIST 项目清理工具 - 安全删除临时文件和调试产物',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  python clean_project.py              # Dry run（只显示，不删除）
  python clean_project.py --delete     # 实际删除（需要确认）
        """
    )
    parser.add_argument(
        '--delete',
        action='store_true',
        help='实际删除文件（默认为 dry run 模式）'
    )
    parser.add_argument(
        '--root',
        type=str,
        default='.',
        help='项目根目录（默认为当前目录）'
    )

    args = parser.parse_args()

    # 获取项目根目录
    project_root = Path(args.root).resolve()
    if not project_root.exists():
        print(f"❌ 错误: 目录不存在: {project_root}")
        sys.exit(1)

    print("🧹 VIST 项目清理工具")
    print("=" * 80)

    if not args.delete:
        print("⚠️  DRY RUN 模式 - 只显示要删除的文件，不会实际删除")
        print("   使用 --delete 参数来实际删除文件")
    else:
        print("⚠️  删除模式 - 将会实际删除文件！")

    print("=" * 80)
    print()

    # 扫描文件
    junk_files = find_junk_files(project_root)

    # 打印摘要
    total_files, total_size = print_summary(junk_files, project_root)

    if total_files == 0:
        print("\n✨ 项目很干净，没有找到需要清理的文件！")
        return

    # 如果是删除模式，需要用户确认
    if args.delete:
        print("\n⚠️  警告: 即将删除以上文件，此操作不可恢复！")
        confirmation = input("请输入 'yes' 确认删除，或按 Enter 取消: ")

        if confirmation.lower() != 'yes':
            print("❌ 已取消删除操作")
            return

        print("\n🗑️  正在删除文件...")
        deleted_count, deleted_size, failed_files = delete_files(junk_files, dry_run=False)

        print("\n" + "=" * 80)
        print(f"✅ 删除完成: {deleted_count} 个文件/目录，释放 {format_size(deleted_size)} 空间")

        if failed_files:
            print(f"\n⚠️  {len(failed_files)} 个文件删除失败:")
            for file_path, error in failed_files:
                print(f"  - {file_path}: {error}")

        print("=" * 80)
    else:
        print("\n💡 提示: 确认无误后，使用 --delete 参数来实际删除这些文件")


if __name__ == '__main__':
    main()
