"""pytest 공통 설정 — src/ 를 import 경로에 추가 (앱은 main.py에서 동일하게 처리)."""
import os
import sys

_SRC = os.path.abspath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src')
)
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)
