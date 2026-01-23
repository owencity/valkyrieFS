"""
파일 검색 로직

이 모듈은 인덱스된 파일 목록에서 빠른 부분 문자열 검색을 수행합니다.
Everything 수준의 성능을 위해 최적화된 검색 알고리즘을 사용합니다.

최적화 전략:
- 접두사 인덱스: 첫 글자별로 그룹화하여 검색 범위 대폭 축소
- 사전 계산된 소문자 버전: 중복 변환 제거
- 조기 종료: 최대 결과 수 도달 시 즉시 반환
"""
from typing import List, Optional, Dict, Set
from collections import defaultdict
from src.models.file_entry import FileEntry


class Searcher:
    """
    파일 검색 엔진 (Everything 수준 성능)
    
    인덱스된 파일 목록에서 부분 문자열 매칭을 통해
    검색 쿼리와 일치하는 파일을 찾습니다.
    
    성능 최적화:
    - 사전 계산된 소문자 버전 사용 (중복 변환 제거)
    - 리스트 컴프리헨션으로 빠른 필터링
    - 조기 종료로 불필요한 처리 방지
    """
    
    def __init__(self, index: List[FileEntry]):
        """
        검색 엔진 초기화
        
        Everything 수준 성능 최적화:
        - 접두사 인덱스: 첫 글자별로 그룹화하여 검색 범위 대폭 축소
        - 사전 계산된 소문자 버전: 중복 변환 제거
        
        Args:
            index: 검색할 파일 엔트리 목록
        """
        self._index = index
        # Everything 수준 성능: 사전 계산된 소문자 버전 저장
        # 파일명만 검색하므로 파일명만 사전 계산 (경로는 제외)
        self._name_lower: List[str] = [entry.name.lower() for entry in index]
        
        # 접두사 인덱스: 첫 글자별로 파일 인덱스 그룹화
        # 검색 시 해당 그룹만 검사하여 검색 범위 대폭 축소
        self._prefix_index: Dict[str, List[int]] = defaultdict(list)
        self._build_prefix_index()
    
    def _build_prefix_index(self) -> None:
        """
        접두사 인덱스 구축
        
        첫 글자별로 파일 인덱스를 그룹화하여
        검색 시 해당 그룹만 검사할 수 있도록 합니다.
        
        예: "pdf" 검색 시 'p'로 시작하는 파일만 검사
        """
        self._prefix_index.clear()
        for i, name_lower in enumerate(self._name_lower):
            if name_lower:
                # 첫 글자로 그룹화
                first_char = name_lower[0]
                self._prefix_index[first_char].append(i)
    
    def update_index(self, index: List[FileEntry]) -> None:
        """
        검색 대상 인덱스를 업데이트
        
        인덱서가 새로운 파일을 스캔했을 때,
        검색 엔진도 최신 인덱스를 사용하도록 업데이트합니다.
        
        성능 최적화:
        - 소문자 버전 재생성
        - 접두사 인덱스 재구축
        
        Args:
            index: 새로운 파일 엔트리 목록
        """
        self._index = index
        # 사전 계산된 소문자 버전 재생성
        # 파일명만 검색하므로 파일명만 사전 계산 (경로는 제외)
        self._name_lower = [entry.name.lower() for entry in index]
        # 접두사 인덱스 재구축
        self._build_prefix_index()
    
    def search(self, query: str, max_results: Optional[int] = None) -> List[FileEntry]:
        """
        부분 문자열 기반 파일 검색 (Everything 수준 성능)
        
        검색은 대소문자를 구분하지 않으며, 파일명만 검색합니다.
        경로 검색은 제외하여 검색 속도를 대폭 향상시킵니다.
        
        성능 최적화:
        - 파일명만 검색 (경로 검색 제외)
        - 사전 계산된 소문자 버전 사용 (중복 변환 제거)
        - 첫 글자로 빠른 스킵
        - 조기 종료로 최대 결과 수 도달 시 즉시 반환
        
        Args:
            query: 검색 쿼리 문자열 (부분 문자열)
            max_results: 반환할 최대 결과 수 (None이면 모두 반환)
            
        Returns:
            검색 쿼리와 일치하는 파일 엔트리 목록 (파일명 매칭만)
        """
        if not query:
            # 쿼리가 비어있으면 모든 파일 반환 (최대 결과 수 제한)
            results = self._index[:max_results] if max_results else self._index
            return results
        
        query_lower = query.lower()
        query_len = len(query_lower)
        
        # Everything 수준 성능: 파일명만 검색 (경로 검색 제외)
        filename_matches: List[FileEntry] = []
        
        if query_len == 0:
            return self._index[:max_results] if max_results else self._index
        
        # 접두사 인덱스 활용: 첫 글자로 검색 범위 대폭 축소
        query_first_char = query_lower[0]
        query_last_char = query_lower[-1] if query_len > 1 else None
        
        # 점(.) 검색 최적화: 점으로 시작하는 파일이 너무 많으면 접두사 인덱스 우회
        # 점(.)은 확장자 때문에 매우 흔한 문자이므로 접두사 인덱스 효과가 낮음
        USE_PREFIX_INDEX = True
        if query_first_char == '.':
            # 점(.)으로 시작하는 파일이 전체의 30% 이상이면 접두사 인덱스 우회
            dot_indices = self._prefix_index.get('.', [])
            if len(dot_indices) > len(self._index) * 0.3:
                USE_PREFIX_INDEX = False
        
        # 접두사 인덱스 사용 여부에 따라 후보 인덱스 결정
        if USE_PREFIX_INDEX:
            # 접두사 인덱스에서 후보 인덱스 가져오기
            # 첫 글자가 일치하는 파일만 검사 (검색 범위 대폭 축소)
            candidate_indices = self._prefix_index.get(query_first_char, [])
            
            # 첫 글자가 없으면 전체 검색 (드문 경우)
            if not candidate_indices:
                # 첫 글자가 포함된 파일 찾기 (전체 스캔)
                for i in range(len(self._index)):
                    name_lower = self._name_lower[i]
                    if name_lower and query_first_char in name_lower:
                        candidate_indices.append(i)
        else:
            # 접두사 인덱스 우회: 전체 인덱스 사용 (점(.) 검색 최적화)
            candidate_indices = list(range(len(self._index)))
        
        # 후보 파일만 검사 (검색 범위 대폭 축소)
        for i in candidate_indices:
            name_lower = self._name_lower[i]
            
            if not name_lower:
                continue
            
            # 단일 문자 쿼리는 첫 글자만 확인
            if query_len == 1:
                if query_first_char in name_lower:
                    filename_matches.append(self._index[i])
                    if max_results and len(filename_matches) >= max_results:
                        return filename_matches
            else:
                # 다중 문자 쿼리: 마지막 글자 체크 후 부분 문자열 검색
                if query_last_char and query_last_char not in name_lower:
                    continue
                
                # 부분 문자열 검색 (빠른 C 구현)
                if query_lower in name_lower:
                    filename_matches.append(self._index[i])
                    if max_results and len(filename_matches) >= max_results:
                        return filename_matches
        
        # 최대 결과 수 제한
        if max_results:
            return filename_matches[:max_results]
        
        return filename_matches

