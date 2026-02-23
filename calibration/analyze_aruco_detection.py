"""
ArUco标记检测精度分析
====================
分析ArUco标记的检测精度、角点质量和中心点准确性

使用方法:
    python analyze_aruco_detection.py
"""

import sys
from pathlib import Path
import numpy as np
import cv2
from typing import Optional, Tuple, List

sys.path.insert(0, str(Path(__file__).parent))

import config

def analyze_aruco_detection(image: np.ndarray, image_name: str) -> dict:
    """分析单张图像的ArUco检测质量"""

    result = {
        'image_name': image_name,
        'markers_detected': 0,
        'marker_details': [],
        'detection_quality': 'unknown'
    }

    # 获取ArUco字典
    aruco_dict = cv2.aruco.getPredefinedDictionary(config.CHARUCO_CONFIG['dict_type'])

    # 检测参数
    detector_params = cv2.aruco.DetectorParameters()
    detector = cv2.aruco.ArucoDetector(aruco_dict, detector_params)

    # 检测标记
    corners, ids, rejected = detector.detectMarkers(image)

    # 创建可视化图像
    vis_image = image.copy()

    if ids is not None and len(ids) > 0:
        result['markers_detected'] = len(ids)

        # 绘制检测到的标记
        cv2.aruco.drawDetectedMarkers(vis_image, corners, ids)

        # 分析每个标记
        for i, (corner, marker_id) in enumerate(zip(corners, ids)):
            corner_points = corner[0]  # shape: (4, 2)

            # 计算中心点
            center = corner_points.mean(axis=0)

            # 计算角点之间的距离（用于评估检测质量）
            edge_lengths = []
            for j in range(4):
                p1 = corner_points[j]
                p2 = corner_points[(j+1) % 4]
                length = np.linalg.norm(p2 - p1)
                edge_lengths.append(length)

            # 计算对角线长度
            diag1 = np.linalg.norm(corner_points[0] - corner_points[2])
            diag2 = np.linalg.norm(corner_points[1] - corner_points[3])

            # 评估检测质量
            edge_std = np.std(edge_lengths)  # 边长标准差，越小越好
            edge_mean = np.mean(edge_lengths)
            edge_cv = edge_std / edge_mean if edge_mean > 0 else 0  # 变异系数

            diag_diff = abs(diag1 - diag2)  # 对角线差异，越小越好
            diag_ratio = diag_diff / max(diag1, diag2) if max(diag1, diag2) > 0 else 0

            # 计算标记面积
            area = cv2.contourArea(corner_points)

            marker_info = {
                'id': int(marker_id[0]),
                'center': center.tolist(),
                'corners': corner_points.tolist(),
                'edge_lengths': [float(l) for l in edge_lengths],
                'edge_mean': float(edge_mean),
                'edge_std': float(edge_std),
                'edge_cv': float(edge_cv),
                'diagonal_diff': float(diag_diff),
                'diagonal_ratio': float(diag_ratio),
                'area': float(area)
            }

            # 质量评估
            if edge_cv < 0.05 and diag_ratio < 0.05:
                marker_info['quality'] = 'excellent'
                quality_color = (0, 255, 0)  # 绿色
            elif edge_cv < 0.10 and diag_ratio < 0.10:
                marker_info['quality'] = 'good'
                quality_color = (0, 255, 255)  # 黄色
            else:
                marker_info['quality'] = 'poor'
                quality_color = (0, 0, 255)  # 红色

            result['marker_details'].append(marker_info)

            # 在图像上绘制高亮中心点
            center_int = tuple(center.astype(int))

            # 绘制多层圆圈，形成高亮效果
            cv2.circle(vis_image, center_int, 12, (0, 255, 255), 2)  # 外圈（青色）
            cv2.circle(vis_image, center_int, 8, (255, 255, 0), 2)   # 中圈（黄色）
            cv2.circle(vis_image, center_int, 4, (255, 0, 255), -1)  # 内圈（紫色，实心）

            # 绘制十字线
            cross_size = 15
            cv2.line(vis_image,
                    (center_int[0] - cross_size, center_int[1]),
                    (center_int[0] + cross_size, center_int[1]),
                    (0, 255, 255), 2)
            cv2.line(vis_image,
                    (center_int[0], center_int[1] - cross_size),
                    (center_int[0], center_int[1] + cross_size),
                    (0, 255, 255), 2)

            # 绘制标记ID和质量
            text_pos = (center_int[0] + 20, center_int[1] - 20)
            cv2.putText(vis_image, f"ID:{marker_id[0]}", text_pos,
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, quality_color, 2)

            # 绘制角点编号
            for j, pt in enumerate(corner_points):
                pt_int = tuple(pt.astype(int))
                cv2.circle(vis_image, pt_int, 3, (0, 255, 0), -1)
                cv2.putText(vis_image, str(j), (pt_int[0]+5, pt_int[1]-5),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.3, (255, 255, 255), 1)

        # 整体质量评估
        avg_cv = np.mean([m['edge_cv'] for m in result['marker_details']])
        if avg_cv < 0.05:
            result['detection_quality'] = 'excellent'
        elif avg_cv < 0.10:
            result['detection_quality'] = 'good'
        else:
            result['detection_quality'] = 'poor'

    else:
        result['detection_quality'] = 'no_markers'

    # 显示被拒绝的候选
    if rejected is not None and len(rejected) > 0:
        result['rejected_candidates'] = len(rejected)
        # 绘制被拒绝的候选（红色）
        for rej_corner in rejected:
            pts = rej_corner[0].astype(int)
            cv2.polylines(vis_image, [pts], True, (0, 0, 255), 1)

    return result, vis_image

