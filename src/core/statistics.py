"""
analyzer.py — 통계·트렌드·이상치 분석 엔진
"""

import math
from typing import Optional


def compute_statistics(data: list, metric_key: str = 'value') -> dict:
    """기본 통계 계산

    Args:
        data: batch_load() 결과 리스트
        metric_key: 측정값 키

    Returns:
        {'count': N, 'mean': ..., 'stdev': ..., 'min': ..., 'max': ..., 'range': ...}
    """
    values = [r[metric_key] for r in data
              if isinstance(r.get(metric_key), (int, float)) and r.get('valid', True)]

    if not values:
        return {'count': 0, 'mean': 0, 'stdev': 0, 'min': 0, 'max': 0, 'range': 0}

    n = len(values)
    mean = sum(values) / n
    variance = sum((v - mean) ** 2 for v in values) / n if n > 1 else 0
    stdev = math.sqrt(variance)

    return {
        'count': n,
        'mean': round(mean, 3),
        'stdev': round(stdev, 3),
        'min': round(min(values), 3),
        'max': round(max(values), 3),
        'range': round(max(values) - min(values), 3),
    }


def compute_group_statistics(data: list, group_by: str = 'lot_name',
                             metric_key: str = 'value') -> list:
    """그룹별 통계

    Args:
        data: batch_load() 결과
        group_by: 그룹화 키 ('lot_name', 'site_id', 'method')
        metric_key: 측정값 키

    Returns:
        [{'group': 'Lot401', 'count': 22, 'mean': ..., ...}, ...]
    """
    groups = {}
    for r in data:
        key = r.get(group_by, 'Unknown')
        if key not in groups:
            groups[key] = []
        groups[key].append(r)

    results = []
    for group_name in sorted(groups.keys()):
        stats = compute_statistics(groups[group_name], metric_key)
        stats['group'] = group_name
        results.append(stats)

    return results


def compute_trend(data: list, metric_key: str = 'value') -> list:
    """Lot 순서별 트렌드 (에이징 분석용)

    Returns:
        [{'lot_name': 'Lot401', 'lot_index': 1, 'mean': ...,
          'stdev': ..., 'min': ..., 'max': ...}, ...]
    """
    lot_groups = {}
    for r in data:
        lot = r.get('lot_name', 'Unknown')
        idx = r.get('lot_index', 0)
        if lot not in lot_groups:
            lot_groups[lot] = {'index': idx, 'values': []}
        val = r.get(metric_key)
        if isinstance(val, (int, float)) and r.get('valid', True):
            lot_groups[lot]['values'].append(val)

    trend = []
    for lot_name in sorted(lot_groups.keys(), key=lambda x: lot_groups[x]['index']):
        info = lot_groups[lot_name]
        vals = info['values']
        if not vals:
            continue

        n = len(vals)
        mean = sum(vals) / n
        variance = sum((v - mean) ** 2 for v in vals) / n if n > 1 else 0

        trend.append({
            'lot_name': lot_name,
            'lot_index': info['index'],
            'count': n,
            'mean': round(mean, 3),
            'stdev': round(math.sqrt(variance), 3),
            'min': round(min(vals), 3),
            'max': round(max(vals), 3),
        })

    return trend


