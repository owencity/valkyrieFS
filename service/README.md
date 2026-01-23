# ValkyrieFS Service (Windows Service)

## 목적

- Everything 스타일 권한 모델:
  - **서비스**가 권한을 가지고 USN/MFT/실시간 반영을 담당
  - **UI**는 일반 권한으로 실행
- UI ↔ 서비스 통신은 **Named Pipe** 사용

## 개발/실행(로컬)

> 이 프로젝트는 `net8.0-windows` 기준입니다.

```powershell
cd C:\dev\valkyrie\service\ValkyrieFS.Service
dotnet build -c Release
```

## 서비스 설치(개요)

실제 배포에서는 Inno Setup에서 설치/등록까지 자동화할 예정입니다.

참고(수동):
- 서비스 등록: `sc.exe create ...`
- 서비스 시작/중지: `sc.exe start/stop ...`


