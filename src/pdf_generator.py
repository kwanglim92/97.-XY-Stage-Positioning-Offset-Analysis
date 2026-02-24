"""
pdf_generator.py — PDF 리포트 자동 생성

matplotlib.backends.backend_pdf.PdfPages 를 활용하여
분석 결과 요약 및 차트를 포함하는 다페이지 리포트 생성
"""

import os
import datetime
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
import visualizer as viz
from analyzer import filter_by_method, compute_trend


def _add_title_page(pdf: PdfPages, root_folder: str, comparison: list):
    """첫 페이지: 보고서 메타데이터 및 Summary 테이블"""
    fig, ax = plt.subplots(figsize=(11, 8.5))
    ax.axis('off')

    # 타이틀
    ax.text(0.5, 0.9, "XY Stage Positioning Offset Analysis Report", 
            ha='center', va='center', fontsize=24, fontweight='bold')
    
    # 메타데이터
    dt_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    ax.text(0.1, 0.8, f"Date: {dt_str}", fontsize=12)
    ax.text(0.1, 0.75, f"Data Path: {root_folder}", fontsize=10)

    # Summary Table
    if comparison:
        col_labels = ['Recipe', 'Round', 'N', 'Mean', 'Stdev', 'Min', 'Max', 'CV%', 'Outliers']
        cell_text = []
        for c in comparison:
            cell_text.append([
                c.get('recipe', ''), c.get('round', ''),
                str(c.get('data_count', 0)),
                f"{c.get('mean', 0):.1f}", f"{c.get('stdev', 0):.1f}",
                f"{c.get('min', 0):.1f}", f"{c.get('max', 0):.1f}",
                f"{c.get('cv_percent', 0):.1f}", str(c.get('outliers', 0))
            ])
        
        table = ax.table(cellText=cell_text, colLabels=col_labels, loc='center', cellLoc='center')
        table.auto_set_font_size(False)
        table.set_fontsize(10)
        table.scale(1, 2)
        
        ax.text(0.5, 0.58, "Overall Summary", ha='center', fontsize=14, fontweight='bold')

    pdf.savefig(fig)
    plt.close(fig)


def _add_recipe_page(pdf: PdfPages, recipe_data: dict, spec_limits: dict):
    """각 Recipe별 통합 결과 페이지 (1st 라운드 기준)"""
    fig = plt.figure(figsize=(11, 8.5))
    
    recipe_name = recipe_data.get('short_name', 'Unknown Recipe')
    fig.suptitle(f"Step: {recipe_name} (1st Round)", fontsize=16, fontweight='bold', y=0.96)
    
    data = recipe_data.get('raw_data', [])
    if not data:
        ax = fig.add_subplot(111)
        ax.axis('off')
        ax.text(0.5, 0.5, "No Data", ha='center')
        pdf.savefig(fig)
        plt.close(fig)
        return

    # Layout: 
    # [ Top Left: Stats ]     [ Top Right: Trend ]
    # [ Bottom Left: Contour X ] [ Bottom Right: Contour Y ]
    
    # --- 1. Stats Table ---
    ax_stat = fig.add_subplot(221)
    ax_stat.axis('off')
    
    stats = recipe_data.get('statistics', {})
    rep = recipe_data.get('repeatability', {}).get('overall', {})
    
    stat_text = (
        f"Data Count: {stats.get('count', 0)}\n"
        f"Mean: {stats.get('mean', 0):.2f}\n"
        f"Stdev: {stats.get('stdev', 0):.2f}\n"
        f"Range: {stats.get('range', 0):.2f}\n"
        f"CV%: {rep.get('cv_percent', 0):.2f}%\n"
        f"Outliers: {recipe_data.get('outlier_count', 0)}"
    )
    ax_stat.text(0.1, 0.9, stat_text, va='top', fontsize=12, bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.2))
    ax_stat.set_title("Statistics", fontsize=12)

    # --- 2. Trend ---
    ax_trend = fig.add_subplot(222)
    trend_data = recipe_data.get('trend', [])
    if trend_data:
        indices = [t['lot_index'] for t in trend_data]
        means = [t['mean'] for t in trend_data]
        labels = [t['lot_name'] for t in trend_data]
        
        ax_trend.plot(indices, means, 'o-', color='#2196F3', markersize=4)
        ax_trend.set_xticks(indices)
        ax_trend.set_xticklabels(labels, rotation=45, ha='right', fontsize=6)
        ax_trend.set_title("Lot Trend", fontsize=12)
        ax_trend.grid(True, alpha=0.3)
    
    # --- 3. Contour X ---
    ax_cx = fig.add_subplot(223)
    d_x = filter_by_method(data, 'X')
    if d_x:
        xs, ys, means, _ = viz._extract_site_data(d_x, 'value', 'X')
        if len(xs) >= 4:
            try:
                from scipy.interpolate import griddata
                import numpy as np
                xi = np.linspace(min(xs) - 1, max(xs) + 1, 80)
                yi = np.linspace(min(ys) - 1, max(ys) + 1, 80)
                Xi, Yi = np.meshgrid(xi, yi)
                Zi = griddata((xs, ys), means, (Xi, Yi), method='cubic')
                cf = ax_cx.contourf(Xi, Yi, Zi, levels=15, cmap='RdYlGn_r', alpha=0.8)
                fig.colorbar(cf, ax=ax_cx, shrink=0.8)
                ax_cx.scatter(xs, ys, c='black', s=10)
            except Exception:
                ax_cx.scatter(xs, ys, c=means, cmap='RdYlGn_r')
    ax_cx.set_title("Contour X", fontsize=12)
    ax_cx.set_aspect('equal')
    
    # --- 4. Contour Y ---
    ax_cy = fig.add_subplot(224)
    d_y = filter_by_method(data, 'Y')
    if d_y:
        xs, ys, means, _ = viz._extract_site_data(d_y, 'value', 'Y')
        if len(xs) >= 4:
            try:
                from scipy.interpolate import griddata
                import numpy as np
                xi = np.linspace(min(xs) - 1, max(xs) + 1, 80)
                yi = np.linspace(min(ys) - 1, max(ys) + 1, 80)
                Xi, Yi = np.meshgrid(xi, yi)
                Zi = griddata((xs, ys), means, (Xi, Yi), method='cubic')
                cf = ax_cy.contourf(Xi, Yi, Zi, levels=15, cmap='RdYlGn_r', alpha=0.8)
                fig.colorbar(cf, ax=ax_cy, shrink=0.8)
                ax_cy.scatter(xs, ys, c='black', s=10)
            except Exception:
                ax_cy.scatter(xs, ys, c=means, cmap='RdYlGn_r')
    ax_cy.set_title("Contour Y", fontsize=12)
    ax_cy.set_aspect('equal')

    fig.tight_layout(rect=[0, 0.03, 1, 0.95])
    pdf.savefig(fig)
    plt.close(fig)


def generate_pdf_report(export_path: str, root_folder: str, recipe_results: list, comparison: list, spec_limits: dict):
    """지정된 경로로 다페이지 PDF 리포트 생성"""
    with PdfPages(export_path) as pdf:
        _add_title_page(pdf, root_folder, comparison)
        
        for result in recipe_results:
            _add_recipe_page(pdf, result, spec_limits)
            
    return True
