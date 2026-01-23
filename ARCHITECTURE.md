# Valkyrie 아키텍처 문서

## 개요

Valkyrie는 Everything과 유사한 고성능 Windows 파일 검색 애플리케이션입니다. Python과 PySide6로 구현되었으며, USN Journal을 활용하여 초고속 파일 인덱싱을 제공합니다.

## 기술 스택

### 프론트엔드
- **PySide6** (Qt 6): 크로스 플랫폼 GUI 프레임워크
  - 버전: >= 6.6.0
  - 용도: 메인 UI 창, 검색 입력, 결과 리스트
  
### 백엔드
- **Python 3.8+**: 메인 언어
  - 멀티스레딩: `ThreadPoolExecutor` (I/O 병목 완화)
  - 비동기 처리: `QThread` (UI 블로킹 방지)

### 데이터베이스
- **SQLite3**: 인덱스 영속성
  - WAL 모드 (Write-Ahead Logging)
  - 메모리 매핑 I/O (256MB)
  - 배치 삽입 (5000개 단위)

### 파일 시스템 접근
- **WalkScanner**: Python `os.walk` 기반 (기본, 안정적)
- **USNJournalScanner (ctypes)**: Python ctypes로 Windows USN Journal 읽기 (중간 성능)
- **USNJournalScannerNative**: C/C++ 네이티브 모듈 (최고 성능)

## 프로젝트 구조

```
valkyrie/
├── src/                          # 소스 코드
│   ├── __init__.py
│   ├── main.py                   # 애플리케이션 진입점
│   │
│   ├── models/                   # 데이터 모델
│   │   ├── __init__.py
│   │   └── file_entry.py         # FileEntry 데이터 클래스
│   │
│   ├── core/                     # 핵심 로직
│   │   ├── __init__.py
│   │   ├── index_manager.py      # 인덱스 관리 (생명주기, 영속화)
│   │   ├── indexer.py            # 레거시 인덱서 (하위 호환성)
│   │   ├── searcher.py           # 검색 엔진 (메모리 기반)
│   │   └── filesystem/           # 파일 시스템 스캐너
│   │       ├── __init__.py
│   │       ├── scanner_interface.py    # 스캐너 인터페이스
│   │       ├── walk_scanner.py         # os.walk 기반
│   │       ├── usn_scanner.py          # USN Journal (플레이스홀더)
│   │       ├── usn_scanner_ctypes.py   # USN Journal (ctypes)
│   │       └── usn_scanner_native.py   # USN Journal (네이티브)
│   │
│   ├── db/                       # 데이터베이스 레이어
│   │   ├── __init__.py
│   │   └── index_db.py           # SQLite 인덱스 영속성
│   │
│   └── ui/                       # UI 컴포넌트
│       ├── __init__.py
│       ├── main_window.py        # 메인 윈도우
│       ├── result_item_widget.py # 검색 결과 아이템 위젯
│       └── styles.py             # Qt Style Sheets (QSS)
│
├── native/                       # C/C++ 네이티브 모듈 (선택)
│   ├── usn_scanner.h             # 헤더 파일
│   ├── usn_scanner.cpp           # USN Journal 스캐너 구현
│   ├── python_bindings.cpp       # Python C Extension 바인딩
│   ├── setup.py                  # 빌드 스크립트
│   └── README.md                 # 네이티브 모듈 가이드
│
├── venv/                         # Python 가상 환경 (생성됨)
├── *.db                          # SQLite 인덱스 데이터베이스 (생성됨)
│
├── requirements.txt              # Python 의존성
├── README.md                     # 프로젝트 개요
├── ARCHITECTURE.md               # 이 문서
├── BUILD_GUIDE.md                # 빌드 가이드
├── USAGE_NATIVE.md               # 네이티브 모듈 사용 가이드
├── IMPLEMENTATION_PLAN.md        # USN Journal 구현 계획
└── USN_JOURNAL_GUIDE.md          # USN Journal 가이드
```

## 아키텍처 레이어

### 1. UI 레이어 (`src/ui/`)

**역할**: 사용자 인터페이스 및 사용자 상호작용 처리

**주요 컴포넌트**:
- `MainWindow`: 메인 애플리케이션 창, 이벤트 처리
- `ResultItemWidget`: 검색 결과 아이템 표시 (파일 아이콘, 이름, 경로)
- `styles.py`: Qt Style Sheets (QSS) 정의

