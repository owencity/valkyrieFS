# ValkyrieFS 기술 스택

## 개요

ValkyrieFS는 고성능 Windows 파일 검색 애플리케이션입니다. Python과 PySide6로 구현되었으며,
네이티브 모듈(C++)을 통해 **MFT 열거(초기 인덱싱)** 및 **메모리 인덱스 검색**을 수행하여 Everything-like 성능을 목표로 합니다.

## 기술 스택 상세

### 프로그래밍 언어

#### Python 3.8+
- **역할**: 메인 애플리케이션 언어
- **버전**: 3.8 이상
- **사용 이유**:
  - 빠른 개발 속도
  - 풍부한 표준 라이브러리
  - 크로스 플랫폼 가능성 (Windows 최적화)
  - GUI 프레임워크 통합 용이

#### C/C++
- **역할**: 고성능 파일 열거 + C++ 메모리 인덱스(검색)
- **컴파일러**: MSVC (Visual Studio 2019+)
- **사용 이유**:
  - Everything 수준의 성능 필요
  - Windows API 직접 접근
  - Python ctypes 오버헤드 제거

### GUI 프레임워크

#### PySide6 (Qt 6)
- **버전**: >= 6.6.0
- **역할**: 데스크톱 GUI
- **선택 이유**:
  - 네이티브 느낌의 Windows UI
  - 성숙한 프레임워크
  - 강력한 스타일링 (QSS)
  - 키보드 중심 인터랙션 지원
  - 멀티스레딩 지원 (QThread)

**주요 사용 컴포넌트**:
- `QMainWindow`: 메인 윈도우
- `QLineEdit`: 검색 입력
- `QListView`: 결과 리스트(가상 렌더링)
- `QAbstractListModel`: 대량 결과 모델
- `QStyledItemDelegate`: 고성능 아이템 렌더링(아이콘/텍스트 직접 paint)
- `QThread`: 백그라운드 인덱싱
- `QThreadPool`/`QRunnable`: 백그라운드 검색(실시간 입력 대응)
- `QTimer`: 입력 디바운스

### 영속화(스냅샷)

#### 바이너리 스냅샷 파일
- **역할**: 인덱스 영속성(재실행 시 빠른 로드)
- **형태**: `index.dat` (C++ 메모리 인덱스 스냅샷)
- **기본 경로**: `~/.valkyrie/index.dat`

> 과거에는 SQLite를 사용했지만, Everything-like 체감을 위해 현재는 **SQLite를 제거**하고
> C++ 메모리 인덱스 스냅샷 방식으로 전환했습니다.

### 파일 시스템 접근

#### Windows API
- **역할**: USN Journal 읽기
- **주요 함수**:
  - `CreateFileW`: 볼륨 핸들 열기
  - `DeviceIoControl`: IOCTL 요청
  - `FSCTL_QUERY_USN_JOURNAL`: 저널 메타데이터 조회
  - `FSCTL_ENUM_USN_DATA`: MFT 열거

**구현 방식**:
1. **C/C++ 네이티브**: Python C Extension (`usn_scanner_native`)
2. **Python ctypes**: Windows API 직접 호출 (`usn_scanner_ctypes`, 개발/보조용)

#### Python 표준 라이브러리
- **`pathlib`**: 경로 처리
- **`threading`**: 인덱싱 상태 동기화
 
> `os.walk` 기반 인덱싱은 Everything-like 전략에서 제외되었고(폴백 없음),
> 코드상으로는 일부 레거시/개발용으로만 남아있습니다.

### 빌드 도구

#### setuptools
- **역할**: Python 패키징 및 네이티브 모듈 빌드
- **버전**: >= 65.0.0

#### wheel
- **역할**: 바이너리 패키징
- **버전**: >= 0.38.0

#### MSVC (Visual Studio)
- **역할**: C/C++ 컴파일
- **버전**: 2019 이상
- **필수 워크로드**: Desktop development with C++

## 아키텍처 패턴

### 1. MVC (Model-View-Controller)
- **Model**: `FileEntry`
- **View**: `MainWindow`, `ResultListModel`, `ResultItemDelegate`
- **Controller**: `IndexManager` + `MemoryIndexManager`

### 2. Strategy Pattern
- **인터페이스**: `FileSystemScanner`
- **구현체**: `WalkScanner`, `USNJournalScanner`, `USNJournalScannerNative`
- **교체 가능**: 런타임에 스캐너 교체

### 3. Repository Pattern
- (과거) SQLite 기반 영속성
- (현재) 스냅샷 파일(`index.dat`) 기반 영속화

### 4. Observer Pattern
- **시그널**: Qt 시그널/슬롯
- **사용**: 인덱싱 진행 상황, 완료 알림

## 의존성 트리

```
valkyrie
├── PySide6>=6.6.0
│   ├── PySide6-QtCore
│   ├── PySide6-QtGui
│   └── PySide6-QtWidgets
│
├── setuptools>=65.0.0 (빌드 시)
├── wheel>=0.38.0 (빌드 시)
│
└── Python 3.8+ 표준 라이브러리
    ├── threading
    ├── pathlib
    ├── os
    └── ctypes (USN Journal 접근)
```

## 플랫폼 요구사항

### 필수
- **OS**: Windows 10/11 (NTFS 파일 시스템)
- **Python**: 3.8 이상
- **디스크 공간**: 스냅샷 파일 크기(파일 수/경로 길이에 따라 가변)

### 선택 (최고 성능)
- **Visual Studio Build Tools**: C/C++ 컴파일러
- **관리자 권한**: USN Journal 최적 접근

## 성능 특성

### 메모리 사용
- **기본 인덱스**: ~200MB (100만 파일)
- **USN Journal**: ~500MB (100만 파일)
- **검색 시**: 메모리 인덱스만 사용 (추가 메모리 없음)

### CPU 사용
- **인덱싱 중**: 멀티코어 활용 (동적 워커 스레드)
- **검색 중**: 단일 스레드 (즉각 응답)

### 디스크 I/O
- **초기 인덱싱**: 높음 (USN Journal 읽기)
- **검색**: 없음 (메모리 기반)
- **스냅샷 저장**: 인덱스 빌드 후 바이너리 저장

## 호환성

### Python 버전
- **지원**: Python 3.8, 3.9, 3.10, 3.11, 3.12+
- **권장**: Python 3.10 이상

### Windows 버전
- **최소**: Windows 10
- **권장**: Windows 11
- **NTFS 필수**: USN Journal 지원

### PySide6 버전
- **최소**: 6.6.0
- **권장**: 최신 버전

## 개발 환경

### 필수 도구
- Python 3.8+ (venv 지원)
- pip
- Git (버전 관리)

### 선택 도구
- Visual Studio 2019+ (C/C++ 빌드)
- PyCharm / VS Code (IDE)
- Python 가상 환경

## 라이선스

- **프로젝트**: 내부 프로젝트
- **PySide6**: LGPL / Commercial

## 참고 자료

- [PySide6 문서](https://doc.qt.io/qtforpython/)
- [USN Journal API](https://learn.microsoft.com/en-us/windows/win32/api/winioctl/)
- [Everything 검색 엔진](https://www.voidtools.com/)

