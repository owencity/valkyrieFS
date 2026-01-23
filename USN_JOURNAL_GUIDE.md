# USN Journal 수준 성능 구현 가이드

## 현실적인 접근

USN Journal을 사용하려면 **Python만으로는 복잡**하지만, **완전히 불가능한 것은 아닙니다**.

## 구현 방법 비교

### 방법 1: Python ctypes (가능하지만 복잡)

**장점:**
- Python만으로 구현 가능
- 추가 의존성 없음

**단점:**
- 구현 복잡도 높음
- MFT 파싱, 경로 재구성 등 많은 작업 필요
- 디버깅 어려움

**구현 필요 작업:**
1. ✅ 기본 구조체 정의 (완료)
2. ⏳ FSCTL_ENUM_USN_DATA로 MFT 읽기
3. ⏳ FileReferenceNumber → 경로 매핑
4. ⏳ USN 레코드 파싱
5. ⏳ 경로 재구성 로직

**예상 작업 시간:** 2-3주

### 방법 2: 기존 라이브러리 사용 (추천)

#### pyusnjrnl (있다면)
```python
# 설치: pip install pyusnjrnl
from pyusnjrnl import USNJournalReader

reader = USNJournalReader("C:")
for record in reader:
    # 파일 정보 처리
```

#### usnrs (Rust 기반)
- GitHub: https://github.com/airbus-cert/usnrs
- Rust로 작성되어 Python 바인딩 제공 가능

### 방법 3: C/C++ 확장 모듈

**장점:**
- 최고 성능
- Everything과 동일한 수준

**단점:**
- 별도 컴파일 필요
- 빌드 환경 설정 필요

**구현 계획:**
```
usn_scanner_cpp/
├── usn_scanner.cpp    # C++ 구현
├── usn_scanner.h
├── setup.py           # Python 빌드 스크립트
└── bindings/          # Python 바인딩
```

## 현재 상황 정리

### 이미 구현된 것
1. ✅ 아키텍처 분리 (스캐너 인터페이스)
2. ✅ USN Journal 스캐너 플레이스홀더
3. ✅ ctypes 기본 구조
4. ✅ 폴백 메커니즘 (os.walk)

### 구현 필요
1. ⏳ 완전한 USN Journal 읽기 로직
2. ⏳ MFT 파싱 및 경로 재구성
3. ⏳ 테스트 및 성능 측정

## 권장 사항

### 단기 (즉시)
- 현재 최적화된 WalkScanner 사용 (이미 구현됨)
- 성능: 수십만 파일을 수 분 내 인덱싱
- 실용적이고 안정적

### 중기 (1-2주)
- Python ctypes로 기본 USN Journal 읽기 구현
- 성능: 3-5배 향상 예상

### 장기 (1개월)
- C/C++ 확장 모듈 구현
- Everything 수준의 성능 달성

## 결론

**현재로서는:**
- 최적화된 WalkScanner가 실용적
- USN Journal 구현은 장기 과제로 진행 권장
- 아키텍처는 이미 USN Journal 지원 준비됨

**필요시:**
- `IndexManager.set_scanner(USNJournalScanner())`로 교체 가능
- UI나 검색 로직 변경 불필요

