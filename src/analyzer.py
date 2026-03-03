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


# ──────────────────────────────────────────────
# Die-based Deviation Analysis (from xy_stage_offset plugin)
# ──────────────────────────────────────────────

# 21 Die 표준 좌표 (wafer 좌표계) — fallback 용
DIE_POSITIONS = [
    (0, 0),   (2, 0),   (4, 0),   (6, 0),   (2, 2),
    (4, 4),   (0, 2),   (0, 4),   (0, 6),   (-2, 2),
    (-4, 4),  (-2, 0),  (-4, 0),  (-6, 0),  (-2, -2),
    (-4, -4), (0, -2),  (0, -4),  (0, -6),  (2, -2),
    (4, -4),
]


def extract_die_positions(data: list) -> dict:
    """측정 데이터에서 Die별 실제 스테이지 좌표 추출.

    raw_data의 x_um, y_um 필드를 Die 번호별로 그룹핑하여
    평균 좌표를 계산합니다.

    Args:
        data: raw_data 리스트 (x_um, y_um, site_id 필드 필요)

    Returns:
        {0: (x_mm, y_mm), 1: (x_mm, y_mm), ...}
        Die 번호(0-based) → (x_mm, y_mm) 튜플
    """
    die_coords = {}  # die_idx -> {'xs': [], 'ys': []}

    for r in data:
        die_idx = extract_die_number(r.get('site_id', ''))
        if die_idx is None:
            continue
        x_um = r.get('x_um', 0)
        y_um = r.get('y_um', 0)
        if x_um == 0 and y_um == 0:
            continue

        if die_idx not in die_coords:
            die_coords[die_idx] = {'xs': [], 'ys': []}
        die_coords[die_idx]['xs'].append(x_um)
        die_coords[die_idx]['ys'].append(y_um)

    # 평균 좌표 계산 (µm → mm 변환)
    positions = {}
    for die_idx, coords in sorted(die_coords.items()):
        avg_x = sum(coords['xs']) / len(coords['xs']) / 1000.0  # µm → mm
        avg_y = sum(coords['ys']) / len(coords['ys']) / 1000.0
        positions[die_idx] = (round(avg_x, 3), round(avg_y, 3))

    return positions


def extract_die_number(site_id: str) -> Optional[int]:
    """Site ID에서 Die 번호 추출 (0-based).
    예: '0002_X000_Y000' → 패턴 ^\\d{2}(\\d{2})_ → 02 → 2-1 = 1
    """
    import re
    m = re.match(r'^\d{2}(\d{2})_', str(site_id))
    if m:
        return int(m.group(1)) - 1
    return None


def get_die_position(die_label: str, dynamic_positions: dict = None) -> Optional[tuple]:
    """Die 라벨 → wafer 좌표. 'Die1' → index 0 → (x, y)

    Args:
        die_label: 'Die1', 'Die2', ... (1-based 표기)
        dynamic_positions: extract_die_positions()에서 반환된 동적 좌표 dict
                          None이면 하드코딩된 DIE_POSITIONS 사용
    """
    import re
    m = re.match(r'Die(\d+)', die_label)
    if not m:
        return None
    die_num_1based = int(m.group(1))
    idx = die_num_1based - 1  # 1-based label → 0-based index

    # 동적 좌표 우선
    if dynamic_positions and idx in dynamic_positions:
        return dynamic_positions[idx]

    # fallback: 하드코딩 좌표
    if 0 <= idx < len(DIE_POSITIONS):
        return DIE_POSITIONS[idx]
    return None


def filter_stabilization_die(data: list) -> list:
    """안정화 Die 제외: 각 Recipe의 가장 처음 측정된 Die를 제거.

    측정 순서상 첫 번째 site_id의 Die 번호를 찾아서,
    해당 Die 번호의 모든 데이터를 제외합니다.
    """
    if not data:
        return data
    # 첫 번째 측정의 Die 번호 추출
    first_die = extract_die_number(data[0].get('site_id', ''))
    if first_die is None:
        return data
    # 해당 Die 번호의 모든 데이터 제외
    return [r for r in data if extract_die_number(r.get('site_id', '')) != first_die]


