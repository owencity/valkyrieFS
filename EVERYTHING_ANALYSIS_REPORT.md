# Everything 동작 원리 분석 및 현재 시스템 개선 보고서

## Everything의 핵심 동작 원리

### 1. 인덱싱 대상: 파일/폴더 이름 + 경로만
- ✅ **파일 내용은 인덱싱하지 않음** (Windows Search와 다름)
- ✅ **이름과 경로만 저장** → 데이터량 작음 (100만 파일 = ~75MB)
- ✅ **파일을 실제로 열지 않음** → 초기 구축 빠름

### 2. 초기 인덱싱: MFT 직접 읽기
- ✅ **폴더 순회 방식 아님** (느린 방식)
- ✅ **NTFS MFT(Master File Table) 직접 읽기**
- ✅ **FSCTL_ENUM_USN_DATA** 사용
- ✅ **볼륨 전체를 한 번에 대량으로 읽음** → 12만 파일 = 1초

### 3. 실시간 업데이트: USN Journal 모니터링
- ✅ **USN Journal(변경 로그) 읽기**
- ✅ **마지막 처리한 USN 위치 저장**
- ✅ **변경된 부분만 읽어서 인덱스 갱신**
- ✅ **전체 재스캔 없이 실시간 반영**

### 4. 검색 최적화
- ✅ **메모리 기반 검색** (디스크/DB 거의 안 씀)
- ✅ **부분 문자열 검색 최적화** (전체 선형 스캔 피함)
- ✅ **타이핑 단위 디바운스**
- ✅ **상위 N개만 즉시 렌더링** (예: 200~1000개)

---

## 현재 시스템 분석

### ✅ 구현 완료된 부분

#### 1. 인덱싱 대상
- ✅ **파일명/경로만 인덱싱** (`FileEntry` 모델)
- ✅ **파일 내용 인덱싱 안 함**
- ✅ **파일과 폴더 모두 인덱싱** (최근 수정)

#### 2. 초기 인덱싱
- ✅ **MFT 직접 읽기 구현** (`native/usn_scanner.cpp`)
- ✅ **FSCTL_ENUM_USN_DATA 사용**
- ✅ **볼륨 전체 대량 읽기**
- ✅ **성능: 1,045,348개 파일 발견** (Everything 수준)

#### 3. 메모리 기반 검색
- ✅ **메모리 인덱스 사용** (`Searcher` 클래스)
- ✅ **DB는 영속화용** (검색 시 사용 안 함)
- ✅ **사전 계산된 소문자 버전** (중복 변환 제거)

#### 4. Everything 방식 시작
- ✅ **DB에서 인덱스 로드 후 즉시 검색 가능**
- ✅ **초기 스캔 생략** (인덱스 있으면)

---

### ❌ 미구현/개선 필요 부분

#### 1. USN Journal 실시간 모니터링 (중요도: 높음)
**현재 상태:**
- ❌ 실시간 모니터링 미구현
- ❌ 마지막 USN 위치 저장 안 함
- ❌ 변경 감지 후 자동 업데이트 안 함

**필요 작업:**
```python
# 구현 필요
class USNJournalMonitor:
    def __init__(self, volume_path: str):
        self.last_usn = self.load_last_usn()  # DB에서 로드
    
    def monitor_changes(self):
        # FSCTL_READ_USN_JOURNAL로 변경 로그 읽기
        # last_usn 이후의 변경만 읽음
        # 인덱스 자동 업데이트
        pass
```

**예상 효과:**
- 파일 추가/삭제/이름변경 시 즉시 반영
- 전체 재스캔 불필요

#### 2. 부분 문자열 검색 최적화 (중요도: 높음)
**현재 상태:**
- ⚠️ **선형 스캔 방식** (100만 개면 느림)
- ⚠️ 첫/마지막 글자 스킵으로 일부 최적화
- ⚠️ Python 오버헤드로 Everything보다 느림

**문제점:**
```python
# 현재: 모든 파일명에 substring 검사
for i in range(index_len):  # 100만 번 반복
    if query_lower in name_lower:  # O(n) 문자열 검색
        matches.append(...)
```

**개선 방안:**