def detect_outliers(data: list, metric_key: str = 'value',
                    method: str = 'iqr', threshold: float = 1.5) -> list:
    """이상치 탐지

    Args:
        method: 'iqr' (IQR × threshold) / 'zscore' (|Z| > threshold) / 'range' (절대범위)
        threshold: IQR 배수 (기본 1.5) 또는 Z-score 기준 (기본 3)

    Returns:
        원본 data에 'is_outlier': True/False 추가된 리스트
    """
    values = [r.get(metric_key, 0) for r in data
              if isinstance(r.get(metric_key), (int, float))]

    if not values:
        return data

    if method == 'iqr':
        sorted_vals = sorted(values)
        n = len(sorted_vals)
        q1 = sorted_vals[n // 4]
        q3 = sorted_vals[3 * n // 4]
        iqr = q3 - q1
        lower = q1 - threshold * iqr
        upper = q3 + threshold * iqr

        for r in data:
            val = r.get(metric_key, 0)
            r['is_outlier'] = val < lower or val > upper

    elif method == 'zscore':
        mean = sum(values) / len(values)
        variance = sum((v - mean) ** 2 for v in values) / len(values)
        std = math.sqrt(variance) if variance > 0 else 1

        for r in data:
            val = r.get(metric_key, 0)
            z = abs(val - mean) / std if std > 0 else 0
            r['is_outlier'] = z > threshold

    elif method == 'range':
        # threshold = (min_val, max_val) 튜플로 사용
        if isinstance(threshold, tuple) and len(threshold) == 2:
            lo, hi = threshold
            for r in data:
                val = r.get(metric_key, 0)
                r['is_outlier'] = val < lo or val > hi
        else:
            for r in data:
                r['is_outlier'] = False

    return data


def filter_by_method(data: list, method: str) -> list:
    """Method(X/Y) 필터링"""
    return [r for r in data if r.get('method', '').upper() == method.upper()]


def filter_valid_only(data: list) -> list:
    """Valid=TRUE 데이터만 필터링"""
    return [r for r in data if r.get('valid', True)]


def compute_repeatability(data: list, metric_key: str = 'value') -> dict:
    """반복성 분석 — Lot 간 변동 + Site 별 변동

    Returns:
        {
            'lot_variation': {'mean_of_means': ..., 'stdev_of_means': ..., ...},
            'site_variation': [{'site_id': ..., 'stdev': ..., 'range': ...}, ...],
            'overall': {'mean': ..., 'stdev': ..., 'cv_percent': ...}
        }
    """
    # Overall
    all_values = [r[metric_key] for r in data
                  if isinstance(r.get(metric_key), (int, float)) and r.get('valid', True)]

    if not all_values:
        return {'lot_variation': {}, 'site_variation': [], 'overall': {}}

    overall_mean = sum(all_values) / len(all_values)
    overall_var = sum((v - overall_mean) ** 2 for v in all_values) / len(all_values)
    overall_std = math.sqrt(overall_var)
    cv = (overall_std / abs(overall_mean) * 100) if overall_mean != 0 else 0

    # Lot별 평균의 변동
    lot_stats = compute_group_statistics(data, 'lot_name', metric_key)
    lot_means = [s['mean'] for s in lot_stats]
    if lot_means:
        mean_of_means = sum(lot_means) / len(lot_means)
        var_of_means = sum((m - mean_of_means) ** 2 for m in lot_means) / len(lot_means)
    else:
        mean_of_means = 0
        var_of_means = 0

    # Site별 변동 (동일 Site의 Lot 간 변동)
    site_groups = {}
    for r in data:
        site = r.get('site_id', '')
        method = r.get('method', '')
        key = f"{site}_{method}"
        if key not in site_groups:
            site_groups[key] = []
        val = r.get(metric_key)
        if isinstance(val, (int, float)) and r.get('valid', True):
            site_groups[key].append(val)

    site_variation = []
    for key in sorted(site_groups.keys()):
        vals = site_groups[key]
        if len(vals) < 2:
            continue
        s_mean = sum(vals) / len(vals)
        s_var = sum((v - s_mean) ** 2 for v in vals) / len(vals)
        site_variation.append({
            'site_key': key,
            'count': len(vals),
            'mean': round(s_mean, 3),
            'stdev': round(math.sqrt(s_var), 3),
            'range': round(max(vals) - min(vals), 3),
        })

    return {
        'lot_variation': {
            'count': len(lot_means),
            'mean_of_means': round(mean_of_means, 3),
            'stdev_of_means': round(math.sqrt(var_of_means), 3),
            'range_of_means': round(max(lot_means) - min(lot_means), 3) if lot_means else 0,
        },
        'site_variation': site_variation,
        'overall': {
            'count': len(all_values),
            'mean': round(overall_mean, 3),
            'stdev': round(overall_std, 3),
            'cv_percent': round(cv, 2),
        },
    }


def compute_cpk(mean: float, stdev: float, lsl: Optional[float] = None, usl: Optional[float] = None) -> float:
    """Cpk(공정능력지수) 계산
    
    Args:
        mean: 평균
        stdev: 표준편차
        lsl: 하한 (Lower Specification Limit)
        usl: 상한 (Upper Specification Limit)
        
    Returns:
        Cpk 값 (계산 불가 시 0.0 반환)
    """
    if stdev == 0 or (lsl is None and usl is None):
        return 0.0
        
    cpk_lsl = (mean - lsl) / (3 * stdev) if lsl is not None else float('inf')
    cpk_usl = (usl - mean) / (3 * stdev) if usl is not None else float('inf')
    
    return round(min(cpk_lsl, cpk_usl), 3)


def compare_1st_2nd_by_site(data_1st: list, data_2nd: list, metric_key: str = 'value') -> list:
    """Site별 1st와 2nd 평균값 매칭하여 비교
    
    Returns:
        [{'site_id': '0001_X000_Y000', 'method': 'X', 
          'val_1st': 123, 'val_2nd': 125, 'diff': -2}, ...]
    """
    def _agg_site(data):
        sites = {}
        for r in data:
            if not r.get('valid', True):
                continue
            site = r.get('site_id', '')
            method = r.get('method', '').upper()
            val = r.get(metric_key)
            if not isinstance(val, (int, float)):
                continue
            
            key = (site, method)
            if key not in sites:
                sites[key] = []
            sites[key].append(val)
            
        res = {}
        for k, vals in sites.items():
            res[k] = sum(vals) / len(vals)
        return res
        
    agg_1st = _agg_site(data_1st)
    agg_2nd = _agg_site(data_2nd)
    
    all_keys = set(agg_1st.keys()) | set(agg_2nd.keys())
    
    results = []
    for site, method in sorted(all_keys):
        v1 = agg_1st.get((site, method))
        v2 = agg_2nd.get((site, method))
        diff = v1 - v2 if v1 is not None and v2 is not None else None
        
        results.append({
            'site_id': site,
            'method': method,
            'val_1st': round(v1, 3) if v1 is not None else None,
            'val_2nd': round(v2, 3) if v2 is not None else None,
            'diff': round(diff, 3) if diff is not None else None
        })
        
    return results

