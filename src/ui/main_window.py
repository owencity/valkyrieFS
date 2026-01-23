"""
메인 UI 창

PySide6를 사용하여 파일 검색 애플리케이션의 사용자 인터페이스를 제공합니다.
모던하고 깔끔한 디자인을 위해 Qt Style Sheets (QSS)를 사용합니다.

UI 코드와 검색/인덱싱 로직이 명확히 분리되어 있습니다.
"""
import sys
from pathlib import Path
from typing import Optional
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QLineEdit, QListView, QLabel,
    QPushButton, QHBoxLayout, QMessageBox
)
from PySide6.QtCore import Qt, Signal, QThread, QTimer, QObject, QRunnable, QThreadPool, Slot, QEvent
from PySide6.QtGui import QFont, QKeyEvent, QShortcut, QKeySequence, QInputMethodEvent

from src.core.index_manager import IndexManager
from src.core.searcher import Searcher
from src.models.file_entry import FileEntry
from src.ui.styles import APPLICATION_STYLE
from src.ui.result_list_model import ResultListModel
from src.ui.result_item_delegate import ResultItemDelegate


class IndexingThread(QThread):
    """
    백그라운드에서 인덱싱 작업을 수행하는 스레드
    
    인덱싱은 I/O 집약적 작업이므로 UI를 블로킹하지 않도록
    별도의 스레드에서 실행합니다.
    
    새로운 아키텍처에서는 IndexManager를 사용하여
    증분 업데이트와 선택적 인덱싱, 전체 폴더 인덱싱을 지원합니다.
    """
    indexing_finished = Signal(int)  # 인덱싱 완료 시 파일 개수를 전달
    indexing_progress = Signal(str, int, int)  # 진행 상황 시그널 (경로, 현재, 전체)
    indexing_error = Signal(str)  # 오류 발생 시 오류 메시지 전달
    
    def __init__(
        self, 
        index_manager: IndexManager, 
        scan_mode: str = "default"
    ):
        """
        인덱싱 스레드 초기화
        
        Args:
            index_manager: 사용할 인덱스 관리자 인스턴스
            scan_mode: "default" (기본 경로들), "entire" (전체 홈 디렉토리)
        """
        super().__init__()
        self.index_manager = index_manager
        self.scan_mode = scan_mode
    
    def run(self) -> None:
        """
        스레드 실행 메서드
        
        인덱싱 작업을 수행하고 완료/오류 시그널을 발생시킵니다.
        """
        try:
            def progress_callback(path: str, current: int, total: int) -> None:
                self.indexing_progress.emit(path, current, total)
            
            if self.scan_mode == "entire":
                # 전체 홈 디렉토리 스캔
                count = self.index_manager.scan_entire_home_directory(progress_callback)
                self.indexing_finished.emit(count)
            else:
                # 기본 경로들 스캔 (선택적 인덱싱)
                results = self.index_manager.scan_default_paths(progress_callback)
                total_count = sum(results.values())
                self.indexing_finished.emit(total_count)
        except Exception as e:
            self.indexing_error.emit(str(e))


