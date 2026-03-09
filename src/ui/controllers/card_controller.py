from core import compute_statistics, filter_by_method, compute_deviation_matrix, compute_cpk
from ui.theme import BG, BG2, BG3, FG, FG2, ACCENT, GREEN, RED, ORANGE, PURPLE


class CardMixin:
    def _update_cards(self, data, recipe):
        d_x = filter_by_method(data, 'X')
        d_y = filter_by_method(data, 'Y')
        s_x = compute_statistics(d_x)
        s_y = compute_statistics(d_y)
        dev_x = compute_deviation_matrix(data, 'X')
        dev_y = compute_deviation_matrix(data, 'Y')
        self._dev_x, self._dev_y = dev_x, dev_y

        spec = self.settings.get('spec_limits', {})
        short = recipe.get('short_name', '')
        sp = spec.get(short, {})
        if not sp:
            self.logger.warn(f"spec_limits에 '{short}' 키 없음 → Cpk 계산 불가")
            sp = {'X': {}, 'Y': {}}
        cpk_x = compute_cpk(s_x['mean'], s_x['stdev'],
                            sp.get('X', {}).get('lsl', -5000), sp.get('X', {}).get('usl', 5000))
        cpk_y = compute_cpk(s_y['mean'], s_y['stdev'],
                            sp.get('Y', {}).get('lsl', -5000), sp.get('Y', {}).get('usl', 5000))

        dev_spec = self.settings.get('spec_deviation', {})
        ds = dev_spec.get(short, {})
        if not ds:
            self.logger.warn(f"spec_deviation에 '{short}' 키 없음 → PASS/FAIL 판정 불가")
        spec_r = ds.get('spec_range')
        spec_s = ds.get('spec_stddev')

        def _pass(st, dev):
            if st['count'] == 0 or spec_r is None or spec_s is None:
                return None
            return dev['overall_range'] <= spec_r and dev['overall_stddev'] <= spec_s

        px = _pass(s_x, dev_x)
        py = _pass(s_y, dev_y)
        self.card_x.update_stats(s_x['mean'], dev_x['overall_range'],
                                 dev_x['overall_stddev'], cpk_x, px,
                                 spec_r=spec_r, spec_s=spec_s)
        self.card_y.update_stats(s_y['mean'], dev_y['overall_range'],
                                 dev_y['overall_stddev'], cpk_y, py,
                                 spec_r=spec_r, spec_s=spec_s)

        # Store pass state and refresh nav buttons (no recursion)
        idx = self.current_recipe_idx
        if px is not None and py is not None:
            overall = px and py
        else:
            overall = None
        self.step_pass_states[idx] = overall
        self._refresh_step_buttons()

    # ──────────────────────────────────────────────
    # Tables
    # ──────────────────────────────────────────────

