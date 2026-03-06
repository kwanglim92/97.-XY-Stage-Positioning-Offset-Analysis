"""
visualizer.py — 차트 시각화 (matplotlib)
"""

import numpy as np
import matplotlib
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
import io

# ── 한국어 폰트 설정 (matplotlib 전역) ──
import platform
if platform.system() == 'Windows':
    plt.rcParams['font.family'] = 'Malgun Gothic'
elif platform.system() == 'Darwin':
    plt.rcParams['font.family'] = 'AppleGothic'
else:
    plt.rcParams['font.family'] = 'NanumGothic'
plt.rcParams['axes.unicode_minus'] = False


# Recipe별 색상 팔레트
RECIPE_COLORS = ['#2196F3', '#4CAF50', '#FF9800', '#E91E63',
                 '#9C27B0', '#00BCD4', '#795548', '#607D8B']


def _fig_to_png(fig: Figure) -> bytes:
    """Figure → PNG bytes 변환 유틸. app.py(JSON-RPC)에서 사용.

    GUI에서는 FigureCanvasQTAgg(fig)를 직접 사용하므로 이 함수를 호출하지 않습니다.
    이 함수는 Figure를 close합니다.
    """
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    buf.seek(0)
    return buf.read()

def plot_trend_chart(trend_data: list, title: str = 'Lot Trend',
                     y_label: str = 'HZ1_O (nm)',
                     show_range: bool = True) -> Figure:
    """Lot별 측정값 트렌드 차트"""
    fig, ax = plt.subplots(figsize=(12, 6))

    indices = [t['lot_index'] for t in trend_data]
    means = [t['mean'] for t in trend_data]
    stdevs = [t['stdev'] for t in trend_data]
    labels = [t['lot_name'] for t in trend_data]

    ax.plot(indices, means, 'o-', color='#2196F3', linewidth=2,
            markersize=6, label='Mean', zorder=3)

    upper = [m + s for m, s in zip(means, stdevs)]
    lower = [m - s for m, s in zip(means, stdevs)]
    ax.fill_between(indices, lower, upper, alpha=0.15, color='#2196F3',
                    label='±1σ')

    if show_range:
        mins = [t['min'] for t in trend_data]
        maxs = [t['max'] for t in trend_data]
        ax.plot(indices, mins, 'v:', color='#FF5722', alpha=0.5,
                markersize=4, label='Min')
        ax.plot(indices, maxs, '^:', color='#4CAF50', alpha=0.5,
                markersize=4, label='Max')

    overall_mean = sum(means) / len(means)
    ax.axhline(overall_mean, color='gray', linestyle='--', alpha=0.5,
               label=f'Overall Mean: {overall_mean:.1f}')

    ax.set_xlabel('Lot Index')
    ax.set_ylabel(y_label)
    ax.set_title(title)
    ax.set_xticks(indices)
    ax.set_xticklabels(labels, rotation=45, ha='right', fontsize=8)
    ax.legend(loc='best', fontsize=8)
    ax.grid(True, alpha=0.3)

    fig.tight_layout()
    return fig


def _extract_site_data(data: list, metric_key: str, method: str):
    """히트맵/컨투어 공통 — Site별 평균값 추출"""
    site_vals = {}
    for r in data:
        if r.get('method', '').upper() != method.upper():
            continue
        sx, sy = r.get('site_x', 0), r.get('site_y', 0)
        val = r.get(metric_key, 0)
        if not isinstance(val, (int, float)):
            continue
        key = (sx, sy)
        if key not in site_vals:
            site_vals[key] = {'values': [], 'site_id': r.get('site_id', '')}
        site_vals[key]['values'].append(val)

    xs = [k[0] for k in site_vals.keys()]
    ys = [k[1] for k in site_vals.keys()]
    means = [sum(v['values']) / len(v['values']) for v in site_vals.values()]

    return xs, ys, means, site_vals


