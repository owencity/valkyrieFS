"""
인덱스 관리 레이어 (Everything 수준 성능)

이 모듈은 파일 인덱싱의 전체 생명주기를 관리합니다:
1. 시작 시 Snapshot에서 인덱스 로드 (메모리 매핑 파일)
2. 선택적 폴더 스캔
3. 증분 업데이트
4. Snapshot에 인덱스 저장 (메모리 매핑 파일)

Everything 방식:
- SQLite 완전 제거
- C++ 메모리 인덱스 사용 (RAM 기반)
- 문자열 풀링으로 메모리 최적화
- Snapshot 방식으로 빠른 저장/로드

설계 이유:
- UI와 파일 시스템 세부사항 분리
- 인덱싱 전략 변경 시 UI 코드 수정 불필요
- 비동기 인덱싱으로 UI 블로킹 방지
"""
import threading
from pathlib import Path
from typing import List, Optional, Callable, Set, Dict, Any
from datetime import datetime

from src.models.file_entry import FileEntry
from src.core.memory_index_manager import MemoryIndexManager
from src.core.filesystem.scanner_interface import FileSystemScanner
from src.core.filesystem.walk_scanner import WalkScanner


class IndexManager:
    """
    인덱스 관리자
    
    파일 인덱스의 생성, 업데이트, 영속화를 관리합니다.
    UI 스레드와 분리되어 비동기로 동작합니다.
    """
    
    # 기본 인덱싱 폴더 목록
    # 선택적 인덱싱 전략: 일반적인 사용자 폴더만 인덱싱
    DEFAULT_INDEX_PATHS = [
        "Documents",
        "Desktop",
        "Downloads",
        "Pictures",
        "Videos",
        "Music"
    ]
    
    def __init__(self, snapshot_path: Optional[str] = None, prefer_fast_scanner: bool = True):
        """
        인덱스 관리자 초기화 (Everything 방식)
        
        Args:
            snapshot_path: Snapshot 파일 경로 (None이면 기본 위치 사용)
            prefer_fast_scanner: True이면 고성능 스캐너(USN Journal) 자동 감지 시도
        """
        # C++ 메모리 인덱스 사용 (SQLite 제거)
        self.memory_index = MemoryIndexManager(snapshot_path)
        
        # Python 쪽에 전체 인덱스를 복제하면(100만~200만) 메모리/속도 모두 손해라서
        # 검색은 C++ 메모리 인덱스에서만 수행하고, UI에 필요한 결과만 FileEntry로 변환합니다.
        
        # 스캐너 설정 (나중에 교체 가능)
        if prefer_fast_scanner:
            # 고성능 스캐너 자동 감지 및 사용
            self._scanner = self._create_best_available_scanner()
        else:
            # 기본 스캐너 사용
            self._scanner: FileSystemScanner = WalkScanner(max_workers=None)
        
        # 진행 중인 작업 추적
        self._is_indexing = False
        self._indexing_lock = threading.Lock()
    
    def _create_best_available_scanner(self) -> FileSystemScanner:
        """
        사용 가능한 가장 빠른 스캐너 생성
        
        우선순위:
        1. 네이티브 USN Journal 스캐너 (C/C++ 모듈)
        2. ctypes 기반 USN Journal 스캐너
        3. WalkScanner (기본)
        
        Returns:
            사용 가능한 가장 빠른 스캐너 인스턴스
        """
        # 1. 네이티브 모듈 시도 (최고 성능)
        try:
            from src.core.filesystem.usn_scanner_native import USNJournalScannerNative
            scanner = USNJournalScannerNative()
            print("=" * 60)
            print("✓ 네이티브 USN Journal 스캐너 활성화 (최고 성능)")
            print(f"  스캐너: {scanner.get_scanner_name()}")
            print("=" * 60)
            return scanner
        except ImportError as e:
            print(f"⚠ 네이티브 모듈 로드 실패: {e}")
        except Exception as e:
            print(f"⚠ 네이티브 스캐너 생성 실패: {e}")
        
        # 2. ctypes 기반 USN Journal 스캐너 시도 (중간 성능)
        try:
            from src.core.filesystem.usn_scanner_ctypes import USNJournalScanner
            scanner = USNJournalScanner()
            print("=" * 60)
            print("✓ ctypes 기반 USN Journal 스캐너 활성화 (중간 성능)")
            print(f"  스캐너: {scanner.get_scanner_name()}")
            print("=" * 60)
            return scanner
        except Exception as e:
            print(f"⚠ ctypes 스캐너 생성 실패: {e}")
        
        # 3. 모든 스캐너 실패 시 오류 발생
        # Everything 방식: MFT/USN Journal만 사용 (WalkScanner 폴백 없음)
        raise RuntimeError(
            "USN Journal/MFT 스캐너를 사용할 수 없습니다. "
            "관리자 권한으로 실행하거나 네이티브 모듈을 빌드하세요."
        )
    
    @property
    def index(self) -> List[FileEntry]:
        """
        (레거시) 현재 메모리 인덱스 반환
        
        주의: Everything 방식으로 전환 후에는 전체 인덱스를 Python으로 복제하지 않습니다.
        
        Returns:
            빈 리스트 (호환성 유지용)
        """
        return []
    
    @property
    def is_indexing(self) -> bool:
        """인덱싱 작업 진행 중 여부"""
        with self._indexing_lock:
            return self._is_indexing
    
    def load_index_from_db(self) -> int:
        """
        Snapshot에서 인덱스 로드 (Everything 방식)
        
        애플리케이션 시작 시 호출되어 이전에 인덱싱된 파일들을
        메모리로 복원합니다. 빠른 시작을 위해 필수적입니다.
        
        Returns:
            로드된 파일 개수
        """
        return self.memory_index.load_snapshot()

    def search(self, query: str, max_results: int = 300) -> List[FileEntry]:
        """
        C++ 메모리 인덱스에서 검색하고, UI에 필요한 만큼만 FileEntry로 변환합니다.
        """
        results: List[FileEntry] = []
        file_dicts = self.memory_index.search(query, max_results=max_results)
        for d in file_dicts:
            try:
                ts = int(d.get("modified_time", 0) or 0)
                if ts <= 0:
                    modified = datetime.fromtimestamp(0)
                else:
                    modified = datetime.fromtimestamp(ts)
                results.append(
                    FileEntry(
                        name=d.get("name", "") or "",
                        path=d.get("path", "") or "",
                        extension=d.get("extension", "") or "",
                        size=int(d.get("size", 0) or 0),
                        modified_time=modified,
                    )
                )
            except Exception:
                continue
        return results
    
    def get_default_index_paths(self) -> List[Path]:
        """
        기본 인덱싱 경로 목록 반환
        
        사용자 홈 디렉토리의 일반적인 폴더들을 반환합니다.
        선택적 인덱싱 전략의 핵심입니다.
        
        Returns:
            인덱싱할 경로 목록
        """
        home = Path.home()
        paths = []
        
        for folder_name in self.DEFAULT_INDEX_PATHS:
            folder_path = home / folder_name
            if folder_path.exists() and folder_path.is_dir():
                paths.append(folder_path)
        
        return paths
    
    def scan_directory(
        self,
        root_path: str,
        force_reindex: bool = False,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> int:
        """
        디렉토리 스캔 및 인덱스 업데이트
        
        증분 업데이트를 수행합니다:
        1. 기존 인덱스와 비교
        2. 변경된 파일만 업데이트
        3. 삭제된 파일 제거
        
        Args:
            root_path: 스캔할 루트 디렉토리 경로
            force_reindex: True이면 전체 재인덱싱 (기존 인덱스 무시)
            progress_callback: 진행 상황 콜백
            
        Returns:
            인덱싱된 파일 개수
        """
        with self._indexing_lock:
            if self._is_indexing:
                raise RuntimeError("Indexing is already in progress")
            self._is_indexing = True
        
        try:
            root_path_obj = Path(root_path).resolve()
            root_path_str = str(root_path_obj)
            
            # 현재 단계에서는 C++ 인덱스에서 "삭제/갱신"을 완전하게 지원하지 않으므로
            # 스캔을 수행하는 경우에는 항상 "리빌드"로 일관되게 처리합니다.
            # (USN 모니터링 단계에서 진짜 증분 업데이트로 전환)
            
            # 파일 시스템 스캔
            print(f"\n[스캔 시작] 경로: {root_path_str}")
            print(f"[스캐너] {self._scanner.get_scanner_name()}")
            
            # 스캔 진행 상황 콜백 래퍼 (UI 업데이트용)
            def scan_progress_wrapper(current: int, total: int) -> None:
                if progress_callback:
                    progress_callback(current, total)
            
            scanned_items = self._scanner.scan_directory(
                root_path_str,
                progress_callback=scan_progress_wrapper
            )
            print(f"[스캔 완료] {len(scanned_items):,}개 파일 발견")
            
            # Everything 수준 성능: 증분 업데이트 계산 최적화
            # UI 반응성을 위해 진행 상황 표시
            if progress_callback:
                progress_callback(len(scanned_items), len(scanned_items) + 1000)
            
            print("[인덱스 업데이트] (현재 단계: 리빌드 방식)")
            print(f"[메모리 인덱스] 리빌드 중... (항목: {len(scanned_items):,}개)")
            
            # 리빌드: 항상 clear 후 전체 추가 → 중복 누적 방지(200만 문제 해결)
            self.memory_index.clear()
            self.memory_index.add_files(scanned_items)  # 스캐너가 dict 리스트를 반환
            self.memory_index.build()
            self.memory_index.save_snapshot()
            
            print(
                f"[인덱싱 완료] (총 {self.memory_index.get_file_count():,}개 항목, "
                f"메모리: {self.memory_index.get_memory_size() / (1024*1024):.1f}MB)\n"
            )
            
            return len(scanned_items)
            
        finally:
            with self._indexing_lock:
                self._is_indexing = False
    
    def _refresh_memory_index(self) -> None:
        """
        Python 인덱스를 C++ 메모리 인덱스와 동기화
        
        Everything 방식: C++ 인덱스가 소스이므로 Python 리스트만 업데이트
        """
        # 전체 인덱스는 Python으로 복제하지 않습니다.
        return
    
    def scan_default_paths(
        self,
        progress_callback: Optional[Callable[[str, int, int], None]] = None
    ) -> Dict[str, int]:
        """
        기본 경로들 스캔
        
        Documents, Desktop 등 일반적인 사용자 폴더를 스캔합니다.
        선택적 인덱싱 전략의 핵심입니다.
        
        Args:
            progress_callback: 진행 상황 콜백 (경로, 현재, 전체)
            
        Returns:
            경로별 인덱싱된 파일 개수 딕셔너리
        """
        default_paths = self.get_default_index_paths()
        results = {}
        
        for path in default_paths:
            path_str = str(path)
            
            def wrapped_callback(current: int, total: int) -> None:
                if progress_callback:
                    progress_callback(path_str, current, total)
            
            count = self.scan_directory(path_str, progress_callback=wrapped_callback)
            results[path_str] = count
        
        return results
    
    def scan_entire_home_directory(
        self,
        progress_callback: Optional[Callable[[str, int, int], None]] = None
    ) -> int:
        """
        전체 홈 디렉토리 스캔
        
        USN Journal 스캐너를 사용하는 경우, 전체 드라이브를 스캔합니다.
        일반 스캐너를 사용하는 경우, 사용자 홈 디렉토리 전체를 인덱싱합니다.
        
        Args:
            progress_callback: 진행 상황 콜백 (경로, 현재, 전체)
            
        Returns:
            인덱싱된 파일 개수
        """
        # USN Journal 스캐너를 사용하는 경우, 전체 드라이브 스캔
        scanner_name = self._scanner.get_scanner_name()
        if "USN Journal" in scanner_name or "USNJournal" in scanner_name:
            # 전체 드라이브 스캔 (예: C:\)
            home_dir = Path.home()
            drive_root = f"{home_dir.drive}\\"
            
            def wrapped_callback(current: int, total: int) -> None:
                if progress_callback:
                    progress_callback(drive_root, current, total)
            
            count = self.scan_directory(drive_root, progress_callback=wrapped_callback)
            return count
        else:
            # 일반 스캐너: 홈 디렉토리만 스캔
            home_dir = Path.home()
            home_str = str(home_dir)
            
            def wrapped_callback(current: int, total: int) -> None:
                if progress_callback:
                    progress_callback(home_str, current, total)
            
            count = self.scan_directory(home_str, progress_callback=wrapped_callback)
            return count
    
    def clear_all(self) -> None:
        """모든 인덱스 삭제 (Everything 방식)"""
        self.memory_index.clear()
        return
    
    def get_statistics(self) -> dict:
        """
        인덱스 통계 정보 반환 (Everything 방식)
        
        Returns:
            통계 정보 딕셔너리
        """
        stats = self.memory_index.get_statistics()
        return {
            'total_files': stats['total_files'],
            'memory_size_bytes': stats['memory_size_bytes'],
            'memory_size_mb': stats['memory_size_mb'],
            'snapshot_path': stats['snapshot_path'],
        }
    
    def set_scanner(self, scanner: FileSystemScanner) -> None:
        """
        파일 시스템 스캐너 설정
        
        나중에 USN Journal 스캐너로 교체할 수 있습니다.
        
        Args:
            scanner: 사용할 스캐너 인스턴스
        """
        self._scanner = scanner

