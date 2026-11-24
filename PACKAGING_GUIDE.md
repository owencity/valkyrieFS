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

#### “다시 만들어야 하나요?” 기준(아이콘)

- **설치파일(Setup.exe) 아이콘만 바꾸고 싶다**
  - Inno Setup의 `SetupIconFile`이 설치기 exe에 아이콘을 **내장**하므로, **설치기(인스톨러)를 다시 빌드해야 합니다.**
- **설치 후 프로그램의 작업표시줄/탐색기 아이콘을 바꾸고 싶다**
  - 가장 확실한 방법은 PyInstaller 빌드 시 `--icon ...ico`로 **앱 exe 아이콘을 내장**하는 것입니다.
  - 그리고 사용자가 설치해서 쓰는 흐름이라면, 새 exe가 포함되도록 **설치기도 다시 빌드/배포**하는 게 안전합니다.
  - 참고: 앱은 런타임에도 `ui/assets/valkyriefs.ico`를 창 아이콘으로 사용하도록 되어 있지만, **고정(Pin) 아이콘/탐색기 표시**는 exe 내장 아이콘 영향이 큽니다.

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

- **SmartScreen 경고(무료 배포여도 발생)**  
  - SmartScreen은 “상업용/무료”와 무관하게 **서명 없음 + 평판 없음**이면 경고가 잘 뜹니다.
  - 무료 배포에서 “구매 없이 경고를 완전히 제거”하는 방법은 현실적으로 없습니다.

- **코드 서명(Code Signing)**: SmartScreen 경고를 **줄이는 가장 확실한 방법**
  - 사내/테스트 배포: 생략 가능(경고가 뜰 수 있음)
  - 외부 공개 배포(무료 포함): 권장
    - **OV(조직 검증)**: 일반적으로 가장 많이 사용(비용/절차 중간)
    - **EV(확장 검증)**: 더 비싸지만 초기 SmartScreen 평판에 더 유리한 편
  - 권장 서명 대상: `ValkyrieFS-Setup.exe`(설치기) + `ValkyrieFS.exe`(앱)
- **관리자 권한**:
  - UI 앱을 매번 관리자 실행하는 대신, “서비스/스케줄러” 쪽에 권한을 집중시키는 것이 Everything 방식입니다.