**옵션 A: 접두사 인덱스 (Prefix Index)**
```python
# 첫 글자별로 그룹화
self._prefix_index = {
    'a': [0, 100, 200, ...],  # 'a'로 시작하는 파일 인덱스
    'b': [50, 150, 250, ...],
    ...
}

# 검색 시 해당 그룹만 검사
candidates = self._prefix_index.get(query[0], [])
for i in candidates:
    if query in self._name_lower[i]:
        matches.append(...)
```

**옵션 B: N-gram 인덱스**
```python
# 2-gram 인덱스 (예: "pdf" → ["pd", "df"])
self._ngram_index = {
    'pd': [0, 100, ...],
    'df': [0, 50, ...],
    ...
}
```

**옵션 C: C/C++ 네이티브 검색 모듈**
```cpp
// native/search_engine.cpp
// C++로 검색 엔진 구현
// Python에서 호출
```

**예상 효과:**
- 검색 속도: 1초 → 0.1초 이하
- Everything 수준 성능 달성

#### 3. 타이핑 단위 최적화 (중요도: 중간)
**현재 상태:**
- ❌ 디바운스 없음
- ❌ 이전 검색 취소 없음
- ⚠️ 버튼 클릭 방식 (실시간 검색 아님)

**개선 방안:**
```python
# 디바운스 추가
from PySide6.QtCore import QTimer

class MainWindow:
    def __init__(self):
        self.search_timer = QTimer()
        self.search_timer.setSingleShot(True)
        self.search_timer.timeout.connect(self._perform_search)
    
    def _on_search_text_changed(self, text: str):
        # 300ms 후 검색 (디바운스)
        self.search_timer.stop()
        self.search_timer.start(300)
```

**예상 효과:**
- 타이핑 중 불필요한 검색 방지
- UI 반응성 향상

#### 4. 결과 상위 N개만 렌더링 (중요도: 중간)
**현재 상태:**
- ✅ `max_results=1000` 제한 있음
- ⚠️ 모든 결과를 한 번에 렌더링

**개선 방안:**
```python
# 가상 스크롤링 또는 지연 렌더링
# 처음 100개만 즉시 렌더링
# 나머지는 스크롤 시 로드
```

---

## 성능 비교

| 항목 | Everything | 현재 시스템 | 목표 |
|------|-----------|------------|------|
| 초기 인덱싱 (100만 파일) | ~10초 | ~20초 | ✅ 달성 |
| 검색 속도 | 0.01-0.1초 | 0.1-0.5초 | ⚠️ 개선 필요 |
| 실시간 업데이트 | ✅ 있음 | ❌ 없음 | ❌ 미구현 |
| 메모리 사용 | ~75MB | ~500MB | ⚠️ 개선 가능 |

---

## 우선순위별 개선 계획

### Phase 1: 검색 성능 개선 (1-2주)
1. **접두사 인덱스 구현**
   - 첫 글자별 그룹화
   - 검색 범위 대폭 축소
   - 예상 효과: 5-10배 속도 향상

2. **디바운스 추가**
   - 타이핑 중 불필요한 검색 방지
   - 예상 효과: UI 반응성 향상

### Phase 2: 실시간 업데이트 (2-3주)
1. **USN Journal 모니터링 스레드**
   - 백그라운드에서 변경 감지
   - 인덱스 자동 업데이트

2. **마지막 USN 위치 저장**
   - DB에 저장하여 재시작 시 이어서 처리

### Phase 3: 최종 최적화 (선택)
1. **C/C++ 네이티브 검색 모듈**
   - Python 오버헤드 제거
   - Everything 수준 성능 달성

---

## 결론

### 현재 상태
- ✅ **인덱싱 성능: Everything 수준 달성**
- ✅ **아키텍처: Everything 방식 준수**
- ⚠️ **검색 성능: 개선 필요** (Python 오버헤드)
- ❌ **실시간 업데이트: 미구현**

### 다음 단계
1. **접두사 인덱스 구현** (검색 속도 5-10배 향상)
2. **USN Journal 모니터링** (실시간 업데이트)
3. **디바운스 추가** (UI 반응성 향상)

이 세 가지를 구현하면 Everything과 거의 동일한 사용자 경험을 제공할 수 있습니다.

