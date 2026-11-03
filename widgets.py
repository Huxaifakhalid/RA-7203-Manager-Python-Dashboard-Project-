from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QVBoxLayout,
)

from PySide6.QtCore import Qt

# ==========================================================
# VALUE CARD
# ==========================================================


class ValueCard(QFrame):

    def __init__(self, title):

        super().__init__()

        self.setFrameShape(QFrame.Shape.Box)

        self.setStyleSheet("""
            QFrame {
                background:#181b1f;
                border:2px solid #444;
                border-radius:10px;
            }
        """)

        layout = QVBoxLayout()

        self.titleLabel = QLabel(title)
        self.titleLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.titleLabel.setStyleSheet("""
            font-size:16px;
            font-weight:bold;
            color:#ffffff;
        """)

        self.valueLabel = QLabel("--")
        self.valueLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.valueLabel.setStyleSheet("""
            font-size:32px;
            font-weight:bold;
            color:#00ff00;
        """)

        layout.addWidget(self.titleLabel)
        layout.addWidget(self.valueLabel)

        self.setLayout(layout)

    def setValue(self, value):

        self.valueLabel.setText(str(value))


# ==========================================================
# FREQUENCY DISPLAY
# ==========================================================


class FrequencyDisplay(QFrame):

    def __init__(self):

        super().__init__()

        self.setFrameShape(QFrame.Shape.Box)

        self.setStyleSheet("""
            QFrame{
                background:black;
                border:3px solid #00aa00;
                border-radius:12px;
            }
        """)

        print("FrequencyDisplay created:", id(self))

        layout = QVBoxLayout()

        title = QLabel("Frequency")

        title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title.setStyleSheet("""
            color:white;
            font-size:16px;
            font-weight:bold;
        """)

        self.value = QLabel("118.500 MHz")

        self.value.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.value.setStyleSheet("""
            color:#00ff00;
            font-size:42px;
            font-weight:bold;
            font-family:Consolas;
        """)

        layout.addWidget(title)

        layout.addWidget(self.value)

        self.setLayout(layout)

    def setValue(self, value):

        self.value.setText(str(value))


# ==========================================================
# STATUS INDICATOR
# ==========================================================


class StatusIndicator(QLabel):

    def __init__(self):

        super().__init__()

        self.disconnected()

    def connected(self):

        self.setText("🟢 Connected")

        self.setStyleSheet("""
            color:green;
            font-size:16px;
            font-weight:bold;
        """)

    def disconnected(self):

        self.setText("🔴 Offline")

        self.setStyleSheet("""
            color:red;
            font-size:16px;
            font-weight:bold;
        """)


# ==========================================================
# ALARM CARD
# ==========================================================


class AlarmCard(ValueCard):

    def __init__(self):

        super().__init__("Alarm")

    def setAlarm(self, alarm):

        self.setValue(alarm)

        if "No Alarm" in alarm:

            self.value.setStyleSheet("""
                color:#00ff00;
                font-size:24px;
                font-weight:bold;
            """)

        else:

            self.value.setStyleSheet("""
                color:red;
                font-size:24px;
                font-weight:bold;
            """)
