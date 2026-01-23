# ValkyrieFS 권한 모델(Everything 방식) 제안

## 목표

- 사용자는 **일반 권한으로 ValkyrieFS UI를 실행**
- 설치 시점에만 권한을 승인하여, 이후에는 **매번 “관리자 권한으로 실행”을 요구하지 않음**
- Everything처럼 **USN/MFT 기반 인덱싱 + USN Journal 기반 실시간 반영**을 지속

---

## 핵심 아이디어: 2프로세스(또는 2컴포넌트)

### 1) ValkyrieFS UI (일반 권한)
- PySide6 UI
- 검색 입력/결과 렌더링
- 인덱스/USN를 직접 만지지 않음(권한 문제 제거)

### 2) ValkyrieFS Service (권한 보유)
- **C# Windows Service**로 설치(예: LocalSystem)
- 담당 업무
  - 초기 인덱싱(MFT 열거)
  - 실시간 반영(USN Journal 모니터링)
  - C++ 메모리 인덱스 유지/스냅샷 저장
  - UI 요청 처리(검색/통계/상태)

UI ↔ Service 통신은 IPC로 처리:
- **Named Pipe(권장)** 또는 Localhost TCP(127.0.0.1)

---

## 왜 이 구조가 “Everything처럼 보이냐”

- 권한은 서비스가 가지고 있으므로 UI는 매번 관리자 실행을 요구하지 않음
- 인덱스가 항상 살아있어서, UI는 “검색만” 하면 됨(즉각 반응)

---

## 우리 코드에 맞춘 단계별 구현 순서(현실적인 로드맵)

### Phase A (빠른 체감)
- 서비스는 우선 “인덱스 로드 + 검색 요청 처리”만 수행
- UI는 로컬 스냅샷을 직접 로드하지 않고 서비스에 검색 요청

### Phase B (Everything 핵심)
- 서비스에 USN Journal 모니터링 추가
- 메모리 인덱스에 upsert/delete/rename/move API 추가

### Phase C (완성도)
- 설치기(Inno Setup)에서 서비스 등록/제거 자동화
- 코드서명/VC++ 런타임 포함으로 배포 안정화


