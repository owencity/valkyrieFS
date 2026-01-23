/*
 * 메모리 기반 파일 인덱스 구현
 * 
 * Everything 수준의 성능을 위한 최적화된 인덱스 관리
 */

#include "memory_index.h"
#include <algorithm>
#include <cstring>
#include <locale>
#include <codecvt>
#include <fstream>
#include <sstream>
#include <unordered_map>
#include <vector>
#include <string>

// Windows min/max 매크로 충돌 방지
#ifdef min
#undef min
#endif
#ifdef max
#undef max
#endif

// MemoryIndex 구현
MemoryIndex::MemoryIndex() {
    // 초기 용량 설정 (성능 최적화)
    entries.reserve(1000000);  // 100만 개 예약
    string_pool.reserve(50 * 1024 * 1024);  // 50MB 예약
    name_lower.reserve(1000000);
    path_index_map.reserve(1000000);
}

MemoryIndex::~MemoryIndex() {
    clear();
}

uint32_t MemoryIndex::add_to_string_pool(const std::wstring& str) {
    // 문자열 풀링: 이미 존재하면 재사용
    auto it = string_map.find(str);
    if (it != string_map.end()) {
        return it->second;
    }
    
    // 새 문자열 추가
    uint32_t offset = static_cast<uint32_t>(string_pool.size());
    string_map[str] = offset;
    
    // 문자열과 null 종료 문자 추가
    string_pool.insert(string_pool.end(), str.begin(), str.end());
    string_pool.push_back(L'\0');
    
    return offset;
}

const wchar_t* MemoryIndex::get_string_from_pool(uint32_t offset) const {
    if (offset >= string_pool.size()) {
        return L"";
    }
    return &string_pool[offset];
}

void MemoryIndex::add_file(
    const wchar_t* path,
    const wchar_t* name,
    const wchar_t* extension,
    uint64_t size,
    int64_t modified_time,
    bool is_directory
) {
    const uint32_t name_offset = add_to_string_pool(name ? name : L"");
    const uint32_t path_offset = add_to_string_pool(path ? path : L"");
    const uint32_t ext_offset = add_to_string_pool(extension ? extension : L"");

    // 중복 방지: 동일 path_offset(=동일 경로 문자열)은 하나로 유지하고 업데이트(upsert)
    auto it = path_index_map.find(path_offset);
    if (it != path_index_map.end()) {
        FileEntry& existing = entries[it->second];
        existing.name_offset = name_offset;
        existing.extension_offset = ext_offset;
        existing.size = size;
        existing.modified_time = modified_time;
        existing.flags = is_directory ? 1 : 0;
        return;
    }

    FileEntry entry;
    entry.name_offset = name_offset;
    entry.path_offset = path_offset;
    entry.extension_offset = ext_offset;
    entry.size = size;
    entry.modified_time = modified_time;
    entry.flags = is_directory ? 1 : 0;

    const uint32_t new_index = static_cast<uint32_t>(entries.size());
    entries.push_back(entry);
    path_index_map[path_offset] = new_index;
}

void MemoryIndex::build_index() {
    // 혹시 남아있는 중복 제거(레거시 스냅샷 로드 등)
    deduplicate_entries_by_path();

    // 소문자 파일명 배열 생성 (검색 최적화)
    name_lower.clear();
    name_lower.reserve(entries.size());
    
    for (const auto& entry : entries) {
        std::wstring name = get_string_from_pool(entry.name_offset);
        std::transform(name.begin(), name.end(), name.begin(), ::towlower);
        name_lower.push_back(name);
    }
    
    // 인덱스 구축
    build_prefix_index();
    build_char_index();
}

void MemoryIndex::build_prefix_index() {
    prefix_index.clear();
    
    for (size_t i = 0; i < name_lower.size(); i++) {
        if (!name_lower[i].empty()) {
            wchar_t first_char = name_lower[i][0];
            prefix_index[first_char].push_back(static_cast<uint32_t>(i));
        }
    }
}

