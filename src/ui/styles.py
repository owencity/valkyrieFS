"""
Qt Style Sheets (QSS) 스타일 정의

이 모듈은 애플리케이션의 전체 스타일을 정의합니다.
모던하고 깨끗한 디자인을 위해 Qt Style Sheets를 사용합니다.

스타일링이 로직과 분리되어 있어 유지보수가 쉽습니다.
"""
from typing import Final


# 애플리케이션 전체 스타일시트
# QSS는 CSS와 유사한 문법을 사용하여 Qt 위젯의 스타일을 정의합니다
APPLICATION_STYLE: Final[str] = """
/* 전체 애플리케이션 스타일 - 밝고 깔끔한 배경 */
QMainWindow {
    background-color: #f8fafc;  /* 아주 연한 슬레이트 배경 (레이어감) */
    border: none;
}

/* 모든 위젯 기본 스타일 */
QWidget {
    background-color: transparent;  /* 기본은 투명, 카드에서 흰색을 담당 */
    color: #1e293b;  /* 진한 슬레이트 색상 텍스트 */
    font-family: "Roboto", "Noto Sans KR", "Pretendard", "Malgun Gothic", sans-serif;
}

/* 중앙 위젯 스타일 */
QWidget#centralWidget {
    background-color: #f8fafc;  /* 전체 배경 톤 통일 */
}

/* 카드 컨테이너 - 검색/결과 영역 공통 */
QWidget#searchCard,
QWidget#resultsCard {
    background-color: #ffffff;
    border: 1px solid #e5e7eb;
    border-radius: 18px;
}

/* 검색 입력 박스 스타일 - 모던하고 트렌디한 디자인 */
QLineEdit#searchInput {
    background-color: #ffffff;  /* 흰색 배경 */
    border: 1px solid #e5e7eb;  /* 더 얇고 세련된 테두리 */
    border-radius: 16px;
    padding: 16px 18px;
    font-family: "Roboto", "Noto Sans KR", "Pretendard", "Malgun Gothic", sans-serif;
    font-size: 15px;  /* 약간 큰 폰트 */
    font-weight: 400;
    color: #1a1a1a;  /* 진한 검정 텍스트 */
    selection-background-color: #6366f1;  /* 인디고 선택 배경 */
    selection-color: #ffffff;  /* 선택된 텍스트 색상 */
}

/* 검색 입력 박스 포커스 상태 - 그림자 효과 느낌의 테두리 */
QLineEdit#searchInput:focus {
    border: 1px solid #6366f1;  /* 인디고 테두리 */
    background-color: #ffffff;
    outline: none;  /* 기본 아웃라인 제거 */
}

/* 검색 입력 박스 비활성화 상태 */
QLineEdit#searchInput:disabled {
    background-color: #f0f0f0;
    border: 2px solid #e8e8e8;
    color: #999999;
}

/* 검색 버튼 스타일 - 모던한 그라데이션 버튼 */
QPushButton#searchButton {
    background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                stop: 0 #6366f1, stop: 1 #4f46e5);  /* 인디고 그라데이션 */
    border: none;
    border-radius: 16px;  /* 검색 입력과 동일한 둥근 모서리 */
    padding: 16px 32px;  /* 더 넉넉한 패딩 */
    font-family: "Roboto", "Noto Sans KR", "Pretendard", "Malgun Gothic", sans-serif;
    font-size: 15px;
    font-weight: 600;  /* 더 굵은 폰트 */
    color: #ffffff;  /* 흰색 텍스트 */
    min-width: 100px;  /* 최소 너비 */
}

QPushButton#searchButton:hover {
    background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                stop: 0 #7c3aed, stop: 1 #6366f1);  /* 보라색 그라데이션 */
}

QPushButton#searchButton:pressed {
    background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                stop: 0 #5b21b6, stop: 1 #4f46e5);  /* 진한 보라색 그라데이션 */
}

QPushButton#searchButton:disabled {
    background-color: #d0d0d0;  /* 비활성화 시 회색 */
    color: #999999;
}

/* 플레이스홀더 텍스트 스타일 (입력 힌트) */
QLineEdit#searchInput::placeholder {
    color: #b0b0b0;  /* 회색 플레이스홀더 (힌트 역할) */
    font-weight: 400;
}

/* 결과 리스트 스타일 - 깔끔하고 모던한 디자인 */
QListView#resultList {
    background-color: #ffffff;  /* 흰색 배경 */
    border: 1px solid #e5e7eb;  /* 부드러운 회색 테두리 */
    border-radius: 14px;
    outline: none;  /* 포커스 아웃라인 제거 */
    padding: 10px;
    font-family: "Roboto", "Noto Sans KR", "Pretendard", "Malgun Gothic", sans-serif;
}

QListView#resultList::item {
    background-color: transparent;
    border: none;
    border-radius: 12px;
    padding: 0px;
    min-height: 60px;  /* 최소 높이로 클릭 영역 확보 */
}

QListView#resultList::item:hover {
    background-color: #f1f5f9;  /* 연한 회색 배경 (호버 피드백) */
    border-radius: 12px;
}

QListView#resultList::item:selected {
    background-color: #eef2ff;  /* 연한 인디고 배경 (선택 강조) */
    color: #1a1a1a;
    border-radius: 12px;
}

QListView#resultList::item:selected:focus {
    background-color: #e0e7ff;  /* 더 진한 인디고 (포커스 강조) */
    border-radius: 12px;
}

/* 스크롤바 스타일 - 미니멀하고 모던한 디자인 */
QScrollBar:vertical {
    background-color: transparent;  /* 투명 배경 */
    width: 10px;  /* 더 얇은 스크롤바 */
    border: none;
    border-radius: 5px;
    margin: 2px;
}

QScrollBar::handle:vertical {
    background-color: #cbd5e1;  /* 연한 회색 핸들 */
    border-radius: 5px;
    min-height: 40px;  /* 더 큰 핸들 */
    margin: 2px;
}

QScrollBar::handle:vertical:hover {
    background-color: #94a3b8;  /* 호버 시 진한 회색 */
}

QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {
    height: 0px;  /* 화살표 버튼 제거 (미니멀 디자인) */
}

QScrollBar:horizontal {
    background-color: transparent;  /* 투명 배경 */
    height: 10px;
    border: none;
    border-radius: 5px;
    margin: 2px;
}

QScrollBar::handle:horizontal {
    background-color: #cbd5e1;  /* 연한 회색 핸들 */
    border-radius: 5px;
    min-width: 40px;  /* 더 큰 핸들 */
    margin: 2px;
}

QScrollBar::handle:horizontal:hover {
    background-color: #94a3b8;  /* 호버 시 진한 회색 */
}

QScrollBar::add-line:horizontal,
QScrollBar::sub-line:horizontal {
    width: 0px;
}

/* 상태 라벨 스타일 - 세련된 정보성 텍스트 */
QLabel#statusLabel {
    font-family: "Roboto", "Noto Sans KR", "Pretendard", "Malgun Gothic", sans-serif;
    font-size: 13px;
    font-weight: 400;
    color: #64748b;  /* 슬레이트 회색 (모던한 색상) */
    padding: 6px 0px;  /* 넉넉한 세로 여백 */
    background-color: transparent;
}

QLabel#hintLabel {
    font-family: "Roboto", "Noto Sans KR", "Pretendard", "Malgun Gothic", sans-serif;
    font-size: 12px;
    font-weight: 400;
    color: #94a3b8;
    padding: 0px 0px 4px 0px;
    background-color: transparent;
}

/* 버튼 스타일 - 깔끔하고 모던한 디자인 */
QPushButton {
    background-color: #ffffff;
    border: 1px solid #e1e8ed;
    border-radius: 10px;  /* 더 둥근 모서리 */
    padding: 10px 20px;  /* 넉넉한 패딩 */
    font-family: "Pretendard", "Noto Sans KR", "Malgun Gothic", sans-serif;
    font-size: 13px;
    font-weight: 500;
    color: #334155;  /* 다크 슬레이트 색상 */
    min-width: 90px;  /* 최소 너비 */
}

QPushButton:hover {
    background-color: #f8fafc;  /* 호버 시 연한 회색 배경 */
    border: 1px solid #cbd5e1;
    color: #1e293b;
}

QPushButton:pressed {
    background-color: #f1f5f9;  /* 눌림 시 더 진한 회색 */
    border: 1px solid #94a3b8;
}

QPushButton:disabled {
    background-color: #f5f5f5;
    border: 1px solid #e8e8e8;
    color: #b0b0b0;
}

/* 결과 아이템 위젯 내부 라벨 스타일 */
QLabel#nameLabel {
    font-family: "Pretendard", "Noto Sans KR", "Malgun Gothic", sans-serif;
    font-size: 14px;  /* 약간 큰 폰트 */
    font-weight: 500;  /* 중간 굵기로 가독성 향상 */
    color: #1e293b;  /* 진한 슬레이트 색상 (주요 텍스트) */
    background-color: transparent;
}

QLabel#pathLabel {
    font-family: "Pretendard", "Noto Sans KR", "Malgun Gothic", sans-serif;
    font-size: 12px;  /* 약간 큰 폰트 */
    font-weight: 400;
    color: #64748b;  /* 슬레이트 회색 (보조 텍스트) */
    background-color: transparent;
}
"""

