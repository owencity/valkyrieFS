"""
USN Journal 기반 파일 시스템 스캐너 (플레이스홀더)

이 모듈은 나중에 USN Journal을 사용하는 고성능 스캐너를 구현하기 위한
플레이스홀더입니다.

구현 시:
1. C/C++ 또는 C# DLL 생성 (USN Journal 읽기)
2. Python에서 ctypes 또는 C extension으로 호출
3. 이 클래스에 USN Journal 스캔 로직 구현

설계 이유:
- 확장 가능한 아키텍처로 나중에 고성능 스캔 방식 추가 가능
- 기존 코드 변경 없이 스캐너 교체 가능
"""
from typing import List, Optional, Callable

from src.models.file_entry import FileEntry
from src.core.filesystem.scanner_interface import FileSystemScanner


class USNJournalScanner(FileSystemScanner):
    """
    USN Journal 기반 파일 시스템 스캐너 (미구현)
    
    나중에 Windows USN Journal을 사용하여 고성능 스캔을 제공합니다.
    
    TODO:
    - Windows DeviceIoControl API 래퍼 구현
    - USN Journal 읽기 로직
    - Python 연동 (ctypes 또는 C extension)
    """
    
    def scan_directory(
        self,
        root_path: str,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> List[FileEntry]:
        """
        USN Journal을 사용한 스캔 (미구현)
        
        현재는 NotImplementedError를 발생시킵니다.
        실제 구현 시 네이티브 모듈을 호출합니다.
        """
        raise NotImplementedError(
            "USN Journal scanner is not yet implemented. "
            "This requires a native C/C++ or C# module."
        )
    
    def get_scanner_name(self) -> str:
        """스캐너 이름 반환"""
        return "USNJournalScanner (not implemented)"