def compute_deviation_matrix(data: list, method: str = 'X',
                             metric_key: str = 'value') -> dict:
    """Die × Repeat(Lot) Deviation 행렬 계산.

    Returns:
        {
            'die_labels': ['Die0', 'Die1', ...],
            'repeat_labels': ['Lot401', 'Lot402', ...],
            'matrix': {repeat_label: {die_label: deviation_um}},
            'average_nm': float,
            'die_stats': [{'die': 'Die0', 'avg': ..., 'stddev': ..., 'range': ...}],
            'overall_range': float,
            'overall_stddev': float,
        }
    """
    # 1) Filter by method
    filtered = [r for r in data
                if r.get('method', '').upper() == method.upper()
                and isinstance(r.get(metric_key), (int, float))
                and r.get('valid', True)]
    if not filtered:
        return {'die_labels': [], 'repeat_labels': [], 'matrix': {},
                'average_nm': 0, 'die_stats': [], 'overall_range': 0, 'overall_stddev': 0}

    # 2) Overall average (nm)
    values = [r[metric_key] for r in filtered]
    average = sum(values) / len(values)

    # 3) Extract die numbers
    for r in filtered:
        r['_die_num'] = extract_die_number(r.get('site_id', ''))

    valid = [r for r in filtered if r['_die_num'] is not None]
    die_numbers = sorted(set(r['_die_num'] for r in valid))

    # 4) Repeat = Lot name ordering
    seen = []
    seen_set = set()
    for r in valid:
        lot = r.get('lot_name', '')
        if lot not in seen_set:
            seen_set.add(lot)
            seen.append(lot)
    repeat_map = {name: i for i, name in enumerate(seen)}

    die_labels = [f"Die{d + 1}" for d in die_numbers]  # 1-based 표기
    repeat_labels = list(seen)

    # 5) Build deviation matrix (nm → µm)
    matrix = {}
    for rl in repeat_labels:
        matrix[rl] = {dl: None for dl in die_labels}

    for r in valid:
        die_label = f"Die{r['_die_num'] + 1}"  # 1-based 표기
        lot = r.get('lot_name', '')
        if lot in matrix and die_label in matrix[lot]:
            deviation = (r[metric_key] - average) / 1000.0
            matrix[lot][die_label] = round(deviation, 6)

    # 6) Statistics
    all_devs = []
    for rl in repeat_labels:
        for dl in die_labels:
            v = matrix[rl].get(dl)
            if v is not None:
                all_devs.append(v)

    if all_devs:
        overall_range = round(max(all_devs) - min(all_devs), 3)
        n = len(all_devs)
        mean_d = sum(all_devs) / n
        var_d = sum((v - mean_d) ** 2 for v in all_devs) / (n - 1) if n > 1 else 0
        overall_stddev = round(math.sqrt(var_d), 3)
    else:
        overall_range = 0.0
        overall_stddev = 0.0

    # Die-level stats
    die_stats = []
    for dl in die_labels:
        dvals = [matrix[rl][dl] for rl in repeat_labels if matrix[rl].get(dl) is not None]
        if dvals:
            davg = sum(dvals) / len(dvals)
            if len(dvals) > 1:
                dvar = sum((v - davg) ** 2 for v in dvals) / (len(dvals) - 1)
                dstd = math.sqrt(dvar)
            else:
                dstd = 0
            drng = max(dvals) - min(dvals)
        else:
            davg = dstd = drng = 0
        die_stats.append({'die': dl, 'avg': round(davg, 3),
                          'stddev': round(dstd, 3), 'range': round(drng, 3)})

    return {
        'die_labels': die_labels,
        'repeat_labels': repeat_labels,
        'matrix': matrix,
        'average_nm': round(average, 3),
        'die_stats': die_stats,
        'overall_range': overall_range,
        'overall_stddev': overall_stddev,
    }


def compute_xy_product(x_die_stats: list, y_die_stats: list) -> dict:
    """X_avg × Y_avg 곱 맵 데이터 (Contour 용).
    Returns: {die_label: x_avg * y_avg}
    """
    x_map = {ds['die']: ds['avg'] for ds in x_die_stats}
    y_map = {ds['die']: ds['avg'] for ds in y_die_stats}
    result = {}
    for d in x_map:
        if d in y_map:
            result[d] = x_map[d] * y_map[d]
    return result


