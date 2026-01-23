# Valkyrie 프로젝트 구조

## 디렉토리 구조

```
valkyrie/
│
├── src/                              # 소스 코드
│   ├── __init__.py                   # 패키지 초기화
│   ├── main.py                       # 애플리케이션 진입점
│   │
│   ├── models/                       # 데이터 모델
│   │   ├── __init__.py
│   │   └── file_entry.py             # FileEntry 데이터 클래스
│   │       - name: str               # 파일명
│   │       - path: str               # 전체 경로
│   │       - extension: str          # 확장자
│   │       - size: int               # 파일 크기 (바이트)
│   │       - modified_time: datetime # 수정 시간
│   │
│   ├── core/                         # 핵심 비즈니스 로직
│   │   ├── __init__.py
│   │   │
│   │   ├── index_manager.py          # 인덱스 관리자
│   │   │   - IndexManager 클래스
│   │   │   - 인덱스 생성, 업데이트, 영속화
│   │   │   - 스캐너 선택 및 관리
│   │   │
│   │   ├── indexer.py                # 레거시 인덱서 (하위 호환성)
│   │   │   - Indexer 클래스
│   │   │   - os.walk 기반 인덱싱
│   │   │
│   │   ├── searcher.py               # 검색 엔진
│   │   │   - Searcher 클래스
│   │   │   - 메모리 기반 부분 문자열 검색
│   │   │   - 파일명 우선순위 정렬
│   │   │
│   │   └── filesystem/               # 파일 시스템 스캐너
│   │       ├── __init__.py           # 스캐너 export
│   │       ├── scanner_interface.py  # FileSystemScanner 인터페이스
│   │       │   - scan_directory()    # 디렉토리 스캔
│   │       │   - get_scanner_name()  # 스캐너 이름
│   │       │
│   │       ├── walk_scanner.py       # os.walk 기반 스캐너
│   │       │   - WalkScanner 클래스
│   │       │   - 멀티스레딩 지원
│   │       │   - 시스템 폴더 스킵
│   │       │
│   │       ├── usn_scanner.py        # USN Journal 스캐너 (플레이스홀더)
│   │       ├── usn_scanner_ctypes.py # USN Journal (ctypes)
│   │       │   - USNJournalScanner 클래스
│   │       │   - Windows API 직접 호출
│   │       │   - FSCTL_ENUM_USN_DATA 구현
│   │       │
│   │       └── usn_scanner_native.py # USN Journal (네이티브 래퍼)
│   │           - USNJournalScannerNative 클래스
│   │           - C/C++ 모듈 래핑
│   │
│   ├── db/                           # 데이터베이스 레이어
│   │   ├── __init__.py
│   │   └── index_db.py               # SQLite 인덱스 영속성
│   │       - IndexDatabase 클래스
│   │       - save_entries()          # 배치 삽입
│   │       - load_all_entries()      # 전체 로드
│   │       - get_indexed_paths()     # 인덱싱된 경로 조회
│   │       - remove_entries_by_paths() # 배치 삭제
│   │
│   └── ui/                           # UI 컴포넌트
│       ├── __init__.py
│       │
│       ├── main_window.py            # 메인 윈도우
│       │   - MainWindow 클래스
│       │   - IndexingThread (QThread)
│       │   - 검색 입력, 결과 리스트
│       │   - 키보드 단축키
│       │
│       ├── result_item_widget.py     # 검색 결과 아이템 위젯
│       │   - ResultItemWidget 클래스
│       │   - 파일 아이콘, 이름, 경로 표시
│       │
│       └── styles.py                 # Qt Style Sheets
│           - APPLICATION_STYLE 상수
│           - 모던한 UI 스타일 정의
│
├── native/                           # C/C++ 네이티브 모듈 (선택)
│   ├── usn_scanner.h                 # 헤더 파일
│   │   - FileInfo 구조체
│   │   - FileInfoArray 구조체
│   │   - scan_usn_journal() 함수
│   │
│   ├── usn_scanner.cpp               # USN Journal 스캐너 구현
│   │   - FSCTL_ENUM_USN_DATA 구현
│   │   - USN_RECORD_V2 파싱
│   │   - 경로 재구성 로직
│   │
│   ├── python_bindings.cpp           # Python C Extension
│   │   - PyInit_usn_scanner_native()
│   │   - py_scan_usn_journal() 함수
│   │
│   ├── setup.py                      # 빌드 스크립트
│   └── README.md                     # 네이티브 모듈 가이드
│
├── venv/                             # Python 가상 환경 (생성됨)
├── *.db                              # SQLite 인덱스 DB (생성됨)
│
├── requirements.txt                  # Python 의존성
│   - PySide6>=6.6.0
│   - setuptools>=65.0.0
│   - wheel>=0.38.0
│
├── README.md                         # 프로젝트 개요
├── ARCHITECTURE.md                   # 아키텍처 문서
├── TECH_STACK.md                     # 기술 스택 문서
├── PROJECT_STRUCTURE.md              # 이 문서
├── BUILD_GUIDE.md                    # 빌드 가이드
├── USAGE_NATIVE.md                   # 네이티브 모듈 사용 가이드
├── IMPLEMENTATION_PLAN.md            # USN Journal 구현 계획
└── USN_JOURNAL_GUIDE.md              # USN Journal 가이드
```

