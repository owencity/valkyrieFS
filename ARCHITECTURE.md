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

---

## 참고: Everything은 “어떤 방식”으로 빠른가

Everything(VOIDTOOLS)은 일반적인 `os.walk`처럼 디렉토리 트리를 재귀 순회해서 인덱스를 만들지 않고,
Windows/NTFS가 이미 유지하고 있는 **메타데이터**를 활용해 “볼륨 단위”로 매우 빠르게 인덱스를 구축합니다.

### 1) 초기 인덱싱: NTFS MFT(Master File Table) 열거

- NTFS 볼륨(C:, D: 등)에는 파일/폴더의 메타데이터가 **MFT**에 “테이블 형태”로 저장됩니다.
- Everything은 이 메타데이터를 읽어 **폴더 순회 없이** 대량 파일 목록을 빠르게 구성합니다.
- 일반적인 구현은 `FSCTL_ENUM_USN_DATA`(+ `DeviceIoControl`)를 이용해 MFT 레코드를 열거합니다.

### 2) 실시간/증분 반영: USN Change Journal

- 초기 구축 후에는 전체를 다시 훑는 대신, NTFS의 **USN Change Journal**(변경 로그)을 이용해
  생성/삭제/이름 변경/이동 같은 이벤트만 반영합니다.
- 그래서 “항상 최신에 가깝게 유지하면서도”, 디스크를 계속 재스캔하지 않아 리소스 사용이 낮습니다.

### 3) 권한 모델: UI(일반 권한) + Service(권한 보유)

- MFT/USN에 접근하려면 환경에 따라 관리자 권한이 필요할 수 있어,
  Everything은 **Everything Service**(Windows 서비스)를 통해 권한을 확보하는 방식을 제공합니다.
- 요약하면:
  - **서비스**: 인덱싱/변경 감지 등 권한 필요한 작업 담당
  - **UI**: 일반 권한으로 실행, 서비스에 검색/상태를 요청(IPC)

> 우리 프로젝트의 “Everything 스타일 권한 모델” 제안은 `SERVICE_MODEL.md`를 참고하세요.

---

## 참고: 다중 드라이브 지원(멀티 볼륨) — 현재 상태와 확장 옵션/리스크

### 현재 동작(우리 코드 기준)

현재 스캔은 크게 두 모드가 있고, **여러 드라이브를 자동으로 전부 인덱싱하지는 않습니다**.

- **기본 스캔(default)**: 사용자 홈의 대표 폴더만 인덱싱  
  (`Documents/Desktop/Downloads/...` 등, `IndexManager.DEFAULT_INDEX_PATHS`)
- **전체 스캔(entire)**:
  - USN 스캐너 사용 시: `Path.home().drive`의 루트만 스캔(예: `C:\`)  
    → 사용자가 파일을 **D:\**에 많이 두면 누락될 수 있음

관련 구현: `src/core/index_manager.py`의 `scan_default_paths()`, `scan_entire_home_directory()`

### 확장 옵션(설계 선택지)

- **옵션 A: 드라이브 자동 탐지 + Fixed(로컬 디스크)만 전체 스캔**
  - Windows 논리 드라이브를 열거 후(C:, D: ...), “로컬 디스크/NTFS”만 USN 인덱싱
  - 장점: 사용자 설정 없이도 D 포함 가능
  - 단점: 초기 인덱싱 범위가 커져 성능/권한 이슈가 크게 증가

- **옵션 B: UI/설정에서 인덱싱 대상 선택(권장)**
  - 최초 실행(또는 설정)에서 “인덱싱할 드라이브/폴더”를 체크로 선택
  - 장점: 사용자가 의도한 범위만 스캔 → 불필요한 디스크 폭주를 줄임
  - 단점: UI/설정 저장/마이그레이션 필요

- **옵션 C: 기본은 홈 폴더(빠른 시작) + 추가 드라이브는 ‘추가 인덱싱’ 기능으로**
  - 장점: 초기 UX 빠름(Everything “즉시 검색” 체감에 유리)
  - 단점: 사용자가 기능을 알아야 D 포함 가능

### 위험성/주의점(실무 리스크)

- **성능/리소스 폭증**: 드라이브를 더 포함할수록 파일 수가 급증 → 인덱싱 시간/메모리 증가
- **권한/접근 실패**: 볼륨마다 권한/정책이 다르고, USN/MFT 접근이 실패할 수 있음
- **파일시스템 차이**: exFAT/FAT32/네트워크 드라이브는 USN 불가 → 폴백/제외 정책 필요
- **아이콘/재파스 포인트/루프**: junction/reparse point 처리 미흡 시 중복/루프 위험
- **서비스 컨텍스트 이슈**: 서비스(LocalSystem)에서는 사용자별 네트워크 드라이브 매핑이 안 보일 수 있음

### 권장 결론(현재 단계에서)

제품 품질/UX 관점에서 가장 안전한 방향은 **옵션 B(사용자 선택형) + 기본은 홈 폴더**입니다.
Everything 수준의 “전체 볼륨”을 목표로 하면 옵션 A도 가능하지만,
드라이브 타입/파일시스템 필터링과 실패 시 폴백 정책을 반드시 같이 설계해야 합니다.