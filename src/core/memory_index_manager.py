"""
C++ 메모리 인덱스 관리자 (Python 래퍼)

Everything 수준의 성능을 위해 C++ 메모리 인덱스를 사용합니다.
SQLite를 완전히 제거하고 RAM 기반 인덱싱을 제공합니다.
"""
import sys
import os
from pathlib import Path
from typing import List, Optional, Callable
from datetime import datetime

# PyInstaller(onefile)에서도 네이티브 모듈을 찾을 수 있도록 경로 헬퍼 사용
from src.utils.runtime_paths import native_dir

# native 디렉토리를 Python 경로에 추가
# 현재 파일 위치: src/core/memory_index_manager.py
# 프로젝트 루트: src/core/../.. = 프로젝트 루트
# __file__ = src/core/memory_index_manager.py
# .parent = src/core/
# .parent.parent = src/
# .parent.parent.parent = 프로젝트 루트
_native_dir_abs = native_dir()

if _native_dir_abs.exists():
    native_path = str(_native_dir_abs)
    if native_path not in sys.path:
        sys.path.insert(0, native_path)

try:
    import memory_index_native
    NATIVE_AVAILABLE = True
except ImportError as e:
    NATIVE_AVAILABLE = False
    print(f"⚠ 메모리 인덱스 네이티브 모듈을 사용할 수 없습니다: {e}")
    print(f"  시도한 경로: {_native_dir_abs}")
    print(f"  경로 존재 여부: {_native_dir_abs.exists()}")
    if _native_dir_abs.exists():
        pyd_files = list(_native_dir_abs.glob("*.pyd"))
        print(f"  .pyd 파일: {[f.name for f in pyd_files]}")
    print("  native 디렉토리에서 'python setup.py build_ext --inplace'를 실행하세요.")


class MemoryIndexManager:
    """
    C++ 메모리 인덱스 관리자
    
    Everything 수준의 성능:
    - RAM 기반 인덱싱 (SQLite 제거)
    - 문자열 풀링 (경로 중복 제거)
    - Snapshot 방식 (메모리 매핑 파일)
    """
    
    def __init__(self, snapshot_path: Optional[str] = None):
        """
        메모리 인덱스 관리자 초기화
        
        Args:
            snapshot_path: Snapshot 파일 경로 (None이면 기본 위치 사용)
        """
        if not NATIVE_AVAILABLE:
            raise RuntimeError(
                "메모리 인덱스 네이티브 모듈이 필요합니다. "
                "native 디렉토리에서 'python setup.py build_ext --inplace'를 실행하세요."
            )
        
        self._index = memory_index_native.MemoryIndex()
        
        # Snapshot 파일 경로 설정
        if snapshot_path is None:
            app_data = Path.home() / ".valkyrie"
            app_data.mkdir(exist_ok=True)
            snapshot_path = str(app_data / "index.dat")
        
        self.snapshot_path = snapshot_path
        
        # 인덱스 빌드 여부
        self._is_built = False
    
    def load_snapshot(self) -> int:
        """
        Snapshot 파일에서 인덱스 로드
        
        Everything 방식: 메모리 매핑 파일로 빠른 로드
        
        Returns:
            로드된 파일 개수
        """
        snapshot_path_obj = Path(self.snapshot_path)
        if not snapshot_path_obj.exists():
            return 0
        
        try:
            if self._index.load_snapshot(self.snapshot_path):
                count = self._index.get_file_count()
                self._is_built = True
                return count
            else:
                return 0
        except Exception as e:
            print(f"⚠ Snapshot 로드 실패: {e}")
            return 0
    
    def add_files(self, file_list: List[dict]) -> None:
        """
        파일 목록을 인덱스에 추가
        
        Args:
            file_list: 파일 정보 딕셔너리 리스트
                각 딕셔너리는 다음 키를 포함:
                - path: 전체 경로
                - name: 파일명
                - extension: 확장자
                - size: 파일 크기
                - modified_time: 수정 시간 (Unix timestamp)
                - is_directory: 디렉토리 여부
        """
        for file_info in file_list:
            self._index.add_file(
                file_info.get('path', ''),
                file_info.get('name', ''),
                file_info.get('extension', ''),
                file_info.get('size', 0),
                file_info.get('modified_time', 0),
                file_info.get('is_directory', False)
            )
    
    def build(self) -> None:
        """
        인덱스 빌드 완료
        
        검색 최적화 구조(접두사 인덱스 등)를 생성합니다.
        파일 추가 후 반드시 호출해야 합니다.
        """
        self._index.build()
        self._is_built = True
    
    def search(self, query: str, max_results: Optional[int] = 1000) -> List[dict]:
        """
        인덱스에서 검색 수행
        
        Args:
            query: 검색 쿼리 문자열
            max_results: 최대 결과 수
            
        Returns:
            파일 정보 딕셔너리 리스트
        """
        if not self._is_built:
            self.build()
        
        # C++ 검색 수행
        result_indices = self._index.search(query, max_results or 1000)
        
        # 인덱스를 파일 정보로 변환
        results = []
        for idx in result_indices:
            file_info = self._index.get_file_info(idx)
            if file_info:
                results.append(file_info)
        
        return results
    
    def save_snapshot(self) -> bool:
        """
        현재 인덱스를 Snapshot 파일로 저장
        
        Everything 방식: 메모리 매핑 파일로 빠른 저장
        
        Returns:
            저장 성공 여부
        """
        try:
            return self._index.save_snapshot(self.snapshot_path)
        except Exception as e:
            print(f"⚠ Snapshot 저장 실패: {e}")
            return False
    
    def get_file_count(self) -> int:
        """인덱스된 파일 개수 반환"""
        return self._index.get_file_count()
    
    def get_memory_size(self) -> int:
        """메모리 사용량 반환 (바이트)"""
        return self._index.get_memory_size()
    
    def clear(self) -> None:
        """인덱스 초기화"""
        self._index.clear()
        self._is_built = False
    
    def get_statistics(self) -> dict:
        """
        인덱스 통계 정보 반환
        
        Returns:
            통계 정보 딕셔너리
        """
        file_count = self.get_file_count()
        memory_size = self.get_memory_size()
        
        return {
            'total_files': file_count,
            'memory_size_bytes': memory_size,
            'memory_size_mb': memory_size / (1024 * 1024),
            'snapshot_path': self.snapshot_path
        }

