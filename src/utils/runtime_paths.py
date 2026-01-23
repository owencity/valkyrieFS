"""
런타임 경로 유틸

PyInstaller(onefile/onedir)로 패키징하면 리소스/네이티브 모듈 경로가
개발 환경(소스 실행)과 달라집니다.

이 모듈은 "소스 실행"과 "frozen 실행"을 모두 지원하는 경로 헬퍼를 제공합니다.
"""

from __future__ import annotations

import sys
from pathlib import Path


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False)) and hasattr(sys, "_MEIPASS")


def base_dir() -> Path:
    """
    - 소스 실행: 프로젝트 루트
    - PyInstaller: sys._MEIPASS (압축 해제된 임시 디렉토리)
    """
    if is_frozen():
        return Path(getattr(sys, "_MEIPASS")).resolve()
    # src/utils/runtime_paths.py -> src/utils -> src -> 프로젝트 루트
    return Path(__file__).resolve().parents[2]


def resource_path(relative_from_src: str) -> Path:
    """
    src/ 기준 상대 경로를 받아 실제 파일 경로로 변환합니다.

    예: resource_path("ui/assets/valkyriefs-wing.svg")
    """
    return (base_dir() / "src" / relative_from_src).resolve()


def native_dir() -> Path:
    """
    네이티브 .pyd를 찾을 디렉토리.
    PyInstaller 번들에는 `native/`로 포함시키는 것을 전제로 합니다.
    """
    if is_frozen():
        return (base_dir() / "native").resolve()
    return (base_dir() / "native").resolve()


