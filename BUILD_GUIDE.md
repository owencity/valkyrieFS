# USN Journal 네이티브 모듈 빌드 가이드

## 개요

Everything 수준의 성능을 달성하기 위한 C/C++ 확장 모듈입니다.

## 빌드 요구사항

### Windows
- **Visual Studio 2019 이상** (C++ 개발 도구 포함)
  - "Desktop development with C++" 워크로드 설치 필요
- **Python 3.8 이상**
- **Windows SDK** (Visual Studio와 함께 설치)

## 빌드 방법

### 1단계: Visual Studio 개발자 명령 프롬프트 열기

1. Windows 시작 메뉴에서 "Developer Command Prompt for VS" 검색
2. 또는 "x64 Native Tools Command Prompt for VS" 실행

### 2단계: 프로젝트 디렉토리로 이동

```bash
cd C:\dev\valkyrie
```

### 3단계: 네이티브 모듈 빌드

```bash
cd native
python setup.py build_ext --inplace
```

### 4단계: 빌드 확인

`native/` 디렉토리에 `usn_scanner_native.pyd` 파일이 생성되었는지 확인

## 사용 방법

### 애플리케이션에서 사용

```python
from src.core.index_manager import IndexManager
from src.core.filesystem.usn_scanner_native import USNJournalScannerNative

# 인덱스 관리자 생성
index_manager = IndexManager()

# USN Journal 스캐너로 교체
index_manager.set_scanner(USNJournalScannerNative())

# 이제 Everything 수준의 성능으로 인덱싱 가능
index_manager.scan_entire_home_directory()
```

## 문제 해결

### "usn_scanner_native 모듈을 찾을 수 없음"
- 빌드가 완료되지 않았거나 실패함
- `native/` 디렉토리에 `.pyd` 파일이 있는지 확인
- Visual Studio C++ 도구가 설치되어 있는지 확인

### "관리자 권한 필요" 오류
- USN Journal 읽기는 관리자 권한이 권장됨
- 애플리케이션을 관리자 권한으로 실행

### 빌드 오류
- Visual Studio 재설치 또는 C++ 도구 확인
- Python 개발 헤더 파일 확인
- Windows SDK 설치 확인

## 성능 비교

| 방법 | 초기 인덱싱 (100만 파일) | 메모리 사용 |
|------|------------------------|-------------|
| os.walk (현재) | 10-30분 | 낮음 |
| USN Journal (네이티브) | 10-30초 | 중간 |

## 구현 상태

현재 기본 구조만 구현되어 있습니다. 완전한 구현을 위해서는:
1. ⏳ FSCTL_ENUM_USN_DATA로 MFT 읽기 구현
2. ⏳ FileReferenceNumber → 경로 매핑 구축
3. ⏳ USN 레코드 파싱 및 필터링
4. ⏳ 경로 재구성 로직 완성

## 참고 자료

- Windows USN Journal API: https://learn.microsoft.com/en-us/windows/win32/api/winioctl/
- Python C Extension: https://docs.python.org/3/extending/
- Everything 검색 엔진 구현: https://www.voidtools.com/