void MemoryIndex::rebuild_string_map_from_pool() {
    // string_pool을 파싱해서 string_map(offset) 복원
    string_map.clear();
    size_t i = 0;
    while (i < string_pool.size()) {
        size_t start = i;
        while (i < string_pool.size() && string_pool[i] != L'\0') {
            i++;
        }
        // [start, i) 가 문자열
        if (i > start) {
            std::wstring s(&string_pool[start], &string_pool[i]);
            string_map.emplace(std::move(s), static_cast<uint32_t>(start));
        } else {
            // 빈 문자열도 등록
            string_map.emplace(L"", static_cast<uint32_t>(start));
        }
        // null 지나가기
        i++;
    }
}

void MemoryIndex::deduplicate_entries_by_path() {
    if (entries.empty()) {
        path_index_map.clear();
        return;
    }

    std::vector<FileEntry> unique;
    unique.reserve(entries.size());
    path_index_map.clear();
    path_index_map.reserve(entries.size());

    for (const auto& e : entries) {
        auto it = path_index_map.find(e.path_offset);
        if (it == path_index_map.end()) {
            const uint32_t idx = static_cast<uint32_t>(unique.size());
            unique.push_back(e);
            path_index_map[e.path_offset] = idx;
        } else {
            // 중복이면 최신 값으로 덮어쓰기(사이즈/시간/플래그 등)
            unique[it->second] = e;
        }
    }

    entries.swap(unique);
}

void MemoryIndex::build_char_index() {
    char_index.clear();
    char_index.reserve(1024);

    // 성능 최적화:
    // - 과거: 파일명 내 중복 문자를 제거하려고 O(n^2) 중복 체크를 수행 → 스냅샷 로드 시 매우 느려짐
    // - 현재: 중복 제거는 검색 시 "연속 중복"만 스킵하는 방식으로 처리
    //   (같은 파일명에서 같은 문자를 여러 번 만나면 같은 인덱스가 연속으로 push됨)
    for (uint32_t i = 0; i < static_cast<uint32_t>(name_lower.size()); i++) {
        const std::wstring& s = name_lower[i];
        if (s.empty()) continue;

        for (wchar_t ch : s) {
            char_index[ch].push_back(i);
        }
    }
}

SearchResult* MemoryIndex::search(const wchar_t* query, size_t max_results) {
    if (!query || wcslen(query) == 0) {
        // 빈 쿼리: 최대 결과 수만큼 반환
        SearchResult* result = new SearchResult;
        size_t count = std::min(entries.size(), max_results > 0 ? max_results : entries.size());
        result->indices = new uint32_t[count];
        result->count = count;
        result->capacity = count;
        
        for (size_t i = 0; i < count; i++) {
            result->indices[i] = static_cast<uint32_t>(i);
        }
        return result;
    }
    
    // 쿼리를 소문자로 변환
    std::wstring query_lower = query;
    std::transform(query_lower.begin(), query_lower.end(), query_lower.begin(), ::towlower);
    
    if (query_lower.empty()) {
        return nullptr;
    }
    
    SearchResult* result = new SearchResult;
    result->count = 0;
    result->capacity = max_results > 0 ? max_results : 1000;
    result->indices = new uint32_t[result->capacity];
    
    const wchar_t first_char = query_lower[0];

    // Everything식: "첫 글자(prefix)"가 아니라 "문자 포함" 인덱스로 후보를 줄임
    const auto it_first = char_index.find(first_char);
    if (it_first == char_index.end()) {
        return result; // 해당 문자가 포함된 파일이 없음
    }

    const std::vector<uint32_t>* candidate_ptr = &it_first->second;

    // 2글자 이상이면 첫/둘째 문자 중 더 희귀한 쪽으로 후보 집합 선택
    if (query_lower.size() >= 2) {
        const wchar_t second_char = query_lower[1];
        const auto it_second = char_index.find(second_char);
        if (it_second != char_index.end()) {
            if (it_second->second.size() < candidate_ptr->size()) {
                candidate_ptr = &it_second->second;
            }
        }
    }

    const wchar_t last_char = query_lower.size() >= 2 ? query_lower.back() : 0;
    
    // 후보 파일만 검사
    uint32_t prev_idx = 0xFFFFFFFFu;
    for (uint32_t idx : *candidate_ptr) {
        // build_char_index가 중복을 허용하므로, 같은 파일 인덱스가 연속으로 들어오는 경우만 스킵
        // (대부분 같은 파일명에서 같은 문자를 여러 번 만날 때 발생)
        if (idx == prev_idx) {
            continue;
        }
        prev_idx = idx;
        const std::wstring& hay = name_lower[idx];
        if (hay.empty()) continue;

        // 마지막 글자 빠른 스킵(2글자 이상)
        if (last_char && hay.find(last_char) == std::wstring::npos) {
            continue;
        }

        if (hay.find(query_lower) != std::wstring::npos) {
            if (result->count >= result->capacity) {
                // 용량 확장
                size_t new_capacity = result->capacity * 2;
                uint32_t* new_indices = new uint32_t[new_capacity];
                std::memcpy(new_indices, result->indices, result->count * sizeof(uint32_t));
                delete[] result->indices;
                result->indices = new_indices;
                result->capacity = new_capacity;
            }
            result->indices[result->count++] = idx;
            
            // 최대 결과 수 도달 시 조기 종료
            if (max_results > 0 && result->count >= max_results) {
                break;
            }
        }
    }
    
    return result;
}

