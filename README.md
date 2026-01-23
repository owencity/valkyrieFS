# ValkyrieFS - 파일 검색 (Everything-like)

ValkyrieFS는 **Windows(NTFS)** 환경에서 Everything과 유사한 “이름 기반” 초고속 파일 검색을 목표로 하는 데스크톱 앱입니다.
UI는 **PySide6**, 인덱싱/검색은 **C++ 네이티브 모듈 + 메모리 인덱스** 중심으로 구성되어 있습니다.

핵심 철학은 Everything과 동일하게 **파일/폴더 “이름 + 경로”만 인덱싱**하고, 검색은 **메모리에서 즉시** 끝내는 것입니다.

## 현재 구현 핵심

- **초기 인덱싱(Everything식)**: NTFS 메타데이터(MFT 열거, `FSCTL_ENUM_USN_DATA`) 기반으로 볼륨을 빠르게 열거 (네이티브)
- **검색(Everything식)**: C++ 메모리 인덱스(`std::vector` + 문자열 풀링 + 보조 인덱스)에서 부분 문자열 검색
- **스냅샷 영속화**: `~/.valkyrie/index.dat`로 저장/로드하여 재실행 시 빠른 시작
- **UI 렌더링 최적화**: `QListView + QAbstractListModel + QStyledItemDelegate`(가상 리스트)
- **실시간 검색 UX**: 디바운스 + 백그라운드 검색(QThreadPool) + 이전 검색 결과 무시(generation)
- **한글 IME 대응**: 조합(preedit) 단계에서도 검색이 갱신되도록 처리

## 요구사항

- **Windows 10/11 + NTFS**
- **Python**: 네이티브 모듈(.pyd)과 동일한 버전 필요  
  - 현재 레포에는 `cp312` 산출물이 포함되어 있어 **Python 3.12** 환경이 가장 안전합니다.
- **선택(필수에 가까움)**: Visual Studio Build Tools (네이티브 모듈 빌드용)

## 설치

```bash
python -m venv venv
venv\Scripts\activate
python -m pip install -r requirements.txt
```

## 네이티브 모듈 빌드(필수)

ValkyrieFS는 **C++ 메모리 인덱스 모듈**이 없으면 실행할 수 없습니다.

```bash
cd native
python setup.py build_ext --inplace
```

성공하면 `native/` 아래에 다음 파일들이 생성됩니다:
- `usn_scanner_native*.pyd` (MFT/USN 기반 스캐너)
- `memory_index_native*.pyd` (C++ 메모리 인덱스)

자세한 내용은 [BUILD_GUIDE.md](BUILD_GUIDE.md), [USAGE_NATIVE.md](USAGE_NATIVE.md)를 참고하세요.

## 실행

패키지 실행 방식으로 실행하세요:

```bash
python -m src.main
```

## 동작 방식(요약)

- **첫 실행**
  - 스냅샷(`~/.valkyrie/index.dat`)이 없으면, 기본 설정상 `C:\` 볼륨을 스캔하여 인덱스를 생성합니다.
  - 스캔 완료 후 스냅샷을 저장합니다.
- **다음 실행**
  - 스냅샷을 로드하고 즉시 검색이 가능해집니다.

## 문서

- [ARCHITECTURE.md](ARCHITECTURE.md): 전체 아키텍처/데이터 흐름
- [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md): 디렉토리 구조/주요 파일
- [TECH_STACK.md](TECH_STACK.md): 기술 스택 정리
- [PERMISSIONS_AND_FALLBACK.md](PERMISSIONS_AND_FALLBACK.md): 권한/실행 정책(현재는 폴백 없음)

## 라이선스

개발 팀 2 내부 프로젝트