def main():
    """主函数"""
    print("\n" + "="*70)
    print("ArUco标记检测精度分析")
    print("="*70)

    # 加载图像
    image_files = sorted(config.PATHS['images_dir'].glob("image_*.png"))

    if len(image_files) == 0:
        print(f"\n✗ 未找到图像文件")
        return

    print(f"\n找到 {len(image_files)} 张图像")

    # 创建输出目录
    output_dir = config.PATHS['data_dir'] / "aruco_detection_analysis"
    output_dir.mkdir(exist_ok=True)

    all_results = []

    print("\n" + "="*70)
    print("逐张分析:")
    print("="*70)

    for i, image_file in enumerate(image_files):
        image = cv2.imread(str(image_file))

        print(f"\n图像 {i+1}: {image_file.name}")
        print("-" * 70)

        result, vis_image = analyze_aruco_detection(image, image_file.name)
        all_results.append(result)

        # 保存可视化结果
        output_path = output_dir / f"analysis_{i:03d}.png"
        cv2.imwrite(str(output_path), vis_image)

        # 打印结果
        print(f"检测到的标记数: {result['markers_detected']}")

        if result['markers_detected'] > 0:
            print(f"整体检测质量: {result['detection_quality']}")
            print(f"\n标记详情:")

            for marker in result['marker_details']:
                print(f"  标记 ID {marker['id']}:")
                print(f"    中心点: ({marker['center'][0]:.1f}, {marker['center'][1]:.1f})")
                print(f"    边长: {[f'{l:.1f}' for l in marker['edge_lengths']]}")
                print(f"    平均边长: {marker['edge_mean']:.1f} px")
                print(f"    边长标准差: {marker['edge_std']:.2f} px")
                print(f"    边长变异系数: {marker['edge_cv']:.4f}", end="")
                if marker['edge_cv'] < 0.05:
                    print(" ✓ (优秀)")
                elif marker['edge_cv'] < 0.10:
                    print(" (良好)")
                else:
                    print(" ⚠️ (较差)")

                print(f"    对角线差异: {marker['diagonal_diff']:.2f} px")
                print(f"    对角线比率: {marker['diagonal_ratio']:.4f}", end="")
                if marker['diagonal_ratio'] < 0.05:
                    print(" ✓ (优秀)")
                elif marker['diagonal_ratio'] < 0.10:
                    print(" (良好)")
                else:
                    print(" ⚠️ (较差)")

                print(f"    标记面积: {marker['area']:.0f} px²")
                print(f"    质量评级: {marker['quality']}")
        else:
            print("  未检测到标记")

        if 'rejected_candidates' in result:
            print(f"\n被拒绝的候选: {result['rejected_candidates']} 个")

    # 统计分析
    print("\n" + "="*70)
    print("统计分析")
    print("="*70)

    total_markers = sum(r['markers_detected'] for r in all_results)
    images_with_markers = sum(1 for r in all_results if r['markers_detected'] > 0)

    print(f"\n总体统计:")
    print(f"  有标记的图像: {images_with_markers}/{len(all_results)}")
    print(f"  检测到的标记总数: {total_markers}")
    print(f"  平均每张图像: {total_markers/len(all_results):.1f} 个标记")

    # 质量分布
    quality_counts = {'excellent': 0, 'good': 0, 'poor': 0}
    all_markers = []
    for r in all_results:
        for m in r.get('marker_details', []):
            quality_counts[m['quality']] += 1
            all_markers.append(m)

    if len(all_markers) > 0:
        print(f"\n检测质量分布:")
        print(f"  优秀: {quality_counts['excellent']} ({quality_counts['excellent']/len(all_markers)*100:.1f}%)")
        print(f"  良好: {quality_counts['good']} ({quality_counts['good']/len(all_markers)*100:.1f}%)")
        print(f"  较差: {quality_counts['poor']} ({quality_counts['poor']/len(all_markers)*100:.1f}%)")

        # 边长统计
        all_edge_lengths = []
        for m in all_markers:
            all_edge_lengths.extend(m['edge_lengths'])

        print(f"\n边长统计:")
        print(f"  平均: {np.mean(all_edge_lengths):.1f} px")
        print(f"  范围: {np.min(all_edge_lengths):.1f} - {np.max(all_edge_lengths):.1f} px")
        print(f"  标准差: {np.std(all_edge_lengths):.1f} px")

        # 变异系数统计
        all_cvs = [m['edge_cv'] for m in all_markers]
        print(f"\n边长变异系数统计:")
        print(f"  平均: {np.mean(all_cvs):.4f}")
        print(f"  最大: {np.max(all_cvs):.4f}")
        print(f"  最小: {np.min(all_cvs):.4f}")

        # 面积统计
        all_areas = [m['area'] for m in all_markers]
        print(f"\n标记面积统计:")
        print(f"  平均: {np.mean(all_areas):.0f} px²")
        print(f"  范围: {np.min(all_areas):.0f} - {np.max(all_areas):.0f} px²")

    print(f"\n✓ 可视化结果已保存到: {output_dir}")
    print("="*70 + "\n")

    # 给出建议
    print("检测质量评估:")
    print("-" * 70)

    if images_with_markers < len(all_results) * 0.5:
        print("⚠️ 超过50%的图像未检测到标记")
        print("   建议: 检查拍摄距离和光照条件")

    if len(all_markers) > 0:
        avg_cv = np.mean([m['edge_cv'] for m in all_markers])
        if avg_cv > 0.10:
            print("⚠️ 平均边长变异系数较大")
            print("   可能原因: 图像模糊、标记变形、或检测不准确")
            print("   建议: 改善图像清晰度，确保标记平整")

        poor_ratio = quality_counts['poor'] / len(all_markers) if len(all_markers) > 0 else 0
        if poor_ratio > 0.3:
            print(f"⚠️ {poor_ratio*100:.1f}%的标记检测质量较差")
            print("   建议: 改善拍摄条件或使用更大的标记")

    print("\n" + "="*70)

if __name__ == "__main__":
    main()
