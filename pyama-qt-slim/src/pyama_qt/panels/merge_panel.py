"""Merge panel for combining analysis results."""

from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


class MergePanel(QWidget):
    """Panel for merging and combining analysis results."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        main_layout = QVBoxLayout(self)

        # Create the two main sections
        assign_group = self._create_assign_group()
        merge_group = self._create_merge_group()

        # Add to main layout with equal stretch
        main_layout.addWidget(assign_group, 1)
        main_layout.addWidget(merge_group, 1)

    def _create_assign_group(self) -> QGroupBox:
        """Create the FOV assignment section."""
        group = QGroupBox("Assign FOVs")
        layout = QVBoxLayout(group)

        # Sample table with mock data
        self.sample_table = QTableWidget()
        self.sample_table.setColumnCount(4)
        self.sample_table.setHorizontalHeaderLabels(["Sample", "FOV Start", "FOV End", "Channel"])

        # Add mock data
        mock_data = [
            ["Sample_001", "1", "10", "GFP"],
            ["Sample_002", "11", "20", "RFP"],
            ["Sample_003", "21", "30", "DAPI"],
            ["Sample_004", "31", "40", "GFP"],
        ]

        self.sample_table.setRowCount(len(mock_data))
        for row, data in enumerate(mock_data):
            for col, value in enumerate(data):
                self.sample_table.setItem(row, col, QTableWidgetItem(value))

        layout.addWidget(self.sample_table)

        # Create buttons
        self.add_btn = QPushButton("Add Sample")
        self.remove_btn = QPushButton("Remove Selected")
        self.load_btn = QPushButton("Load from YAML")
        self.save_btn = QPushButton("Save to YAML")

        # Arrange buttons in rows
        btn_row1 = QHBoxLayout()
        btn_row1.addWidget(self.add_btn)
        btn_row1.addWidget(self.remove_btn)

        btn_row2 = QHBoxLayout()
        btn_row2.addWidget(self.load_btn)
        btn_row2.addWidget(self.save_btn)

        layout.addLayout(btn_row1)
        layout.addLayout(btn_row2)

        return group

    def _create_merge_group(self) -> QGroupBox:
        """Create the merge samples section."""
        group = QGroupBox("Merge Samples")
        layout = QVBoxLayout(group)

        # Sample YAML selector
        sample_row = QHBoxLayout()
        sample_row.addWidget(QLabel("Sample YAML:"))
        sample_row.addStretch()
        sample_browse_btn = QPushButton("Browse")
        sample_row.addWidget(sample_browse_btn)
        layout.addLayout(sample_row)
        self.sample_edit = QLineEdit()
        self.sample_edit.setText("samples/sample_assignment.yaml")
        layout.addWidget(self.sample_edit)

        # Processing Results YAML selector
        results_row = QHBoxLayout()
        results_row.addWidget(QLabel("Results YAML:"))
        results_row.addStretch()
        results_browse_btn = QPushButton("Browse")
        results_row.addWidget(results_browse_btn)
        layout.addLayout(results_row)
        self.results_edit = QLineEdit()
        self.results_edit.setText("results/processing_results.yaml")
        layout.addWidget(self.results_edit)

        # Merge button
        self.merge_btn = QPushButton("Merge")
        layout.addWidget(self.merge_btn)

        return group
