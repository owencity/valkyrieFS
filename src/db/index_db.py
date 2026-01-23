"""
SQLite 데이터베이스 관리

이 모듈은 파일 인덱스를 SQLite 데이터베이스에 저장하고 조회합니다.
증분 업데이트를 위해 파일의 수정 시간도 추적합니다.

데이터베이스 스키마:
- file_index: 파일 메타데이터 저장
  - path (PRIMARY KEY): 파일 전체 경로
  - name: 파일명
  - extension: 파일 확장자
  - size: 파일 크기 (바이트)
  - modified_time: 마지막 수정 시간 (Unix timestamp)
  - indexed_at: 인덱싱된 시간 (Unix timestamp)
  - indexed_path: 인덱싱된 루트 경로 (선택적 인덱싱 추적용)
"""
import sqlite3
import threading
from pathlib import Path
from typing import List, Optional, Dict
from datetime import datetime

from src.models.file_entry import FileEntry


class IndexDatabase:
    """
    인덱스 데이터베이스 관리자
    
    SQLite를 사용하여 파일 인덱스를 영속화합니다.
    스레드 안전성을 보장하기 위해 연결당 하나의 스레드만 사용합니다.
    """
    
    def __init__(self, db_path: Optional[str] = None):
        """
        데이터베이스 초기화
        
        Args:
            db_path: 데이터베이스 파일 경로 (None이면 기본 위치 사용)
        """
        if db_path is None:
            # 기본 위치: 사용자 앱 데이터 디렉토리
            app_data = Path.home() / ".valkyrie"
            app_data.mkdir(exist_ok=True)
            db_path = str(app_data / "index.db")
        
        self.db_path = db_path
        self._local = threading.local()  # 스레드 로컬 저장소
        
        # 데이터베이스 초기화 (테이블 생성)
        self._initialize_database()
    
    def _get_connection(self) -> sqlite3.Connection:
        """
        스레드 로컬 데이터베이스 연결 반환
        
        각 스레드가 독립적인 연결을 사용하므로 스레드 안전성을 보장합니다.
        
        Returns:
            SQLite 데이터베이스 연결
        """
        if not hasattr(self._local, 'connection'):
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            conn.row_factory = sqlite3.Row  # 딕셔너리처럼 접근 가능
            
            # 성능 최적화: WAL 모드 및 동기화 설정
            # WAL 모드: 쓰기 성능 향상, 읽기와 쓰기 동시 접근 가능
            conn.execute('PRAGMA journal_mode=WAL')
            # 정상 동기화 모드 (안정성과 성능 균형)
            conn.execute('PRAGMA synchronous=NORMAL')
            # 페이지 크기 최적화 (더 큰 페이지 = 더 빠른 I/O)
            conn.execute('PRAGMA page_size=4096')
            # 캐시 크기 증가 (메모리 사용 증가하지만 성능 향상)
            conn.execute('PRAGMA cache_size=-64000')  # 64MB 캐시
            
            self._local.connection = conn
        return self._local.connection
    
    def _initialize_database(self) -> None:
        """
        데이터베이스 스키마 초기화
        
        테이블이 없으면 생성하고, 필요한 인덱스를 생성합니다.
        성능 최적화를 위한 PRAGMA 설정도 수행합니다.
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # 성능 최적화 PRAGMA 설정
        # WAL 모드: 읽기와 쓰기 병렬 처리 가능 (성능 대폭 향상)
        cursor.execute("PRAGMA journal_mode=WAL")
        
        # 동기화 설정: 성능 우선 (OS 크래시 시 일부 데이터 손실 가능성 있으나 인덱스이므로 허용)
        cursor.execute("PRAGMA synchronous=NORMAL")
        
        # 페이지 크기: 4KB → 64KB (대량 삽입 성능 향상)
        cursor.execute("PRAGMA page_size=65536")
        
        # 캐시 크기: 64MB (기본값보다 훨씬 큼)
        cursor.execute("PRAGMA cache_size=-16384")  # -16384 = 64MB (음수는 KB 단위)
        
        # 메모리 매핑 I/O: 더 빠른 읽기
        cursor.execute("PRAGMA mmap_size=268435456")  # 256MB
        
        # 파일 인덱스 테이블 생성
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS file_index (
                path TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                extension TEXT NOT NULL,
                size INTEGER NOT NULL,
                modified_time REAL NOT NULL,
                indexed_at REAL NOT NULL,
                indexed_path TEXT NOT NULL
            )
        """)
        
        # 검색 성능을 위한 인덱스 생성
        # 파일명 검색 최적화
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_name ON file_index(name)
        """)
        
        # 경로 검색 최적화
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_path ON file_index(path)
        """)
        
        # 증분 업데이트를 위한 인덱스
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_indexed_path ON file_index(indexed_path)
        """)
        
        # 통합 인덱스: 검색 성능 향상
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_name_ext ON file_index(name, extension)
        """)
        
        conn.commit()
    
    def save_entries(self, entries: List[FileEntry], indexed_path: str) -> int:
        """
        파일 엔트리들을 데이터베이스에 저장
        
        배치 삽입으로 성능을 최적화합니다.
        기존 엔트리는 업데이트됩니다.
        
        Args:
            entries: 저장할 파일 엔트리 목록
            indexed_path: 인덱싱된 루트 경로
            
        Returns:
            저장된 엔트리 개수
        """
        if not entries:
            return 0
        
        conn = self._get_connection()
        indexed_at = datetime.now().timestamp()
        
        # 배치 크기 증가 (대량 삽입 성능 향상)
        # Everything 수준 성능: 더 큰 배치로 DB 쓰기 속도 향상
        # 10,000개씩 배치 처리로 트랜잭션 오버헤드 최소화
        BATCH_SIZE = 10000
        
        # 데이터 준비
        data = [
            (
                entry.path,
                entry.name,
                entry.extension,
                entry.size,
                entry.modified_time.timestamp(),
                indexed_at,
                indexed_path
            )
            for entry in entries
        ]
        
        # 배치로 나누어 처리 (대량 데이터 처리 시 효율적)
        try:
            cursor = conn.cursor()
            
            # 트랜잭션 시작 (배치로 나누어 처리)
            for i in range(0, len(data), BATCH_SIZE):
                batch = data[i:i + BATCH_SIZE]
                cursor.executemany("""
                    INSERT OR REPLACE INTO file_index
                    (path, name, extension, size, modified_time, indexed_at, indexed_path)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, batch)
            
            # 한 번에 커밋 (트랜잭션 최적화)
            conn.commit()
            
        except Exception as e:
            conn.rollback()
            raise
        
        return len(entries)
    
    def load_all_entries(self) -> List[FileEntry]:
        """
        모든 파일 엔트리를 데이터베이스에서 로드
        
        애플리케이션 시작 시 메모리 인덱스를 복원하는 데 사용됩니다.
        
        Returns:
            로드된 파일 엔트리 목록
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM file_index")
        rows = cursor.fetchall()
        
        entries = []
        for row in rows:
            entry = FileEntry(
                name=row['name'],
                path=row['path'],
                extension=row['extension'],
                size=row['size'],
                modified_time=datetime.fromtimestamp(row['modified_time'])
            )
            entries.append(entry)
        
        return entries
    
    def get_indexed_paths(self) -> List[str]:
        """
        현재 인덱싱된 루트 경로 목록 반환
        
        선택적 인덱싱에서 어떤 경로가 인덱싱되었는지 추적합니다.
        
        Returns:
            인덱싱된 경로 목록
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT DISTINCT indexed_path FROM file_index")
        rows = cursor.fetchall()
        
        return [row['indexed_path'] for row in rows]
    
    def get_entries_by_path(self, indexed_path: str) -> List[FileEntry]:
        """
        특정 루트 경로에 속한 파일 엔트리들 반환
        
        증분 업데이트 시 기존 인덱스와 비교하는 데 사용됩니다.
        
        Args:
            indexed_path: 조회할 루트 경로
            
        Returns:
            해당 경로의 파일 엔트리 목록
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM file_index WHERE indexed_path = ?", (indexed_path,))
        rows = cursor.fetchall()
        
        entries = []
        for row in rows:
            entry = FileEntry(
                name=row['name'],
                path=row['path'],
                extension=row['extension'],
                size=row['size'],
                modified_time=datetime.fromtimestamp(row['modified_time'])
            )
            entries.append(entry)
        
        return entries
    
    def remove_entries_by_path(self, indexed_path: str) -> int:
        """
        특정 루트 경로의 모든 엔트리 삭제
        
        전체 재인덱싱 전에 기존 인덱스를 정리하는 데 사용됩니다.
        
        Args:
            indexed_path: 삭제할 루트 경로
            
        Returns:
            삭제된 엔트리 개수
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM file_index WHERE indexed_path = ?", (indexed_path,))
        deleted_count = cursor.rowcount
        conn.commit()
        
        return deleted_count
    
    def remove_entries_by_paths(self, paths: List[str]) -> int:
        """
        여러 파일 경로의 엔트리 삭제 (배치 처리)
        
        SQLite의 변수 제한(999개)을 회피하기 위해 배치로 나누어 삭제합니다.
        대량 파일 삭제 시 사용됩니다.
        
        Args:
            paths: 삭제할 파일 경로 목록
            
        Returns:
            삭제된 엔트리 개수
        """
        if not paths:
            return 0
        
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # SQLite 변수 제한(999개)을 고려하여 배치 크기 설정
        # 안전 마진을 두어 500개씩 처리
        BATCH_SIZE = 500
        total_deleted = 0
        
        # 배치로 나누어 삭제
        for i in range(0, len(paths), BATCH_SIZE):
            batch = paths[i:i + BATCH_SIZE]
            placeholders = ','.join('?' * len(batch))
            cursor.execute(
                f"DELETE FROM file_index WHERE path IN ({placeholders})",
                batch
            )
            total_deleted += cursor.rowcount
        
        conn.commit()
        return total_deleted
    
    def get_statistics(self) -> Dict[str, int]:
        """
        데이터베이스 통계 정보 반환
        
        디버깅 및 모니터링에 사용됩니다.
        
        Returns:
            통계 정보 딕셔너리
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) as total FROM file_index")
        total = cursor.fetchone()['total']
        
        cursor.execute("SELECT COUNT(DISTINCT indexed_path) as paths FROM file_index")
        paths = cursor.fetchone()['paths']
        
        return {
            'total_files': total,
            'indexed_paths': paths
        }
    
    def clear_all(self) -> None:
        """
        모든 인덱스 데이터 삭제
        
        전체 재인덱싱을 위한 초기화에 사용됩니다.
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM file_index")
        conn.commit()

