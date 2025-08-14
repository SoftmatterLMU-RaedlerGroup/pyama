#!/usr/bin/env python3

import sys
from PySide6.QtWidgets import QApplication
from pyama_qt.processing.ui.main_window import MainWindow
import multiprocessing as mp

def main():
    app = QApplication(sys.argv)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    mp.freeze_support()
    mp.set_start_method("spawn", True)
    main()
