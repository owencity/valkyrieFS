/*
 * USN Journal 스캐너 구현
 * 
 * Windows NTFS의 USN Journal을 직접 읽어서
 * Everything 수준의 빠른 파일 인덱싱을 제공합니다.
 * 
 * 성능:
 * - 수백만 파일을 수 초 내에 인덱싱
 * - os.walk보다 수백 배 빠름
 * 
 * 요구사항:
 * - Windows NTFS 파일 시스템
 * - 관리자 권한 권장 (볼륨 핸들 접근)
 */

#include "usn_scanner.h"
#include <windows.h>
#include <winioctl.h>
#include <vector>
#include <map>
#include <string>
#include <algorithm>
#include <cstdlib>
#include <cstring>

// Windows API는 winioctl.h에 이미 정의되어 있음
// 중복 정의 제거

// 파일 정보 맵 (경로 재구성을 위해)
std::map<DWORDLONG, std::wstring> file_name_map;
std::map<DWORDLONG, DWORDLONG> parent_ref_map;

// 볼륨 핸들 열기
HANDLE open_volume(const wchar_t* volume_path) {
    wchar_t volume_name[MAX_PATH];
    
    // 볼륨 경로 정규화 (C: 또는 C:\ -> \\.\C:)
    std::wstring vol_path(volume_path);
    // 백슬래시 제거 (C:\ -> C:)
    while (!vol_path.empty() && (vol_path.back() == L'\\' || vol_path.back() == L'/')) {
        vol_path.pop_back();
    }
    
    swprintf_s(volume_name, MAX_PATH, L"\\\\.\\%s", vol_path.c_str());
    
    // Everything처럼 GENERIC_READ만으로 먼저 시도
    // 관리자 권한 없이도 읽기 가능할 수 있음
    HANDLE handle = CreateFileW(
        volume_name,
        GENERIC_READ,  // Everything은 READ만 사용
        FILE_SHARE_READ | FILE_SHARE_WRITE,
        NULL,
        OPEN_EXISTING,
        FILE_ATTRIBUTE_NORMAL,
        NULL
    );
    
    // READ만으로 실패하면 WRITE 권한 추가하여 재시도
    if (handle == INVALID_HANDLE_VALUE) {
        DWORD error = GetLastError();
        if (error == ERROR_ACCESS_DENIED || error == 5) {
            // 관리자 권한 필요 - READ | WRITE로 재시도
            handle = CreateFileW(
                volume_name,
                GENERIC_READ | GENERIC_WRITE,
                FILE_SHARE_READ | FILE_SHARE_WRITE,
                NULL,
                OPEN_EXISTING,
                FILE_ATTRIBUTE_NORMAL,
                NULL
            );
        }
    }
    
    // 오류가 발생하면 마지막 오류 코드 보존
    if (handle == INVALID_HANDLE_VALUE) {
        // GetLastError()는 호출자가 확인할 수 있도록 유지됨
    }
    
    return handle;
}

// USN Journal 메타데이터 조회
bool query_usn_journal(HANDLE volume_handle, USN_JOURNAL_DATA_V0* journal_data) {
    DWORD bytes_returned = 0;
    
    BOOL result = DeviceIoControl(
        volume_handle,
        FSCTL_QUERY_USN_JOURNAL,
        NULL,
        0,
        journal_data,
        sizeof(USN_JOURNAL_DATA_V0),
        &bytes_returned,
        NULL
    );
    
    return result != FALSE;
}

// 배열 확장 (성능 최적화: 더 큰 단위로 확장)
void expand_array(FileInfoArray* array) {
    // Everything 수준: 더 큰 단위로 확장하여 재할당 횟수 감소
    size_t new_capacity = array->capacity * 2;
    // 최대 100만까지는 2배씩, 그 이후는 1.5배씩 확장 (메모리 효율성)
    if (new_capacity > 1000000) {
        new_capacity = array->capacity + (array->capacity / 2);
    }
    array->files = (FileInfo*)realloc(array->files, sizeof(FileInfo) * new_capacity);
    array->capacity = new_capacity;
}

// 경로 재구성 (FileReferenceNumber → 전체 경로)
std::wstring reconstruct_path(DWORDLONG file_ref) {
    std::vector<std::wstring> path_parts;
    DWORDLONG current_ref = file_ref;
    
    // 루트 참조 (일반적으로 5)
    if (current_ref == 5) {
        return L"";
    }
    
    // 부모를 따라 올라가면서 경로 구성
    int max_depth = 256;  // 무한 루프 방지
    while (current_ref != 0 && current_ref != 5 && max_depth-- > 0) {
        if (file_name_map.find(current_ref) != file_name_map.end()) {
            path_parts.insert(path_parts.begin(), file_name_map[current_ref]);
        } else {
            // 이름을 찾을 수 없으면 중단
            break;
        }
        
        if (parent_ref_map.find(current_ref) != parent_ref_map.end()) {
            current_ref = parent_ref_map[current_ref];
        } else {
            break;
        }
    }
    
    // 경로 조합
    std::wstring full_path;
    for (size_t i = 0; i < path_parts.size(); i++) {
        if (i > 0) full_path += L"\\";
        full_path += path_parts[i];
    }
    
    return full_path;
}