def plot_site_heatmap(data: list, metric_key: str = 'value',
                      method: str = 'X',
                      title: str = 'Site Heatmap',
                      mode: str = 'scatter') -> Figure:
    """Site 좌표 기반 히트맵/컨투어맵

    Args:
        mode: 'scatter' (산점도) 또는 'contour' (등고선)
    """
    fig, ax = plt.subplots(figsize=(10, 8))

    xs, ys, means, site_vals = _extract_site_data(data, metric_key, method)

    if not xs:
        ax.text(0.5, 0.5, 'No data', ha='center', va='center',
                transform=ax.transAxes, fontsize=14)
        return fig

    if mode == 'contour' and len(xs) >= 4:
        # 등고선 보간
        from scipy.interpolate import griddata

        xi = np.linspace(min(xs) - 1, max(xs) + 1, 100)
        yi = np.linspace(min(ys) - 1, max(ys) + 1, 100)
        Xi, Yi = np.meshgrid(xi, yi)

        Zi = griddata((xs, ys), means, (Xi, Yi), method='cubic')

        cf = ax.contourf(Xi, Yi, Zi, levels=20, cmap='RdYlGn_r', alpha=0.8)
        plt.colorbar(cf, ax=ax, label=f'Mean {metric_key}')

        # 등고선 라인
        cs = ax.contour(Xi, Yi, Zi, levels=10, colors='gray',
                        linewidths=0.5, alpha=0.5)
        ax.clabel(cs, inline=True, fontsize=6, fmt='%.0f')

        # 원래 데이터 포인트도 표시
        ax.scatter(xs, ys, c=means, s=80, cmap='RdYlGn_r',
                   edgecolors='black', linewidths=0.8, zorder=3)

        mode_label = 'Contour'
    else:
        # 산점도 (기존)
        scatter = ax.scatter(xs, ys, c=means, s=200, cmap='RdYlGn_r',
                             edgecolors='black', linewidths=0.5, zorder=3)
        plt.colorbar(scatter, ax=ax, label=f'Mean {metric_key}')
        mode_label = 'Scatter'

    # 값 라벨
    for (x, y), val_info in site_vals.items():
        mean_val = sum(val_info['values']) / len(val_info['values'])
        ax.annotate(f'{mean_val:.0f}', (x, y), textcoords="offset points",
                    xytext=(0, 12), ha='center', fontsize=7)

    ax.set_xlabel('Site X')
    ax.set_ylabel('Site Y')
    ax.set_title(f'{title} [{mode_label}] (Method: {method})')
    ax.grid(True, alpha=0.3)
    ax.set_aspect('equal')

    fig.tight_layout()
    return fig


def plot_boxplot(data: list, metric_key: str = 'value',
                 group_by: str = 'lot_name',
                 title: str = 'Distribution by Lot') -> Figure:
    """그룹별 박스플롯"""
    fig, ax = plt.subplots(figsize=(12, 6))

    groups = {}
    for r in data:
        key = r.get(group_by, 'Unknown')
        val = r.get(metric_key)
        if isinstance(val, (int, float)):
            if key not in groups:
                groups[key] = []
            groups[key].append(val)

    sorted_keys = sorted(groups.keys())
    box_data = [groups[k] for k in sorted_keys]

    bp = ax.boxplot(box_data, labels=sorted_keys, patch_artist=True,
                    boxprops=dict(facecolor='#E3F2FD', edgecolor='#1565C0'),
                    medianprops=dict(color='#D32F2F', linewidth=2),
                    flierprops=dict(marker='o', markerfacecolor='#FF5722',
                                    markersize=4))

    ax.set_xlabel(group_by.replace('_', ' ').title())
    ax.set_ylabel(metric_key)
    ax.set_title(title)
    ax.tick_params(axis='x', rotation=45)
    ax.grid(True, alpha=0.3, axis='y')

    fig.tight_layout()
    return fig


def plot_histogram(data: list, metric_key: str = 'value',
                   bins: int = 50,
                   title: str = 'Distribution') -> Figure:
    """측정값 히스토그램 + 정규분포 곡선"""
    fig, ax = plt.subplots(figsize=(10, 6))

    values = [r.get(metric_key, 0) for r in data
              if isinstance(r.get(metric_key), (int, float))]

    if not values:
        return fig

    ax.hist(values, bins=bins, color='#42A5F5', edgecolor='white',
            alpha=0.8, density=True, label='Data')

    mean = sum(values) / len(values)
    std = (sum((v - mean) ** 2 for v in values) / len(values)) ** 0.5
    if std > 0:
        x = np.linspace(min(values), max(values), 200)
        y = (1 / (std * np.sqrt(2 * np.pi))) * np.exp(-0.5 * ((x - mean) / std) ** 2)
        ax.plot(x, y, 'r-', linewidth=2, label=f'Normal (μ={mean:.1f}, σ={std:.1f})')

    ax.axvline(mean, color='#D32F2F', linestyle='--', alpha=0.7)
    ax.set_xlabel(metric_key)
    ax.set_ylabel('Density')
    ax.set_title(title)
    ax.legend()
    ax.grid(True, alpha=0.3)

    fig.tight_layout()
    return fig


