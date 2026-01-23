/*
 * 메모리 기반 파일 인덱스 관리
 * 
 * Everything 수준의 성능을 위해 RAM에 모든 인덱스를 저장합니다.
 * 
 * 최적화 기법:
 * - 문자열 풀링: 경로 중복 제거
 * - 비트 필드: 파일 속성 최소화
 * - 메모리 매핑 파일: Snapshot 방식
 */

#ifndef MEMORY_INDEX_H
#define MEMORY_INDEX_H

#include <windows.h>
#include <vector>
#include <string>
#include <unordered_map>
#include <cstdint>

#ifdef __cplusplus
extern "C" {
#endif

// 파일 엔트리 구조체 (최적화된 크기)
// Everything 방식: 최소 메모리 사용
typedef struct {
    uint32_t name_offset;      // 문자열 풀 내 이름 오프셋
    uint32_t path_offset;       // 문자열 풀 내 경로 오프셋
    uint32_t extension_offset;  // 문자열 풀 내 확장자 오프셋
    uint64_t size;              // 파일 크기
    int64_t modified_time;      // 수정 시간 (Unix timestamp)
    uint16_t flags;             // 비트 필드: 디렉토리 여부 등
} FileEntry;

// 검색 결과 구조체
typedef struct {
    uint32_t* indices;         // 매칭된 파일 인덱스 배열
    size_t count;               // 결과 개수
    size_t capacity;            // 할당된 용량
} SearchResult;

// 메모리 인덱스 관리자
class MemoryIndex {
public:
    MemoryIndex();
    ~MemoryIndex();
    
    // 파일 추가
    void add_file(
        const wchar_t* path,
        const wchar_t* name,
        const wchar_t* extension,
        uint64_t size,
        int64_t modified_time,
        bool is_directory
    );
    
    // 인덱스 빌드 완료 (검색 최적화 구조 생성)
    void build_index();
    
    // 검색 수행
    SearchResult* search(const wchar_t* query, size_t max_results);
    
    // 검색 결과 해제
    void free_search_result(SearchResult* result);
    
    // Snapshot 저장 (메모리 매핑 파일)
    bool save_snapshot(const wchar_t* file_path);
    
    // Snapshot 로드 (메모리 매핑 파일)
    bool load_snapshot(const wchar_t* file_path);
    
    // 인덱스 통계
    size_t get_file_count() const { return entries.size(); }
    size_t get_memory_size() const;
    
    // 인덱스 초기화
    void clear();
    
    // 파일 정보 가져오기 (Python 바인딩용)
    bool get_file_info(size_t index, wchar_t* path_buf, size_t path_buf_size,
                       wchar_t* name_buf, size_t name_buf_size,
                       wchar_t* ext_buf, size_t ext_buf_size,
                       uint64_t* size, int64_t* modified_time) const;

private:
    // 파일 엔트리 배열
    std::vector<FileEntry> entries;

    // 경로 오프셋 -> 엔트리 인덱스 (중복 방지 / 업데이트용)
    std::unordered_map<uint32_t, uint32_t> path_index_map;
    
    // 문자열 풀 (경로 중복 제거)
    std::vector<wchar_t> string_pool;
    std::unordered_map<std::wstring, uint32_t> string_map;
    
    // 접두사 인덱스 (검색 최적화)
    std::unordered_map<wchar_t, std::vector<uint32_t>> prefix_index;

    // 문자 포함 인덱스 (Everything처럼 1~2글자 검색을 빠르게)
    // key 문자(anywhere) -> 해당 문자를 포함하는 파일 인덱스 목록
    std::unordered_map<wchar_t, std::vector<uint32_t>> char_index;
    
    // 소문자 파일명 배열 (검색 최적화)
    std::vector<std::wstring> name_lower;
    
    // 문자열 풀에 추가하고 오프셋 반환
    uint32_t add_to_string_pool(const std::wstring& str);
    
    // 문자열 풀에서 가져오기
    const wchar_t* get_string_from_pool(uint32_t offset) const;
    
    // 접두사 인덱스 구축
    void build_prefix_index();

    // 문자 포함 인덱스 구축
    void build_char_index();

    // 스냅샷 로드 후 문자열 맵 복원
    void rebuild_string_map_from_pool();

    // 스냅샷/레거시 데이터 중복 제거
    void deduplicate_entries_by_path();
};

// C 인터페이스 (Python 바인딩용)
typedef void* MemoryIndexHandle;

MemoryIndexHandle create_memory_index();
void destroy_memory_index(MemoryIndexHandle handle);
void memory_index_add_file(
    MemoryIndexHandle handle,
    const wchar_t* path,
    const wchar_t* name,
    const wchar_t* extension,
    uint64_t size,
    int64_t modified_time,
    bool is_directory
);
void memory_index_build(MemoryIndexHandle handle);
SearchResult* memory_index_search(MemoryIndexHandle handle, const wchar_t* query, size_t max_results);
void memory_index_free_search_result(MemoryIndexHandle handle, SearchResult* result);
bool memory_index_save_snapshot(MemoryIndexHandle handle, const wchar_t* file_path);
bool memory_index_load_snapshot(MemoryIndexHandle handle, const wchar_t* file_path);
size_t memory_index_get_file_count(MemoryIndexHandle handle);
size_t memory_index_get_memory_size(MemoryIndexHandle handle);
void memory_index_clear(MemoryIndexHandle handle);
bool memory_index_get_file_info(
    MemoryIndexHandle handle,
    size_t index,
    wchar_t* path_buf, size_t path_buf_size,
    wchar_t* name_buf, size_t name_buf_size,
    wchar_t* ext_buf, size_t ext_buf_size,
    uint64_t* size,
    int64_t* modified_time
);

#ifdef __cplusplus
}
#endif

#endif // MEMORY_INDEX_H