// 파일 정보 추가 (배열 확장 포함)
void add_file_info(
    FileInfoArray* array,
    const wchar_t* full_path,
    const wchar_t* file_name,
    const wchar_t* extension,
    __int64 size,
    __int64 modified_time
) {
    // 배열 확장 필요 시
    if (array->count >= array->capacity) {
        expand_array(array);
    }
    
    FileInfo* info = &array->files[array->count];
    
    // 문자열 복사 (메모리 할당)
    size_t path_len = wcslen(full_path);
    info->path = (wchar_t*)malloc((path_len + 1) * sizeof(wchar_t));
    wcscpy_s(info->path, path_len + 1, full_path);
    
    size_t name_len = wcslen(file_name);
    info->name = (wchar_t*)malloc((name_len + 1) * sizeof(wchar_t));
    wcscpy_s(info->name, name_len + 1, file_name);
    
    size_t ext_len = wcslen(extension);
    info->extension = (wchar_t*)malloc((ext_len + 1) * sizeof(wchar_t));
    wcscpy_s(info->extension, ext_len + 1, extension);
    
    info->size = size;
    info->modified_time = modified_time;
    
    array->count++;
}

// USN Journal 읽기 및 파일 목록 추출
FileInfoArray* scan_usn_journal(const wchar_t* volume_path, ProgressCallback callback) {
    // 맵 초기화
    file_name_map.clear();
    parent_ref_map.clear();
    
    // 볼륨 핸들 열기
    HANDLE volume_handle = open_volume(volume_path);
    if (volume_handle == INVALID_HANDLE_VALUE) {
        // 오류 코드 보존 - GetLastError()는 이미 설정됨
        SetLastError(GetLastError());  // 명시적으로 오류 보존
        return NULL;
    }
    
    // USN Journal 메타데이터 조회
    USN_JOURNAL_DATA_V0 journal_data;
    if (!query_usn_journal(volume_handle, &journal_data)) {
        DWORD error = GetLastError();
        CloseHandle(volume_handle);
        SetLastError(error);  // 오류 코드 보존
        return NULL;
    }
    
    // 파일 정보 배열 초기화
    FileInfoArray* result = (FileInfoArray*)malloc(sizeof(FileInfoArray));
    if (result == NULL) {
        CloseHandle(volume_handle);
        return NULL;
    }
    
    result->count = 0;
    result->capacity = 100000;  // 초기 용량 증가 (Everything 수준: 대량 파일 대비)
    result->files = (FileInfo*)malloc(sizeof(FileInfo) * result->capacity);
    if (result->files == NULL) {
        free(result);
        CloseHandle(volume_handle);
        return NULL;
    }
    
    // FSCTL_ENUM_USN_DATA로 MFT 열거
    // Everything 수준 성능: 더 큰 버퍼로 I/O 횟수 감소
    const DWORD buffer_size = 4 * 1024 * 1024;  // 4MB 버퍼 (기존 1MB → 4배 증가)
    BYTE* buffer = (BYTE*)malloc(buffer_size);
    if (buffer == NULL) {
        free(result->files);
        free(result);
        CloseHandle(volume_handle);
        return NULL;
    }
    
    MFT_ENUM_DATA_V0 enum_data;
    enum_data.StartFileReferenceNumber = 0;  // 처음부터
    enum_data.LowUsn = 0;  // 모든 USN
    enum_data.HighUsn = journal_data.MaxUsn;
    
    DWORD bytes_returned = 0;
    size_t total_processed = 0;
    
    // 첫 번째 패스: 파일 이름과 부모 관계 수집
    bool done = false;
    while (!done) {
        if (!DeviceIoControl(
            volume_handle,
            FSCTL_ENUM_USN_DATA,
            &enum_data,
            sizeof(enum_data),
            buffer,
            buffer_size,
            &bytes_returned,
            NULL
        )) {
            DWORD error = GetLastError();
            if (error == ERROR_HANDLE_EOF) {
                done = true;
                break;
            } else {
                // 오류 발생
                free(buffer);
                free(result->files);
                free(result);
                CloseHandle(volume_handle);
                return NULL;
            }
        }
        
        // 버퍼의 첫 8바이트는 다음 시작 참조 번호
        USN* next_usn = (USN*)buffer;
        enum_data.StartFileReferenceNumber = *next_usn;
        
        // USN 레코드 파싱
        BYTE* ptr = buffer + sizeof(USN);
        DWORD remaining = bytes_returned - sizeof(USN);
        
        while (remaining > 0) {
            USN_RECORD_V2* record = (USN_RECORD_V2*)ptr;
            
            // 레코드 길이 확인
            if (record->RecordLength == 0 || record->RecordLength > remaining) {
                break;
            }
            
            // 파일 이름 추출
            WCHAR* file_name_ptr = (WCHAR*)((BYTE*)record + record->FileNameOffset);
            int name_len = record->FileNameLength / sizeof(WCHAR);
            
            if (name_len > 0 && name_len < MAX_PATH) {
                std::wstring file_name(file_name_ptr, name_len);
                DWORDLONG file_ref = record->FileReferenceNumber;
                DWORDLONG parent_ref = record->ParentFileReferenceNumber;
                
                // 맵에 저장
                file_name_map[file_ref] = file_name;
                parent_ref_map[file_ref] = parent_ref;
            }
            
            // 진행 상황 콜백
            total_processed++;
            if (callback && (total_processed % 1000 == 0)) {
                // 대략적인 진행 상황 (정확한 총 개수는 미리 알 수 없음)
                callback(total_processed, total_processed + 10000);
            }
            
            // 다음 레코드로 이동
            ptr += record->RecordLength;
            remaining -= record->RecordLength;
        }
    }
    
    // 두 번째 패스: 파일 정보 수집 및 경로 재구성
    enum_data.StartFileReferenceNumber = 0;
    enum_data.LowUsn = 0;
    enum_data.HighUsn = journal_data.MaxUsn;
    done = false;
    
    while (!done) {
        bytes_returned = 0;
        if (!DeviceIoControl(
            volume_handle,
            FSCTL_ENUM_USN_DATA,
            &enum_data,
            sizeof(enum_data),
            buffer,
            buffer_size,
            &bytes_returned,
            NULL
        )) {
            DWORD error = GetLastError();
            if (error == ERROR_HANDLE_EOF) {
                done = true;
                break;
            } else {
                break;
            }
        }
        
        if (bytes_returned < sizeof(USN)) {
            break;
        }
        
        USN* next_usn = (USN*)buffer;
        enum_data.StartFileReferenceNumber = *next_usn;
        
        BYTE* ptr = buffer + sizeof(USN);
        DWORD remaining = bytes_returned - sizeof(USN);
        
        while (remaining >= sizeof(USN_RECORD_V2)) {
            USN_RECORD_V2* record = (USN_RECORD_V2*)ptr;
            
            if (record->RecordLength == 0 || record->RecordLength > remaining) {
                break;
            }
            
            // Everything 방식: 파일과 폴더 모두 인덱싱
            // 디렉토리도 포함하여 Everything과 동일한 결과 생성
            // FILE_ATTRIBUTE_DIRECTORY는 이미 winnt.h에 정의되어 있음
            bool is_directory = (record->FileAttributes & FILE_ATTRIBUTE_DIRECTORY) != 0;
            
            WCHAR* file_name_ptr = (WCHAR*)((BYTE*)record + record->FileNameOffset);
            int name_len = record->FileNameLength / sizeof(WCHAR);
            
            if (name_len > 0 && name_len < MAX_PATH) {
                std::wstring file_name(file_name_ptr, name_len);
                DWORDLONG file_ref = record->FileReferenceNumber;
                
                // 경로 재구성
                std::wstring full_path = reconstruct_path(file_ref);
                if (!full_path.empty()) {
                    // 볼륨 루트 추가 (예: "C:")
                    std::wstring volume_root(volume_path);
                    if (volume_root.back() != L'\\') {
                        volume_root += L"\\";
                    }
                    full_path = volume_root + full_path;
                    
                    // 확장자 추출 (폴더는 확장자 없음)
                    size_t dot_pos = file_name.find_last_of(L'.');
                    std::wstring extension = (dot_pos != std::wstring::npos && !is_directory) 
                        ? file_name.substr(dot_pos) 
                        : L"";
                    
                    // Everything 방식: 파일과 폴더 모두 처리
                    // 시간 변환 (FILETIME -> Unix timestamp)
                    __int64 unix_time = 0;
                    if (record->TimeStamp.QuadPart != 0) {
                        // FILETIME은 1601-01-01부터 100-nanosecond 간격
                        // Unix timestamp는 1970-01-01부터 초 단위
                        const __int64 FILETIME_EPOCH = 116444736000000000LL;
                        unix_time = (record->TimeStamp.QuadPart - FILETIME_EPOCH) / 10000000;
                    }
                    
                    // 파일 크기: 폴더는 0, 파일은 별도로 가져와야 함 (USN 레코드에 없음)
                    __int64 file_size = 0;
                    
                    add_file_info(
                        result,
                        full_path.c_str(),
                        file_name.c_str(),
                        extension.c_str(),
                        file_size,
                        unix_time
                    );
                    
                    // 진행 상황 콜백
                    if (callback && (result->count % 1000 == 0)) {
                        callback(result->count, result->count + 10000);
                    }
                }
            }
            
            ptr += record->RecordLength;
            remaining -= record->RecordLength;
        }
    }
    
    free(buffer);
    CloseHandle(volume_handle);
    return result;
}

// 파일 정보 배열 해제
void free_file_info_array(FileInfoArray* array) {
    if (array == NULL) return;
    
    for (size_t i = 0; i < array->count; i++) {
        if (array->files[i].path) free(array->files[i].path);
        if (array->files[i].name) free(array->files[i].name);
        if (array->files[i].extension) free(array->files[i].extension);
    }
    
    free(array->files);
    free(array);
}