def plot_tiff_profile(data_2d, info: dict,
                      title: str = None) -> Figure:
    """TIFF Raw Height 프로파일 시각화"""
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    z_unit = info.get('z_unit', '')
    channel = info.get('channel_name', '')
    mode = info.get('head_mode', '')
    w = info.get('width', 1)
    h = info.get('height', 1)

    if title is None:
        title = f'{channel} [{mode}]'

    if h == 1 or w == 1:
        profile = data_2d.flatten()
        scan_size = info.get('scan_size_width', 0) if w > 1 else info.get('scan_size_height', 0)

        if scan_size and scan_size > 0:
            x_axis = np.linspace(0, scan_size, len(profile))
            x_label = 'Position (μm)'
        else:
            x_axis = np.arange(len(profile))
            x_label = 'Pixel'

        axes[0].plot(x_axis, profile, color='#1565C0', linewidth=0.5)
        axes[0].set_xlabel(x_label)
        axes[0].set_ylabel(f'Z ({z_unit})')
        axes[0].set_title(f'{title} — Profile')
        axes[0].grid(True, alpha=0.3)

        axes[1].hist(profile, bins=80, color='#42A5F5', edgecolor='white', alpha=0.8)
        axes[1].set_xlabel(f'Z ({z_unit})')
        axes[1].set_ylabel('Count')
        axes[1].set_title('Distribution')
        axes[1].grid(True, alpha=0.3)
    else:
        im = axes[0].imshow(data_2d, origin='lower', cmap='viridis', aspect='auto')
        plt.colorbar(im, ax=axes[0], label=f'Z ({z_unit})')
        axes[0].set_title(f'{title} — 2D')
        axes[0].set_xlabel('X (px)')
        axes[0].set_ylabel('Y (px)')

        mid_row = h // 2
        axes[1].plot(data_2d[mid_row, :], color='#1565C0', linewidth=0.5)
        axes[1].set_xlabel('X (px)')
        axes[1].set_ylabel(f'Z ({z_unit})')
        axes[1].set_title(f'H-Profile (row={mid_row})')
        axes[1].grid(True, alpha=0.3)

    fig.suptitle(title, fontsize=12, fontweight='bold')
    fig.tight_layout()
    return fig


# ──────────────────────────────────────────────
# Multi-Recipe 비교 차트
# ──────────────────────────────────────────────

def plot_recipe_comparison_boxplot(recipe_results: list) -> Figure:
    """Recipe별 박스플롯 비교 (X/Y 분리, 2행)"""
    n = len(recipe_results)
    if n == 0:
        fig, ax = plt.subplots()
        return fig

    fig, axes = plt.subplots(2, n, figsize=(4 * n, 8), sharey='row')
    if n == 1:
        axes = axes.reshape(2, 1)

    for row, axis_name in enumerate(['X', 'Y']):
        for i, result in enumerate(recipe_results):
            ax = axes[row][i]
            data = result.get('raw_data', [])
            color = RECIPE_COLORS[i % len(RECIPE_COLORS)]

            values = [r.get('value', 0) for r in data
                      if isinstance(r.get('value'), (int, float))
                      and r.get('method') == axis_name]

            if values:
                bp = ax.boxplot([values], patch_artist=True,
                                boxprops=dict(facecolor=color + '40',
                                              edgecolor=color),
                                medianprops=dict(color='#D32F2F', linewidth=2),
                                flierprops=dict(marker='o', markerfacecolor='#FF5722',
                                                markersize=3))

            stats_vals = np.array(values) if values else np.array([0])
            ax.set_title(f'{result.get("short_name", "?")} ({axis_name})\n'
                         f'μ={np.mean(stats_vals):.0f}  σ={np.std(stats_vals):.0f}',
                         fontsize=9)
            ax.grid(True, alpha=0.3, axis='y')

        axes[row][0].set_ylabel(f'{axis_name} Offset (nm)')

    fig.suptitle('Recipe Comparison (X / Y)', fontsize=12, fontweight='bold')
    fig.tight_layout()
    return fig


def plot_recipe_comparison_trend(recipe_results: list) -> Figure:
    """Recipe별 트렌드 오버레이 (X/Y 분리, 2행)"""
    fig, axes = plt.subplots(2, 1, figsize=(12, 8), sharex=True)

    for row, axis_name in enumerate(['X', 'Y']):
        ax = axes[row]
        for i, result in enumerate(recipe_results):
            # trend_x/trend_y 우선, 없으면 기존 trend 사용
            trend = result.get(f'trend_{axis_name.lower()}', [])
            if not trend:
                continue

            color = RECIPE_COLORS[i % len(RECIPE_COLORS)]
            indices = [t['lot_index'] for t in trend]
            means = [t['mean'] for t in trend]

            ax.plot(indices, means, 'o-', color=color, linewidth=2,
                    markersize=5, label=result.get('short_name', f'Recipe {i+1}'))

        ax.set_ylabel(f'{axis_name} Offset (nm)')
        ax.set_title(f'Recipe Trend Comparison — {axis_name}')
        ax.legend(loc='best', fontsize=8)
        ax.grid(True, alpha=0.3)

    axes[1].set_xlabel('Lot Index')
    fig.tight_layout()
    return fig


