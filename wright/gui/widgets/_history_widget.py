import logging
from typing import Iterable, Optional, cast

from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtWidgets import (
    QHeaderView,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..globals import _STORAGE_DIR
from ..models import OverallStatus, PartialRun

_LOGGER = logging.getLogger(__name__)


class HistoryWidget(QWidget):
    """Show previous runs."""

    runSelected = pyqtSignal(PartialRun)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._layout = QVBoxLayout()
        self.setLayout(self._layout)
        self.setMinimumWidth(250)

        self._table = QTableWidget(self)
        self._table.setColumnCount(2)
        self._table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._table.setHorizontalHeaderLabels(("Done at", "Hostname"))
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Fixed
        )
        self._table.setColumnWidth(0, 140)
        self._table.verticalHeader().hide()
        self._table.setShowGrid(False)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self._layout.addWidget(self._table)

        self._table.currentItemChanged.connect(self._onSelection)

        self.refresh()

    def _onSelection(self, current: QTableWidgetItem) -> None:
        partial_run = current.data(Qt.ItemDataRole.UserRole)
        self.runSelected.emit(partial_run)

    def latestRun(self) -> Optional[PartialRun]:
        item = cast(
            Optional[QTableWidgetItem], self._table.item(self._table.rowCount() - 1, 0)
        )
        if item is None:
            return None
        partial_run = item.data(Qt.ItemDataRole.UserRole)
        assert isinstance(partial_run, PartialRun)
        return partial_run

    def refresh(self) -> None:
        partial_runs = list(self._partial_runs())
        # Sort by done date
        partial_runs = sorted(partial_runs, key=lambda pr: pr.done_at)
        self._table.setRowCount(len(partial_runs))
        for row, partial_run in enumerate(partial_runs):
            # Done at
            done_at = partial_run.done_at.strftime("%Y-%m-%d %H:%M:%S")
            done_at_item = QTableWidgetItem(done_at)
            _set_item_details(done_at_item, partial_run)
            self._table.setItem(row, 0, done_at_item)
            # Hostname
            hostname_item = QTableWidgetItem(partial_run.plan.parameters.hostname)
            _set_item_details(hostname_item, partial_run)
            self._table.setItem(row, 1, hostname_item)
        # Wait 0.1 seconds before we scroll. Otherwise, it doesn't actually
        # scroll to the bottom. Maybe the scroll happens before the UI
        # refreshes?
        QTimer.singleShot(100, self._scroll_to_bottom)

    def _scroll_to_bottom(self) -> None:
        scroll_bar = self._table.verticalScrollBar()
        scroll_bar.setValue(scroll_bar.maximum())

    def _partial_runs(self) -> Iterable[PartialRun]:
        directories = (d for d in _STORAGE_DIR.iterdir() if d.is_dir())
        for directory in directories:
            try:
                yield PartialRun.from_dir(directory)
            except ValueError as exc:
                _LOGGER.warning(
                    f"Could not parse run directory {directory} due to: {exc}"
                )


def _set_item_details(item: QTableWidgetItem, partial_run: PartialRun) -> None:
    item.setFlags(Qt.ItemFlag.ItemIsEnabled)
    item.setData(Qt.ItemDataRole.UserRole, partial_run)
    # Set background color
    background_color: Optional[Qt.GlobalColor] = None
    if partial_run.status.overall is OverallStatus.COMPLETED:
        background_color = Qt.GlobalColor.green
    elif partial_run.status.overall is OverallStatus.FAILED:
        background_color = Qt.GlobalColor.red
    if background_color is not None:
        item.setBackground(background_color)
