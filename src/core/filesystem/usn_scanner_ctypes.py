"""
USN Journal 스캐너 (ctypes 기반 Python 구현)

이 모듈은 Python의 ctypes를 사용하여 Windows USN Journal을 직접 읽습니다.
Everything 수준의 성능을 목표로 합니다.

참고:
- USN Journal 접근에는 관리자 권한이 필요할 수 있습니다
- Windows NTFS 파일 시스템에서만 동작합니다
- DeviceIoControl API를 사용하여 저수준 파일 시스템 접근
"""
import ctypes
from ctypes import wintypes
from pathlib import Path
from typing import List, Optional, Callable, Dict
from datetime import datetime

from src.models.file_entry import FileEntry
from src.core.filesystem.scanner_interface import FileSystemScanner


# Windows API 상수 및 구조체 정의
GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000
FILE_SHARE_READ = 0x00000001
FILE_SHARE_WRITE = 0x00000002
OPEN_EXISTING = 3
FILE_ATTRIBUTE_NORMAL = 0x80

# IOCTL 코드
FSCTL_READ_USN_JOURNAL = 0x000900bb
FSCTL_QUERY_USN_JOURNAL = 0x000900f4
FSCTL_ENUM_USN_DATA = 0x000900b3

# USN Journal 관련 상수
USN_REASON_FILE_CREATE = 0x00000100
USN_REASON_FILE_DELETE = 0x00000200
USN_REASON_DATA_EXTEND = 0x00000002
USN_REASON_DATA_TRUNCATION = 0x00000004
USN_REASON_DATA_OVERWRITE = 0x00000001
USN_REASON_RENAME_OLD_NAME = 0x00002000
USN_REASON_RENAME_NEW_NAME = 0x00004000


class USN_RECORD_V2(ctypes.Structure):
    """
    USN Journal 레코드 구조체
    
    Windows USN Journal의 각 변경 사항을 나타냅니다.
    """
    _fields_ = [
        ("RecordLength", wintypes.DWORD),
        ("MajorVersion", wintypes.WORD),
        ("MinorVersion", wintypes.WORD),
        ("FileReferenceNumber", ctypes.c_ulonglong),
        ("ParentFileReferenceNumber", ctypes.c_ulonglong),
        ("USN", ctypes.c_longlong),
        ("TimeStamp", wintypes.LARGE_INTEGER),
        ("Reason", wintypes.DWORD),
        ("SourceInfo", wintypes.DWORD),
        ("SecurityId", wintypes.DWORD),
        ("FileAttributes", wintypes.DWORD),
        ("FileNameLength", wintypes.WORD),
        ("FileNameOffset", wintypes.WORD),
        ("FileName", wintypes.WCHAR * 1),  # 동적 크기
    ]


class READ_USN_JOURNAL_DATA_V0(ctypes.Structure):
    """
    USN Journal 읽기 요청 구조체
    """
    _fields_ = [
        ("StartUsn", ctypes.c_longlong),
        ("ReasonMask", wintypes.DWORD),
        ("ReturnOnlyOnClose", wintypes.DWORD),
        ("Timeout", ctypes.c_ulonglong),
        ("BytesToWaitFor", wintypes.DWORD),
        ("UsnJournalID", ctypes.c_ulonglong),
    ]


class USN_JOURNAL_DATA_V0(ctypes.Structure):
    """
    USN Journal 메타데이터 구조체
    """
    _fields_ = [
        ("UsnJournalID", ctypes.c_ulonglong),
        ("FirstUsn", ctypes.c_longlong),
        ("NextUsn", ctypes.c_longlong),
        ("LowestValidUsn", ctypes.c_longlong),
        ("MaxUsn", ctypes.c_longlong),
        ("MaximumSize", ctypes.c_ulonglong),
        ("AllocationDelta", ctypes.c_ulonglong),
    ]


class MFT_ENUM_DATA_V0(ctypes.Structure):
    """
    MFT 열거 데이터 구조체 (FSCTL_ENUM_USN_DATA용)
    """
    _fields_ = [
        ("StartFileReferenceNumber", ctypes.c_ulonglong),
        ("LowUsn", ctypes.c_longlong),
        ("HighUsn", ctypes.c_longlong),
    ]