def compute_affine_transform(x_die_stats: list, y_die_stats: list) -> dict:
    """Affine Transform 기반 계통 오차(Systematic Error) 분리.

    수학적 모델:
        dx = Tx + Sx * x - Theta * y
        dy = Ty + Sy * y + Theta * x

    Returns:
        {
            'tx': float,       # X Translation Shift (µm)
            'ty': float,       # Y Translation Shift (µm)
            'sx_ppm': float,   # X Scaling error (ppm)
            'sy_ppm': float,   # Y Scaling error (ppm)
            'theta_deg': float,# Rotation error (degrees)
            'theta_urad': float,# Rotation error (µrad)
            'residual_x': float, # X fitting residual RMS (µm)
            'residual_y': float, # Y fitting residual RMS (µm)
            'n_dies': int,
        }
    """
    import numpy as np

    # Build position and offset arrays
    x_map = {ds['die']: ds['avg'] for ds in x_die_stats}
    y_map = {ds['die']: ds['avg'] for ds in y_die_stats}
    common = sorted(set(x_map.keys()) & set(y_map.keys()))

    if len(common) < 3:
        return {'tx': 0, 'ty': 0, 'sx_ppm': 0, 'sy_ppm': 0,
                'theta_deg': 0, 'theta_urad': 0,
                'residual_x': 0, 'residual_y': 0, 'n_dies': 0}

    positions = []
    dx_vals = []
    dy_vals = []
    for d in common:
        pos = get_die_position(d)
        if pos is None:
            continue
        positions.append(pos)
        dx_vals.append(x_map[d])
        dy_vals.append(y_map[d])

    n = len(positions)
    if n < 3:
        return {'tx': 0, 'ty': 0, 'sx_ppm': 0, 'sy_ppm': 0,
                'theta_deg': 0, 'theta_urad': 0,
                'residual_x': 0, 'residual_y': 0, 'n_dies': 0}

    xs = np.array([p[0] for p in positions], dtype=float)
    ys = np.array([p[1] for p in positions], dtype=float)
    dx = np.array(dx_vals, dtype=float)
    dy = np.array(dy_vals, dtype=float)

    # --- Solve for X: dx = Tx + Sx * x - Theta * y ---
    #   A_x @ [Tx, Sx, -Theta]^T = dx
    A_x = np.column_stack([np.ones(n), xs, -ys])
    sol_x, res_x, _, _ = np.linalg.lstsq(A_x, dx, rcond=None)
    tx, sx, neg_theta_x = sol_x

    # --- Solve for Y: dy = Ty + Sy * y + Theta * x ---
    A_y = np.column_stack([np.ones(n), ys, xs])
    sol_y, res_y, _, _ = np.linalg.lstsq(A_y, dy, rcond=None)
    ty, sy, theta_y = sol_y

    # Average theta from both equations
    theta_rad = (neg_theta_x + theta_y) / 2.0

    # Residuals
    dx_fit = A_x @ sol_x
    dy_fit = A_y @ sol_y
    res_rms_x = float(np.sqrt(np.mean((dx - dx_fit) ** 2)))
    res_rms_y = float(np.sqrt(np.mean((dy - dy_fit) ** 2)))

    return {
        'tx': round(float(tx), 4),
        'ty': round(float(ty), 4),
        'sx_ppm': round(float(sx) * 1e6, 2),
        'sy_ppm': round(float(sy) * 1e6, 2),
        'theta_deg': round(float(math.degrees(theta_rad)), 6),
        'theta_urad': round(float(theta_rad * 1e6), 2),
        'residual_x': round(res_rms_x, 4),
        'residual_y': round(res_rms_y, 4),
        'n_dies': n,
    }


# ──────────────────────────────────────────────
# Pareto & Correlation Analysis (Phase 2)
# ──────────────────────────────────────────────

def compute_pareto_data(data: list, group_by: str = 'die') -> list:
    """Die별 또는 Lot별 이상치 빈도 파레토 분석.

    Args:
        data: raw_data 리스트 (is_outlier 필드 필요)
        group_by: 'die' 또는 'lot'

    Returns:
        [{'label': 'Die5', 'count': 12, 'percent': 30.0, 'cumulative': 30.0}, ...]
        (이상치 수 내림차순 정렬)
    """
    counts = {}
    for r in data:
        if not r.get('is_outlier', False):
            continue
        if group_by == 'die':
            die_num = extract_die_number(r.get('site_id', ''))
            key = f'Die{die_num + 1}' if die_num is not None else 'Unknown'  # 1-based
        else:
            key = r.get('lot_name', 'Unknown')
        counts[key] = counts.get(key, 0) + 1

    total = sum(counts.values())
    if total == 0:
        return []

    # 내림차순 정렬
    sorted_items = sorted(counts.items(), key=lambda x: -x[1])

    result = []
    cumulative = 0.0
    for label, count in sorted_items:
        pct = count / total * 100
        cumulative += pct
        result.append({
            'label': label,
            'count': count,
            'percent': round(pct, 1),
            'cumulative': round(cumulative, 1),
        })

    return result


def compute_correlation(x_die_stats: list, y_die_stats: list) -> dict:
    """X/Y Die별 평균 편차 간 피어슨 상관관계 분석.

    Returns:
        {
            'pearson_r': float,     # 피어슨 상관계수
            'r_squared': float,     # 결정계수
            'slope': float,         # 회귀선 기울기
            'intercept': float,     # 회귀선 절편
            'points': [(x_avg, y_avg, die_label), ...],
            'n': int,
        }
    """
    x_map = {ds['die']: ds['avg'] for ds in x_die_stats}
    y_map = {ds['die']: ds['avg'] for ds in y_die_stats}
    common = sorted(set(x_map.keys()) & set(y_map.keys()))

    if len(common) < 3:
        return {'pearson_r': 0, 'r_squared': 0, 'slope': 0, 'intercept': 0,
                'points': [], 'n': 0}

    xs = [x_map[d] for d in common]
    ys = [y_map[d] for d in common]
    n = len(xs)

    # Pearson r
    mx = sum(xs) / n
    my = sum(ys) / n
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / n
    sx = math.sqrt(sum((x - mx) ** 2 for x in xs) / n) if n > 1 else 1
    sy = math.sqrt(sum((y - my) ** 2 for y in ys) / n) if n > 1 else 1
    r = cov / (sx * sy) if sx > 0 and sy > 0 else 0

    # Linear regression: y = slope * x + intercept
    slope = cov / (sx ** 2) if sx > 0 else 0
    intercept = my - slope * mx

    points = [(x_map[d], y_map[d], d) for d in common]

    return {
        'pearson_r': round(r, 4),
        'r_squared': round(r ** 2, 4),
        'slope': round(slope, 4),
        'intercept': round(intercept, 4),
        'points': points,
        'n': n,
    }
