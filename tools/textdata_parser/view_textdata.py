#!/usr/bin/env python3
"""view_textdata - PyQt6 GUI viewer for textdata_en_parsed.json.

Displays all extracted strings in a searchable, sortable table.
"""

import json
import sys
from pathlib import Path

from PyQt6.QtCore import QAbstractTableModel, QModelIndex, Qt, QSortFilterProxyModel
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QApplication,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QTableView,
    QVBoxLayout,
    QWidget,
)


class StringTableModel(QAbstractTableModel):
    """Wraps parsed JSON data into a Qt table model."""

    COLUMNS = [
        'index_addr',
        'string_addr',
        'stripped_offset',
        'hex_data',
        'ascii_data',
        'byte_count',
    ]

    HEADER_LABELS = [
        'INDEX_ADDR',
        'STRING_ADDR',
        'STRIPPED',
        'HEX',
        'ASCII',
        'BYTES',
    ]

    def __init__(self, data: list[dict]):
        super().__init__()
        self._rows = data

    def rowCount(self, parent=QModelIndex()) -> int:
        return len(self._rows)

    def columnCount(self, parent=QModelIndex()) -> int:
        return len(self.COLUMNS)

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole):
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == Qt.Orientation.Horizontal:
            return self.HEADER_LABELS[section]
        return str(section + 1)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        if role == Qt.ItemDataRole.DisplayRole or role == Qt.ItemDataRole.EditRole:
            row = self._rows[index.row()]
            col = self.COLUMNS[index.column()]
            val = row.get(col)
            if isinstance(val, str):
                return val
            return str(val) if val is not None else ''
        if role == Qt.ItemDataRole.TextAlignmentRole:
            col = self.COLUMNS[index.column()]
            if col in ('hex_data', 'ascii_data'):
                return Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
            return Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter
        return None

    def flags(self, index: QModelIndex):
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable


class MainWindow(QMainWindow):
    """Main application window."""

    def __init__(self, json_path: str):
        super().__init__()
        self.setWindowTitle('Text Data Viewer')
        self.resize(1200, 700)

        self._load_data(json_path)

    def _load_data(self, json_path: str):
        path = Path(json_path)
        if not path.exists():
            print(f'Error: file not found: {json_path}')
            sys.exit(1)

        data = json.loads(path.read_text(encoding='utf-8'))
        strings = data.get('strings', [])
        print(f'Loaded {len(strings)} strings from {path.name}')

        self._model = StringTableModel(strings)

        self._proxy = QSortFilterProxyModel()
        self._proxy.setSourceModel(self._model)
        self._proxy.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self._proxy.setSortRole(Qt.ItemDataRole.EditRole)

        self._setup_ui()

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # Search bar
        search_layout = QHBoxLayout()
        search_label = QLabel('Search:')
        search_label.setStyleSheet('font-weight: bold;')
        search_layout.addWidget(search_label)

        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText('Type to filter...')
        self._search_input.textChanged.connect(self._on_search_changed)
        search_layout.addWidget(self._search_input)
        search_layout.setStretch(1, 1)
        layout.addLayout(search_layout)

        # Table
        self._table = QTableView()
        self._table.setModel(self._proxy)
        self._table.setAlternatingRowColors(True)
        self._table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
        self._table.horizontalHeader().setStretchLastSection(False)
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)


        self._table.setFont(QFont('Monospace', 10))
        self._table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._table.customContextMenuRequested.connect(self._on_context_menu)
        layout.addWidget(self._table)

        # Status bar
        self._status_label = QLabel('')
        self.statusBar().addPermanentWidget(self._status_label)
        self.statusBar().showMessage(f'Loaded {self._model.rowCount()} strings')

    def _on_search_changed(self, text: str):
        self._proxy.setFilterRegularExpression(text)
        visible = self._proxy.rowCount()
        total = self._model.rowCount()
        self.statusBar().showMessage(f'{visible} / {total} strings')

    def _on_context_menu(self, pos):
        index = self._table.indexAt(pos)
        if not index.isValid():
            return

        menu = QMenu(self)
        copy_action = menu.addAction('Copy')
        action = menu.exec(self._table.viewport().mapToGlobal(pos))

        if action == copy_action:
            col_idx = index.column()
            proxy_data = self._table.model().data(index, Qt.ItemDataRole.DisplayRole)
            if proxy_data:
                QApplication.clipboard().setText(str(proxy_data))


def main():
    if len(sys.argv) > 1:
        json_path = sys.argv[1]
    else:
        json_path = 'textdata_en_parsed.json'

    app = QApplication(sys.argv)
    app.setStyle('Fusion')

    win = MainWindow(json_path)
    win.show()

    sys.exit(app.exec())


if __name__ == '__main__':
    main()