def plot_recipe_comparison_heatmap(recipe_results: list,
                                   method: str = 'X',
                                   mode: str = 'scatter') -> Figure:
    """Recipe별 히트맵/컨투어 2×2 그리드"""
    n = len(recipe_results)
    cols = min(n, 2)
    rows = max(1, (n + 1) // 2)

    fig, axes = plt.subplots(rows, cols, figsize=(6 * cols, 5 * rows))
    if n == 1:
        axes = np.array([[axes]])
    elif rows == 1:
        axes = axes.reshape(1, -1)

    for i, result in enumerate(recipe_results):
        r, c = divmod(i, cols)
        ax = axes[r][c]

        data = result.get('raw_data', [])
        xs, ys, means, site_vals = _extract_site_data(data, 'value', method)

        if not xs:
            ax.text(0.5, 0.5, 'No data', ha='center', va='center',
                    transform=ax.transAxes)
            ax.set_title(result.get('short_name', ''))
            continue

        if mode == 'contour' and len(xs) >= 4:
            try:
                from scipy.interpolate import griddata
                xi = np.linspace(min(xs) - 1, max(xs) + 1, 80)
                yi = np.linspace(min(ys) - 1, max(ys) + 1, 80)
                Xi, Yi = np.meshgrid(xi, yi)
                Zi = griddata((xs, ys), means, (Xi, Yi), method='cubic')
                cf = ax.contourf(Xi, Yi, Zi, levels=15, cmap='RdYlGn_r', alpha=0.8)
                fig.colorbar(cf, ax=ax, shrink=0.8)
                ax.scatter(xs, ys, c='black', s=15, zorder=3)
            except Exception:
                ax.scatter(xs, ys, c=means, s=100, cmap='RdYlGn_r',
                           edgecolors='black', linewidths=0.5)
        else:
            scatter = ax.scatter(xs, ys, c=means, s=100, cmap='RdYlGn_r',
                                 edgecolors='black', linewidths=0.5)
            fig.colorbar(scatter, ax=ax, shrink=0.8)

        ax.set_title(result.get('short_name', ''), fontsize=10)
        ax.set_aspect('equal')
        ax.grid(True, alpha=0.3)

    # 빈 subplot 숨기기
    for j in range(n, rows * cols):
        r, c = divmod(j, cols)
        axes[r][c].set_visible(False)

    fig.suptitle(f'Recipe Heatmap Comparison (Method: {method})',
                 fontsize=12, fontweight='bold')
    fig.tight_layout()
    return fig


# ──────────────────────────────────────────────
# Wafer-level Visualizations (ported from xy_stage_offset)
# ──────────────────────────────────────────────

from analyzer import DIE_POSITIONS, get_die_position


def _hsl_to_rgb(h, s, l):
    c = (1 - abs(2 * l - 1)) * s
    x = c * (1 - abs((h / 60) % 2 - 1))
    m = l - c / 2
    if h < 60:    r, g, b = c, x, 0
    elif h < 120: r, g, b = x, c, 0
    elif h < 180: r, g, b = 0, c, x
    elif h < 240: r, g, b = 0, x, c
    elif h < 300: r, g, b = x, 0, c
    else:         r, g, b = c, 0, x
    return (r + m, g + m, b + m)


def _color_from_die(die_idx, total=21):
    hue = (die_idx % total) * (360.0 / total)
    return _hsl_to_rgb(hue, 0.6, 0.5)


def _color_from_die_hex(die_idx, total=21):
    """Die 인덱스 → '#RRGGBB' hex 문자열 (pyqtgraph/Qt 호환)."""
    r, g, b = _color_from_die(die_idx, total)
    return f'#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}'


def plot_wafer_contour(die_stats: list, title: str = 'Wafer Contour',
                       vmin: float = 0.0, vmax: float = 1.0,
                       wafer_radius_um: float = 150_000,
                       dynamic_positions: dict = None) -> Figure:
    """Die 좌표계 기반 원형 Wafer Contour Map (µm 단위).

    Args:
        die_stats: [{'die': 'Die1', 'avg': ...}, ...]
        wafer_radius_um: 웨이퍼 반경 (µm) — 200mm=100000, 300mm=150000
        dynamic_positions: 데이터 기반 동적 Die 좌표 dict
    """
    from scipy.interpolate import griddata
    from matplotlib.patches import Circle
    from matplotlib.colors import Normalize

    positions, values, die_labels = [], [], []
    for ds in die_stats:
        pos = get_die_position(ds['die'], dynamic_positions)
        if pos is not None:
            # mm → µm 변환
            positions.append((pos[0] * 1000, pos[1] * 1000))
            values.append(abs(ds['avg']))
            die_labels.append(ds['die'])

    fig, ax = plt.subplots(figsize=(7, 7))
    fig.patch.set_facecolor('#1e1e2e')
    ax.set_facecolor('#262637')

    if len(positions) < 3:
        ax.text(0.5, 0.5, 'Insufficient Die data', ha='center', va='center',
                transform=ax.transAxes, fontsize=14, color='#cdd6f4')
        return fig

    xs = np.array([p[0] for p in positions], dtype=float)
    ys = np.array([p[1] for p in positions], dtype=float)
    zs = np.array(values, dtype=float)

    # ── 원형 보정: 외곽 Die 기반 경계에 가상 포인트 추가 ──
    # 측정 영역만 커버 (웨이퍼 엣지까지 확장하지 않음)
    from scipy.spatial import cKDTree
    data_r = float(np.sqrt(xs**2 + ys**2).max()) + 5000  # 외곽 Die + 5mm 여유
    n_boundary = 48
    angles = np.linspace(0, 2 * np.pi, n_boundary, endpoint=False)
    bx = data_r * np.cos(angles)
    by = data_r * np.sin(angles)
    tree = cKDTree(np.column_stack([xs, ys]))
    _, nearest_idx = tree.query(np.column_stack([bx, by]))
    bz = zs[nearest_idx]
    xs_ext = np.concatenate([xs, bx])
    ys_ext = np.concatenate([ys, by])
    zs_ext = np.concatenate([zs, bz])

    # 고해상도 그리드 (400×400)
    grid_res = 400
    pad = data_r * 1.05
    x_range = np.linspace(-pad, pad, grid_res)
    y_range = np.linspace(-pad, pad, grid_res)
    xi, yi = np.meshgrid(x_range, y_range)

    zi = griddata((xs_ext, ys_ext), zs_ext, (xi, yi), method='cubic')

    # 원형 마스킹 (측정 영역만)
    dist = np.sqrt(xi**2 + yi**2)
    zi[dist > data_r] = np.nan

    # Contour 렌더링 (30 레벨, 부드러운 그라데이션)
    auto_vmin = float(np.nanmin(zs)) if vmin == 0.0 and vmax == 1.0 else vmin
    auto_vmax = float(np.nanmax(zs)) if vmin == 0.0 and vmax == 1.0 else vmax
    if auto_vmin == auto_vmax:
        auto_vmax = auto_vmin + 0.1
    levels = np.linspace(auto_vmin, auto_vmax, 30)
    norm = Normalize(vmin=auto_vmin, vmax=auto_vmax)

    cf = ax.contourf(xi, yi, zi, levels=levels, cmap='RdYlGn_r', norm=norm, extend='both')

    # 원형 clip_path — 깔끔한 원형 클리핑 (matplotlib 버전 호환)
    clip_circle = Circle((0, 0), wafer_radius_um, transform=ax.transData)
    try:
        # matplotlib >= 3.8
        for artist in cf.artists if hasattr(cf, 'artists') else cf.collections:
            artist.set_clip_path(clip_circle)
    except (AttributeError, TypeError):
        pass  # NaN 마스킹만으로 충분

    # 웨이퍼 경계 원 (점선)
    wafer_outline = Circle((0, 0), wafer_radius_um, fill=False,
                            edgecolor='#888', linewidth=1.5,
                            linestyle='--', alpha=0.7)
    ax.add_patch(wafer_outline)

    # Die 점 (작은 원)
    ax.scatter(xs, ys, c='#1e1e2e', s=25, zorder=5,
               edgecolors='white', linewidths=0.6, alpha=0.8)

    # Die 값 annotation (흰색 + 검정 외곽선 + 반투명 배경으로 시인성 극대화)
    from matplotlib.patheffects import withStroke
    outline = withStroke(linewidth=4, foreground='black')
    for i, (x, y) in enumerate(zip(xs, ys)):
        val = zs[i]
        ax.text(x, y + wafer_radius_um * 0.04, f'{val:.2f}',
                ha='center', va='bottom', fontsize=7.5, fontweight='bold',
                color='white', zorder=6,
                path_effects=[outline],
                bbox=dict(boxstyle='round,pad=0.12', fc='black',
                          ec='none', alpha=0.45))

    # Colorbar
    cbar = fig.colorbar(cf, ax=ax, shrink=0.75, pad=0.04)
    cbar.set_label('Deviation (µm)', color='#aaa')
    cbar.ax.yaxis.set_tick_params(color='#777')
    for label in cbar.ax.get_yticklabels():
        label.set_color('#aaa')

    # 축 스타일
    ax.set_xlim(-wafer_radius_um * 1.08, wafer_radius_um * 1.08)
    ax.set_ylim(-wafer_radius_um * 1.08, wafer_radius_um * 1.08)
    ax.set_aspect('equal')
    ax.set_xlabel('X (µm)', color='#aaa')
    ax.set_ylabel('Y (µm)', color='#aaa')
    ax.set_title(title, fontsize=11, color='#89b4fa')
    ax.tick_params(colors='#777')
    for s in ax.spines.values():
        s.set_color('#363650')
    fig.tight_layout()
    return fig


def plot_xy_scatter(x_dev_result: dict, y_dev_result: dict,
                    title: str = 'XY Scatter') -> Figure:
    """X/Y Deviation을 Die별 색상으로 구분한 산점도.

    Args:
        x_dev_result, y_dev_result: compute_deviation_matrix() 결과
    """
    fig, ax = plt.subplots(figsize=(7, 6))

    die_labels = x_dev_result.get('die_labels', [])
    repeat_labels = x_dev_result.get('repeat_labels', [])
    x_matrix = x_dev_result.get('matrix', {})
    y_matrix = y_dev_result.get('matrix', {})

    for dl in die_labels:
        idx = int(dl.replace('Die', '')) - 1  # 1-based label → 0-based index
        color = _color_from_die(idx)
        xvals, yvals = [], []
        for rl in repeat_labels:
            xv = x_matrix.get(rl, {}).get(dl)
            yv = y_matrix.get(rl, {}).get(dl)
            if xv is not None and yv is not None:
                xvals.append(xv)
                yvals.append(yv)
        if xvals:
            ax.scatter(xvals, yvals, c=[color], s=20, label=dl, alpha=0.8, edgecolors='none')

    ax.set_xlabel('X Offset (µm)')
    ax.set_ylabel('Y Offset (µm)')
    ax.set_xlim(-5, 5)
    ax.set_ylim(-5, 5)
    ax.set_xticks(range(-5, 6))
    ax.set_yticks(range(-5, 6))
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=6, ncol=3, loc='upper right', framealpha=0.7)
    ax.set_title(title, fontsize=11)
    fig.tight_layout()
    return fig



