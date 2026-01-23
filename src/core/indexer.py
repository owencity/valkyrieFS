"""
파일 시스템 인덱싱 로직

이 모듈은 지정된 디렉토리를 재귀적으로 스캔하여
모든 파일의 메타데이터를 수집하고 메모리에 저장합니다.

인덱싱은 첫 실행 시에만 수행되며, 이후 검색 시에는
이 인덱스를 사용하여 빠른 검색을 제공합니다.
"""
import os
from pathlib import Path
from typing import List, Set
from concurrent.futures import ThreadPoolExecutor
import threading

from src.models.file_entry import FileEntry


class Indexer:
    """
    파일 시스템 인덱서
    
    지정된 디렉토리를 스캔하여 파일 메타데이터를 수집하고
    메모리 내 인덱스로 유지합니다.
    """
    
    def __init__(self):
        """
        인덱서 초기화
        
        인덱스는 리스트 형태로 파일 엔트리를 저장합니다.
        동시성 제어를 위해 threading.Lock을 사용합니다.
        """
        self._index: List[FileEntry] = []
        self._lock = threading.Lock()
        self._is_indexing = False
    
    @property
    def index(self) -> List[FileEntry]:
        """
        현재 인덱스의 읽기 전용 복사본 반환
        
        Returns:
            인덱싱된 모든 파일 엔트리의 리스트
        """
        with self._lock:
            return self._index.copy()
    
    @property
    def is_indexing(self) -> bool:
        """
        현재 인덱싱 작업이 진행 중인지 확인
        
        Returns:
            인덱싱 중이면 True, 아니면 False
        """
        return self._is_indexing
    
    def scan_directory(self, root_path: str, max_workers: int = 4) -> int:
        """
        지정된 디렉토리를 재귀적으로 스캔하여 파일 메타데이터를 수집
        
        Windows NTFS 파일 시스템에서 효율적으로 작동하도록 설계되었습니다.
        멀티스레딩을 사용하여 I/O 병목을 완화합니다.
        
        Args:
            root_path: 스캔할 루트 디렉토리 경로
            max_workers: 동시에 실행할 스레드 수
            
        Returns:
            인덱싱된 파일의 개수
        """
        self._is_indexing = True
        root = Path(root_path)
        new_index: List[FileEntry] = []
        index_lock = threading.Lock()
        
        def process_file(file_path: Path) -> None:
            """
            단일 파일을 처리하여 인덱스에 추가
            
            이 함수는 ThreadPoolExecutor에 의해 병렬로 실행됩니다.
            각 스레드가 독립적으로 파일을 처리하고,
            최종 결과를 스레드 안전하게 병합합니다.
            """
            try:
                if file_path.is_file():
                    entry = FileEntry.from_path(file_path)
                    with index_lock:
                        new_index.append(entry)
            except (OSError, PermissionError):
                # 접근할 수 없는 파일은 무시 (권한 없는 시스템 파일 등)
                pass
        
        try:
            # 모든 파일 경로를 수집
            all_files: List[Path] = []
            for root_dir, dirs, files in os.walk(root):
                # 숨김 디렉토리 스킵 (성능 최적화)
                dirs[:] = [d for d in dirs if not d.startswith('.')]
                
                for file in files:
                    all_files.append(Path(root_dir) / file)
            
            # 멀티스레드로 파일 처리
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                executor.map(process_file, all_files)
            
            # 인덱스 업데이트 (원자적 연산)
            with self._lock:
                self._index = new_index
            
            return len(self._index)
            
        finally:
            self._is_indexing = False
    
    def get_index_size(self) -> int:
        """
        현재 인덱스에 저장된 파일 개수 반환
        
        Returns:
            인덱싱된 파일의 개수
        """
        with self._lock:
            return len(self._index)

