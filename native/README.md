# USN Journal 네이티브 모듈

Everything 수준의 성능을 제공하는 USN Journal 스캐너입니다.

## 빌드 요구사항

### Windows
- Visual Studio 2019 이상 (C++ 개발 도구)
- Python 3.8 이상
- Windows SDK

### 빌드 방법

```bash
# Visual Studio 개발자 명령 프롬프트에서
cd native
python setup.py build_ext --inplace
```

## 사용 방법

빌드가 완료되면 Python에서 사용 가능:

```python
import usn_scanner_native

# USN Journal 스캔
files = usn_scanner_native.scan_usn_journal("C:")

# 파일 정보는 딕셔너리 리스트로 반환
for file_info in files:
    print(file_info['path'])
    print(file_info['name'])
    print(file_info['size'])
```

## 성능

- 초기 인덱싱: 100만 파일을 10-30초 내에 처리
- Everything 수준의 성능

## 구현 상태

현재는 기본 구조만 구현되어 있습니다. 완전한 구현을 위해서는:
1. FSCTL_ENUM_USN_DATA로 MFT 읽기
2. FileReferenceNumber → 경로 매핑 구축
3. USN 레코드 파싱 및 필터링
4. 경로 재구성 로직