def plot_die_position_map(dynamic_positions: dict = None,
                          wafer_radius_um: float = 150_000) -> Figure:
    """21 Die 좌표 배치 참조도.

    Args:
        dynamic_positions: {0: (x_mm, y_mm), ...} — 데이터에서 추출된 실제 좌표
        wafer_radius_um: 웨이퍼 반경 (µm) — 축 범위 결정용
    """
    fig, ax = plt.subplots(figsize=(8, 7))
    fig.patch.set_facecolor('#262637')
    ax.set_facecolor('#1e1e2e')

    # 좌표 소스 결정
    if dynamic_positions:
        die_indices = sorted(dynamic_positions.keys())
        positions = [(i, dynamic_positions[i]) for i in die_indices]
    else:
        positions = [(i, pos) for i, pos in enumerate(DIE_POSITIONS)]

    # mm → µm 변환하여 표시
    positions_um = [(idx, (x * 1000, y * 1000)) for idx, (x, y) in positions]

    # Die 마커 + 번호
    sc_list = []
    legend_handles = []
    for die_idx, (x, y) in positions_um:
        c = _color_from_die(die_idx)
        sc = ax.scatter(x, y, c=[c], s=800, zorder=5, edgecolors='white', linewidths=0.8,
                        label=f'Die {die_idx + 1}')
        ax.annotate(str(die_idx + 1), (x, y), ha='center', va='center',
                    fontsize=11, fontweight='bold', color='white', zorder=6)
        sc_list.append((die_idx, x, y, sc))
        legend_handles.append(sc)

    # 측정 순서 화살표
    for i in range(len(positions_um) - 1):
        _, (x0, y0) = positions_um[i]
        _, (x1, y1) = positions_um[i + 1]
        ax.annotate('', xy=(x1, y1), xytext=(x0, y0),
                    arrowprops=dict(arrowstyle='->', color='#585b70',
                                    lw=0.8, connectionstyle='arc3,rad=0.15'),
                    zorder=2)

    # 호버 툴팁
    hover_annot = ax.annotate('', xy=(0, 0), xytext=(15, 15),
                               textcoords='offset points',
                               bbox=dict(boxstyle='round,pad=0.4',
                                         fc='#313244', ec='#89b4fa', alpha=0.95),
                               color='white', fontsize=9,
                               arrowprops=dict(arrowstyle='->', color='#89b4fa'),
                               zorder=10)
    hover_annot.set_visible(False)

    def on_hover(event):
        if event.inaxes != ax:
            hover_annot.set_visible(False)
            fig.canvas.draw_idle()
            return
        found = False
        for die_idx, dx, dy, sc in sc_list:
            contains, _ = sc.contains(event)
            if contains:
                hover_annot.xy = (dx, dy)
                hover_annot.set_text(
                    f"Die {die_idx + 1}\n"
                    f"X: {dx:,.0f} µm\n"
                    f"Y: {dy:,.0f} µm")
                hover_annot.set_visible(True)
                found = True
                break
        if not found:
            hover_annot.set_visible(False)
        fig.canvas.draw_idle()

    fig.canvas.mpl_connect('motion_notify_event', on_hover)

    # 웨이퍼 경계 원 (점선, 반투명)
    from matplotlib.patches import Circle
    wafer_circle = Circle((0, 0), wafer_radius_um, fill=False,
                           edgecolor='#888', linewidth=1.5,
                           linestyle='--', alpha=0.5)
    ax.add_patch(wafer_circle)

    # 축 범위 — 웨이퍼 반경 기준
    ax.set_xlim(-wafer_radius_um * 1.05, wafer_radius_um * 1.05)
    ax.set_ylim(-wafer_radius_um * 1.05, wafer_radius_um * 1.05)
    ax.set_aspect('equal')
    ax.set_xlabel('X (µm)', color='#aaa')
    ax.set_ylabel('Y (µm)', color='#aaa')
    ax.set_title(f'Die Position Map ({len(positions_um)} Dies)',
                 color='#89b4fa', fontsize=12)
    ax.tick_params(colors='#777')
    for s in ax.spines.values():
        s.set_color('#363650')
    ax.grid(True, alpha=0.15, color='#555')

    # Die 범례 (우측)
    leg = ax.legend(handles=legend_handles,
                    loc='center left', bbox_to_anchor=(1.02, 0.5),
                    fontsize=9, frameon=True, framealpha=0.7,
                    facecolor='#313244', edgecolor='#45475a',
                    labelcolor='#cdd6f4', ncol=1,
                    markerscale=0.6, handletextpad=0.5,
                    borderpad=0.6, labelspacing=1.2,
                    handleheight=1.0)
    leg.set_title('Die', prop={'size': 10, 'weight': 'bold'})
    leg.get_title().set_color('#89b4fa')

    fig.tight_layout()
    return fig



