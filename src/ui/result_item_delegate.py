"""
검색 결과 렌더링 델리게이트 (가상 렌더링)

QListView는 화면에 보이는 항목만 paint()를 호출하므로,
수만 개 결과가 있어도 UI가 멈추지 않습니다.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Tuple

from PySide6.QtCore import Qt, QRect, QSize, QFileInfo
from PySide6.QtGui import QPainter, QFont, QColor, QPen
from PySide6.QtWidgets import QStyledItemDelegate, QFileIconProvider, QStyleOptionViewItem, QStyle

from src.models.file_entry import FileEntry


@dataclass(frozen=True)
class _IconKey:
    is_dir: bool
    ext: str


class ResultItemDelegate(QStyledItemDelegate):
    """
    - 파일 아이콘 + 파일명(굵게) + 경로(연하게) 렌더링
    - 아이콘은 확장자 기반 캐시(매 paint마다 시스템 아이콘 조회 방지)
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._icon_provider = QFileIconProvider()
        self._icon_cache: Dict[_IconKey, object] = {}

        # 결과 영역 타이포: 과하게 크거나 두껍지 않게(윈도우에서 자연스럽게)
        # Pretendard가 없으면 시스템 폰트로 폴백됩니다.
        # 파일명은 너무 굵지 않게(가독성 유지 + 부담 감소)
        # Medium이 필요하면 Normal -> Medium으로 조정 가능
        self._name_font = QFont("Roboto", 12, QFont.Weight.Normal)
        self._path_font = QFont("Roboto", 10, QFont.Weight.Normal)

        self._name_color = QColor("#1e293b")
        self._path_color = QColor("#6b7280")

    def sizeHint(self, option: QStyleOptionViewItem, index) -> QSize:
        # 기존 ResultItemWidget과 동일한 클릭 영역 확보
        return QSize(option.rect.width(), 60)

    def _get_icon(self, entry: FileEntry):
        p = Path(entry.path)
        is_dir = False  # 현재 엔트리는 파일 기준이지만, 안전하게 처리
        ext = (entry.extension or "").lower()
        key = _IconKey(is_dir=is_dir, ext=ext)
        cached = self._icon_cache.get(key)
        if cached is not None:
            return cached

        # 파일 존재 여부 확인은 비용이 커서 paint에서 하지 않음
        # QFileInfo만으로도 확장자 기반 아이콘을 얻을 수 있음
        icon = self._icon_provider.icon(QFileInfo(str(p)))
        self._icon_cache[key] = icon
        return icon

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index) -> None:
        entry: FileEntry = index.data(Qt.ItemDataRole.UserRole)
        if not entry:
            super().paint(painter, option, index)
            return

        painter.save()
        try:
            # PySide6에서 option.state는 QStyle.State 플래그입니다.
            # 선택/호버 배경은 스타일시트에서 처리하지만, 기본 선택 배경도 지원
            if option.state & QStyle.StateFlag.State_Selected:
                painter.fillRect(option.rect, QColor("#e0e7ff"))
            elif option.state & QStyle.StateFlag.State_MouseOver:
                painter.fillRect(option.rect, QColor("#f1f5f9"))

            r = option.rect
            padding_x = 12
            padding_y = 10
            icon_size = 24
            gap = 12

            icon_rect = QRect(
                r.left() + padding_x,
                r.top() + padding_y,
                icon_size,
                icon_size,
            )

            # 아이콘
            icon = self._get_icon(entry)
            pix = icon.pixmap(icon_size, icon_size)
            painter.drawPixmap(icon_rect, pix)

            text_left = icon_rect.right() + gap
            text_right = r.right() - padding_x

            name_rect = QRect(
                text_left,
                r.top() + padding_y - 1,
                max(0, text_right - text_left),
                22,
            )
            path_rect = QRect(
                text_left,
                name_rect.bottom() + 2,
                max(0, text_right - text_left),
                18,
            )

            # 파일명
            painter.setFont(self._name_font)
            painter.setPen(QPen(self._name_color))
            painter.drawText(
                name_rect,
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                entry.name,
            )

            # 경로(말줄임)
            painter.setFont(self._path_font)
            painter.setPen(QPen(self._path_color))
            metrics = painter.fontMetrics()
            elided = metrics.elidedText(entry.path, Qt.TextElideMode.ElideMiddle, path_rect.width())
            painter.drawText(
                path_rect,
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                elided,
            )
        finally:
            # 예외가 나도 painter 상태를 반드시 복구 (QPainter::end 경고 방지)
            painter.restore()