**특징**:
- UI와 로직 분리 (MVC 패턴)
- 비동기 인덱싱 (UI 블로킹 없음)
- 키보드 중심 인터랙션

### 2. 비즈니스 로직 레이어 (`src/core/`)

**역할**: 인덱싱, 검색, 파일 시스템 접근 로직

#### 2.1 인덱스 관리 (`index_manager.py`)
- **책임**: 인덱스의 전체 생명주기 관리
  - 초기화: DB에서 기존 인덱스 로드
  - 스캔: 파일 시스템 스캔 및 인덱스 업데이트
  - 영속화: DB에 인덱스 저장
  - 증분 업데이트: 변경된 파일만 업데이트

#### 2.2 검색 엔진 (`searcher.py`)
- **책임**: 메모리 기반 고속 검색
  - 부분 문자열 매칭 (대소문자 무시)
  - 파일명 우선순위
  - 즉각적인 응답 (메모리 인덱스 사용)

#### 2.3 파일 시스템 스캐너 (`filesystem/`)

**인터페이스 패턴**:
- `FileSystemScanner`: 추상 기본 클래스
- 여러 구현체로 교체 가능

**구현체**:
1. **WalkScanner**: Python 표준 라이브러리 사용
   - 장점: 안정적, 크로스 플랫폼
   - 단점: 성능 제한적 (중간 규모 폴더에 적합)
   - 성능: 10-30분 (100만 파일)

2. **USNJournalScanner (ctypes)**: Python ctypes로 Windows API 직접 호출
   - 장점: 추가 컴파일 불필요, Everything 수준 성능
   - 단점: Python 오버헤드
   - 성능: 30초-2분 (100만 파일)

3. **USNJournalScannerNative**: C/C++ 네이티브 모듈
   - 장점: 최고 성능
   - 단점: 별도 빌드 필요
   - 성능: 10-30초 (100만 파일)

### 3. 데이터 레이어 (`src/db/`)

**역할**: 인덱스 영속성 관리

**주요 컴포넌트**:
- `IndexDatabase`: SQLite 래퍼
  - 스키마: `file_index` 테이블
  - 최적화: WAL 모드, 메모리 매핑, 배치 처리

**스키마**:
```sql
CREATE TABLE file_index (
    path TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    extension TEXT NOT NULL,
    size INTEGER NOT NULL,
    modified_time REAL NOT NULL,
    indexed_at REAL NOT NULL,
    indexed_path TEXT NOT NULL
);
```

**인덱스**:
- `idx_name`: 파일명 검색 (COLLATE NOCASE)
- `idx_extension`: 확장자 검색
- `idx_indexed_path`: 증분 업데이트용

### 4. 모델 레이어 (`src/models/`)

**역할**: 데이터 구조 정의

**주요 클래스**:
- `FileEntry`: 파일 메타데이터
  - `name`: 파일명
  - `path`: 전체 경로
  - `extension`: 확장자
  - `size`: 파일 크기 (바이트)
  - `modified_time`: 수정 시간 (datetime)

## 데이터 흐름

### 1. 초기 인덱싱

```
[사용자] 
  ↓
[MainWindow] → _start_initial_indexing()
  ↓
[IndexManager] → load_index_from_db()
  ↓
[IndexDatabase] → load_all_entries()
  ↓
[MainWindow] → IndexingThread (백그라운드)
  ↓
[IndexManager] → scan_default_paths() 또는 scan_entire_home_directory()
  ↓
[FileSystemScanner] → scan_directory()
  ↓
[IndexManager] → update_index() → save_entries()
  ↓
[IndexDatabase] → save_entries() (배치 처리)
  ↓
[IndexManager] → _refresh_memory_index()
  ↓
[Searcher] → update_index() (검색 가능)
```

### 2. 검색

```
[사용자] → 검색어 입력
  ↓
[MainWindow] → _on_search_button_clicked()
  ↓
[Searcher] → search(query)
  ↓
[메모리 인덱스] → 필터링 (부분 문자열 매칭)
  ↓
[MainWindow] → 결과 표시 (ResultItemWidget)
```

### 3. 증분 업데이트

```
[IndexManager] → update_index()
  ↓
[IndexDatabase] → get_indexed_paths()
  ↓
[FileSystemScanner] → scan_directory()
  ↓
[IndexManager] → diff 계산
  ↓
[IndexDatabase] → remove_entries_by_paths() (삭제된 파일)
  ↓
[IndexDatabase] → save_entries() (새/변경된 파일)
```