void MemoryIndex::free_search_result(SearchResult* result) {
    if (result) {
        delete[] result->indices;
        delete result;
    }
}

bool MemoryIndex::save_snapshot(const wchar_t* file_path) {
    // TODO: 메모리 매핑 파일로 저장 구현
    // 현재는 간단한 바이너리 저장
    std::ofstream file(file_path, std::ios::binary);
    if (!file.is_open()) {
        return false;
    }
    
    // 헤더: 파일 개수, 문자열 풀 크기
    size_t entry_count = entries.size();
    size_t pool_size = string_pool.size();
    
    file.write(reinterpret_cast<const char*>(&entry_count), sizeof(entry_count));
    file.write(reinterpret_cast<const char*>(&pool_size), sizeof(pool_size));
    
    // 엔트리 배열 저장
    file.write(reinterpret_cast<const char*>(entries.data()), 
               entries.size() * sizeof(FileEntry));
    
    // 문자열 풀 저장
    file.write(reinterpret_cast<const char*>(string_pool.data()),
               string_pool.size() * sizeof(wchar_t));
    
    return true;
}

bool MemoryIndex::load_snapshot(const wchar_t* file_path) {
    // TODO: 메모리 매핑 파일로 로드 구현
    // 현재는 간단한 바이너리 로드
    std::ifstream file(file_path, std::ios::binary);
    if (!file.is_open()) {
        return false;
    }
    
    clear();
    
    // 헤더 읽기
    size_t entry_count = 0;
    size_t pool_size = 0;
    
    file.read(reinterpret_cast<char*>(&entry_count), sizeof(entry_count));
    file.read(reinterpret_cast<char*>(&pool_size), sizeof(pool_size));
    
    // 엔트리 배열 로드
    entries.resize(entry_count);
    file.read(reinterpret_cast<char*>(entries.data()), 
              entry_count * sizeof(FileEntry));
    
    // 문자열 풀 로드
    string_pool.resize(pool_size);
    file.read(reinterpret_cast<char*>(string_pool.data()),
              pool_size * sizeof(wchar_t));
    
    // 스냅샷 로드 후 문자열 풀 기반 맵 복원 + 중복 제거
    rebuild_string_map_from_pool();
    deduplicate_entries_by_path();

    // 인덱스 재구축
    build_index();
    
    return true;
}

