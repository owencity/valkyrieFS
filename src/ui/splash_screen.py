"""
스플래시(런처) 화면

- 앱 시작 시 로고/환영 문구를 먼저 보여주고, 백그라운드에서 인덱싱이 진행되도록 합니다.
- "숨쉬는" 느낌은 로고에 Opacity 애니메이션을 적용하여 구현합니다.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve, Property
from PySide6.QtGui import QPixmap, QPainter, QColor, QFont, QIcon
from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout, QGraphicsOpacityEffect, QGraphicsDropShadowEffect


def _load_logo_pixmap(svg_path: Path, size: int = 160) -> QPixmap:
    """
    SVG 로고를 QPixmap으로 로드합니다.
    QtSvg 모듈이 없을 수 있어, 가능한 경로를 순서대로 시도합니다.
    """
    if not svg_path.exists():
        pm = QPixmap(size, size)
        pm.fill(Qt.GlobalColor.transparent)
        return pm

    # 1) QtSvg가 있으면 가장 선명하게 렌더링 가능
    try:
        from PySide6.QtSvg import QSvgRenderer  # type: ignore

        pm = QPixmap(size, size)
        pm.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pm)
        try:
            renderer = QSvgRenderer(str(svg_path))
            renderer.render(painter)
        finally:
            painter.end()
        return pm
    except Exception:
        pass

    # 2) QIcon을 통한 렌더링(환경에 따라 품질이 떨어질 수 있음)
    icon = QIcon(str(svg_path))
    pm = icon.pixmap(size, size)
    if pm.isNull():
        pm = QPixmap(size, size)
        pm.fill(Qt.GlobalColor.transparent)
    return pm


def _tint_pixmap(src: QPixmap, color: QColor) -> QPixmap:
    if src.isNull():
        return src
    pm = QPixmap(src.size())
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    try:
        p.drawPixmap(0, 0, src)
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
        p.fillRect(pm.rect(), color)
    finally:
        p.end()
    return pm


class _LogoFillWidget(QWidget):
    """
    로고를 '회색 베이스 + 좌→우 색 채움'으로 그리는 위젯
    """

    def __init__(self, logo_svg_path: Path, size: int = 168, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setFixedSize(size, size)

        raw = _load_logo_pixmap(logo_svg_path, size=size)
        self._base_pm = _tint_pixmap(raw, QColor("#cbd5e1"))   # 연한 슬레이트(빈 상태)
        self._fill_pm = _tint_pixmap(raw, QColor("#6366f1"))   # 인디고(채움)
        self._progress = 0.0
        self._scale = 1.0

    def get_progress(self) -> float:
        return float(self._progress)

    def set_progress(self, v: float) -> None:
        v = max(0.0, min(1.0, float(v)))
        if v == self._progress:
            return
        self._progress = v
        self.update()

    progress = Property(float, get_progress, set_progress)

    def get_scale(self) -> float:
        return float(self._scale)

    def set_scale(self, v: float) -> None:
        v = max(0.5, min(1.5, float(v)))
        if v == self._scale:
            return
        self._scale = v
        self.update()

    scale = Property(float, get_scale, set_scale)

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        try:
            p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            # 스케일 적용: 로고를 중앙 기준으로 확대/축소
            if self._scale != 1.0:
                cx = self.width() / 2.0
                cy = self.height() / 2.0
                p.translate(cx, cy)
                p.scale(self._scale, self._scale)
                p.translate(-cx, -cy)

            # 1) 회색 베이스(전체)
            if not self._base_pm.isNull():
                p.drawPixmap(0, 0, self._base_pm)

            # 2) 좌→우 채움(클립)
            if not self._fill_pm.isNull() and self._progress > 0:
                w = int(self.width() * self._progress)
                p.save()
                try:
                    p.setClipRect(0, 0, w, self.height())
                    p.drawPixmap(0, 0, self._fill_pm)
                finally:
                    p.restore()
        finally:
            p.end()


class SplashScreen(QWidget):
    """
    프레임 없는 런처 스타일 스플래시 화면
    """

    def __init__(self, logo_svg_path: Path, parent: Optional[QWidget] = None):
        super().__init__(parent)

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        # "박스"처럼 보이지 않게, 아주 부드러운 반투명 백플레이트(유리판 느낌)만 제공
        # (배경이 완전 투명하면 콘솔/화면이 비쳐서 텍스트가 흐릿해 보임)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        panel = QWidget(self)
        panel.setObjectName("splashPanel")
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(42, 36, 42, 32)
        panel_layout.setSpacing(12)
        panel_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(panel)

        # 로고
        # 로고(채움) + 그림자/숨쉬기 효과를 동시에 적용하기 위해 컨테이너를 사용
        self.logo_container = QWidget()
        self.logo_container.setFixedSize(180, 180)

        self.logo_widget = _LogoFillWidget(logo_svg_path, size=180, parent=self.logo_container)
        self.logo_widget.move(0, 0)

        # 1) 그림자는 컨테이너에 적용
        shadow = QGraphicsDropShadowEffect(self.logo_container)
        shadow.setBlurRadius(26)
        shadow.setOffset(0, 8)
        shadow.setColor(QColor(15, 23, 42, 42))  # #0f172a, alpha 약하게
        self.logo_container.setGraphicsEffect(shadow)

        # 2) 숨쉬는 opacity는 로고 위젯에 적용 (너무 투명하지 않게 범위를 올림)
        self._opacity = QGraphicsOpacityEffect(self.logo_widget)
        self._opacity.setOpacity(0.96)
        self.logo_widget.setGraphicsEffect(self._opacity)

        self._breath_anim = QPropertyAnimation(self._opacity, b"opacity", self)
        self._breath_anim.setDuration(1400)
        # 너무 투명해지지 않게(배경 비침 최소화)
        self._breath_anim.setStartValue(0.90)
        self._breath_anim.setEndValue(1.0)
        self._breath_anim.setEasingCurve(QEasingCurve.Type.InOutSine)
        self._breath_anim.setLoopCount(-1)  # 무한 반복

        # 로고 채움(좌→우) 애니메이션
        self._fill_anim = QPropertyAnimation(self.logo_widget, b"progress", self)
        self._fill_anim.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self._fill_anim.setStartValue(0.0)
        self._fill_anim.setEndValue(1.0)

        # 채움 완료 시 튕김(스케일) 모션
        self._bounce_anim = QPropertyAnimation(self.logo_widget, b"scale", self)
        self._bounce_anim.setDuration(420)
        # 0.0 -> 1.0, 중간에 살짝 커졌다가 다시 제자리
        self._bounce_anim.setStartValue(1.0)
        self._bounce_anim.setKeyValueAt(0.65, 1.08)
        self._bounce_anim.setEndValue(1.0)
        self._bounce_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        # 채움이 다 차면 bounce
        self._fill_anim.finished.connect(self._bounce_anim.start)

        # 환영 문구
        self.title_label = QLabel("ValkyrieFS")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_font = QFont("Roboto", 20)
        title_font.setBold(True)
        self.title_label.setFont(title_font)

        self.subtitle_label = QLabel("어서오세요, 환영합니다.")
        self.subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.subtitle_label.setFont(QFont("Roboto", 12))

        panel_layout.addWidget(self.logo_container)
        layout.addSpacing(2)
        panel_layout.addWidget(self.title_label)
        panel_layout.addWidget(self.subtitle_label)

        # 스타일(스플래시 전용): 백플레이트는 "박스"가 아니라 유리판 느낌(테두리/강한 대비 없음)
        self.setStyleSheet(
            """
            QWidget#splashPanel {
                background-color: rgba(248, 250, 252, 235); /* #f8fafc with alpha */
                border-radius: 26px;
            }
            QLabel {
                color: #0f172a;
                background: transparent;
                font-family: "Roboto", "Noto Sans KR", "Pretendard", "Malgun Gothic", sans-serif;
            }
            """
        )

        self.resize(520, 420)

    def start(self, duration_ms: int = 10000) -> None:
        self._breath_anim.start()
        self._fill_anim.setDuration(max(300, int(duration_ms)))
        self._fill_anim.start()

