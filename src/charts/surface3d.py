import copy
import numpy as np
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSlider, QRadioButton, QButtonGroup
from PySide6.QtGui import QPainter, QColor, QFont, QLinearGradient
from PySide6.QtCore import Qt

try:
    import pyqtgraph.opengl as gl
    _GL_AVAILABLE = True
except ImportError:
    _GL_AVAILABLE = False

try:
    from scipy.interpolate import griddata
    from scipy.optimize import curve_fit
    _SCIPY_AVAILABLE = True
except ImportError:
    _SCIPY_AVAILABLE = False

# ─── 테마 상수 ───
BG      = '#1e1e2e'
BG2     = '#313244'
BG3     = '#181825'
FG      = '#cdd6f4'
FG2     = '#a6adc8'
ACCENT  = '#89b4fa'
RED     = '#f38ba8'


# ─── 2D Polynomial 모델 함수군 ───
def poly1d_2d(xy, a, b, c):
    """1차 평면 (Tilt)"""
    x, y = xy
    return a * x + b * y + c


def poly2d_2d(xy, a, b, c, d, e, f):
    """2차 곡면 (Curve/Bowl)"""
    x, y = xy
    return a*x**2 + b*y**2 + c*x*y + d*x + e*y + f


# ─── Colorbar 위젯 ───
class ColorBarWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(60)
        self.z_min = -1.0
        self.z_max = 1.0

    def set_range(self, z_min, z_max):
        self.z_min = z_min
        self.z_max = z_max
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        rect_w = 20
        rect_h = max(self.height() - 60, 20)
        rect_x = 10
        rect_y = 30

        # 그라데이션: 상단(빨강=양수 큰 값) → 중간(초록=0) → 하단(파랑=음수 큰 값)
        gradient = QLinearGradient(rect_x, rect_y, rect_x, rect_y + rect_h)
        gradient.setColorAt(0.0, QColor(220, 50, 50))
        gradient.setColorAt(0.5, QColor(50, 200, 100))
        gradient.setColorAt(1.0, QColor(50, 100, 220))

        painter.fillRect(rect_x, rect_y, rect_w, rect_h, gradient)

        painter.setPen(QColor(FG))
        font = QFont()
        font.setPointSize(7)
        painter.setFont(font)

        text_x = rect_x + rect_w + 3
        painter.drawText(text_x, rect_y + 8, f"{self.z_max:+.2f}")
        painter.drawText(text_x, rect_y + rect_h // 2 + 4, "0.00")
        painter.drawText(text_x, rect_y + rect_h, f"{self.z_min:+.2f}")


# ─── 메인 3D Surface 위젯 ───
class Surface3DWidget(QWidget):
    def __init__(self, die_stats: list, title: str = '3D Surface', parent=None):
        super().__init__(parent)
        self.die_stats = copy.deepcopy(die_stats)
        self.title = title

        # 좌표 및 Z 데이터
        self.xs, self.ys = [], []
        self.zs_raw = []
        self.zs_tilt = []
        self.zs_curve = []
        self.zs_resid = []
        self.zs = []              # 현재 선택 모델의 Die 포인트 값

        # 보간 그리드 (렌더링용)
        self.xi = None
        self.yi = None
        self.Zi_grid = None      # 보간된 그리드 행렬
        self.colors = None

        # 옵션 상태
        self.z_scale = 1.0
        self.current_model = 'raw'

        # 3D 아이템 핸들
        self.surface_item = None
        self.scatter_item = None
        self.grid_item = None
        self.zero_plane = None

        # GL/View 객체 (임포트 실패 시 None)
        self.view = None
        self.colorbar = None
        self._render_items = []  # 렌더링된 GL 아이템 추적용

        # 폰트 (GLTextItem용)
        from PySide6.QtGui import QFont as _QFont
        self._label_font = _QFont('Arial', 10, _QFont.Bold)
        self._die_font = _QFont('Arial', 7)

        self._init_ui()
        self._load_data()
        if self.view is not None and self.Zi_grid is None:
            self._show_info_msg(
                "Die 데이터 없음" if not self.die_stats
                else "3D 보간에 최소 4개 Die 필요")
        self._render()

    # ── UI 구성 ──────────────────────────────────────────────
    def _init_ui(self):
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        # 제목 바
        title_lbl = QLabel(f"  {self.title}")
        title_lbl.setStyleSheet(
            f"color:{FG}; font-size:10pt; font-weight:bold; background:{BG2}; padding:4px;")
        self.main_layout.addWidget(title_lbl)

        # 3D 뷰 + Colorbar 수평 배치
        view_row = QHBoxLayout()
        self._view_row = view_row
        self.main_layout.addLayout(view_row, 1)

        if not _GL_AVAILABLE or not _SCIPY_AVAILABLE:
            missing = []
            if not _GL_AVAILABLE: missing.append("PyOpenGL")
            if not _SCIPY_AVAILABLE: missing.append("scipy")
            err = QLabel(f"3D 표시 불가\npip install {' '.join(missing)}")
            err.setStyleSheet(f"color:{RED}; font-size:10pt; padding:40px;")
            err.setAlignment(Qt.AlignCenter)
            view_row.addWidget(err)
        else:
            self.view = gl.GLViewWidget()
            self.view.setBackgroundColor(BG)
            self.view.setCameraPosition(distance=20, elevation=30, azimuth=45)
            view_row.addWidget(self.view, 1)

            self.colorbar = ColorBarWidget()
            view_row.addWidget(self.colorbar)

        # ── 하단 컨트롤 바 ──
        ctrl = QHBoxLayout()
        ctrl.setContentsMargins(10, 4, 10, 4)

        ctrl.addWidget(self._make_label("Z Scale:"))
        self.scale_slider = QSlider(Qt.Horizontal)
        self.scale_slider.setRange(1, 50)
        self.scale_slider.setValue(1)
        self.scale_slider.setFixedWidth(110)
        self.scale_slider.valueChanged.connect(self._on_scale_changed)
        ctrl.addWidget(self.scale_slider)

        self.scale_val_lbl = QLabel("x1")
        self.scale_val_lbl.setStyleSheet(f"color:{ACCENT}; min-width:28px;")
        ctrl.addWidget(self.scale_val_lbl)

        ctrl.addStretch()
        ctrl.addWidget(self._make_label("Model:"))

        self.grp_model = QButtonGroup(self)
        for i, name in enumerate(['Raw', 'Tilt', 'Curve', 'Residual']):
            rb = QRadioButton(name)
            rb.setStyleSheet(f"color:{FG};")
            if i == 0:
                rb.setChecked(True)
            self.grp_model.addButton(rb, i)
            ctrl.addWidget(rb)

        # ★ idClicked 시그널 사용 (int 전달) - buttonClicked는 QPushButton 전달
        self.grp_model.idClicked.connect(self._on_model_changed)

        self.main_layout.addLayout(ctrl)

    def _make_label(self, text):
        lbl = QLabel(text)
        lbl.setStyleSheet(f"color:{FG}; font-weight:bold;")
        return lbl

    def _show_info_msg(self, msg: str):
        """데이터 부족 시 빈 3D 뷰 대신 안내 라벨 표시."""
        if self.view is not None:
            self.view.hide()
        if self.colorbar is not None:
            self.colorbar.hide()
        info = QLabel(msg)
        info.setStyleSheet(f"color:{FG2}; font-size:11pt; padding:40px;")
        info.setAlignment(Qt.AlignCenter)
        self._view_row.addWidget(info, 1)

    # ── 데이터 로딩 ──────────────────────────────────────────
    def _load_data(self):
        if not self.die_stats or self.view is None:
            return

        from core import get_die_position

        for ds in self.die_stats:
            pos = get_die_position(ds['die'])
            if pos:
                self.xs.append(pos[0])
                self.ys.append(pos[1])
                self.zs_raw.append(ds['avg'])

        if len(self.xs) < 4:
            return

        # ── Polynomial Curve Fitting ──
        xs_arr = np.array(self.xs, dtype=float)
        ys_arr = np.array(self.ys, dtype=float)
        zs_arr = np.array(self.zs_raw, dtype=float)

        try:
            p1, _ = curve_fit(poly1d_2d, (xs_arr, ys_arr), zs_arr)
            self.zs_tilt = poly1d_2d((xs_arr, ys_arr), *p1).tolist()

            p2, _ = curve_fit(poly2d_2d, (xs_arr, ys_arr), zs_arr,
                               p0=[0, 0, 0, 0, 0, float(np.mean(zs_arr))])
            zs_curve_arr = poly2d_2d((xs_arr, ys_arr), *p2)
            self.zs_curve = zs_curve_arr.tolist()
            self.zs_resid = (zs_arr - zs_curve_arr).tolist()
        except Exception:
            self.zs_tilt = self.zs_raw[:]
            self.zs_curve = self.zs_raw[:]
            self.zs_resid = [0.0] * len(self.zs_raw)

        # 초기 보간 행렬 생성
        self._rebuild_grid()

    def _rebuild_grid(self):
        """현재 모델(self.current_model)에 맞춰 보간 그리드 및 컬러맵 재생성"""
        if len(self.xs) < 4:
            return

        # 모델 선택
        model_map = {
            'raw':   self.zs_raw,
            'tilt':  self.zs_tilt,
            'curve': self.zs_curve,
            'resid': self.zs_resid,
        }
        self.zs = model_map.get(self.current_model, self.zs_raw)

        # 보간 그리드
        self.xi = np.linspace(min(self.xs) - 1, max(self.xs) + 1, 50)
        self.yi = np.linspace(min(self.ys) - 1, max(self.ys) + 1, 50)
        Xi, Yi = np.meshgrid(self.xi, self.yi)
        self.Zi_grid = griddata((self.xs, self.ys), self.zs, (Xi, Yi), method='cubic')
        self.Zi_grid = np.nan_to_num(self.Zi_grid, nan=0.0)

        # Colorbar 범위 갱신
        z_min = float(np.nanmin(self.zs))
        z_max = float(np.nanmax(self.zs))
        if self.colorbar:
            self.colorbar.set_range(z_min, z_max)

        # RGBA 컬러맵
        z_range = z_max - z_min if z_max != z_min else 1.0
        Zi_norm = np.clip((self.Zi_grid - z_min) / z_range, 0, 1)
        self.colors = np.zeros((*self.Zi_grid.shape, 4), dtype=np.float32)
        self.colors[..., 0] = Zi_norm           # R
        self.colors[..., 1] = 1.0 - np.abs(Zi_norm - 0.5) * 2  # G
        self.colors[..., 2] = 1.0 - Zi_norm     # B
        self.colors[..., 3] = 0.85

    # ── 렌더링 ───────────────────────────────────────────────
    def _render(self):
        if self.view is None or self.Zi_grid is None:
            return

        # 기존 아이템 제거
        for item in self._render_items:
            try:
                self.view.removeItem(item)
            except Exception:
                pass
        self._render_items.clear()

        scaled_Zi = self.Zi_grid * self.z_scale
        z_min_scaled = float(np.min(self.zs)) * self.z_scale

        # 1. Surface
        surface = gl.GLSurfacePlotItem(
            x=self.xi, y=self.yi, z=scaled_Zi,
            colors=self.colors, shader='shaded', smooth=True)
        self.view.addItem(surface)
        self._render_items.append(surface)

        # 2. 바닥 Grid
        w = max(self.xs) - min(self.xs) + 4
        h = max(self.ys) - min(self.ys) + 4
        cx, cy = float(np.mean(self.xs)), float(np.mean(self.ys))

        grid = gl.GLGridItem()
        grid.setSize(w, h, 0)
        grid.setSpacing(1, 1, 1)
        grid.translate(cx, cy, min(z_min_scaled - 0.5, -0.5))
        self.view.addItem(grid)
        self._render_items.append(grid)

        # 3. Z=0 기준면
        zp = gl.GLGridItem()
        zp.setSize(w, h, 0)
        zp.setSpacing(1, 1, 1)
        zp.translate(cx, cy, 0.0)
        self.view.addItem(zp)
        self._render_items.append(zp)

        # 4. X/Y/Z 축 화살표 (원점 기준)
        axis = gl.GLAxisItem()
        axis.setSize(w * 0.5, h * 0.5, max(abs(z_min_scaled), 1.0))
        axis.translate(min(self.xs) - 1, min(self.ys) - 1, 0)
        self.view.addItem(axis)
        self._render_items.append(axis)

        # 5. 축 레이블 텍스트
        ax_origin_x = min(self.xs) - 1
        ax_origin_y = min(self.ys) - 1
        ax_len_x = w * 0.5
        ax_len_y = h * 0.5
        ax_len_z = max(abs(z_min_scaled), 1.0)

        for text, pos, color in [
            ('X',  (ax_origin_x + ax_len_x + 0.3, ax_origin_y, 0),        (1, 0.3, 0.3, 1)),
            ('Y',  (ax_origin_x, ax_origin_y + ax_len_y + 0.3, 0),        (0.3, 1, 0.3, 1)),
            ('Z (μm)', (ax_origin_x, ax_origin_y, ax_len_z + 0.3),        (0.3, 0.5, 1, 1)),
            ('O',  (ax_origin_x - 0.3, ax_origin_y - 0.3, -0.1),          (0.8, 0.8, 0.8, 0.7)),
        ]:
            t = gl.GLTextItem(pos=np.array(pos), text=text, color=color)
            t.setData(font=self._label_font)
            self.view.addItem(t)
            self._render_items.append(t)

        # 6. Die 마커 + 번호 텍스트
        die_nums = []
        for ds in self.die_stats:
            from core import get_die_position
            pos = get_die_position(ds['die'])
            if pos:
                die_nums.append(ds['die'])

        pts = np.array([[x, y, z * self.z_scale + 0.05]
                        for x, y, z in zip(self.xs, self.ys, self.zs)])
        scatter = gl.GLScatterPlotItem(
            pos=pts, size=8, color=(1, 1, 1, 1), pxMode=True)
        self.view.addItem(scatter)
        self._render_items.append(scatter)

        # Die 번호 텍스트 (약간 위에 표시)
        for i, (x, y, z) in enumerate(zip(self.xs, self.ys, self.zs)):
            if i < len(die_nums):
                dt = gl.GLTextItem(
                    pos=np.array([x, y, z * self.z_scale + 0.25]),
                    text=str(die_nums[i]),
                    color=(1, 1, 1, 0.85))
                dt.setData(font=self._die_font)
                self.view.addItem(dt)
                self._render_items.append(dt)

    # ── 이벤트 핸들러 ─────────────────────────────────────────
    def _on_scale_changed(self, val: int):
        self.z_scale = float(val)
        self.scale_val_lbl.setText(f"x{val}")
        self._render()

    def _on_model_changed(self, btn_id: int):
        """QButtonGroup.idClicked → int 전달"""
        models = {0: 'raw', 1: 'tilt', 2: 'curve', 3: 'resid'}
        self.current_model = models.get(btn_id, 'raw')
        self._rebuild_grid()
        self._render()


# ─── 하위 호환 래퍼 ───────────────────────────────────────────
def create_3d_surface_widget(die_stats: list, title: str = '3D Surface') -> QWidget:
    return Surface3DWidget(die_stats, title)
