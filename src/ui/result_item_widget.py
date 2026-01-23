"""
검색 결과 리스트 아이템 위젯

이 모듈은 검색 결과를 표시하기 위한 커스텀 위젯을 제공합니다.
파일 아이콘, 파일명(주요 텍스트), 경로(보조 텍스트)를 포함합니다.

UI와 로직을 분리하기 위해 별도의 위젯으로 분리되었습니다.
"""
from pathlib import Path
from PySide6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QLabel, QSizePolicy, QFileIconProvider
from PySide6.QtCore import Qt, QSize, QFileInfo
from PySide6.QtGui import QIcon, QFont

from src.models.file_entry import FileEntry


class ResultItemWidget(QWidget):
    """
    검색 결과 리스트의 개별 아이템 위젯
    
    파일 아이콘, 파일명, 경로를 시각적으로 구분하여 표시합니다.
    한국 사용자에게 친숙한 레이아웃을 제공합니다.
    """
    
    def __init__(self, entry: FileEntry, parent=None):
        """
        결과 아이템 위젯 초기화
        
        Args:
            entry: 표시할 파일 엔트리
            parent: 부모 위젯
        """
        super().__init__(parent)
        self.entry = entry
        
        # 아이콘 제공자 (파일 시스템 아이콘 가져오기)
        self.icon_provider = QFileIconProvider()
        
        # UI 구성
        self._setup_ui()
    
    def _setup_ui(self) -> None:
        """
        UI 컴포넌트를 생성하고 레이아웃을 구성합니다.
        
        넉넉한 간격과 명확한 시각적 계층 구조를 제공합니다.
        """
        # 메인 레이아웃 (가로 방향)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)  # 넉넉한 패딩
        layout.setSpacing(12)  # 요소 간 간격
        
        # 파일 아이콘
        icon_label = QLabel()
        icon_label.setFixedSize(24, 24)  # 아이콘 크기 고정
        icon_label.setAlignment(Qt.AlignCenter)
        
        # 파일 경로로부터 아이콘 가져오기
        file_path = Path(self.entry.path)
        
        # Windows에서 파일 시스템 아이콘 가져오기
        # QFileIconProvider는 파일 타입별 시스템 아이콘을 제공합니다
        # QFileInfo 객체로 변환해야 함 (Path 객체는 직접 사용 불가)
        if file_path.exists() and file_path.is_file():
            # 실제 파일이 존재하면 QFileInfo로 아이콘 가져오기 (확장자별 아이콘)
            file_info = QFileInfo(str(file_path))
            icon = self.icon_provider.icon(file_info)
        elif file_path.exists():
            # 디렉토리인 경우 폴더 아이콘
            icon = self.icon_provider.icon(QFileIconProvider.IconType.Folder)
        else:
            # 파일이 존재하지 않으면 기본 파일 아이콘
            # 경로 문자열만으로도 확장자 기반 아이콘을 가져올 수 있음
            file_info = QFileInfo(str(file_path))
            icon = self.icon_provider.icon(file_info)
        
        icon_pixmap = icon.pixmap(24, 24)
        icon_label.setPixmap(icon_pixmap)
        icon_label.setScaledContents(True)
        
        # 아이콘을 왼쪽에 배치하고 레이아웃에 추가
        layout.addWidget(icon_label, 0)
        
        # 파일명과 경로를 포함하는 세로 레이아웃
        text_layout = QVBoxLayout()
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(4)  # 파일명과 경로 간 간격
        
        # 파일명 (주요 텍스트)
        self.name_label = QLabel(self.entry.name)
        self.name_label.setObjectName("nameLabel")  # QSS 선택자를 위한 이름
        self.name_label.setFont(QFont("Pretendard", 13, QFont.Weight.Medium))
        # 텍스트가 길면 말줄임표(...) 처리
        self.name_label.setTextFormat(Qt.TextFormat.PlainText)
        # 텍스트 말줄임표 설정
        self.name_label.setWordWrap(False)
        # 주요 텍스트 색상은 스타일시트에서 설정 (명확한 가독성)
        text_layout.addWidget(self.name_label)
        
        # 경로 (보조 텍스트)
        self.path_label = QLabel(self.entry.path)
        self.path_label.setObjectName("pathLabel")  # QSS 선택자를 위한 이름
        self.path_label.setFont(QFont("Pretendard", 11))
        # 보조 텍스트는 회색으로 표시 (스타일시트에서 설정)
        # 텍스트가 길면 말줄임표 처리
        self.path_label.setTextFormat(Qt.TextFormat.PlainText)
        self.path_label.setWordWrap(False)
        text_layout.addWidget(self.path_label)
        
        # 세로 레이아웃을 메인 레이아웃에 추가
        layout.addLayout(text_layout, 1)  # 남은 공간을 차지
        
        # 여백 추가 (오른쪽 정렬을 위해)
        layout.addStretch()
        
        # 위젯 크기 정책 설정
        self.setMinimumHeight(60)  # 최소 높이로 클릭 영역 확보
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    
    def set_selected(self, selected: bool) -> None:
        """
        아이템 선택 상태에 따라 스타일을 업데이트합니다.
        
        키보드 네비게이션과 마우스 선택 모두를 지원하기 위해
        선택 상태를 외부에서 제어할 수 있습니다.
        
        Args:
            selected: 선택 여부
        """
        # 선택 상태는 스타일시트에서 :hover와 :selected 상태로 처리
        # 이 메서드는 추가 로직이 필요한 경우를 위한 확장점
        pass

