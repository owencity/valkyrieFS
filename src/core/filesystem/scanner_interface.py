"""
파일 시스템 스캐너 인터페이스

이 추상 기본 클래스는 파일 시스템 스캔 방식을 정의합니다.
다양한 구현체(일반 스캔, USN Journal 등)가 이 인터페이스를 구현합니다.
"""
from abc import ABC, abstractmethod
from typing import List, Callable, Optional
from pathlib import Path

from src.models.file_entry import FileEntry


class FileSystemScanner(ABC):
    """
    파일 시스템 스캐너 추상 인터페이스
    
    이 인터페이스를 구현하는 클래스는 다양한 방식으로
    파일 시스템을 스캔할 수 있습니다.
    
    설계 이유:
    - 전략 패턴을 사용하여 스캔 방식 교체 가능
    - UI와 검색 로직이 스캔 구현에 의존하지 않음
    - 나중에 USN Journal 같은 고성능 구현 추가 용이
    """
    
    @abstractmethod
    def scan_directory(
        self,
        root_path: str,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> List[FileEntry]:
        """
        지정된 디렉토리를 스캔하여 파일 엔트리 목록 반환
        
        Args:
            root_path: 스캔할 루트 디렉토리 경로
            progress_callback: 진행 상황 콜백 함수 (현재, 전체) -> None
            
        Returns:
            스캔된 파일 엔트리 목록
        """
        pass
    
    @abstractmethod
    def get_scanner_name(self) -> str:
        """
        스캐너 이름 반환
        
        로깅 및 디버깅에 사용됩니다.
        
        Returns:
            스캐너 이름 문자열
        """
        pass