class USNJournalScanner(FileSystemScanner):
    """
    USN Journal 기반 파일 시스템 스캐너
    
    Windows NTFS의 USN Journal을 직접 읽어서
    Everything 수준의 빠른 인덱싱을 제공합니다.
    
    성능:
    - 수백만 파일을 수 초 내에 인덱싱 가능
    - os.walk보다 수백 배 빠름
    
    제약사항:
    - Windows NTFS에서만 동작
    - 관리자 권한 권장
    - C 드라이브 전체 스캔 가능
    """
    
    def __init__(self):
        """
        USN Journal 스캐너 초기화
        
        Windows API를 로드합니다.
        """
        # Windows API 로드
        self.kernel32 = ctypes.windll.kernel32
        self.kernel32.CreateFileW.argtypes = [
            wintypes.LPWSTR,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.LPVOID,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.HANDLE
        ]
        self.kernel32.CreateFileW.restype = wintypes.HANDLE
        
        self.kernel32.DeviceIoControl.argtypes = [
            wintypes.HANDLE,
            wintypes.DWORD,
            wintypes.LPVOID,
            wintypes.DWORD,
            wintypes.LPVOID,
            wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD),
            wintypes.LPVOID
        ]
        self.kernel32.DeviceIoControl.restype = wintypes.BOOL
        
        self.kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        self.kernel32.CloseHandle.restype = wintypes.BOOL
    
    def scan_directory(
        self,
        root_path: str,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> List[FileEntry]:
        """
        USN Journal을 사용하여 디렉토리 스캔
        
        주의: USN Journal은 볼륨 단위로 작동하므로,
        특정 디렉토리만 스캔하는 것은 제한적입니다.
        
        Args:
            root_path: 스캔할 루트 디렉토리 경로
            progress_callback: 진행 상황 콜백 (현재 처리 수, 전체 파일 수)
            
        Returns:
            스캔된 파일 엔트리 목록
        """
        root_path_obj = Path(root_path)
        if not root_path_obj.exists():
            return []
        
        # 드라이브 루트 가져오기 (예: C:\)
        drive_letter = root_path_obj.drive
        if not drive_letter:
            # 드라이브가 없으면 홈 디렉토리에서 추론
            drive_letter = Path.home().drive
        
        # USN Journal 읽기를 위한 볼륨 핸들 열기
        # 형식: \\.\C:
        volume_path = f"\\\\.\\{drive_letter}"
        
        entries = []
        
        try:
            # 볼륨 핸들 열기
            volume_handle = self.kernel32.CreateFileW(
                volume_path,
                GENERIC_READ | GENERIC_WRITE,
                FILE_SHARE_READ | FILE_SHARE_WRITE,
                None,
                OPEN_EXISTING,
                FILE_ATTRIBUTE_NORMAL,
                None
            )
            
            if volume_handle == -1:  # INVALID_HANDLE_VALUE
                # 권한 부족 또는 USN Journal 비활성화
                # os.walk로 폴백
                return self._fallback_scan(root_path, progress_callback)
            
            # USN Journal 메타데이터 조회
            journal_data = USN_JOURNAL_DATA_V0()
            bytes_returned = wintypes.DWORD()
            
            result = self.kernel32.DeviceIoControl(
                volume_handle,
                FSCTL_QUERY_USN_JOURNAL,
                None,
                0,
                ctypes.byref(journal_data),
                ctypes.sizeof(journal_data),
                ctypes.byref(bytes_returned),
                None
            )
            
            if not result:
                # USN Journal 없음, 폴백
                self.kernel32.CloseHandle(volume_handle)
                return self._fallback_scan(root_path, progress_callback)
            
            # FSCTL_ENUM_USN_DATA로 MFT 읽기
            entries = self._enumerate_usn_records(
                volume_handle,
                journal_data,
                root_path,
                progress_callback
            )
            
            self.kernel32.CloseHandle(volume_handle)
            
            if not entries:
                # 빈 결과면 폴백
                print("USN Journal 읽기 결과 없음 → WalkScanner로 폴백")
                return self._fallback_scan(root_path, progress_callback)
            
            return entries
            
        except Exception as e:
            # 오류 발생 시 폴백
            print(f"USN Journal 접근 실패: {e} → WalkScanner로 폴백")
            try:
                if 'volume_handle' in locals() and volume_handle != -1:
                    self.kernel32.CloseHandle(volume_handle)
            except:
                pass
            return self._fallback_scan(root_path, progress_callback)
    
    def _enumerate_usn_records(
        self,
        volume_handle: int,
        journal_data: USN_JOURNAL_DATA_V0,
        root_path: str,
        progress_callback: Optional[Callable[[int, int], None]]
    ) -> List[FileEntry]:
        """
        FSCTL_ENUM_USN_DATA를 사용하여 USN 레코드 열거
        
        Args:
            volume_handle: 볼륨 핸들
            journal_data: USN Journal 메타데이터
            root_path: 필터링할 루트 경로
            progress_callback: 진행 상황 콜백
            
        Returns:
            파일 엔트리 목록
        """
        # 파일 이름 맵 (FileReferenceNumber -> 파일명)
        file_name_map: dict[int, str] = {}
        # 부모 참조 맵 (FileReferenceNumber -> ParentFileReferenceNumber)
        parent_ref_map: dict[int, int] = {}
        
        buffer_size = 1024 * 1024  # 1MB 버퍼
        buffer = ctypes.create_string_buffer(buffer_size)
        bytes_returned = wintypes.DWORD()
        
        enum_data = MFT_ENUM_DATA_V0()
        enum_data.StartFileReferenceNumber = 0  # 처음부터
        enum_data.LowUsn = 0  # 모든 USN
        enum_data.HighUsn = journal_data.MaxUsn
        
        # 첫 번째 패스: 파일 이름과 부모 관계 수집
        done = False
        total_processed = 0
        
        while not done:
            result = self.kernel32.DeviceIoControl(
                volume_handle,
                FSCTL_ENUM_USN_DATA,
                ctypes.byref(enum_data),
                ctypes.sizeof(enum_data),
                buffer,
                buffer_size,
                ctypes.byref(bytes_returned),
                None
            )
            
            if not result:
                error = ctypes.get_last_error()
                if error == 38:  # ERROR_HANDLE_EOF
                    done = True
                    break
                else:
                    # 오류 발생
                    return []
            
            # 버퍼의 첫 8바이트는 다음 시작 USN
            next_usn_ptr = ctypes.cast(buffer, ctypes.POINTER(ctypes.c_longlong))
            next_usn = next_usn_ptr.contents.value
            enum_data.StartFileReferenceNumber = next_usn
            
            # USN 레코드 파싱
            offset = ctypes.sizeof(ctypes.c_longlong)  # USN 크기
            remaining = bytes_returned.value - offset
            
            while remaining > 0:
                # 레코드 시작 위치
                record_ptr = ctypes.cast(
                    ctypes.addressof(buffer) + offset,
                    ctypes.POINTER(USN_RECORD_V2)
                )
                record = record_ptr.contents
                
                # 레코드 길이 확인
                if record.RecordLength == 0 or record.RecordLength > remaining:
                    break
                
                # 파일 이름 추출
                file_name_offset = offset + record.FileNameOffset
                name_length = record.FileNameLength // 2  # WCHAR = 2 bytes
                
                if name_length > 0 and name_length < 260:  # MAX_PATH
                    file_name_ptr = ctypes.cast(
                        ctypes.addressof(buffer) + file_name_offset,
                        ctypes.POINTER(wintypes.WCHAR * name_length)
                    )
                    file_name = ''.join(file_name_ptr.contents)
                    
                    file_ref = record.FileReferenceNumber
                    parent_ref = record.ParentFileReferenceNumber
                    
                    # 맵에 저장
                    file_name_map[file_ref] = file_name
                    parent_ref_map[file_ref] = parent_ref
                
                # 진행 상황 콜백
                total_processed += 1
                if progress_callback and total_processed % 1000 == 0:
                    progress_callback(total_processed, total_processed + 10000)
                
                # 다음 레코드로 이동
                offset += record.RecordLength
                remaining -= record.RecordLength
        
        # 두 번째 패스: 파일 정보 수집 및 경로 재구성
        enum_data.StartFileReferenceNumber = 0
        enum_data.LowUsn = 0
        enum_data.HighUsn = journal_data.MaxUsn
        done = False
        entries = []
        
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
        
        while not done:
            result = self.kernel32.DeviceIoControl(
                volume_handle,
                FSCTL_ENUM_USN_DATA,
                ctypes.byref(enum_data),
                ctypes.sizeof(enum_data),
                buffer,
                buffer_size,
                ctypes.byref(bytes_returned),
                None
            )
            
            if not result:
                error = ctypes.get_last_error()
                if error == 38:  # ERROR_HANDLE_EOF
                    done = True
                    break
                else:
                    break
            
            next_usn_ptr = ctypes.cast(buffer, ctypes.POINTER(ctypes.c_longlong))
            next_usn = next_usn_ptr.contents.value
            enum_data.StartFileReferenceNumber = next_usn
            
            offset = ctypes.sizeof(ctypes.c_longlong)
            remaining = bytes_returned.value - offset
            
            while remaining > 0:
                record_ptr = ctypes.cast(
                    ctypes.addressof(buffer) + offset,
                    ctypes.POINTER(USN_RECORD_V2)
                )
                record = record_ptr.contents
                
                if record.RecordLength == 0 or record.RecordLength > remaining:
                    break
                
                # 파일만 처리 (디렉토리 제외)
                FILE_ATTRIBUTE_DIRECTORY = 0x10
                if not (record.FileAttributes & FILE_ATTRIBUTE_DIRECTORY):
                    file_name_offset = offset + record.FileNameOffset
                    name_length = record.FileNameLength // 2
                    
                    if name_length > 0 and name_length < 260:
                        file_name_ptr = ctypes.cast(
                            ctypes.addressof(buffer) + file_name_offset,
                            ctypes.POINTER(wintypes.WCHAR * name_length)
                        )
                        file_name = ''.join(file_name_ptr.contents)
                        file_ref = record.FileReferenceNumber
                        
                        # 경로 재구성
                        full_path = self._reconstruct_path(
                            file_ref,
                            file_name_map,
                            parent_ref_map
                        )
                        
                        if full_path:
                            # 볼륨 루트 추가
                            if root_drive:
                                full_path = f"{root_drive}\\{full_path}"
                            full_path_normalized = full_path.lower()
                            
                            # 경로 필터링: 전체 볼륨이면 모든 파일 포함
                            # 특정 경로면 해당 경로만 포함
                            if is_volume_scan or full_path_normalized.startswith(root_path_normalized):
                                # 확장자 추출
                                dot_pos = file_name.rfind('.')
                                extension = file_name[dot_pos:] if dot_pos >= 0 else ""
                                
                                # 시간 변환 (FILETIME -> datetime)
                                filetime_epoch = 116444736000000000  # 1601-01-01 00:00:00
                                unix_timestamp = (record.TimeStamp.QuadPart - filetime_epoch) / 10000000
                                modified_time = datetime.fromtimestamp(unix_timestamp)
                                
                                # FileEntry 생성 (파일 크기는 별도로 가져와야 함)
                                entry = FileEntry(
                                    name=file_name,
                                    path=full_path,
                                    extension=extension,
                                    size=0,  # USN 레코드에 없음
                                    modified_time=modified_time
                                )
                                entries.append(entry)
                                
                                if progress_callback and len(entries) % 1000 == 0:
                                    progress_callback(len(entries), len(entries) + 1000)
                
                offset += record.RecordLength
                remaining -= record.RecordLength
        
        return entries
    
    def _reconstruct_path(
        self,
        file_ref: int,
        file_name_map: dict[int, str],
        parent_ref_map: dict[int, int]
    ) -> str:
        """
        FileReferenceNumber로부터 전체 경로 재구성
        
        Args:
            file_ref: 파일 참조 번호
            file_name_map: FileReferenceNumber -> 파일명 맵
            parent_ref_map: FileReferenceNumber -> 부모 참조 번호 맵
            
        Returns:
            재구성된 경로 (없으면 빈 문자열)
        """
        # 루트 참조 (일반적으로 5)
        if file_ref == 5:
            return ""
        
        path_parts = []
        current_ref = file_ref
        max_depth = 256  # 무한 루프 방지
        
        while current_ref != 0 and current_ref != 5 and max_depth > 0:
            if current_ref in file_name_map:
                path_parts.insert(0, file_name_map[current_ref])
            else:
                break
            
            if current_ref in parent_ref_map:
                current_ref = parent_ref_map[current_ref]
            else:
                break
            
            max_depth -= 1
        
        return "\\".join(path_parts)
    
    def _fallback_scan(
        self,
        root_path: str,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> List[FileEntry]:
        """
        USN Journal 접근 실패 시 os.walk로 폴백
        
        Args:
            root_path: 스캔할 경로
            progress_callback: 진행 상황 콜백
            
        Returns:
            스캔된 파일 엔트리 목록
        """
        from src.core.filesystem.walk_scanner import WalkScanner
        scanner = WalkScanner(max_workers=None)  # CPU 코어 수에 따라 자동 결정
        return scanner.scan_directory(root_path, progress_callback)
    
    def get_scanner_name(self) -> str:
        """스캐너 이름 반환"""
        return "USNJournalScanner (ctypes based)"