def plot_die_position_map_mini(dynamic_positions: dict = None,
                                wafer_radius_um: float = 150_000,
                                excluded_dies: set = None) -> tuple:
    """Die Position Map 미니 버전 — Die 필터 확장 패널용.

    - 범례, 축 라벨, 측정 순서 화살표 제거 (공간 절약)
    - picker=True → 클릭 이벤트 감지 가능
    - excluded_dies 내의 Die는 회색 + 반투명으로 표시

    Returns:
        (fig, die_scatter_map) — die_scatter_map: {die_idx: scatter_artist}
    """
    fig, ax = plt.subplots(figsize=(3.5, 3.2))
    fig.patch.set_facecolor('#262637')
    ax.set_facecolor('#1e1e2e')

    if excluded_dies is None:
        excluded_dies = set()

    # 좌표 소스 결정
    if dynamic_positions:
        die_indices = sorted(dynamic_positions.keys())
        positions = [(i, dynamic_positions[i]) for i in die_indices]
    else:
        positions = [(i, pos) for i, pos in enumerate(DIE_POSITIONS)]

    # mm → µm
    positions_um = [(idx, (x * 1000, y * 1000)) for idx, (x, y) in positions]

    # 웨이퍼 경계 원
    from matplotlib.patches import Circle
    wafer_circle = Circle((0, 0), wafer_radius_um, fill=False,
                           edgecolor='#555', linewidth=1, linestyle='--', alpha=0.4)
    ax.add_patch(wafer_circle)

    # Die 마커 + 번호
    die_scatter_map = {}  # {die_idx: scatter_artist}
    for die_idx, (x, y) in positions_um:
        is_excluded = die_idx in excluded_dies
        if is_excluded:
            c = '#555555'
            alpha = 0.35
            edge_color = '#444'
            text_color = '#666'
        else:
            c = _color_from_die(die_idx)
            alpha = 1.0
            edge_color = 'white'
            text_color = 'white'

        sc = ax.scatter(x, y, c=[c], s=280, zorder=5, alpha=alpha,
                        edgecolors=edge_color, linewidths=0.5,
                        picker=True, pickradius=8)
        ax.annotate(str(die_idx + 1), (x, y), ha='center', va='center',
                    fontsize=7, fontweight='bold', color=text_color,
                    alpha=alpha, zorder=6)
        die_scatter_map[die_idx] = sc

    # 축 범위 — 웨이퍼 반경 기준 (간소화)
    ax.set_xlim(-wafer_radius_um * 1.08, wafer_radius_um * 1.08)
    ax.set_ylim(-wafer_radius_um * 1.08, wafer_radius_um * 1.08)
    ax.set_aspect('equal')
    ax.set_title(f'Die Position ({len(positions_um)})',
                 color='#89b4fa', fontsize=9, pad=4)
    ax.tick_params(colors='#555', labelsize=6)
    for s in ax.spines.values():
        s.set_color('#363650')
    ax.grid(True, alpha=0.1, color='#444')

    fig.tight_layout(pad=0.5)
    return fig, die_scatter_map