## 스캐너 선택 로직

`IndexManager`는 초기화 시 사용 가능한 가장 빠른 스캐너를 자동으로 선택합니다:

```
1. 네이티브 모듈 시도 (USNJournalScannerNative)
   ↓ 실패
2. ctypes 기반 시도 (USNJournalScanner)
   ↓ 실패
3. WalkScanner 사용 (기본, 항상 사용 가능)
```

**폴백 전략**: 각 스캐너는 실패 시 자동으로 `WalkScanner`로 폴백합니다.

## 성능 최적화

### 1. 인덱싱 최적화
- **멀티스레딩**: CPU 코어 수에 따른 동적 워커 스레드
- **배치 처리**: DB 삽입 시 5000개 단위 배치
- **스킵 로직**: 시스템 폴더, 캐시 폴더 자동 스킵
- **USN Journal**: 직접 MFT 읽기로 파일 시스템 순회 생략

### 2. 데이터베이스 최적화
- **WAL 모드**: 읽기/쓰기 병렬 처리
- **메모리 매핑**: 256MB 메모리 매핑 I/O
- **인덱스**: 파일명, 확장자 인덱스 (COLLATE NOCASE)
- **배치 삽입**: 트랜잭션당 5000개

### 3. 검색 최적화
- **메모리 인덱스**: 디스크 I/O 없음
- **부분 문자열 매칭**: 효율적인 필터링
- **우선순위 정렬**: 파일명 매칭 우선

### 4. UI 최적화
- **비동기 인덱싱**: UI 블로킹 없음
- **지연 렌더링**: 결과가 많을 때 효율적 표시
- **키보드 중심**: 빠른 작업 흐름

## 확장 가능성

### 1. 새로운 스캐너 추가

`FileSystemScanner` 인터페이스를 구현하기만 하면 됩니다:

```python
class MyCustomScanner(FileSystemScanner):
    def scan_directory(self, root_path: str, ...) -> List[FileEntry]:
        # 구현
        pass
    
    def get_scanner_name(self) -> str:
        return "MyCustomScanner"
```

그 다음 `IndexManager.set_scanner()`로 교체:

```python
index_manager.set_scanner(MyCustomScanner())
```

### 2. 검색 알고리즘 변경

`Searcher` 클래스를 확장하거나 교체:

```python
class RegexSearcher(Searcher):
    def search(self, query: str) -> List[FileEntry]:
        # 정규표현식 검색 구현
        pass
```

### 3. 데이터베이스 스키마 확장

필요시 `IndexDatabase` 스키마를 확장하여 추가 메타데이터 저장 가능.

## 의존성 관리

### 필수 의존성
- `PySide6>=6.6.0`: GUI 프레임워크

### 개발 의존성
- `setuptools>=65.0.0`: 네이티브 모듈 빌드
- `wheel>=0.38.0`: 패키징

### 빌드 요구사항 (네이티브 모듈)
- Visual Studio 2019+ (C++ 컴파일러)
- Windows SDK

## 보안 고려사항

1. **관리자 권한**: USN Journal 접근 시 권장 (필수는 아님)
2. **파일 시스템 접근**: 사용자 파일만 인덱싱 (시스템 폴더 제외)
3. **데이터베이스**: 로컬 SQLite 파일 (암호화 불필요)
4. **경로 검증**: 사용자 입력 경로 검증

## 성능 벤치마크

| 작업 | WalkScanner | USN (ctypes) | USN (Native) |
|------|-------------|--------------|--------------|
| 초기 인덱싱 (100만 파일) | ~15분 | ~1분 | ~20초 |
| 메모리 사용 | ~200MB | ~500MB | ~500MB |
| 검색 응답 시간 | <1ms | <1ms | <1ms |
| DB 로드 시간 | ~2초 | ~2초 | ~2초 |

## 향후 개선 방향

1. **실시간 변경 감지**: USN Journal을 이용한 실시간 업데이트
2. **전체 텍스트 검색**: 파일 내용 검색
3. **정규표현식 검색**: 고급 검색 패턴
4. **필터링 UI**: 파일 타입, 크기, 날짜 범위 필터
5. **다중 드라이브 지원**: 여러 드라이브 동시 인덱싱
