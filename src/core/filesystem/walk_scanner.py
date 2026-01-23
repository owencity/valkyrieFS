"""
일반 파일 시스템 스캐너 (os.walk 기반)

이 모듈은 Python의 os.walk를 사용하여 파일 시스템을 스캔합니다.
현재는 이 방식만 구현되어 있지만, 나중에 USN Journal 스캐너로 교체 가능합니다.

성능:
- 중간 규모 폴더 (수만~수십만 파일)에 적합
- 멀티스레딩으로 I/O 병목 완화
- 전체 디스크 스캔에는 부적합
"""
import os
from pathlib import Path
from typing import List, Optional, Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import multiprocessing

from src.models.file_entry import FileEntry
from src.core.filesystem.scanner_interface import FileSystemScanner


class WalkScanner(FileSystemScanner):
    """
    os.walk 기반 파일 시스템 스캐너 (성능 최적화)
    
    Python 표준 라이브러리를 사용하여 파일 시스템을 재귀적으로 스캔합니다.
    멀티스레딩을 사용하여 I/O 병목을 완화합니다.
    
    성능 최적화:
    - CPU 코어 수에 따른 동적 스레드 수 결정
    - 배치 처리로 락 경합 감소
    - 불필요한 디렉토리 스킵
    
    설계 이유:
    - 크로스 플랫폼 가능
    - 구현 단순, 유지보수 용이
    - 전체 디렉토리 인덱싱에 충분한 성능
    """
    
    # Windows에서 스킵할 일반적인 디렉토리 (성능 최적화)
    # 시스템 폴더와 프로그램 폴더는 인덱싱할 필요 없음
    SKIP_DIRS = {
        'AppData', 'Local', 'Roaming', 'ProgramData',
        'System Volume Information', '$Recycle.Bin', 'Windows',
        'Program Files', 'Program Files (x86)', 'node_modules',
        '.git', '.svn', '__pycache__', '.pytest_cache', 'venv', 'env'
    }
    
    # 스킵할 파일 확장자 (임시 파일, 캐시 등)
    SKIP_EXTENSIONS = {
        '.tmp', '.temp', '.cache', '.log', '.bak', '.swp',
        '.lock', '.part', '.download'
    }
    
    def __init__(self, max_workers: Optional[int] = None):
        """
        스캐너 초기화
        
        Args:
            max_workers: 동시에 실행할 스레드 수 (None이면 CPU 코어 수 * 2)
        """
        if max_workers is None:
            # CPU 코어 수의 3배 (I/O 집약적 작업이므로)
            # 최소 8, 최대 32로 증가 (더 빠른 스캔)
            cpu_count = multiprocessing.cpu_count()
            max_workers = max(8, min(cpu_count * 3, 32))
        self.max_workers = max_workers
    
    def scan_directory(
        self,
        root_path: str,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> List[FileEntry]:
        """
        지정된 디렉토리를 재귀적으로 스캔
        
        Args:
            root_path: 스캔할 루트 디렉토리 경로
            progress_callback: 진행 상황 콜백 (현재 처리 수, 전체 파일 수)
            
        Returns:
            스캔된 파일 엔트리 목록
        """
        root = Path(root_path)
        if not root.exists():
            return []
        
        # 배치 처리로 락 경합 감소
        entries: List[FileEntry] = []
        entries_lock = threading.Lock()
        BATCH_SIZE = 500  # 배치 크기 증가 (락 경합 감소)
        
        def process_file(file_path: Path) -> Optional[FileEntry]:
            """
            단일 파일 처리 (최적화)
            
            ThreadPoolExecutor에서 병렬로 실행됩니다.
            불필요한 파일은 빠르게 스킵합니다.
            """
            try:
                # 확장자로 빠른 필터링 (스킵할 파일 즉시 제외)
                if file_path.suffix.lower() in self.SKIP_EXTENSIONS:
                    return None
                
                if file_path.is_file():
                    return FileEntry.from_path(file_path)
            except (OSError, PermissionError, FileNotFoundError):
                # 접근 권한 없는 파일이나 삭제된 파일은 무시
                pass
            return None
        
        def should_skip_dir(dir_name: str, parent_path: Path) -> bool:
            """
            디렉토리 스킵 여부 결정
            
            성능 최적화를 위해 불필요한 디렉토리는 스킵합니다.
            전체 드라이브 스캔 시에는 최소한만 스킵합니다.
            """
            # 전체 드라이브 루트 스캔인지 확인 (예: C:\)
            root_upper = str(root).upper().rstrip('\\')
            is_drive_root = (
                root_upper == root.drive.upper() or 
                root_upper == f"{root.drive.upper()}\\"
            )
            
            # 숨김 디렉토리 스킵
            if dir_name.startswith('.'):
                return True
            
            # 전체 드라이브 스캔 시: 최소한만 스킵
            if is_drive_root:
                # 전체 드라이브 스캔 시에는 매우 제한적으로만 스킵
                # System Volume Information, $Recycle.Bin만 스킵 (접근 불가)
                if dir_name in ['System Volume Information', '$Recycle.Bin']:
                    return True
                return False  # Windows, Program Files 등도 스캔
            
            # 일반 스캔: 기존 로직 유지
            # Windows 시스템 디렉토리 스킵
            if dir_name in self.SKIP_DIRS:
                return True
            
            # AppData 하위 특정 폴더만 스킵 (일부는 인덱싱 가능)
            if parent_path.name == 'AppData':
                if dir_name in ['Local', 'Roaming']:
                    # AppData/Local과 AppData/Roaming의 특정 하위 폴더만 스킵
                    return True
            
            return False
        
        # 모든 파일 경로 수집 (최적화된 필터링)
        all_files: List[Path] = []
        root_path_obj = Path(root)
        
        for root_dir, dirs, files in os.walk(root, followlinks=False):  # symlink 따라가지 않음
            # 필터링된 디렉토리 목록으로 교체 (in-place 수정으로 효율적)
            current_path = Path(root_dir)
            
            # 디렉토리 필터링 (리스트 컴프리헨션 최적화)
            dirs[:] = [
                d for d in dirs 
                if not should_skip_dir(d, current_path.parent if current_path.parent != current_path else root_path_obj)
            ]
            
            # 파일 경로 추가 (리스트 컴프리헨션으로 최적화)
            # 확장자로 빠른 사전 필터링
            all_files.extend(
                current_path / file 
                for file in files 
                if not file.lower().endswith(tuple(self.SKIP_EXTENSIONS))
            )
        
        total_files = len(all_files)
        processed_count = 0
        batch: List[FileEntry] = []
        
        # 멀티스레드로 파일 처리 (배치 처리)
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_file = {
                executor.submit(process_file, file_path): file_path
                for file_path in all_files
            }
            
            for future in as_completed(future_to_file):
                entry = future.result()
                if entry:
                    batch.append(entry)
                    
                    # 배치 크기에 도달하면 일괄 추가 (락 경합 감소)
                    if len(batch) >= BATCH_SIZE:
                        with entries_lock:
                            entries.extend(batch)
                        batch.clear()
                
                processed_count += 1
                if progress_callback:
                    progress_callback(processed_count, total_files)
            
            # 남은 배치 처리
            if batch:
                with entries_lock:
                    entries.extend(batch)
        
        return entries
    
    def get_scanner_name(self) -> str:
        """스캐너 이름 반환"""
        return "WalkScanner (os.walk based)"