def plot_vector_map(x_die_stats: list, y_die_stats: list,
                    title: str = 'Vector Map (Quiver)',
                    scale_pct: int = 10,
                    wafer_radius_um: float = 150_000,
                    dynamic_positions: dict = None) -> Figure:
    """Die별 XY Offset 벡터를 화살표(quiver)로 시각화 (µm 단위).

    Args:
        x_die_stats, y_die_stats: compute_deviation_matrix()['die_stats']
        scale_pct: 화살표 배율 (%) — 최대 벡터가 웨이퍼 반경의 N% 길이
        wafer_radius_um: 웨이퍼 반경 (µm)
        dynamic_positions: 데이터 기반 동적 Die 좌표 dict
    """
    from matplotlib.patches import Circle
    from matplotlib.colors import Normalize

    x_map = {ds['die']: ds['avg'] for ds in x_die_stats}
    y_map = {ds['die']: ds['avg'] for ds in y_die_stats}
    common = sorted(set(x_map.keys()) & set(y_map.keys()))

    fig, ax = plt.subplots(figsize=(7, 7))
    fig.patch.set_facecolor('#1e1e2e')
    ax.set_facecolor('#262637')

    if len(common) < 2:
        ax.text(0.5, 0.5, 'Insufficient Die data', ha='center', va='center',
                transform=ax.transAxes, fontsize=14, color='#cdd6f4')
        return fig

    xs, ys, us, vs, mags = [], [], [], [], []
    for d in common:
        pos = get_die_position(d, dynamic_positions)
        if pos is None:
            continue
        # mm → µm 변환
        xs.append(pos[0] * 1000)
        ys.append(pos[1] * 1000)
        us.append(x_map[d])
        vs.append(y_map[d])
        mags.append(np.sqrt(x_map[d]**2 + y_map[d]**2))

    xs = np.array(xs); ys = np.array(ys)
    us = np.array(us); vs = np.array(vs)
    mags = np.array(mags)

    # Wafer boundary circle
    circle = Circle((0, 0), wafer_radius_um, fill=False, edgecolor='#555',
                     linewidth=1.5, linestyle='--')
    ax.add_patch(circle)

    # Die positions (background dots)
    ax.scatter(xs, ys, c='#45475a', s=120, zorder=2, edgecolors='#585b70', linewidths=0.5)

    # Quiver — 슬라이더 배율(%) 기반 스케일링
    # 최대 벡터가 웨이퍼 반경의 scale_pct% 길이가 되도록
    max_mag = max(mags.max(), 0.001)
    target_arrow_len = wafer_radius_um * (scale_pct / 100.0)
    arrow_scale = max_mag / target_arrow_len

    norm = Normalize(vmin=0, vmax=max_mag)
    q = ax.quiver(xs, ys, us, vs, mags, cmap='hot_r', norm=norm,
                  angles='xy', scale_units='xy',
                  scale=arrow_scale,
                  width=0.007, headwidth=4, headlength=5,
                  minlength=0.5, zorder=5)

    cbar = fig.colorbar(q, ax=ax, shrink=0.75, pad=0.04)
    cbar.set_label('Magnitude (µm)', color='#aaa')
    cbar.ax.yaxis.set_tick_params(color='#777')
    for lbl in cbar.ax.get_yticklabels():
        lbl.set_color('#aaa')

    # Die labels
    for i, d in enumerate(common):
        pos = get_die_position(d, dynamic_positions)
        if pos:
            ax.annotate(d.replace('Die', ''), (pos[0] * 1000, pos[1] * 1000),
                        textcoords='offset points', xytext=(6, 6),
                        fontsize=7, color='#89b4fa', fontweight='bold')

    ax.set_xlim(-wafer_radius_um * 1.05, wafer_radius_um * 1.05)
    ax.set_ylim(-wafer_radius_um * 1.05, wafer_radius_um * 1.05)
    ax.set_aspect('equal')
    ax.set_xlabel('X (µm)', color='#aaa')
    ax.set_ylabel('Y (µm)', color='#aaa')
    ax.set_title(title, color='#89b4fa', fontsize=12)
    ax.tick_params(colors='#777')
    for s in ax.spines.values():
        s.set_color('#363650')
    ax.grid(True, alpha=0.1, color='#555')
    fig.tight_layout()
    return fig
