"""
exporter.py — CSV / Excel 내보내기
"""

import os
import csv
from typing import Optional


def export_combined_csv(data: list, output_path: str,
                        delimiter: str = '\t') -> str:
    """Analysis.txt 대체 — 배치 데이터를 CSV/TSV로 내보내기

    Args:
        data: batch_load() 결과
        output_path: 출력 파일 경로
        delimiter: 구분자 ('\\t' = TSV, ',' = CSV)

    Returns:
        저장된 파일 경로
    """
    if not data:
        return ''

    header = ['Foldername', 'Filename', 'Site ID', 'Site X', 'Site Y',
              'Point No', 'X (um)', 'Y (um)', 'Method ID', 'State',
              'Valid', 'HZ1_O (nm)', 'HZ1_O_Valid']

    with open(output_path, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f, delimiter=delimiter)
        writer.writerow(header)

        for r in data:
            writer.writerow([
                r.get('lot_name', ''),
                r.get('filename', ''),
                r.get('site_id', ''),
                r.get('site_x', ''),
                r.get('site_y', ''),
                r.get('point_no', ''),
                r.get('x_um', ''),
                r.get('y_um', ''),
                r.get('method', ''),
                r.get('state', ''),
                'TRUE' if r.get('valid', True) else 'FALSE',
                r.get('value', ''),
                'TRUE' if r.get('value_valid', True) else 'FALSE',
            ])

    return output_path


def export_statistics_csv(stats: list, output_path: str) -> str:
    """그룹별 통계를 CSV로 내보내기

    Args:
        stats: analyzer.compute_group_statistics() 결과
    """
    if not stats:
        return ''

    header = ['Group', 'Count', 'Mean', 'Stdev', 'Min', 'Max', 'Range']

    with open(output_path, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        writer.writerow(header)
        for s in stats:
            writer.writerow([
                s.get('group', ''),
                s.get('count', 0),
                s.get('mean', 0),
                s.get('stdev', 0),
                s.get('min', 0),
                s.get('max', 0),
                s.get('range', 0),
            ])

    return output_path


def export_excel_report(data: list, stats: dict, trend: list,
                        output_path: str) -> str:
    """Excel 리포트 (openpyxl 사용)

    시트 구성:
        1. Raw Data — 전체 측정 데이터
        2. Statistics — 그룹별 통계
        3. Trend — Lot별 트렌드
        4. Repeatability — 반복성 분석
    """
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    except ImportError:
        # openpyxl 없으면 CSV로 대체
        return export_combined_csv(data, output_path.replace('.xlsx', '.csv'))

    wb = Workbook()

    # 공통 스타일
    header_font = Font(name='맑은 고딕', bold=True, size=10)
    header_fill = PatternFill(start_color='1565C0', end_color='1565C0',
                              fill_type='solid')
    header_font_white = Font(name='맑은 고딕', bold=True, size=10, color='FFFFFF')
    data_font = Font(name='맑은 고딕', size=9)
    thin_border = Border(
        left=Side(style='thin', color='D0D0D0'),
        right=Side(style='thin', color='D0D0D0'),
        top=Side(style='thin', color='D0D0D0'),
        bottom=Side(style='thin', color='D0D0D0'),
    )

    # === Sheet 1: Raw Data ===
    ws1 = wb.active
    ws1.title = 'Raw Data'

    headers_raw = ['Lot', 'Filename', 'Site ID', 'Site X', 'Site Y',
                   'Point No', 'X (um)', 'Y (um)', 'Method', 'State',
                   'Valid', 'HZ1_O (nm)', 'Outlier']

    for col, h in enumerate(headers_raw, 1):
        cell = ws1.cell(row=1, column=col, value=h)
        cell.font = header_font_white
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal='center')
        cell.border = thin_border

    for row_idx, r in enumerate(data, 2):
        values = [
            r.get('lot_name', ''), r.get('filename', ''),
            r.get('site_id', ''), r.get('site_x', ''),
            r.get('site_y', ''), r.get('point_no', ''),
            r.get('x_um', ''), r.get('y_um', ''),
            r.get('method', ''), r.get('state', ''),
            'TRUE' if r.get('valid', True) else 'FALSE',
            r.get('value', ''),
            'YES' if r.get('is_outlier', False) else '',
        ]
        for col, val in enumerate(values, 1):
            cell = ws1.cell(row=row_idx, column=col, value=val)
            cell.font = data_font
            cell.border = thin_border

    # 열 너비 조정
    for col in range(1, len(headers_raw) + 1):
        ws1.column_dimensions[chr(64 + col) if col <= 26 else 'A'].width = 14

    # === Sheet 2: Statistics ===
    if stats.get('overall'):
        ws2 = wb.create_sheet('Statistics')
        stat_headers = ['항목', '값']
        for col, h in enumerate(stat_headers, 1):
            cell = ws2.cell(row=1, column=col, value=h)
            cell.font = header_font_white
            cell.fill = header_fill

        overall = stats['overall']
        stat_rows = [
            ('전체 데이터 수', overall.get('count', 0)),
            ('평균 (Mean)', overall.get('mean', 0)),
            ('표준편차 (Stdev)', overall.get('stdev', 0)),
            ('변동계수 (CV%)', overall.get('cv_percent', 0)),
        ]
        lot_var = stats.get('lot_variation', {})
        if lot_var:
            stat_rows.extend([
                ('', ''),
                ('--- Lot간 변동 ---', ''),
                ('Lot 수', lot_var.get('count', 0)),
                ('평균의 평균', lot_var.get('mean_of_means', 0)),
                ('평균의 표준편차', lot_var.get('stdev_of_means', 0)),
                ('평균의 범위', lot_var.get('range_of_means', 0)),
            ])

        for row_idx, (label, val) in enumerate(stat_rows, 2):
            ws2.cell(row=row_idx, column=1, value=label).font = data_font
            ws2.cell(row=row_idx, column=2, value=val).font = data_font

    # === Sheet 3: Trend ===
    if trend:
        ws3 = wb.create_sheet('Trend')
        trend_headers = ['Lot', 'Index', 'Count', 'Mean', 'Stdev', 'Min', 'Max']
        for col, h in enumerate(trend_headers, 1):
            cell = ws3.cell(row=1, column=col, value=h)
            cell.font = header_font_white
            cell.fill = header_fill

        for row_idx, t in enumerate(trend, 2):
            values = [t['lot_name'], t['lot_index'], t['count'],
                      t['mean'], t['stdev'], t['min'], t['max']]
            for col, val in enumerate(values, 1):
                ws3.cell(row=row_idx, column=col, value=val).font = data_font

    wb.save(output_path)
    return output_path
