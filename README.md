# ValkyrieFS - 파일 검색 (Everything-like)

![ValkyrieFS 로고](src/ui/assets/valkyriefs-wing.svg)

ValkyrieFS는 **Windows(NTFS)** 환경에서 Everything과 유사한 “이름 기반” 초고속 파일 검색을 목표로 하는 데스크톱 앱입니다.

개인 사이드 프로젝트로, **빠른 검색/깔끔한 UI/키보드 중심 UX**에 집중합니다.

## 다운로드 (설치파일)

설치파일은 **GitHub Releases**에서 다운로드합니다.

- **바로 다운로드(클릭 즉시 다운로드)**: [ValkyrieFS-Setup.exe 다운로드](https://github.com/owencity/valkyrieFS/releases/latest/download/ValkyrieFS-Setup.exe)
- **최신 릴리즈 페이지**: [Releases (latest)](https://github.com/owencity/valkyrieFS/releases/latest)
- **릴리즈 목록**: [Releases](https://github.com/owencity/valkyrieFS/releases)

위 “바로 다운로드”를 누르면 `ValkyrieFS-Setup.exe`가 즉시 내려받아집니다.

## 설치/실행

1. `ValkyrieFS-Setup.exe` 실행
2. 베타 버전이라 Windows에서 “보호됨” 경고가 뜰 수 있습니다.  
   - **“추가 정보” → “실행”**을 눌러 진행하세요.
3. 설치 과정에서 **1회 UAC(권한 승인)**가 뜰 수 있습니다. (Everything 스타일: 서비스 등록/시작)
4. 설치 완료 후 **관리자 권한 없이** ValkyrieFS를 실행해서 사용합니다.

## 프로그램 설명

ValkyrieFS는 파일 내용이 아니라 **파일/폴더 이름(및 경로)** 기반으로 검색합니다.
그래서 대량 파일 환경에서도 빠르게 동작하는 것을 목표로 합니다.

### 주요 기능(베타)

- **즉시 검색**: 입력과 동시에 결과 업데이트(디바운스 적용)
- **키보드 중심 UX**: `Ctrl+L`(검색 포커스), `Esc`(지우기), `Enter`(열기)
- **한글 IME 입력 대응**: 조합 중에도 검색 결과 갱신
- **대량 결과 UI 최적화**: 가상 리스트 렌더링으로 끊김 최소화
- **권한 모델(Everything 스타일)**: 설치 시 권한 승인 후, 실행은 일반 권한

## 요구사항

- **Windows 10/11 + NTFS**

## 개발자 문서(개발/빌드/배포)

- [PACKAGING_GUIDE.md](PACKAGING_GUIDE.md): 빌드/배포(onedir + 설치기)
- [SERVICE_MODEL.md](SERVICE_MODEL.md): Everything 스타일 권한 모델(UI + 서비스 + IPC)
- [ARCHITECTURE.md](ARCHITECTURE.md): 전체 아키텍처/데이터 흐름
- [TECH_STACK.md](TECH_STACK.md): 기술 스택
- [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md): 디렉토리 구조

## 라이선스

개인 사이드 프로젝트

