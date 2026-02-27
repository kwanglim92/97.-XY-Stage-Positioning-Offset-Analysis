"""
settings.py — 설정 저장/로드 (JSON)

사용자 설정을 앱 로컬 디렉토리에 JSON으로 저장
"""

import os
import json

# 설정 파일 경로 (src/ 폴더에 저장)
SETTINGS_DIR = os.path.dirname(os.path.abspath(__file__))
SETTINGS_FILE = os.path.join(SETTINGS_DIR, 'settings.json')

DEFAULT_SETTINGS = {
    'last_folder': '',
    'last_axis': 'both',
    'use_all_range': True,
    'last_range_start': '',
    'last_range_end': '',
    'outlier_method': 'iqr',
    'outlier_threshold': 1.5,
    'export_delimiter': '\t',
    'window_geometry': '',
    'recent_folders': [],  # 최근 5개 폴더 기록
    'spec_limits': {
        'Vision Pattern Recognize': {'X': {'lsl': -5000.0, 'usl': 5000.0}, 'Y': {'lsl': -5000.0, 'usl': 5000.0}},
        'In-Die Align': {'X': {'lsl': -5000.0, 'usl': 5000.0}, 'Y': {'lsl': -5000.0, 'usl': 5000.0}},
        'LLC Translation': {'X': {'lsl': -5000.0, 'usl': 5000.0}, 'Y': {'lsl': -5000.0, 'usl': 5000.0}},
        'Global Align': {'X': {'lsl': -5000.0, 'usl': 5000.0}, 'Y': {'lsl': -5000.0, 'usl': 5000.0}}
    },
    'spec_deviation': {
        'Vision Pattern Rec…': {'spec_range': 4.0, 'spec_stddev': 0.8},
        'In-Die Align':       {'spec_range': 4.0, 'spec_stddev': 0.8},
        'LLC Translation':    {'spec_range': 4.0, 'spec_stddev': 0.8},
        'Global Align':       {'spec_range': 7.5, 'spec_stddev': 2.2},
    },
    'standard_recipe_names': [
        'Vision Pattern',
        'In-Die Align',
        'LLC Translation',
        'Global Align',
    ],
}


# 매 실행 시 코드 기본값을 우선 사용하는 키 (코드 업데이트 시 자동 반영)
_ALWAYS_DEFAULT_KEYS = {'standard_recipe_names'}

# 매 실행 시 리셋되는 키 (세션 비유지)
_RESET_ON_START_KEYS = {'last_folder'}


def load_settings() -> dict:
    """설정 파일 로드 (3단계 병합)

    1. DEFAULT_SETTINGS 기본값으로 시작
    2. 저장된 settings.json에서 persistent 키만 병합
    3. _ALWAYS_DEFAULT_KEYS → 코드 기본값 강제
    4. _RESET_ON_START_KEYS → 기본값으로 리셋
    """
    settings = DEFAULT_SETTINGS.copy()

    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                saved = json.load(f)
            # persistent 키만 병합 (always-default, reset 키 제외)
            for k, v in saved.items():
                if k not in _ALWAYS_DEFAULT_KEYS and k not in _RESET_ON_START_KEYS:
                    settings[k] = v
        except (json.JSONDecodeError, IOError):
            pass

    return settings


def save_settings(settings: dict):
    """설정 파일 저장"""
    try:
        with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(settings, f, indent=2, ensure_ascii=False)
    except IOError:
        pass


def add_recent_folder(settings: dict, folder_path: str) -> dict:
    """최근 폴더 추가 (최대 5개, 중복 제거)"""
    recents = settings.get('recent_folders', [])
    # 이미 존재하면 제거 후 맨 앞에 추가
    if folder_path in recents:
        recents.remove(folder_path)
    recents.insert(0, folder_path)
    settings['recent_folders'] = recents[:5]
    return settings
