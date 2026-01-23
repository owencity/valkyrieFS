"""
파일 시스템 스캐너 모듈

다양한 방식의 파일 시스템 스캐너를 제공합니다:
- WalkScanner: os.walk 기반 (기본, 안정적)
- USNJournalScanner: ctypes 기반 USN Journal (중간 성능)
- USNJournalScannerNative: C/C++ 네이티브 모듈 (최고 성능)
"""

from src.core.filesystem.scanner_interface import FileSystemScanner
from src.core.filesystem.walk_scanner import WalkScanner

# 선택적 import (사용 가능한 경우에만)
try:
    from src.core.filesystem.usn_scanner_ctypes import USNJournalScanner
    __all__ = ['FileSystemScanner', 'WalkScanner', 'USNJournalScanner']
except ImportError:
    __all__ = ['FileSystemScanner', 'WalkScanner']

try:
    from src.core.filesystem.usn_scanner_native import USNJournalScannerNative
    __all__.append('USNJournalScannerNative')
except ImportError:
    pass
