"""
검색 결과 리스트 모델 (가상 리스트)

QListWidget(아이템/위젯 생성) 대신 QListView + Model로 전환하여
화면에 보이는 범위만 렌더링되도록 합니다.
"""

from __future__ import annotations

from typing import List, Optional

from PySide6.QtCore import QAbstractListModel, QModelIndex, Qt

from src.models.file_entry import FileEntry


class ResultListModel(QAbstractListModel):
    """
    검색 결과를 담는 리스트 모델

    - DisplayRole: 표시용 텍스트(파일명)
    - UserRole: FileEntry 원본
    """

    def __init__(self, entries: Optional[List[FileEntry]] = None, parent=None):
        super().__init__(parent)
        self._entries: List[FileEntry] = entries or []

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return len(self._entries)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        row = index.row()
        if row < 0 or row >= len(self._entries):
            return None

        entry = self._entries[row]

        if role == Qt.ItemDataRole.DisplayRole:
            return entry.name
        if role == Qt.ItemDataRole.UserRole:
            return entry
        return None

    def set_entries(self, entries: List[FileEntry]) -> None:
        self.beginResetModel()
        self._entries = entries
        self.endResetModel()

    def entry_at(self, row: int) -> Optional[FileEntry]:
        if 0 <= row < len(self._entries):
            return self._entries[row]
        return None


