import math
import numpy as np
from PySide6.QtWidgets import QDialog, QVBoxLayout, QMessageBox
from core.die_analysis import get_die_position
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT

class RepeatContourDialog(QDialog):
    def __init__(self, parent=None, axis='X', dev_data=None, dyn_positions=None):
        super().__init__(parent)
        self.setWindowTitle(f"Repeat별 Contour Map — {axis} Offset")
        self.resize(1400, 850)
        self.axis = axis
        self.dev_data = dev_data or {}
        self.dyn_positions = dyn_positions
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        matrix = self.dev_data.get('matrix', {})
        die_labels = self.dev_data.get('die_labels', [])
        repeat_labels = self.dev_data.get('repeat_labels', [])

        if not repeat_labels or not die_labels:
            QMessageBox.information(self, "알림", f"{self.axis} 데이터가 없습니다.")
            return

        from scipy.interpolate import griddata
        from matplotlib.colors import Normalize
        from matplotlib.patheffects import withStroke
        import matplotlib.pyplot as plt

        n = len(repeat_labels)
        cols = min(5, n)
        rows = math.ceil(n / cols)
        cell = 4.2
        fig, axes = plt.subplots(rows, cols, figsize=(cell*cols, cell*rows + 0.8), dpi=110)
        fig.patch.set_facecolor('#1e1e2e')
        if rows == 1 and cols == 1: axes = [[axes]]
        elif rows == 1: axes = [axes]
        elif cols == 1: axes = [[ax] for ax in axes]

        all_vals = [abs(matrix.get(rl, {}).get(dl, 0))
                    for rl in repeat_labels for dl in die_labels
                    if matrix.get(rl, {}).get(dl) is not None]
        vmax_global = max(all_vals) if all_vals else 1.0

        for idx, rl in enumerate(repeat_labels):
            r, c = divmod(idx, cols)
            ax = axes[r][c]
            ax.set_facecolor('#1e1e2e')
            positions, values = [], []
            for dl in die_labels:
                v = matrix.get(rl, {}).get(dl)
                pos = get_die_position(dl, self.dyn_positions)
                if v is not None and pos is not None:
                    positions.append(pos); values.append(v)
            if len(positions) < 3:
                ax.text(0.5, 0.5, 'N/A', ha='center', va='center',
                        transform=ax.transAxes, color='#555', fontsize=12)
                ax.set_xlabel(rl, fontsize=10, fontweight='bold', color='#89b4fa')
                continue

            xs = np.array([p[0] for p in positions], dtype=float)
            ys = np.array([p[1] for p in positions], dtype=float)
            zs = np.array(values, dtype=float)

            data_r = float(np.sqrt(xs**2 + ys**2).max()) + 1.5
            n_boundary = 36
            angles = np.linspace(0, 2 * np.pi, n_boundary, endpoint=False)
            bx = data_r * np.cos(angles)
            by = data_r * np.sin(angles)
            from scipy.spatial import cKDTree
            tree = cKDTree(np.column_stack([xs, ys]))
            _, nearest_idx = tree.query(np.column_stack([bx, by]))
            bz = zs[nearest_idx]
            xs_ext = np.concatenate([xs, bx])
            ys_ext = np.concatenate([ys, by])
            zs_ext = np.concatenate([zs, bz])

            grid_res = 400
            pad = data_r * 1.05
            xi2, yi2 = np.meshgrid(
                np.linspace(-pad, pad, grid_res),
                np.linspace(-pad, pad, grid_res))
            zi = griddata((xs_ext, ys_ext), zs_ext, (xi2, yi2), method='cubic')
            zi[np.sqrt(xi2**2 + yi2**2) > data_r] = np.nan
            norm = Normalize(vmin=-vmax_global, vmax=vmax_global)
            ax.contourf(xi2, yi2, zi, levels=50, cmap='RdYlGn', norm=norm, extend='both')

            ax.scatter(xs, ys, c='none', s=20, zorder=5, edgecolors='#ccc', linewidths=0.6)

            outline_w = withStroke(linewidth=2.5, foreground='#1e1e2e')
            for i, (x, y) in enumerate(zip(xs, ys)):
                val = zs[i]
                txt_color = '#ff6b6b' if abs(val) > vmax_global * 0.65 else '#e0e0e0'
                ax.text(x, y + 0.5, f'{val:.2f}', ha='center', va='bottom', fontsize=5.5,
                        color=txt_color, zorder=6, path_effects=[outline_w])

            lim = data_r * 1.12
            ax.set_xlim(-lim, lim); ax.set_ylim(-lim, lim)
            ax.set_aspect('equal')
            ax.tick_params(labelsize=6, colors='#666', direction='in', length=3, width=0.5)
            for s in ax.spines.values():
                s.set_color('#363650'); s.set_linewidth(0.5)
            ax.set_xlabel(rl, fontsize=9, fontweight='bold', color='#89b4fa', labelpad=3)

        for idx in range(n, rows*cols):
            r, c = divmod(idx, cols)
            axes[r][c].set_visible(False)

        fig.suptitle(f'{self.axis} Offset — Repeat별 Contour Map', fontsize=14,
                     fontweight='bold', color='#cdd6f4')
        fig.tight_layout(rect=[0, 0, 1, 0.96])

        canvas = FigureCanvasQTAgg(fig)
        toolbar = NavigationToolbar2QT(canvas, self)
        layout.addWidget(toolbar)
        layout.addWidget(canvas)