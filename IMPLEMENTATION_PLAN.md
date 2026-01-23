# USN Journal 수준 성능 구현 계획

## 현재 상황

사용자는 Everything 수준의 성능을 원합니다. 이를 위해서는 USN Journal 사용이 필수적입니다.

## 구현 방법 선택

### 옵션 1: Python ctypes (추천 - 즉시 구현 가능)

**장점:**
- Python만으로 구현 가능
- 추가 의존성 없음
- 상대적으로 구현이 간단

**단점:**
- 완전한 USN Journal 파싱이 복잡함
- 성능이 C/C++보다는 낮음

**구현 단계:**
1. ✅ ctypes로 기본 구조체 정의 (완료)
2. ⏳ FSCTL_ENUM_USN_DATA로 MFT 읽기
3. ⏳ FSCTL_READ_USN_JOURNAL로 변경 감지
4. ⏳ 파일 경로 재구성 로직

### 옵션 2: C/C++ 확장 모듈

**장점:**
- 최고 성능
- Everything과 동일한 수준

**단점:**
- 별도 컴파일 필요
- 빌드 환경 필요

**구현 계획:**
```cpp
// usn_scanner.cpp
// Windows API로 USN Journal 읽기
// Python C extension으로 빌드
```

### 옵션 3: Rust + PyO3 (권장 - 장기적)

**장점:**
- 네이티브 성능
- 메모리 안전
- 현대적인 언어

**단점:**
- 초기 구현 시간 필요
- Rust 학습 곡선

## 즉시 사용 가능한 해결책

현재로서는 **기존 라이브러리 사용**을 추천합니다:

### 1. pyusnjrnl (만약 있다면)
```python
# 사용 예시
from pyusnjrnl import USNJournalReader
reader = USNJournalReader("C:")
for record in reader.read_all():
    # 파일 정보 처리
```

### 2. 직접 구현 (ctypes)

복잡하지만 가능합니다. 현재 `usn_scanner_ctypes.py`에 기본 구조를 만들었습니다.

## 권장 구현 순서

### Phase 1: 기본 USN Journal 읽기 (1-2일)
1. 볼륨 핸들 열기
2. USN Journal 메타데이터 조회
3. 기본 레코드 읽기

### Phase 2: 파일 경로 재구성 (2-3일)
1. FileReferenceNumber로 경로 추적
2. MFT 파싱으로 경로 재구성
3. 캐싱 최적화

### Phase 3: 통합 (1일)
1. IndexManager와 통합
2. 성능 테스트
3. 오류 처리

## 성능 비교 예상

| 방법 | 초기 인덱싱 (100만 파일) | 메모리 사용 |
|------|------------------------|-------------|
| os.walk (현재) | 10-30분 | 낮음 |
| USN Journal (ctypes) | 30초-2분 | 중간 |
| USN Journal (C/C++) | 10-30초 | 중간 |

## 결론

**즉시 적용 가능:** ctypes 기반 구현 (1-2주)
**최고 성능:** C/C++ 확장 (1개월)

현재로서는 ctypes 버전부터 시작하는 것을 추천합니다.

