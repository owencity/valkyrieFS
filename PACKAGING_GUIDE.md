# ValkyrieFS 배포(설치파일) 가이드

## 목표

- **Windows 단일 실행 파일(exe)** 생성 (PyInstaller)
- 필요 시 **설치파일(.exe installer)** 생성 (Inno Setup/NSIS)
- 네이티브 모듈(`*.pyd`)과 리소스(아이콘/SVG)를 함께 포함

> 주의: 이 프로젝트는 **네이티브 모듈이 필수**입니다. (`memory_index_native`, `usn_scanner_native`)

---

## 0) 사전 준비

- Python 버전: 네이티브 모듈과 동일한 버전 권장 (현재 `cp312`이면 Python 3.12)
- Visual Studio Build Tools(선택): 네이티브 모듈을 새로 빌드할 경우 필요

---

## 1) 네이티브 모듈 빌드

```powershell
cd C:\dev\valkyrie\native
python setup.py build_ext --inplace
```

생성 확인:
- `native\usn_scanner_native*.pyd`
- `native\memory_index_native*.pyd`

---

## 2) PyInstaller로 exe 만들기

### 권장: onedir(폴더형 배포본) — 안정성/성능 우선

프로젝트 루트에서 실행:

```powershell
cd C:\dev\valkyrie
python -m pip install pyinstaller

pyinstaller --noconfirm --clean -w `
  -n ValkyrieFS `
  --add-data "src\ui\assets;src\ui\assets" `
  --add-binary "native\*.pyd;native" `
  --hidden-import PySide6.QtSvg `
  -p native `
  -p src `
  src\main.py
```

산출물:
- `dist\ValkyrieFS\ValkyrieFS.exe` (폴더 안에 `.pyd`, Qt DLL 등 포함)

### 아이콘(중요)

Windows exe/설치 아이콘은 **.ico**가 가장 안정적입니다.
- 현재 앱 내부 아이콘은 SVG를 사용하지만,
- PyInstaller `--icon`은 보통 `.ico`를 권장합니다.

권장 절차:
- `src/ui/assets/valkyriefs.ico` 파일을 준비(로고 SVG → ICO 변환)
- PyInstaller 빌드 시 `--icon`으로 ICO 지정
- Inno Setup에서도 `SetupIconFile`로 ICO 지정(설치기 아이콘)

PyInstaller 예시(onedir):
```powershell
pyinstaller --noconfirm --clean -w `
  -n ValkyrieFS `
  --icon "src\ui\assets\valkyriefs.ico" `
  --add-data "src\ui\assets;src\ui\assets" `
  --add-binary "native\*.pyd;native" `
  --hidden-import PySide6.QtSvg `
  -p native `
  -p src `
  src\main.py
```

---

## 3) 설치파일(.exe installer) 만들기 (선택)

### Inno Setup(추천)

- Inno Setup 설치 후,
- `dist\ValkyrieFS.exe`를 포함하는 스크립트를 작성합니다.
- 설치 경로: `Program Files\ValkyrieFS`
- 시작 메뉴/바탕화면 바로가기 생성
 - Everything 스타일 권한 모델을 위해 **서비스 등록/시작** 단계 포함

> 추가로 **VC++ 런타임**이 필요한 환경이 있을 수 있습니다(네이티브 모듈이 `/MD`로 빌드됨).
> 가장 안전하게 가려면 설치 프로그램에 **Microsoft Visual C++ Redistributable(x64)** 설치 단계를 포함하세요.

템플릿:
- `installer/ValkyrieFS.iss`

---

## 4) “권한 부여(Everything 방식)” — 실행 때마다 관리자 실행하지 않기

팀장님 요구사항(“실행 때마다 관리자 권한 X, 설치할 때 권한이 부여된 것처럼”)을 만족하려면
**Everything과 동일한 구조**로 가야 합니다:

- **권한을 가진 백그라운드 프로세스(서비스)** 가 USN/MFT 접근 및 실시간 변경(USN Journal 모니터링)을 담당
- **UI는 일반 권한으로 실행**하고, 서비스에 IPC로 요청(검색/상태/갱신)을 보냄

### 옵션 A) Windows Service(추천)
- 장점: 가장 Everything에 가까움(항상 동작, 권한/보안 모델 명확)
- 단점: 구현/배포가 다소 복잡(설치/업데이트/IPC 설계 필요)

설치기에서 해야 할 일(개요):
- 서비스 바이너리 설치
- `sc.exe create`로 서비스 등록(예: LocalSystem)
- 부팅 시 자동 시작
- 언인스톨 시 서비스 중지/삭제

### 옵션 B) 작업 스케줄러(대안)
- 로그인 시 “최상위 권한”으로 백그라운드 프로세스 실행
- 서비스보다 구현은 쉬우나, 관리/안정성은 서비스가 더 좋음

---

## 5) “등록” 관련(선택/권장)

- **코드 서명(Code Signing)**: SmartScreen 경고를 줄이려면 필요
  - 개인/테스트 배포: 생략 가능(경고 뜰 수 있음)
  - 외부 배포: 권장(특히 EV Code Signing이면 효과 큼)
- **관리자 권한**:
  - UI 앱을 매번 관리자 실행하는 대신, “서비스/스케줄러” 쪽에 권한을 집중시키는 것이 Everything 방식입니다.


