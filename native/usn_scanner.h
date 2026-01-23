/*
 * USN Journal 스캐너 헤더 파일
 * 
 * Windows USN Journal을 읽어서 파일 목록을 추출하는
 * 고성능 네이티브 모듈입니다.
 * 
 * Everything 수준의 성능을 목표로 합니다.
 */

#ifndef USN_SCANNER_H
#define USN_SCANNER_H

#include <windows.h>
#include <winioctl.h>

#ifdef __cplusplus
extern "C" {
#endif

// 파일 정보 구조체
typedef struct {
    wchar_t* path;        // 전체 파일 경로
    wchar_t* name;        // 파일명
    wchar_t* extension;   // 확장자
    __int64 size;         // 파일 크기 (바이트)
    __int64 modified_time; // 수정 시간 (Unix timestamp)
} FileInfo;

// 파일 정보 배열 구조체
typedef struct {
    FileInfo* files;      // 파일 정보 배열
    size_t count;         // 파일 개수
    size_t capacity;      // 할당된 용량
} FileInfoArray;

// 콜백 함수 타입 (진행 상황 보고)
typedef void (*ProgressCallback)(size_t current, size_t total);

/*
 * 볼륨의 USN Journal을 읽어서 파일 목록을 추출
 * 
 * Args:
 *   volume_path: 볼륨 경로 (예: "C:")
 *   callback: 진행 상황 콜백 (NULL 가능)
 * 
 * Returns:
 *   FileInfoArray*: 파일 정보 배열 (사용 후 free_file_info_array로 해제)
 *   NULL: 오류 발생
 */
FileInfoArray* scan_usn_journal(const wchar_t* volume_path, ProgressCallback callback);

/*
 * 파일 정보 배열 해제
 * 
 * Args:
 *   array: 해제할 파일 정보 배열
 */
void free_file_info_array(FileInfoArray* array);

#ifdef __cplusplus
}
#endif

#endif // USN_SCANNER_H