class MainWindow(QMainWindow):
    """
    메인 애플리케이션 창
    
    검색 입력 박스와 결과 리스트를 포함하며,
    사용자 입력에 따라 실시간으로 검색 결과를 업데이트합니다.
    
    키보드 중심 인터랙션을 지원하여 빠른 작업 흐름을 제공합니다.
    """
    search_finished = Signal(int, str, list)  # generation, query, results
    
    startup_loaded = Signal(int)   # 스냅샷 로드 결과(파일 개수)
    startup_failed = Signal(str)   # 스냅샷 로드 실패 메시지

    def __init__(self, auto_start: bool = True):
        """
        메인 창 초기화
        
        UI 컴포넌트를 생성하고, 인덱서와 검색기를 초기화합니다.
        첫 실행 시 자동으로 인덱싱을 시작합니다.
        """
        super().__init__()
        self.setWindowTitle("ValkyrieFS - 파일 검색")
        self.setGeometry(100, 100, 900, 650)  # 약간 큰 창 크기 (넉넉한 공간)
        
        # 핵심 컴포넌트 초기화 (UI와 로직 분리)
        # 새로운 아키텍처: IndexManager가 인덱싱과 영속화를 관리
        self.index_manager = IndexManager()
        self.searcher: Optional[Searcher] = None
        self.indexing_thread: Optional[IndexingThread] = None

        # 검색 스레드 풀 + 검색 취소(세대 번호로 무시)
        self.search_thread_pool = QThreadPool.globalInstance()
        self._search_generation = 0
        self.search_finished.connect(self._on_search_finished)

        # IME(한글 조합) 입력 중 preedit 문자열을 포함한 "미리보기 쿼리"
        # QLineEdit.text()에 아직 확정(commit)되지 않은 문자를 검색에 반영하기 위함
        self._ime_preview_query: Optional[str] = None
        
        # 실시간 검색을 위한 디바운스 타이머
        # Everything처럼 타이핑할 때마다 자동 검색 (디바운스로 성능 최적화)
        self.search_timer = QTimer(self)
        self.search_timer.setSingleShot(True)  # 한 번만 실행
        self.search_timer.timeout.connect(self._on_search_timer_timeout)
        self.debounce_delay = 150  # 150ms 디바운스 (Everything 수준)
        
        # UI 구성
        self._setup_ui()
        self._apply_styles()
        self._setup_keyboard_shortcuts()
        
        # 스냅샷 로드/초기 인덱싱은 UI 스레드를 막지 않도록 비동기로 시작
        self.startup_loaded.connect(self._on_startup_loaded)
        self.startup_failed.connect(self._on_startup_failed)

        if auto_start:
            self.start_initial_indexing_async()

    def start_initial_indexing_async(self, status_callback=None) -> None:
        """
        앱 시작 시 스냅샷 로드/초기 인덱싱을 백그라운드에서 시작합니다.
        status_callback을 넘기면(예: 스플래시) 상태 메시지를 함께 업데이트합니다.
        """
        if status_callback:
            try:
                status_callback("스냅샷(index.dat) 로드 중...")
            except Exception:
                pass

        class _SnapshotLoadRunnable(QRunnable):
            def __init__(self, window: "MainWindow"):
                super().__init__()
                self.window = window

            def run(self) -> None:
                try:
                    count = self.window.index_manager.load_index_from_db()
                    self.window.startup_loaded.emit(int(count))
                except Exception as e:
                    self.window.startup_failed.emit(str(e))

        self.search_thread_pool.start(_SnapshotLoadRunnable(self))

    @Slot(int)
    def _on_startup_loaded(self, count: int) -> None:
        # 기존 로직 재사용: 스냅샷이 있으면 즉시 검색 가능
        if count > 0:
            self.status_label.setText(
                f"인덱스 로드 완료: {count:,}개 파일 - 검색 가능 "
                f"(Everything 방식: 초기 스캔 생략)"
            )
            self.search_input.setEnabled(True)
            self.search_button.setEnabled(True)
            self.reindex_button.setEnabled(True)
            return

        # 스냅샷이 없으면 초기 스캔
        self.status_label.setText("초기 인덱싱 시작 중... (처음 한 번만 필요)")
        self._start_indexing(scan_mode="entire")

    @Slot(str)
    def _on_startup_failed(self, message: str) -> None:
        self.status_label.setText(f"인덱스 로드 실패: {message}")
        # 실패 시에도 재인덱싱 경로를 열어둠(사용자가 수동으로 재시도 가능)
        self.search_input.setEnabled(False)
        self.search_button.setEnabled(False)
        self.reindex_button.setEnabled(True)
    
    def _setup_ui(self) -> None:
        """
        UI 컴포넌트를 생성하고 레이아웃을 구성합니다.
        
        넉넉한 간격과 명확한 시각적 계층 구조를 제공합니다.
        """
        # 중앙 위젯과 레이아웃
        central_widget = QWidget()
        central_widget.setObjectName("centralWidget")  # 스타일시트 적용을 위한 이름
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        layout.setSpacing(16)  # 더 넉넉한 간격 (세련된 느낌)
        layout.setContentsMargins(32, 32, 32, 32)  # 더 넉넉한 여백 (트렌디한 느낌)
        
        # 검색 입력 박스와 검색 버튼을 포함하는 레이아웃
        search_card = QWidget()
        search_card.setObjectName("searchCard")
        search_layout = QHBoxLayout(search_card)
        search_layout.setSpacing(12)  # 더 넉넉한 간격
        search_layout.setContentsMargins(16, 14, 16, 14)
        
        # 검색 입력 박스 (시각적으로 강조)
        self.search_input = QLineEdit()
        self.search_input.setObjectName("searchInput")  # QSS 선택자를 위한 이름
        self.search_input.setPlaceholderText("파일명 또는 경로를 입력하세요...")
        self.search_input.setFont(QFont("Roboto", 14))
        # Enter 키로 검색 (실시간 검색 제거)
        # Everything 방식: 실시간 검색 (디바운스 적용)
        self.search_input.textChanged.connect(self._on_search_text_changed)
        self.search_input.returnPressed.connect(self._on_search_button_clicked)
        # 한글 IME 조합(preedit) 중에도 검색이 갱신되도록 이벤트 필터 설치
        self.search_input.installEventFilter(self)
        
        # 검색 입력 박스에 포커스 설정 (키보드 중심 인터랙션)
        # 애플리케이션 시작 시 바로 입력 가능하도록
        self.search_input.setFocus()
        
        search_layout.addWidget(self.search_input, 1)  # 남은 공간을 차지
        
        # 검색 버튼
        self.search_button = QPushButton("검색")
        self.search_button.setObjectName("searchButton")
        self.search_button.clicked.connect(self._on_search_button_clicked)
        self.search_button.setEnabled(False)  # 인덱싱 완료 전에는 비활성화
        search_layout.addWidget(self.search_button)
        
        layout.addWidget(search_card)

        # 힌트 라벨 (키보드 중심 UX)
        self.hint_label = QLabel("팁: Ctrl+L 검색 포커스 · Esc 지우기 · Enter 선택 항목 열기")
        self.hint_label.setObjectName("hintLabel")
        self.hint_label.setFont(QFont("Roboto", 11))
        layout.addWidget(self.hint_label)
        
        # 상태 표시 라벨 (정보성 텍스트)
        self.status_label = QLabel("초기화 중...")
        self.status_label.setObjectName("statusLabel")  # QSS 선택자를 위한 이름
        self.status_label.setFont(QFont("Roboto", 12))
        layout.addWidget(self.status_label)
        
        # 결과 리스트
        results_card = QWidget()
        results_card.setObjectName("resultsCard")
        results_layout = QVBoxLayout(results_card)
        results_layout.setContentsMargins(12, 12, 12, 12)
        results_layout.setSpacing(0)

        self.result_list = QListView()
        self.result_list.setObjectName("resultList")
        self.result_list.setFont(QFont("Pretendard", 11))

        # 가상 리스트: 모델/델리게이트
        self.result_model = ResultListModel([])
        self.result_delegate = ResultItemDelegate(self.result_list)
        self.result_list.setModel(self.result_model)
        self.result_list.setItemDelegate(self.result_delegate)
        self.result_list.setUniformItemSizes(True)  # 스크롤 성능 향상
        self.result_list.setMouseTracking(True)     # hover repaint

        # 활성화(Enter) / 더블클릭 지원
        self.result_list.activated.connect(self._on_item_activated)
        # 주의: QListView에서는 doubleClicked가 activated도 함께 유발하는 경우가 있어
        # 핸들러를 두 개 연결하면 탐색기가 2번 뜰 수 있습니다.
        # activated 하나로 통일 (Enter/더블클릭 모두 처리)
        
        # 키보드 네비게이션을 위한 설정
        self.result_list.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        
        results_layout.addWidget(self.result_list)
        layout.addWidget(results_card, 1)  # 남은 공간을 차지
        
        # 재인덱싱 버튼 (하단 배치)
        button_layout = QHBoxLayout()
        self.reindex_button = QPushButton("전체 재인덱싱")
        self.reindex_button.clicked.connect(lambda: self._start_indexing(scan_mode="entire", force_reindex=True))
        self.reindex_button.setEnabled(False)
        button_layout.addWidget(self.reindex_button)
        button_layout.addStretch()  # 오른쪽 정렬을 위한 여백
        layout.addLayout(button_layout)
    
    def _apply_styles(self) -> None:
        """
        Qt Style Sheets (QSS)를 적용하여 모던하고 깔끔한 디자인을 제공합니다.
        
        QSS는 CSS와 유사한 문법을 사용하여 위젯의 시각적 스타일을 정의합니다.
        스타일과 로직이 분리되어 있어 디자인 변경이 용이합니다.
        """
        self.setStyleSheet(APPLICATION_STYLE)
    
    def _setup_keyboard_shortcuts(self) -> None:
        """
        키보드 단축키를 설정하여 키보드 중심 인터랙션을 제공합니다.
        
        키보드만으로도 애플리케이션을 효율적으로 사용할 수 있도록 합니다.
        이는 빠른 작업 흐름과 접근성을 향상시킵니다.
        """
        # Ctrl+L: 검색 입력 박스로 포커스 이동
        focus_search_shortcut = QShortcut(QKeySequence("Ctrl+L"), self)
        focus_search_shortcut.activated.connect(
            lambda: self.search_input.setFocus()
        )
        
        # Escape: 검색 입력 박스 비우기 및 포커스 이동
        clear_search_shortcut = QShortcut(QKeySequence("Escape"), self)
        clear_search_shortcut.activated.connect(
            lambda: (self.search_input.clear(), self.search_input.setFocus())
        )
    
    def keyPressEvent(self, event: QKeyEvent) -> None:
        """
        키보드 이벤트를 처리하여 키보드 중심 인터랙션을 제공합니다.
        
        Args:
            event: 키보드 이벤트
        """
        # Down Arrow: 검색 입력에서 첫 번째 결과로 이동
        if event.key() == Qt.Key.Key_Down and self.search_input.hasFocus():
            if self.result_model.rowCount() > 0:
                self.result_list.setCurrentIndex(self.result_model.index(0, 0))
                self.result_list.setFocus()
                event.accept()
                return
        
        # Up Arrow: 결과 리스트의 첫 번째 항목에서 검색 입력으로 이동
        if event.key() == Qt.Key.Key_Up and self.result_list.hasFocus():
            if self.result_list.currentIndex().row() == 0:
                self.search_input.setFocus()
                event.accept()
                return
        
        super().keyPressEvent(event)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        """
        IME(한글 조합) 입력 중에도 검색이 업데이트되도록 보조 트리거를 제공합니다.

        Qt의 textChanged는 조합이 "확정(commit)"될 때만 늦게 들어오는 경우가 있어,
        InputMethod 이벤트에서 preeditString을 포함한 미리보기 쿼리를 만들어 검색합니다.
        """
        if watched is self.search_input and not self.index_manager.is_indexing:
            if event.type() == QEvent.Type.InputMethod:
                # IME 조합(preedit) 문자열을 포함해 "정" 1글자만 입력해도 즉시 검색되게 함
                try:
                    ime_event: QInputMethodEvent = event  # type: ignore[assignment]
                    preedit = ime_event.preeditString()
                except Exception:
                    preedit = ""

                base = self.search_input.text()
                if preedit:
                    # base는 확정된 텍스트, preedit은 조합 중 텍스트
                    self._ime_preview_query = f"{base}{preedit}"
                else:
                    self._ime_preview_query = None

                self.search_timer.stop()
                self.search_timer.start(self.debounce_delay)

            elif event.type() == QEvent.Type.KeyRelease:
                # 영문/숫자 입력 등도 자연스럽게 디바운스 유지
                self.search_timer.stop()
                self.search_timer.start(self.debounce_delay)
        return super().eventFilter(watched, event)
    
    def _start_initial_indexing(self) -> None:
        """
        애플리케이션 시작 시 초기 인덱싱을 수행합니다.
        
        Everything 방식:
        1. 먼저 데이터베이스에서 기존 인덱스 로드 (빠른 시작)
        2. 인덱스가 있으면 스캔 생략 (Everything처럼 즉시 검색 가능)
        3. 인덱스가 없거나 부족할 때만 초기 스캔 수행
        4. 향후: USN Journal 모니터링으로 실시간 업데이트
        """
        # 레거시(동기) 메서드는 남겨두되, 이제는 비동기 경로를 사용합니다.
        # (호환성 유지용)
        self.start_initial_indexing_async()
    
    def _start_indexing(self, scan_mode: str = "entire", force_reindex: bool = False) -> None:
        """
        인덱싱 작업을 시작합니다.
        
        새로운 아키텍처에서는 선택적 인덱싱, 전체 폴더 인덱싱, 증분 업데이트를 지원합니다.
        
        Args:
            scan_mode: "default" (기본 경로들), "entire" (전체 홈 디렉토리)
            force_reindex: True이면 전체 재인덱싱
        """
        if self.index_manager.is_indexing:
            # 이미 인덱싱 중이면 중단하지 않고 무시
            return
        
        if force_reindex:
            mode_text = "전체 폴더" if scan_mode == "entire" else "기본 경로"
            self.status_label.setText(f"{mode_text} 전체 재인덱싱 시작...")
        else:
            mode_text = "전체 홈 디렉토리" if scan_mode == "entire" else "기본 경로들"
            self.status_label.setText(f"{mode_text} 증분 업데이트 중...")
        
        # 검색은 계속 가능 (이미 로드된 인덱스 사용)
        # 하지만 재인덱싱 중에는 버튼 비활성화
        if force_reindex:
            self.search_input.setEnabled(False)
            self.search_button.setEnabled(False)
            self.result_model.set_entries([])
        
        self.reindex_button.setEnabled(False)
        
        # 백그라운드 스레드에서 인덱싱 수행
        self.indexing_thread = IndexingThread(self.index_manager, scan_mode)
        self.indexing_thread.indexing_finished.connect(self._on_indexing_finished)
        self.indexing_thread.indexing_progress.connect(self._on_indexing_progress)
        self.indexing_thread.indexing_error.connect(self._on_indexing_error)
        self.indexing_thread.start()
    
    def _on_indexing_progress(self, path: str, current: int, total: int) -> None:
        """
        인덱싱 진행 상황 콜백
        
        Args:
            path: 현재 스캔 중인 경로
            current: 현재 처리된 파일 수
            total: 전체 파일 수
        """
        progress_text = f"인덱싱 중: {Path(path).name} ({current:,}/{total:,})..."
        self.status_label.setText(progress_text)
    
    def _on_indexing_finished(self, file_count: int) -> None:
        """
        인덱싱 완료 시 호출되는 콜백
        
        새로운 아키텍처에서는 인덱스가 메모리와 데이터베이스에 모두 저장됩니다.
        
        Args:
            file_count: 인덱싱된 파일의 개수
        """
        # 통계 정보 표시
        stats = self.index_manager.get_statistics()
        memory_mb = stats.get('memory_size_mb', 0)
        self.status_label.setText(
            f"인덱싱 완료: {stats['total_files']:,}개 파일 "
            f"(메모리: {memory_mb:.1f}MB) - 검색 가능"
        )
        
        self.search_input.setEnabled(True)
        self.search_button.setEnabled(True)
        self.reindex_button.setEnabled(True)
        
        # 검색 입력 박스에 포커스 설정 (키보드 중심 인터랙션)
        self.search_input.setFocus()
    
    def _on_indexing_error(self, error_message: str) -> None:
        """
        인덱싱 중 오류 발생 시 호출되는 콜백
        
        Args:
            error_message: 오류 메시지
        """
        self.status_label.setText(f"인덱싱 오류: {error_message}")
        self.search_input.setEnabled(True)
        self.search_button.setEnabled(True)
        self.reindex_button.setEnabled(True)
        QMessageBox.critical(self, "인덱싱 오류", f"인덱싱 중 오류가 발생했습니다:\n{error_message}")
    
    def _on_search_text_changed(self, text: str) -> None:
        """
        검색 입력 텍스트가 변경될 때 호출됩니다.
        
        Everything 방식: 실시간 검색 (디바운스 적용)
        타이핑 중에는 검색을 지연시키고, 타이핑이 멈추면 자동 검색합니다.
        """
        # 인덱싱이 완료되지 않았으면 검색 불가
        # (Everything 방식: C++ 메모리 인덱스에서 검색)
        if self.index_manager.is_indexing:
            return

        # textChanged는 "확정(commit)" 기준이므로 IME 미리보기는 해제
        self._ime_preview_query = None
        
        # 디바운스: 타이핑이 멈출 때까지 대기
        # 이전 타이머 취소하고 새로 시작
        self.search_timer.stop()
        self.search_timer.start(self.debounce_delay)
    
    def _on_search_timer_timeout(self) -> None:
        """
        디바운스 타이머가 만료되면 자동으로 검색을 수행합니다.
        
        Everything처럼 타이핑이 멈추면 즉시 검색합니다.
        """
        if self.index_manager.is_indexing:
            return

        # IME 조합 중이면 preedit까지 포함한 미리보기 쿼리로 검색
        query = self._ime_preview_query if self._ime_preview_query is not None else self.search_input.text()
        self._request_search(query)
    
    def _on_search_button_clicked(self) -> None:
        """
        검색 버튼을 클릭하거나 Enter 키를 눌렀을 때 호출됩니다.
        
        디바운스 타이머를 취소하고 즉시 검색을 수행합니다.
        """
        if self.index_manager.is_indexing:
            return
        
        # 디바운스 타이머 취소 (즉시 검색)
        self.search_timer.stop()
        
        query = self.search_input.text()
        self._request_search(query, immediate=True)
    
    def _request_search(self, query: str, immediate: bool = False) -> None:
        """
        검색을 백그라운드에서 수행하도록 요청합니다.
        
        Everything 방식:
        - UI 스레드는 입력/렌더링만 담당
        - 검색은 백그라운드에서 수행
        - 새로운 입력이 오면 이전 검색 결과는 무시(취소 효과)
        
        Args:
            query: 검색 쿼리 문자열
        """
        # 세대 증가: 이전 검색 결과는 무시
        self._search_generation += 1
        generation = self._search_generation

        runnable = _SearchRunnable(self, generation, query)
        self.search_thread_pool.start(runnable)

        # 즉시 반응(옵션): 상태 라벨만 먼저 업데이트
        if immediate and query:
            self.status_label.setText(f"'{query}' 검색 중...")

    @Slot(int, str, list)
    def _on_search_finished(self, generation: int, query: str, results: list) -> None:
        # 최신 검색만 반영 (cancel 효과)
        if generation != self._search_generation:
            return

        self._render_results(query, results)

    def _render_results(self, query: str, results: list) -> None:
        """
        UI 스레드에서 결과 렌더링 (가상 리스트)
        """
        self.result_model.set_entries(results)
        
        # 결과 개수 업데이트 (정보 제공)
        if query:
            self.status_label.setText(
                f"'{query}' 검색 결과: {len(results):,}개 (가상 리스트)"
            )
        else:
            self.status_label.setText(
                f"전체 파일: {len(results):,}개 (가상 리스트)"
            )
    
    def _format_size(self, size_bytes: int) -> str:
        """
        파일 크기를 읽기 쉬운 형식으로 변환합니다.
        
        Args:
            size_bytes: 바이트 단위 크기
            
        Returns:
            포맷된 크기 문자열 (예: "1.5 MB")
        """
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.1f} PB"
    
    def _on_item_activated(self, index) -> None:
        """
        결과 리스트 아이템이 활성화되었을 때 호출됩니다.
        
        Enter 키 또는 더블 클릭으로 호출되므로 키보드/마우스 인터랙션을 모두 지원합니다.
        
        Args:
            index: 활성화된 모델 인덱스
        """
        entry: FileEntry = index.data(Qt.ItemDataRole.UserRole)
        if entry:
            self._open_file_location(entry)
    
    def _open_file_location(self, entry: FileEntry) -> None:
        """
        Windows 탐색기에서 파일 위치를 엽니다.
        
        Args:
            entry: 열 파일 엔트리
        """
        file_path = Path(entry.path)
        if file_path.exists():
            # Windows 탐색기에서 파일 선택하여 열기
            import subprocess
            subprocess.run(
                ['explorer', '/select,', str(file_path.resolve())],
                check=False
            )


class _SearchRunnable(QRunnable):
    """
    백그라운드 검색 작업

    - 검색은 C++ 메모리 인덱스에서 수행
    - 결과 FileEntry 리스트만 UI 스레드로 전달
    - cancel은 generation mismatch로 처리(이전 결과 무시)
    """

    def __init__(self, window: MainWindow, generation: int, query: str):
        super().__init__()
        self.window = window
        self.generation = generation
        self.query = query

    def run(self) -> None:
        try:
            # 1~2글자도 즉시 응답해야 하므로 max_results는 넉넉히(가상 리스트라 렌더 부담 낮음)
            results = self.window.index_manager.search(self.query, max_results=2000)
        except Exception:
            results = []

        # UI 스레드로 안전하게 전달 (queued signal)
        self.window.search_finished.emit(self.generation, self.query, results)
