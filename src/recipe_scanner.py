"""
recipe_scanner.py — Multi-Recipe 자동 탐지 및 비교

데이터 폴더 구조:
    data/
    ├── 1. Vision Pattern Recognize/
    │   ├── 1st/  ← Lot 폴더들
    │   └── 2nd/
    ├── 2. In-Die Align/
    │   ├── 1st/
    │   └── 2nd/
    └── ...
"""

import os
import re
from csv_loader import scan_lot_folders, batch_load, get_scan_summary
from analyzer import (compute_statistics, compute_trend,
                      detect_outliers, compute_repeatability,
                      compute_group_statistics, filter_by_method)


def scan_recipes(root_path: str) -> list:
    """루트 폴더에서 Recipe 하위 구조 자동 탐지

    Args:
        root_path: 최상위 데이터 폴더 (예: ".../data")

    Returns:
        [{'name': '1. Vision Pattern Recognize', 'path': '...',
          'index': 1, 'short_name': 'Vision Pattern',
          'rounds': [{'name': '1st', 'path': '...', 'lot_count': 11},
                     {'name': '2nd', ...}]}, ...]
    """
    if not os.path.isdir(root_path):
        return []

    recipes = []

    for name in sorted(os.listdir(root_path)):
        recipe_path = os.path.join(root_path, name)
        if not os.path.isdir(recipe_path):
            continue

        # 하위에 1st/2nd 또는 직접 Lot 폴더가 있는지 확인
        rounds = []
        sub_items = sorted(os.listdir(recipe_path))

        for sub in sub_items:
            sub_path = os.path.join(recipe_path, sub)
            if not os.path.isdir(sub_path):
                continue

            lots = scan_lot_folders(sub_path)
            if lots:
                rounds.append({
                    'name': sub,
                    'path': sub_path,
                    'lot_count': len(lots),
                })

        # 라운드가 없으면 직접 Lot 검색
        if not rounds:
            lots = scan_lot_folders(recipe_path)
            if lots:
                rounds.append({
                    'name': '(root)',
                    'path': recipe_path,
                    'lot_count': len(lots),
                })

        if rounds:
            # 인덱스 추출 (폴더명 앞의 숫자)
            idx_match = re.match(r'^(\d+)', name)
            idx = int(idx_match.group(1)) if idx_match else len(recipes) + 1

            # 짧은 이름 생성
            short = re.sub(r'^\d+\.\s*', '', name).strip()
            if len(short) > 20:
                short = short[:18] + '…'

            recipes.append({
                'name': name,
                'path': recipe_path,
                'index': idx,
                'short_name': short,
                'rounds': rounds,
            })

    recipes.sort(key=lambda x: x['index'])
    return recipes


def load_recipe_data(recipe: dict, round_name: str = '1st',
                     lot_range=None, axis='both') -> dict:
    """단일 Recipe의 데이터 로드 + 분석

    Returns:
        {'recipe': ..., 'round': ..., 'raw_data': [...],
         'statistics': {...}, 'trend': [...], 'repeatability': {...},
         'group_stats': [...], 'outlier_count': N}
    """
    # 해당 라운드 찾기
    round_info = None
    for r in recipe.get('rounds', []):
        if r['name'] == round_name:
            round_info = r
            break

    if not round_info:
        # 첫 번째 라운드 사용
        round_info = recipe['rounds'][0] if recipe.get('rounds') else None

    if not round_info:
        return {'recipe': recipe['name'], 'round': round_name,
                'raw_data': [], 'error': 'No data found'}

    data = batch_load(round_info['path'], lot_range=lot_range, axis=axis)
    if not data:
        return {'recipe': recipe['name'], 'round': round_info['name'],
                'raw_data': [], 'error': 'No data loaded'}

    data = detect_outliers(data, method='iqr')

    return {
        'recipe': recipe['name'],
        'short_name': recipe.get('short_name', recipe['name']),
        'round': round_info['name'],
        'round_path': round_info['path'],
        'raw_data': data,
        'statistics': compute_statistics(data),
        'trend': compute_trend(data),
        'trend_x': compute_trend([r for r in data if r.get('method') == 'X']),
        'trend_y': compute_trend([r for r in data if r.get('method') == 'Y']),
        'repeatability': compute_repeatability(data),
        'group_stats': compute_group_statistics(data, 'lot_name'),
        'outlier_count': sum(1 for r in data if r.get('is_outlier')),
    }


def load_all_recipes(root_path: str, round_name: str = '1st',
                     axis: str = 'both',
                     progress_cb=None) -> list:
    """모든 Recipe 일괄 로드

    Args:
        progress_cb: callback(recipe_index, total, recipe_name)

    Returns:
        [load_recipe_data() 결과, ...]
    """
    recipes = scan_recipes(root_path)
    results = []

    for i, recipe in enumerate(recipes):
        if progress_cb:
            progress_cb(i + 1, len(recipes), recipe['name'])
        result = load_recipe_data(recipe, round_name=round_name, axis=axis)
        results.append(result)

    return results


def compare_recipes(results: list) -> list:
    """Recipe간 핵심 지표 비교 테이블

    Returns:
        [{'recipe': 'Vision Pattern', 'lots': 11,
          'mean': ..., 'stdev': ..., 'min': ..., 'max': ...,
          'cv_percent': ..., 'outliers': 24}, ...]
    """
    comparison = []
    for r in results:
        stats = r.get('statistics', {})
        rep = r.get('repeatability', {})
        overall = rep.get('overall', {})

        comparison.append({
            'recipe': r.get('short_name', r.get('recipe', '')),
            'round': r.get('round', ''),
            'data_count': stats.get('count', 0),
            'mean': stats.get('mean', 0),
            'stdev': stats.get('stdev', 0),
            'min': stats.get('min', 0),
            'max': stats.get('max', 0),
            'range': stats.get('range', 0),
            'cv_percent': overall.get('cv_percent', 0),
            'outliers': r.get('outlier_count', 0),
        })

    return comparison
