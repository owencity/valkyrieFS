"""
USN Journal 스캐너 (Rust 바인딩 기반 - 예제)

이 모듈은 나중에 Rust로 작성된 USN Journal 리더를
Python에서 호출하는 방법을 보여줍니다.

구현 방법:
1. Rust로 USN Journal 읽기 라이브러리 작성
2. PyO3를 사용하여 Python 바인딩 생성
3. 이 모듈에서 Rust 라이브러리 호출

참고 프로젝트:
- usnrs (https://github.com/airbus-cert/usnrs)
- pyusnjrnl

현재는 플레이스홀더입니다.
"""
from typing import List, Optional, Callable

from src.models.file_entry import FileEntry
from src.core.filesystem.scanner_interface import FileSystemScanner


class USNJournalScannerRust(FileSystemScanner):
    """
    Rust 기반 USN Journal 스캐너 (미구현)
    
    Rust로 작성된 고성능 USN Journal 리더를
    Python에서 호출합니다.
    
    장점:
    - 네이티브 성능 (C/C++ 수준)
    - 메모리 안전성 (Rust의 장점)
    - Python 바인딩 용이 (PyO3)
    
    구현 계획:
    1. Rust 프로젝트 생성
    2. USN Journal 읽기 로직 구현
    3. PyO3로 Python 바인딩
    4. Python 패키지로 빌드
    """
    
    def scan_directory(
        self,
        root_path: str,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> List[FileEntry]:
        """
        Rust USN Journal 스캐너로 스캔 (미구현)
        """
        raise NotImplementedError(
            "Rust-based USN Journal scanner is not yet implemented. "
            "This requires:\n"
            "1. Rust project with USN Journal reading logic\n"
            "2. PyO3 bindings for Python\n"
            "3. Building as Python package\n\n"
            "For now, use WalkScanner or implement ctypes-based version."
        )
    
    def get_scanner_name(self) -> str:
        """스캐너 이름 반환"""
        return "USNJournalScanner (Rust-based, not implemented)"

