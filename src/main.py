"""
Valkyrie 애플리케이션 진입점

이 파일은 애플리케이션을 시작하는 메인 엔트리 포인트입니다.
PySide6 애플리케이션을 초기화하고 메인 창을 표시합니다.
"""
import sys
from pathlib import Path
import time
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon
from PySide6.QtCore import QTimer
from src.ui.splash_screen import SplashScreen
from src.ui.main_window import MainWindow
from src.utils.runtime_paths import resource_path


def main() -> int:
    """
    애플리케이션 메인 함수
    
    PySide6 애플리케이션을 생성하고 메인 창을 표시합니다.
    
    Returns:
        애플리케이션 종료 코드 (0 = 정상 종료)
    """
    # QApplication 인스턴스 생성 (단일 프로세스 애플리케이션)
    app = QApplication(sys.argv)
    
    # 애플리케이션 이름과 버전 설정 (시스템 통합을 위해)
    app.setApplicationName("ValkyrieFS")
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("ValkyrieFS")

    # Windows 작업표시줄 아이콘/그룹핑을 안정적으로 표시하려면 AppUserModelID가 필요합니다.
    # (PyInstaller로 단일 exe로 만들 때도 동일하게 유효)
    if sys.platform == "win32":
        try:
            import ctypes  # 지연 import (Windows에서만)

            app_id = "DevTeam2.ValkyrieFS"
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
        except Exception:
            # AppUserModelID 설정 실패해도 앱은 동작해야 함
            pass

    # 앱 아이콘(날개 로고) 설정
    # Windows 아이콘은 .ico가 가장 안정적(탐색기/작업표시줄/바로가기)
    # 없으면 SVG로 폴백(개발/디버그용)
    ico_path = resource_path("ui/assets/valkyriefs.ico")
    svg_icon_path = resource_path("ui/assets/valkyriefs-wing.svg")
    icon_path = ico_path if ico_path.exists() else svg_icon_path
    if icon_path.exists():
        app_icon = QIcon(str(icon_path))
        app.setWindowIcon(app_icon)
    
    # 중요: 이벤트 루프(app.exec) 시작 전(=여기)에서 무거운 작업을 하면
    # 스플래시조차 렌더링되지 않고 "렉"처럼 보입니다.
    # 따라서 MainWindow 생성/스냅샷 로드는 이벤트 루프가 시작된 뒤(QTimer 0ms)로 미룹니다.
    min_ms = 10000
    started_at = time.monotonic()

    # 스플래시(런처) 화면: "배경 없는 날개 마크"로 좌→우 채움 모션을 자연스럽게 만듭니다.
    splash_logo_path = resource_path("ui/assets/valkyriefs-wing-mark.svg")
    splash = SplashScreen(splash_logo_path if splash_logo_path.exists() else svg_icon_path)
    # 로고: 숨쉬는 효과 + 좌→우 색 채움(10초)
    splash.start(duration_ms=min_ms)
    splash.show()

    state = {"window": None}

    def bootstrap_after_event_loop() -> None:
        window = MainWindow(auto_start=False)
        state["window"] = window
        if not app.windowIcon().isNull():
            window.setWindowIcon(app.windowIcon())

        # 스플래시 표시 중에도 스냅샷 로드는 백그라운드로 시작
        window.start_initial_indexing_async()

        def show_main_window() -> None:
            elapsed_ms = int((time.monotonic() - started_at) * 1000)
            remaining = max(0, min_ms - elapsed_ms)
            if remaining > 0:
                QTimer.singleShot(remaining, show_main_window)
                return

            splash.close()
            window.show()

        QTimer.singleShot(min_ms, show_main_window)

    # 이벤트 루프가 시작된 직후에 부트스트랩 수행
    QTimer.singleShot(0, bootstrap_after_event_loop)

    # 이벤트 루프 시작 (애플리케이션이 종료될 때까지 실행)
    return app.exec()


if __name__ == "__main__":
    # 진입점: 이 스크립트가 직접 실행될 때만 main() 함수 호출
    sys.exit(main())