size_t MemoryIndex::get_memory_size() const {
    return entries.size() * sizeof(FileEntry) +
           string_pool.size() * sizeof(wchar_t) +
           name_lower.size() * sizeof(std::wstring) +
           prefix_index.size() * sizeof(std::vector<uint32_t>);
}

void MemoryIndex::clear() {
    entries.clear();
    string_pool.clear();
    string_map.clear();
    path_index_map.clear();
    name_lower.clear();
    prefix_index.clear();
    char_index.clear();
}

bool MemoryIndex::get_file_info(
    size_t index,
    wchar_t* path_buf, size_t path_buf_size,
    wchar_t* name_buf, size_t name_buf_size,
    wchar_t* ext_buf, size_t ext_buf_size,
    uint64_t* size,
    int64_t* modified_time
) const {
    if (index >= entries.size()) {
        return false;
    }
    
    const FileEntry& entry = entries[index];
    
    // 문자열 복사
    const wchar_t* path = get_string_from_pool(entry.path_offset);
    const wchar_t* name = get_string_from_pool(entry.name_offset);
    const wchar_t* ext = get_string_from_pool(entry.extension_offset);
    
    wcsncpy_s(path_buf, path_buf_size, path, _TRUNCATE);
    wcsncpy_s(name_buf, name_buf_size, name, _TRUNCATE);
    wcsncpy_s(ext_buf, ext_buf_size, ext, _TRUNCATE);
    
    *size = entry.size;
    *modified_time = entry.modified_time;
    
    return true;
}

// C 인터페이스 구현
MemoryIndexHandle create_memory_index() {
    return new MemoryIndex();
}

void destroy_memory_index(MemoryIndexHandle handle) {
    delete static_cast<MemoryIndex*>(handle);
}

void memory_index_add_file(
    MemoryIndexHandle handle,
    const wchar_t* path,
    const wchar_t* name,
    const wchar_t* extension,
    uint64_t size,
    int64_t modified_time,
    bool is_directory
) {
    static_cast<MemoryIndex*>(handle)->add_file(
        path, name, extension, size, modified_time, is_directory
    );
}

void memory_index_build(MemoryIndexHandle handle) {
    static_cast<MemoryIndex*>(handle)->build_index();
}

SearchResult* memory_index_search(MemoryIndexHandle handle, const wchar_t* query, size_t max_results) {
    return static_cast<MemoryIndex*>(handle)->search(query, max_results);
}

void memory_index_free_search_result(MemoryIndexHandle handle, SearchResult* result) {
    static_cast<MemoryIndex*>(handle)->free_search_result(result);
}

bool memory_index_save_snapshot(MemoryIndexHandle handle, const wchar_t* file_path) {
    return static_cast<MemoryIndex*>(handle)->save_snapshot(file_path);
}

bool memory_index_load_snapshot(MemoryIndexHandle handle, const wchar_t* file_path) {
    return static_cast<MemoryIndex*>(handle)->load_snapshot(file_path);
}

size_t memory_index_get_file_count(MemoryIndexHandle handle) {
    return static_cast<MemoryIndex*>(handle)->get_file_count();
}

size_t memory_index_get_memory_size(MemoryIndexHandle handle) {
    return static_cast<MemoryIndex*>(handle)->get_memory_size();
}

void memory_index_clear(MemoryIndexHandle handle) {
    static_cast<MemoryIndex*>(handle)->clear();
}

bool memory_index_get_file_info(
    MemoryIndexHandle handle,
    size_t index,
    wchar_t* path_buf, size_t path_buf_size,
    wchar_t* name_buf, size_t name_buf_size,
    wchar_t* ext_buf, size_t ext_buf_size,
    uint64_t* size,
    int64_t* modified_time
) {
    return static_cast<MemoryIndex*>(handle)->get_file_info(
        index, path_buf, path_buf_size, name_buf, name_buf_size,
        ext_buf, ext_buf_size, size, modified_time
    );
}

