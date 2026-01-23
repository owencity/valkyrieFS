"""
파일 메타데이터를 저장하는 데이터 클래스

이 모델은 인덱싱된 파일의 기본 정보를 담고 있습니다.
인덱서가 스캔한 파일 정보를 저장하고, 검색 결과로 반환됩니다.
"""
from dataclasses import dataclass
from pathlib import Path
from datetime import datetime


@dataclass
class FileEntry:
    """
    단일 파일의 메타데이터를 나타내는 클래스
    
    Attributes:
        name: 파일명 (예: "example.txt")
        path: 전체 경로 (예: "C:\\Users\\user\\Documents\\example.txt")
        extension: 파일 확장자 (예: ".txt")
        size: 파일 크기 (바이트)
        modified_time: 마지막 수정 시간
    """
    name: str
    path: str
    extension: str
    size: int
    modified_time: datetime
    
    @classmethod
    def from_path(cls, file_path: Path) -> "FileEntry":
        """
        Path 객체로부터 FileEntry 인스턴스를 생성
        
        이 메서드는 파일 시스템의 Path 객체를 받아서
        필요한 메타데이터를 추출하여 FileEntry 객체로 변환합니다.
        
        Args:
            file_path: 파일 경로를 나타내는 Path 객체
            
        Returns:
            파일 메타데이터를 담은 FileEntry 인스턴스
        """
        try:
            stat = file_path.stat()
            return cls(
                name=file_path.name,
                path=str(file_path.resolve()),
                extension=file_path.suffix.lower(),
                size=stat.st_size,
                modified_time=datetime.fromtimestamp(stat.st_mtime)
            )
        except (OSError, PermissionError):
            # 접근 권한이 없거나 파일이 삭제된 경우 예외 발생 가능
            raise