## 주요 파일 설명

### 진입점

#### `src/main.py`
- **역할**: 애플리케이션 시작점
- **내용**:
  - `QApplication` 초기화
  - `MainWindow` 생성 및 표시
  - 이벤트 루프 시작

### 핵심 모듈

#### `src/core/index_manager.py`
- **역할**: 인덱스 생명주기 관리
- **주요 메서드**:
  - `load_index_from_db()`: DB에서 인덱스 로드
  - `scan_directory()`: 디렉토리 스캔
  - `scan_default_paths()`: 기본 경로들 스캔
  - `scan_entire_home_directory()`: 전체 홈 디렉토리 스캔
  - `set_scanner()`: 스캐너 교체
  - `get_statistics()`: 인덱스 통계

#### `src/core/searcher.py`
- **역할**: 메모리 기반 검색
- **주요 메서드**:
  - `search(query: str)`: 검색 수행
  - `update_index()`: 인덱스 업데이트

#### `src/db/index_db.py`
- **역할**: SQLite 영속성
- **주요 메서드**:
  - `save_entries()`: 배치 삽입 (5000개 단위)
  - `load_all_entries()`: 전체 로드
  - `get_indexed_paths()`: 인덱싱된 경로 조회
  - `remove_entries_by_paths()`: 배치 삭제

### UI 컴포넌트

#### `src/ui/main_window.py`
- **역할**: 메인 UI 창
- **주요 위젯**:
  - `search_input`: 검색 입력 (QLineEdit)
  - `search_button`: 검색 버튼 (QPushButton)
  - `result_list`: 결과 리스트 (QListWidget)
  - `status_label`: 상태 표시 (QLabel)
  - `reindex_button`: 재인덱싱 버튼 (QPushButton)

#### `src/ui/result_item_widget.py`
- **역할**: 검색 결과 아이템
- **표시 내용**:
  - 파일 아이콘 (QFileIconProvider)
  - 파일명 (주요 텍스트)
  - 파일 경로 (보조 텍스트)

## 데이터 흐름

### 초기화
```
main.py
  → MainWindow.__init__()
    → IndexManager.__init__()
      → _create_best_available_scanner()  # 스캐너 자동 선택
    → _start_initial_indexing()
      → load_index_from_db()  # 빠른 시작
      → IndexingThread 시작  # 백그라운드 업데이트
```

### 인덱싱
```
IndexingThread.run()
  → IndexManager.scan_directory()
    → FileSystemScanner.scan_directory()
      → List[FileEntry] 반환
    → IndexDatabase.save_entries()  # 배치 저장
    → _refresh_memory_index()  # 메모리 업데이트
```

### 검색
```
사용자 입력
  → MainWindow._on_search_button_clicked()
    → Searcher.search(query)
      → 메모리 인덱스 필터링
    → MainWindow._display_results()
      → ResultItemWidget 생성
```

## 파일 명명 규칙

### Python 파일
- **snake_case**: `file_entry.py`, `index_manager.py`
- **모듈 이름 = 클래스 이름 (소문자)**: `IndexManager` → `index_manager.py`

### 클래스
- **PascalCase**: `IndexManager`, `FileEntry`

### 함수/메서드
- **snake_case**: `scan_directory()`, `load_index_from_db()`

### 상수
- **UPPER_SNAKE_CASE**: `DEFAULT_INDEX_PATHS`, `APPLICATION_STYLE`

## 모듈 의존성

### 의존성 방향
```
ui/
  → core/
    → db/
    → models/
  → models/

core/
  → db/
  → models/
  → filesystem/

db/
  → models/
```

### 금지된 순환 참조
- `core` → `ui` (비즈니스 로직은 UI 의존하지 않음)
- `models` → `core` (모델은 순수 데이터)

## 확장 포인트

### 새로운 스캐너 추가
1. `src/core/filesystem/`에 새 파일 생성
2. `FileSystemScanner` 상속
3. `scan_directory()` 구현
4. `IndexManager.set_scanner()`로 교체

### 새로운 검색 알고리즘
1. `src/core/`에 새 검색 클래스 생성
2. `MainWindow`에서 교체

### 데이터베이스 스키마 확장
1. `src/db/index_db.py` 수정
2. 마이그레이션 로직 추가

## 빌드 산출물

### Python 패키지
- **소스 코드**: `src/` 디렉토리
- **실행 파일**: `python -m src.main`

### 네이티브 모듈 (선택)
- **출력**: `native/usn_scanner_native.pyd`
- **빌드**: `python native/setup.py build_ext --inplace`

### 데이터베이스
- **출력**: 프로젝트 루트의 `*.db` 파일
- **생성**: 첫 실행 시 자동 생성

