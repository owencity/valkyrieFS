"""
USN Journal 스캐너 (네이티브 C/C++ 모듈 사용)

이 모듈은 C/C++로 작성된 USN Journal 스캐너를
Python에서 사용하기 위한 래퍼입니다.

Everything 수준의 성능을 제공합니다.
"""
import sys
from pathlib import Path
from typing import List, Optional, Callable, Dict, Any
from datetime import datetime

from src.models.file_entry import FileEntry
from src.core.filesystem.scanner_interface import FileSystemScanner

# native 디렉토리를 Python 경로에 추가
_native_dir = Path(__file__).parent.parent.parent.parent / "native"
if _native_dir.exists() and str(_native_dir) not in sys.path:
    sys.path.insert(0, str(_native_dir))

try:
    # 네이티브 모듈 import 시도
    import usn_scanner_native
    NATIVE_MODULE_AVAILABLE = True
except ImportError as e:
    # 네이티브 모듈이 없으면 사용 불가
    NATIVE_MODULE_AVAILABLE = False
    usn_scanner_native = None
    # 디버깅을 위한 정보 (개발 중에만 표시)
    import warnings
    warnings.warn(f"네이티브 USN Journal 모듈을 로드할 수 없습니다: {e}")


class USNJournalScannerNative(FileSystemScanner):
    """
    USN Journal 네이티브 스캐너
    
    C/C++로 작성된 고성능 USN Journal 스캐너를 사용합니다.
    Everything 수준의 성능을 제공합니다.
    
    성능:
    - 수백만 파일을 수 초 내에 인덱싱
    - os.walk보다 수백 배 빠름
    
    요구사항:
    - 네이티브 모듈이 빌드되어 있어야 함 (native/usn_scanner_native.pyd)
    - Windows NTFS 파일 시스템
    - 관리자 권한 권장
    """
    
    def __init__(self):
        """
        네이티브 스캐너 초기화
        
        네이티브 모듈이 사용 가능한지 확인합니다.
        """
        if not NATIVE_MODULE_AVAILABLE:
            raise ImportError(
                "Native USN Journal scanner module not available. "
                "Please build it first using: python native/setup.py build_ext --inplace"
            )
    
    def scan_directory(
        self,
        root_path: str,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> List[Dict[str, Any]]:
        """
        USN Journal을 사용하여 디렉토리 스캔
        
        주의: USN Journal은 볼륨 단위로 작동하므로,
        특정 디렉토리만 스캔하는 것은 제한적입니다.
        
        Args:
            root_path: 스캔할 루트 디렉토리 경로
            progress_callback: 진행 상황 콜백 (현재 처리 수, 전체 파일 수)
            
        Returns:
            스캔된 파일 정보 딕셔너리 목록
            (C++ 메모리 인덱스에 바로 넣기 위한 형태)
        """
        root_path_obj = Path(root_path)
        if not root_path_obj.exists():
            return []
        
        # 드라이브 루트 가져오기 (예: "C:")
        drive_letter = root_path_obj.drive
        if not drive_letter:
            drive_letter = Path.home().drive
        
        # 드라이브 루트만 추출 (예: "C:" 또는 "C:\" -> "C:")
        # USN Journal은 드라이브 루트만 필요
        volume_path = drive_letter.rstrip('\\').rstrip('/')
        if not volume_path.endswith(':'):
            # "C:" 형식으로 정규화
            volume_path = drive_letter.split(':')[0] + ':'
        
        try:
            print(f"  [USN Journal] 볼륨 경로: {volume_path}")
            print(f"  [USN Journal] 스캔 시작 중...")
            
            # 네이티브 모듈로 USN Journal 스캔
            # 주의: 관리자 권한이 필요할 수 있습니다
            file_list = usn_scanner_native.scan_usn_journal(volume_path)
            
            if file_list:
                print(f"  [USN Journal] {len(file_list):,}개 파일 발견")
            else:
                print(f"  [USN Journal] 스캔 결과 없음")
            
            # 빈 리스트인 경우 오류 발생 (폴백 없음)
            if not file_list or len(file_list) == 0:
                raise RuntimeError(
                    "USN Journal/MFT 스캔 결과 없음. "
                    "관리자 권한으로 실행하거나 USN Journal이 활성화되어 있는지 확인하세요."
                )
            
            # 경로 필터링 설정
            # USN Journal은 볼륨 전체를 스캔하므로, 요청한 경로만 필터링
            root_path_obj = Path(root_path)
            root_path_normalized = str(root_path_obj.resolve()).lower().rstrip('\\')
            root_drive = root_path_obj.drive.upper()
            
            # 전체 볼륨 스캔인지 확인 (예: "C:" 또는 "C:\")
            # 홈 디렉토리 전체 스캔도 전체 드라이브 스캔으로 처리
            is_volume_scan = (
                len(root_path_normalized) <= len(root_drive) + 1 or
                root_path_normalized.endswith('\\users\\' + Path.home().name.lower()) or
                root_path_normalized == str(Path.home()).lower()
            )
            
            # Python에서 FileEntry를 100만개 단위로 만드는 것은 병목이므로
            # C++ 메모리 인덱스에 바로 넣을 수 있는 dict 리스트를 그대로 반환합니다.
            
            # 경로 필터링 및 FileEntry 생성 (최적화된 루프)
            # Everything 수준 성능: 리스트 컴프리헨션으로 대량 처리 최적화
            processed_count = 0
            total_files = len(file_list)
            
            # 사전 필터링: 전체 볼륨 스캔이 아니면 경로 필터링
            if not is_volume_scan:
                # 경로 필터링을 먼저 수행하여 불필요한 처리 제거
                filtered_list = [
                    fi for fi in file_list
                    if fi.get('path', '').lower().startswith(root_path_normalized)
                ]
                file_list = filtered_list
                total_files = len(file_list)
            
            # 진행 상황 콜백: 스캔이 끝난 뒤 Python 처리 단계는 최소화했으므로
            # 마지막 완료만 보장합니다.
            if progress_callback:
                progress_callback(total_files, total_files)
            
            return file_list
            
        except Exception as e:
            # 오류 발생 시 예외 전파 (폴백 없음 - MFT/USN Journal만 사용)
            error_msg = str(e)
            print(f"\n[USN Journal/MFT 스캔 실패]")
            print(f"  볼륨: {volume_path}")
            print(f"  오류: {error_msg}")
            if "Access denied" in error_msg or "권한" in error_msg:
                print(f"  → 관리자 권한이 필요합니다.")
            elif "not found" in error_msg.lower() or "찾을 수 없" in error_msg:
                print(f"  → 볼륨을 찾을 수 없습니다.")
            elif "Invalid parameter" in error_msg or "USN Journal" in error_msg:
                print(f"  → USN Journal이 비활성화되어 있을 수 있습니다.")
            print(f"  → Everything 방식: MFT/USN Journal만 사용합니다.\n")
            raise  # 예외 전파하여 사용자에게 알림
    
    
    def get_scanner_name(self) -> str:
        """스캐너 이름 반환"""
        return "USNJournalScannerNative (C/C++ based)"

