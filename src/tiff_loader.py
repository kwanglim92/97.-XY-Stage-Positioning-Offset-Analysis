"""
tiff_loader.py — PSPylib TIFF 파일 로더

PSPylib_TIFF_가이드.md 패턴 기반
"""

import os
import numpy as np

try:
    import pspylib.tiff.reader as tiffReader
    HAS_PSPYLIB = True
except ImportError:
    HAS_PSPYLIB = False


def _decode_ascii(field_value):
    """uint16/int16 배열을 문자열로 변환"""
    if isinstance(field_value, list):
        return ''.join(chr(c) for c in field_value if c != 0)
    return str(field_value)


def _header_val(sh, key):
    """Header에서 값 추출 (안전)"""
    entry = sh.get(key)
    if entry is None:
        return None
    return entry[0]


def load_tiff(path: str) -> dict:
    """TIFF 로드 → 메타데이터 + 2D 데이터 dict 반환

    Returns:
        {
            'path': ..., 'filename': ...,
            'info': {channel_name, head_mode, width, height, ...},
            'data_2d': np.ndarray (height, width),
            'statistics': {min, max, mean, std, range},
        }
    """
    if not HAS_PSPYLIB:
        raise ImportError("PSPylib가 설치되지 않았습니다. "
                          "pip install pspylib-0.1.2-py3-none-any.whl")

    reader = tiffReader.TiffReader()
    reader.load(path)

    sh = reader.data.scanHeader.scanHeader
    zdata = reader.data.scanData.ZData
    w = _header_val(sh, 'width')
    h = _header_val(sh, 'height')

    # 2D reshape
    data_2d = zdata.reshape(h, w) if (w and h and w * h == len(zdata)) else zdata

    info = get_tiff_info(reader)

    # 통계
    stats = {
        'min': float(np.min(data_2d)),
        'max': float(np.max(data_2d)),
        'mean': float(np.mean(data_2d)),
        'std': float(np.std(data_2d)),
        'range': float(np.max(data_2d) - np.min(data_2d)),
    }

    return {
        'path': path,
        'filename': os.path.basename(path),
        'info': info,
        'data_2d': data_2d,
        'statistics': stats,
    }


def get_tiff_info(reader) -> dict:
    """메타데이터를 정리된 dict로 반환"""
    sh = reader.data.scanHeader.scanHeader

    def _ascii(key):
        val = _header_val(sh, key)
        if val is None:
            return ''
        if isinstance(val, list):
            return ''.join(chr(c) for c in val if c != 0)
        return str(val)

    categories = {0: '2D Image', 1: 'Line Profile', 2: 'Spectroscopy'}
    data_types = {0: 'int16', 1: 'int32', 2: 'float32'}

    return {
        'category': categories.get(_header_val(sh, 'dataCategory'), 'Unknown'),
        'channel_name': _ascii('channelName'),
        'head_mode': _ascii('headMode'),
        'width': _header_val(sh, 'width'),
        'height': _header_val(sh, 'height'),
        'scan_size_width': _header_val(sh, 'scanSizeWidth'),
        'scan_size_height': _header_val(sh, 'scanSizeHeight'),
        'scan_offset_x': _header_val(sh, 'scanOffsetX'),
        'scan_offset_y': _header_val(sh, 'scanOffsetY'),
        'scan_rate': _header_val(sh, 'scanRate'),
        'z_unit': _ascii('unit'),
        'data_gain': _header_val(sh, 'dataGain'),
        'z_scale': _header_val(sh, 'ZScale'),
        'z_offset': _header_val(sh, 'ZOffset'),
        'data_type': data_types.get(_header_val(sh, 'dataType'), 'unknown'),
        'setpoint': _header_val(sh, 'setpoint'),
        'setpoint_unit': _ascii('setpointUnit'),
        'tip_bias': _header_val(sh, 'tipBias'),
        'sample_bias': _header_val(sh, 'sampleBias'),
        'cantilever_name': _ascii('cantileverName'),
        'stage_x': _header_val(sh, 'stageX'),
        'stage_y': _header_val(sh, 'stageY'),
    }


def get_tiff_summary(path: str) -> dict:
    """빠른 메타데이터 요약 (로드 + 기본 통계)"""
    result = load_tiff(path)
    return {
        'filename': result['filename'],
        'channel': result['info']['channel_name'],
        'mode': result['info']['head_mode'],
        'resolution': f"{result['info']['width']}x{result['info']['height']}",
        'unit': result['info']['z_unit'],
        **result['statistics'],
    }


def load_lot_tiffs(lot_path: str, progress_cb=None) -> list:
    """Lot 폴더의 모든 TIFF 일괄 로드

    Args:
        lot_path: Lot 폴더 경로
        progress_cb: callback(current, total, filename)

    Returns:
        [{tiff_data}, ...]
    """
    tiff_files = sorted([
        f for f in os.listdir(lot_path)
        if f.lower().endswith(('.tiff', '.tif'))
    ])

    results = []
    for i, fname in enumerate(tiff_files):
        if progress_cb:
            progress_cb(i + 1, len(tiff_files), fname)
        try:
            result = load_tiff(os.path.join(lot_path, fname))
            results.append(result)
        except Exception as e:
            results.append({
                'filename': fname,
                'error': str(e),
            })

    return results


def find_tiff_files(directory: str) -> list:
    """폴더 내 TIFF 파일 검색 (재귀)"""
    tiff_files = []
    for root, dirs, files in os.walk(directory):
        for fname in sorted(files):
            if fname.lower().endswith(('.tiff', '.tif')):
                tiff_files.append(os.path.join(root, fname))
    return tiff_files
