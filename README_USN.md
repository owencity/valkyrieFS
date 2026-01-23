# USN Journal 수준 성능 구현 현황

## 현재 상황

### ✅ 완료된 것
1. **SQL 오류 수정**: `too many SQL variables` 문제 해결
2. **성능 최적화**: 멀티스레딩, 배치 처리, 필터링 등
3. **아키텍처 준비**: USN Journal 스캐너 교체 가능한 구조

### ⏳ 구현 필요
**USN Journal 스캐너 완전 구현**

## USN Journal 구현 현실

### Python만으로 가능한가?

**답: 가능하지만 복잡합니다.**

Python `ctypes`를 사용하여 Windows API (`DeviceIoControl`)를 직접 호출할 수 있습니다. 하지만:

1. **MFT 읽기 복잡**: FileReferenceNumber로 경로 재구성 필요
2. **디버깅 어려움**: 저수준 API 오류 처리 복잡
3. **성능 제약**: Python 오버헤드로 네이티브보다 느림

### 실제 구현 방법

#### 방법 1: 기존 라이브러리 활용 (가장 현실적)

```bash
# pyusnjrnl (있다면)
pip install pyusnjrnl

# 또는 usnrs (Rust 기반, Python 바인딩 필요)
```

#### 방법 2: Python ctypes 구현 (2-3주)

현재 `src/core/filesystem/usn_scanner_ctypes.py`에 기본 구조가 있습니다.

**구현 필요:**
- FSCTL_ENUM_USN_DATA로 MFT 읽기
- FileReferenceNumber → 경로 매핑
- USN 레코드 파싱

#### 방법 3: C/C++ 확장 모듈 (최고 성능)

**Everything 수준의 성능 달성 가능**

1. C/C++로 USN Journal 읽기 모듈 작성
2. Python C extension으로 빌드
3. Python에서 호출

## 권장 사항

### 즉시 사용 가능
현재 최적화된 `WalkScanner`는:
- 수십만 파일을 수 분 내 인덱싱
- 실용적이고 안정적
- 추가 작업 없이 사용 가능

### USN Journal 수준 성능이 필요하다면

**단기 (1주):**
- 기존 라이브러리(pyusnjrnl 등) 확인 및 사용

**중기 (2-3주):**
- Python ctypes로 기본 구현
- 성능: 3-5배 향상

**장기 (1개월):**
- C/C++ 확장 모듈 구현
- Everything 수준 성능 달성

## 결론

아키텍처는 USN Journal 지원 준비가 되어 있습니다. 
필요시 `IndexManager.set_scanner(USNJournalScanner())`로 교체하면 됩니다.

**현재로서는:**
- 최적화된 WalkScanner 사용 권장
- USN Journal은 장기 과제로 진행

