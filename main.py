import sys

# from PySide6.QtWidgets import QApplication
from PyQt6.QtWidgets import QApplication

from dashboard_fixed import Dashboard

# from dashboard_backup import Dashboard


def main():
    print("Starting application...")

    app = QApplication(sys.argv)

    print("Creating dashboard...")

    window = Dashboard()

    print("Dashboard created.")

    window.show()

    print("Window shown.")

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
