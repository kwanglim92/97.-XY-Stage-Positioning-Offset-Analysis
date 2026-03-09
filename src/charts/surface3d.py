import pyqtgraph as pg
import pyqtgraph.opengl as gl
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel
from PySide6.QtCore import Qt, QPointF
import numpy as np

# Theme colors
BG      = '#1e1e2e'
BG2     = '#313244'
BG3     = '#181825'
FG      = '#cdd6f4'
FG2     = '#a6adc8'
ACCENT  = '#89b4fa'
GREEN   = '#a6e3a1'
RED     = '#f38ba8'
ORANGE  = '#fab387'
PURPLE  = '#cba6f7'

pg.setConfigOptions(background=BG, foreground=FG, antialias=True)
def create_3d_surface_widget(die_stats: list,
                              title: str = '3D Surface') -> QWidget:
    """Die별 평균 편차를 3D 표면 맵으로 시각화.

    Features:
      - scipy griddata 보간 → GLSurfacePlotItem
      - Die 위치 ScatterPlot 마커
      - 마우스 회전/줌/패닝
      - 컬러맵: RdYlGn_r 스타일

    Args:
        die_stats: [{'die': 1, 'avg': 0.5, ...}, ...]
    """
    from PySide6.QtWidgets import QVBoxLayout, QLabel

    container = QWidget()
    layout = QVBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)

    # 제목
    title_label = QLabel(f"  🌐 {title}")
    title_label.setStyleSheet(f"color: {FG}; font-size: 10pt; font-weight: bold; "
                               f"background: {BG2}; padding: 4px;")
    layout.addWidget(title_label)

    if not die_stats:
        info = QLabel("Die 데이터 없음")
        info.setStyleSheet(f"color: {FG2}; font-size: 11pt; padding: 40px;")
        info.setAlignment(Qt.AlignCenter)
        layout.addWidget(info, 1)
        return container

    try:
        import pyqtgraph.opengl as gl
        from scipy.interpolate import griddata
    except ImportError as e:
        info = QLabel(f"3D 표시 불가: {e}\npip install PyOpenGL scipy")
        info.setStyleSheet(f"color: {RED}; font-size: 10pt; padding: 40px;")
        info.setAlignment(Qt.AlignCenter)
        layout.addWidget(info, 1)
        return container

    # Die 위치 매핑
    from core import DIE_POSITIONS, get_die_position

    xs, ys, zs = [], [], []
    for ds in die_stats:
        pos = get_die_position(ds['die'])
        if pos:
            xs.append(pos[0])
            ys.append(pos[1])
            zs.append(ds['avg'])

    if len(xs) < 4:
        info = QLabel("3D 보간에 최소 4개 Die 필요")
        info.setStyleSheet(f"color: {FG2}; font-size: 11pt; padding: 40px;")
        info.setAlignment(Qt.AlignCenter)
        layout.addWidget(info, 1)
        return container

    # 보간 그리드
    import numpy as np

    xi = np.linspace(min(xs) - 1, max(xs) + 1, 50)
    yi = np.linspace(min(ys) - 1, max(ys) + 1, 50)
    Xi, Yi = np.meshgrid(xi, yi)
    Zi = griddata((xs, ys), zs, (Xi, Yi), method='cubic')

    # NaN → 0 (보간 범위 밖)
    Zi = np.nan_to_num(Zi, nan=0.0)

    # 색상 맵 생성 (RdYlGn_r 스타일)
    z_min, z_max = np.nanmin(zs), np.nanmax(zs)
    z_range = z_max - z_min if z_max != z_min else 1.0

    # normalize Zi for colormap
    Zi_norm = (Zi - z_min) / z_range
    Zi_norm = np.clip(Zi_norm, 0, 1)

    # RGBA 색상 배열
    colors = np.zeros((*Zi.shape, 4), dtype=np.float32)
    # 파란색(낮은 값) → 초록 → 빨강(높은 값)
    colors[..., 0] = Zi_norm  # R
    colors[..., 1] = 1.0 - np.abs(Zi_norm - 0.5) * 2  # G (중간에서 최대)
    colors[..., 2] = 1.0 - Zi_norm  # B
    colors[..., 3] = 0.85  # Alpha

    # GLViewWidget 생성
    view = gl.GLViewWidget()
    view.setBackgroundColor(BG)
    view.setCameraPosition(distance=20, elevation=30, azimuth=45)

    # Surface
    surface = gl.GLSurfacePlotItem(
        x=xi, y=yi, z=Zi,
        colors=colors,
        shader='shaded',
        smooth=True)
    view.addItem(surface)

    # 그리드
    grid = gl.GLGridItem()
    grid.setSize(max(xs) - min(xs) + 4, max(ys) - min(ys) + 4, 0)
    grid.setSpacing(1, 1, 1)
    grid.translate(np.mean(xs), np.mean(ys), z_min - 0.5)
    view.addItem(grid)

    # Die 마커 (scatter)
    die_points = np.array([[x, y, z + 0.1] for x, y, z in zip(xs, ys, zs)])
    scatter = gl.GLScatterPlotItem(
        pos=die_points,
        size=8,
        color=(1, 1, 1, 1),
        pxMode=True)
    view.addItem(scatter)

    layout.addWidget(view, 1)
    return container



