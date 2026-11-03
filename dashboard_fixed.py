# ==========================================================
# RA7203 Receiver Dashboard - FINAL COMPLETE VERSION
# PyQt6 + SNMP
# ==========================================================
#
# Retains the RA7203 monitoring dashboard and MDT-style device tab.
# Fixes:
#   1. Proper black background / white text.
#   2. Large Receiver Status row.
#   3. Frequency displayed in MHz.
#   4. Frequency SET is performed in a background thread so the GUI
#      does not freeze and polling cannot immediately overwrite it.
#   5. Screen-saver DIM LEVEL uses the documented
#      intusrScreenSaverLvl OID, range 1..5.
#   6. Screen-saver write is performed in a background thread.
#   7. Offline/Connected status is based on the confirmed frequency
#      read, not on optional OIDs.
#   8. Connected Devices tab includes Add Device, Add Range,
#      Other Devices menu, Connect Selected, Remove and Refresh.
#   9. IP changes do not block the GUI.
#  10. No unverified Mode/State OIDs are used.
#
# IMPORTANT:
# A successful SNMP READ does not guarantee SNMP WRITE permission.
# If the radio returns "noAccess" on a SET, the radio's SNMP write
# community / SNMPv3 RW credentials must be configured correctly.
# The dashboard reports that error instead of pretending the SET worked.
# ==========================================================

import sys
import ipaddress
import traceback
from datetime import datetime

from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QFormLayout,
    QLabel,
    QPushButton,
    QLineEdit,
    QTextEdit,
    QSlider,
    QFrame,
    QComboBox,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QMenu,
    QDialog,
    QDialogButtonBox,
    QMessageBox,
    QScrollArea,
    QToolButton,
)

from device_history import (
    load_devices,
    add_or_update_device,
    set_device_status,
)
from snmp_client_fixed import client, SNMPClient
from config import RX_IP, TX_IP, REFRESH_TIME

from decoder import (
    decode_power_source,
    decode_lo_lock,
    decode_alarm,
)

# ==========================================================
# CONFIRMED RA7203 OIDs
# ==========================================================

OIDS = {
    # Receiver control / monitoring
    "frequency": "1.3.6.1.4.1.22154.3.1.2.3.4.0",  # bsFrequencyICAO, kHz, RW
    "temperature": "1.3.6.1.4.1.22154.3.1.2.5.2.3.5.0",
    "rssi": "1.3.6.1.4.1.22154.3.1.2.5.2.5.4.0",
    "carrier_noise": "1.3.6.1.4.1.22154.3.1.2.5.2.5.10.0",
    "offset": "1.3.6.1.4.1.22154.3.1.2.5.2.5.9.0",
    "alarm": "1.3.6.1.4.1.22154.3.1.2.5.2.7.0",
    # Power
    "power_source": "1.3.6.1.4.1.22154.3.1.2.5.2.3.7.0",
    "dc_input": "1.3.6.1.4.1.22154.3.1.2.5.2.3.8.0",
    "rail_12v": "1.3.6.1.4.1.22154.3.1.2.5.2.3.2.0",
    "rail_5v": "1.3.6.1.4.1.22154.3.1.2.5.2.3.3.0",
    "rail_3v3": "1.3.6.1.4.1.22154.3.1.2.5.2.3.4.0",
    # RF
    "rf_lo_lock": "1.3.6.1.4.1.22154.3.1.2.5.2.2.2.0",
    "lna_current": "1.3.6.1.4.1.22154.3.1.2.5.2.2.4.0",
    "if_current": "1.3.6.1.4.1.22154.3.1.2.5.2.2.5.0",
    "agc": "1.3.6.1.4.1.22154.3.1.2.5.2.5.3.0",
    # IMPORTANT: this is SCREEN SAVER / DIM LEVEL, not intusrDispIntensity.
    # Jotron MIB: intusrScreenSaverLvl, Integer32(1..5), read-write.
    "screen_saver_level": "1.3.6.1.4.1.22154.3.1.2.2.3.5.13.0",
}

# NOTE:
# The MIB hierarchy is intusrConfig 13 -> .13.0 for intusrScreenSaverLvl.
# This is deliberately used instead of intusrDispIntensity (.5.13.0),
# because the requested dashboard control is the radio SCREEN SAVER dim level.

# ==========================================================
# COLORS
# ==========================================================

BG = "#000000"
PANEL = "#080b0d"
CARD = "#0c1013"
CARD_DARK = "#050607"
BORDER = "#303940"
BORDER2 = "#46515a"
GREEN = "#00ff18"
GREEN_DARK = "#00c800"
RED = "#ff3b30"
YELLOW = "#ffb300"
WHITE = "#ffffff"
MUTED = "#aeb7bd"


# ==========================================================
# UI HELPERS
# ==========================================================


def section_title(text):
    label = QLabel(text)
    label.setObjectName("sectionTitle")
    return label


class ParameterCard(QFrame):
    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.setObjectName("parameterCard")
        self.setMinimumHeight(78)
        self.setMaximumHeight(90)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(7, 5, 7, 5)
        layout.setSpacing(3)

        title_label = QLabel(title)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        title_label.setObjectName("cardTitle")
        layout.addWidget(title_label)

        self.valueLabel = QLabel("--")
        self.valueLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.valueLabel.setFont(QFont("Segoe UI", 17, QFont.Weight.Bold))
        self.valueLabel.setObjectName("cardValue")
        layout.addWidget(self.valueLabel)

    def setValue(self, value):
        self.valueLabel.setText(str(value))


class FrequencyPanel(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("frequencyPanel")
        self.setMinimumHeight(108)
        self.setMaximumHeight(120)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 7, 10, 7)
        layout.setSpacing(4)

        title = QLabel("FREQUENCY")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        title.setObjectName("frequencyTitle")
        layout.addWidget(title)

        self.frequencyLabel = QLabel("-- MHz")
        self.frequencyLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.frequencyLabel.setMinimumHeight(55)
        self.frequencyLabel.setFont(QFont("Consolas", 30, QFont.Weight.Bold))
        self.frequencyLabel.setObjectName("frequencyValue")
        layout.addWidget(self.frequencyLabel)

    def setValue(self, value):
        self.frequencyLabel.setText(str(value))


# ==========================================================
# BACKGROUND SNMP WORKERS
# ==========================================================


class SNMPConnectionWorker(QThread):
    finished = pyqtSignal(str, bool, object)

    def __init__(self, ip, parent=None):
        super().__init__(parent)
        self.ip = ip

    def run(self):
        try:
            snmp = SNMPClient()
            snmp.set_ip(self.ip)

            # Use the confirmed frequency OID as the connectivity test.
            # This is better than sysDescr because it tests the actual RA7203.
            _, error = snmp.read(OIDS["frequency"])
            self.finished.emit(self.ip, error is None, error)
        except Exception as exc:
            self.finished.emit(self.ip, False, str(exc))


class SNMPPollWorker(QThread):
    finished = pyqtSignal(str, object, object)

    def __init__(self, ip, parent=None):
        super().__init__(parent)
        self.ip = ip

    def run(self):
        try:
            snmp = SNMPClient()
            snmp.set_ip(self.ip)

            # Frequency is the required connectivity read.
            frequency, error = snmp.read(OIDS["frequency"])
            if error is not None:
                self.finished.emit(self.ip, {}, error)
                return

            data = {"frequency": frequency}

            # Optional monitoring OIDs are read independently. Their failure
            # must NOT make an otherwise reachable receiver appear Offline.
            for name, oid in OIDS.items():
                if name == "frequency":
                    continue
                try:
                    value, _ = snmp.read(oid)
                    data[name] = value
                except Exception:
                    data[name] = None

            self.finished.emit(self.ip, data, None)

        except Exception as exc:
            self.finished.emit(self.ip, {}, str(exc))


class SNMPWriteWorker(QThread):
    finished = pyqtSignal(str, int, object, bool, object)

    def __init__(self, ip, operation, oid, value, parent=None):
        super().__init__(parent)
        self.ip = ip
        self.operation = operation
        self.oid = oid
        self.value = int(value)

    def run(self):
        try:
            snmp = SNMPClient()
            snmp.set_ip(self.ip)
            success, error = snmp.write(self.oid, self.value)
            self.finished.emit(
                self.operation,
                self.value,
                self.ip,
                bool(success),
                error,
            )
        except Exception as exc:
            self.finished.emit(
                self.operation,
                self.value,
                self.ip,
                False,
                str(exc),
            )


# ==========================================================
# DASHBOARD
# ==========================================================


class Dashboard(QMainWindow):
    def __init__(self):
        super().__init__()

        print("Creating dashboard...")

        self.setWindowTitle("RA7203 Receiver Dashboard")
        self.resize(1600, 900)
        self.setMinimumSize(1280, 720)

        # Operation / worker state
        self._operation_id = 0
        self._current_ip = RX_IP
        self._poll_worker = None
        self._connection_worker = None
        self._write_worker = None

        # Frequency protection. Polling must not put the old frequency back
        # immediately after a successful SET.
        self._pending_frequency = None
        self._pending_frequency_started = None

        # Screen saver protection for the same reason.
        self._pending_screen_saver = None

        self._build_ui()
        self._apply_style()

        # Existing shared client remains available for normal application use.
        self.snmp = client
        self.snmp.set_ip(self._current_ip)

        # Timer only schedules background work; no SNMP call occurs on GUI thread.
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.load_data)
        refresh_ms = max(2000, int(float(REFRESH_TIME) * 1000))
        self.timer.start(refresh_ms)

        QTimer.singleShot(150, self.load_data)

        print("Dashboard created.")
        # Help menu
        help_menu = self.menuBar().addMenu("Help")
        help_menu.addAction("About / User Guide", self.show_about)

    # ==========================================================
    # BUILD UI
    # ==========================================================

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)

        root = QVBoxLayout(central)
        root.setContentsMargins(6, 4, 6, 4)
        root.setSpacing(0)

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        root.addWidget(self.tabs)

        # ------------------------------------------------------
        # DASHBOARD TAB
        # ------------------------------------------------------
        self.dashboardTab = QWidget()
        self.tabs.addTab(self.dashboardTab, "Dashboard")

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        content = QWidget()
        self.dashboardContentLayout = QVBoxLayout(content)
        self.dashboardContentLayout.setContentsMargins(12, 7, 12, 7)
        self.dashboardContentLayout.setSpacing(6)
        scroll.setWidget(content)

        dashboardLayout = QVBoxLayout(self.dashboardTab)
        dashboardLayout.setContentsMargins(0, 0, 0, 0)
        dashboardLayout.addWidget(scroll)

        # ------------------------------------------------------
        # HEADER
        # ------------------------------------------------------
        header = QHBoxLayout()
        header.setSpacing(7)

        title = QLabel("RA7203 Receiver Dashboard")
        title.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        title.setObjectName("mainTitle")
        header.addWidget(title)
        header.addStretch()

        header.addWidget(QLabel("Device:"))

        self.deviceBox = QComboBox()
        self.deviceBox.addItems(["Receiver", "Transmitter"])
        self.deviceBox.setMinimumWidth(135)
        self.deviceBox.setFixedHeight(34)
        self.deviceBox.currentTextChanged.connect(self.device_selection_changed)
        header.addWidget(self.deviceBox)

        header.addWidget(QLabel("IP:"))

        self.ipInput = QLineEdit(self._current_ip)
        self.ipInput.setPlaceholderText("10.21.14.253")
        self.ipInput.setMinimumWidth(220)
        self.ipInput.setFixedHeight(34)
        self.ipInput.returnPressed.connect(self.connect_to_device)
        header.addWidget(self.ipInput)

        self.connectButton = QPushButton("Connect")
        self.connectButton.setFixedSize(90, 34)
        self.connectButton.clicked.connect(self.connect_to_device)
        header.addWidget(self.connectButton)

        self.connectionDot = QLabel("●")
        self.connectionDot.setFont(QFont("Segoe UI", 17))
        self.connectionDot.setObjectName("connectionDot")
        header.addWidget(self.connectionDot)

        self.connectionLabel = QLabel("Offline")
        self.connectionLabel.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        self.connectionLabel.setObjectName("connectionLabel")
        header.addWidget(self.connectionLabel)

        self.dashboardContentLayout.addLayout(header)

        # ------------------------------------------------------
        # FREQUENCY
        # ------------------------------------------------------
        freq_row = QHBoxLayout()
        self.frequencyPanel = FrequencyPanel()
        freq_row.addWidget(self.frequencyPanel, 1)
        self.dashboardContentLayout.addLayout(freq_row)

        freq_input = QHBoxLayout()
        self.frequencyInput = QLineEdit()
        self.frequencyInput.setPlaceholderText("Enter frequency in MHz, e.g. 121.700")
        self.frequencyInput.setFixedHeight(34)
        self.frequencyInput.returnPressed.connect(self.set_frequency)
        freq_input.addWidget(self.frequencyInput, 1)

        self.setFrequencyButton = QPushButton("Set Frequency")
        self.setFrequencyButton.setFixedHeight(34)
        self.setFrequencyButton.clicked.connect(self.set_frequency)
        freq_input.addWidget(self.setFrequencyButton)
        self.dashboardContentLayout.addLayout(freq_input)

        # ------------------------------------------------------
        # MONITORING
        # ------------------------------------------------------
        self.dashboardContentLayout.addWidget(section_title("Receiver Monitoring"))

        monitoring_grid = QGridLayout()
        monitoring_grid.setHorizontalSpacing(7)
        monitoring_grid.setVerticalSpacing(7)

        self.temperatureCard = ParameterCard("Temperature")
        self.rssiCard = ParameterCard("RSSI")
        self.cnCard = ParameterCard("Carrier / Noise")
        self.offsetCard = ParameterCard("Frequency Offset")
        self.powerSourceCard = ParameterCard("Power Source")
        self.alarmCard = ParameterCard("Alarm")
        self.agcCard = ParameterCard("AGC (raw)")
        self.loMonitorCard = ParameterCard("RF LO Lock")

        monitor_cards = [
            self.temperatureCard,
            self.rssiCard,
            self.cnCard,
            self.offsetCard,
            self.powerSourceCard,
            self.alarmCard,
            self.agcCard,
            self.loMonitorCard,
        ]

        for index, card in enumerate(monitor_cards):
            monitoring_grid.addWidget(card, index // 4, index % 4)

        self.dashboardContentLayout.addLayout(monitoring_grid)

        # ------------------------------------------------------
        # RECEIVER STATUS - LARGE
        # ------------------------------------------------------
        self.dashboardContentLayout.addWidget(section_title("Receiver Status"))

        status_frame = QFrame()
        status_frame.setObjectName("statusFrame")
        status_layout = QGridLayout(status_frame)
        status_layout.setContentsMargins(10, 9, 10, 9)
        status_layout.setSpacing(8)

        self.statusPower = QLabel("POWER: --")
        self.statusSignal = QLabel("SIGNAL: --")
        self.statusLO = QLabel("RF LO: --")
        self.statusAlarm = QLabel("ALARM: --")

        status_labels = [
            self.statusPower,
            self.statusSignal,
            self.statusLO,
            self.statusAlarm,
        ]

        for index, label in enumerate(status_labels):
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setMinimumHeight(62)
            label.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
            label.setObjectName("statusItem")
            status_layout.addWidget(label, 0, index)

        self.dashboardContentLayout.addWidget(status_frame)

        # ------------------------------------------------------
        # TECHNICAL / POWER
        # ------------------------------------------------------
        self.dashboardContentLayout.addWidget(
            section_title("Technical / Power Parameters")
        )

        technical_grid = QGridLayout()
        technical_grid.setHorizontalSpacing(7)
        technical_grid.setVerticalSpacing(7)

        self.dcInputCard = ParameterCard("DC Input")
        self.power12Card = ParameterCard("12V Rail")
        self.power5Card = ParameterCard("5V Rail")
        self.power3v3Card = ParameterCard("3.3V Rail")
        self.rfLoLockCard = ParameterCard("RF LO Lock")
        self.lnaCurrentCard = ParameterCard("LNA Current")
        self.ifCurrentCard = ParameterCard("IF Current")
        self.technicalAgcCard = ParameterCard("AGC")

        tech_cards = [
            self.dcInputCard,
            self.power12Card,
            self.power5Card,
            self.power3v3Card,
            self.rfLoLockCard,
            self.lnaCurrentCard,
            self.ifCurrentCard,
            self.technicalAgcCard,
        ]

        for index, card in enumerate(tech_cards):
            technical_grid.addWidget(card, index // 4, index % 4)

        self.dashboardContentLayout.addLayout(technical_grid)

        # ------------------------------------------------------
        # SCREEN SAVER DIM LEVEL
        # ------------------------------------------------------
        screen_frame = QFrame()
        screen_frame.setObjectName("brightnessFrame")
        screen_layout = QHBoxLayout(screen_frame)
        screen_layout.setContentsMargins(10, 6, 10, 6)
        screen_layout.setSpacing(7)

        screen_title = QLabel("Receiver Screen Saver Dim Level")
        screen_title.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        screen_layout.addWidget(screen_title)

        min_label = QLabel("1")
        screen_layout.addWidget(min_label)

        self.brightnessSlider = QSlider(Qt.Orientation.Horizontal)
        self.brightnessSlider.setRange(1, 5)
        self.brightnessSlider.setValue(5)
        self.brightnessSlider.setTracking(False)
        self.brightnessSlider.valueChanged.connect(self.update_brightness_label)
        self.brightnessSlider.sliderReleased.connect(self.set_display_brightness)
        screen_layout.addWidget(self.brightnessSlider, 1)

        max_label = QLabel("5")
        screen_layout.addWidget(max_label)

        self.brightnessValueLabel = QLabel("5")
        self.brightnessValueLabel.setMinimumWidth(32)
        self.brightnessValueLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.brightnessValueLabel.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        self.brightnessValueLabel.setObjectName("brightnessValue")
        screen_layout.addWidget(self.brightnessValueLabel)

        self.dashboardContentLayout.addWidget(screen_frame)

        # ------------------------------------------------------
        # EVENT LOG
        # ------------------------------------------------------
        self.dashboardContentLayout.addWidget(section_title("Event Log"))

        self.logBox = QTextEdit()
        self.logBox.setReadOnly(True)
        self.logBox.setMinimumHeight(100)
        self.logBox.setMaximumHeight(155)
        self.dashboardContentLayout.addWidget(self.logBox)

        footer = QHBoxLayout()
        self.lastUpdateLabel = QLabel("Last Update: --")
        self.lastUpdateLabel.setObjectName("mutedText")
        footer.addWidget(self.lastUpdateLabel)
        footer.addStretch()

        refresh_seconds = int(float(REFRESH_TIME))
        self.refreshLabel = QLabel(f"Auto Refresh: ON ({refresh_seconds} s)")
        self.refreshLabel.setObjectName("refreshText")
        footer.addWidget(self.refreshLabel)
        self.dashboardContentLayout.addLayout(footer)

        # ------------------------------------------------------
        # CONNECTED DEVICES TAB
        # ------------------------------------------------------
        self.devicesTab = QWidget()
        self.tabs.addTab(self.devicesTab, "Connected Devices")
        self.create_devices_tab()

    def show_about(self):
        QMessageBox.information(
            self,
            "About RA-7203 Manager",
            """
    <h2>RA-7203 Manager</h2>

    <p><b>Jotron RA-7203 Receiver Management Application</b></p>

    <p>
    This application provides monitoring and management of the
    RA-7203 receiver through SNMP.
    </p>

    <h3>Getting Started</h3>

    <ol>
    <li>Connect the computer and RA-7203 to the same network.</li>
    <li>Make sure the receiver is powered on.</li>
    <li>Enter the receiver IP address.</li>
    <li>Verify the SNMP configuration.</li>
    <li>Click <b>Connect</b>.</li>
    <li>Confirm that the status changes to <b>Online</b>.</li>
    </ol>

    <h3>Troubleshooting</h3>

    <ul>
    <li>Verify the receiver IP address.</li>
    <li>Check the Ethernet connection.</li>
    <li>Verify the computer IP address and subnet.</li>
    <li>Verify that SNMP is enabled on the receiver.</li>
    <li>Verify SNMP credentials/community settings.</li>
    <li>Check firewall and network restrictions.</li>
    </ul>

    <p>
    <b>Note:</b> A successful ping only confirms IP connectivity.
    SNMP communication must also be permitted and correctly configured.
    </p>

    <hr>

    <h3>Application Information</h3>

    <table>
    <tr>
    <td><b>Author:</b> <b>Engineer Huzaifa Hassan</b> under supervision of <b>Sir Abdul Mutahher</b></td>
    </tr>

    <tr>
    <td><b>Application:</b> <b>RA-7203 Manager</b></td>
    </tr>

    <tr>
    <td><b>Version:</b> <b>1.0</b></td>
    </tr>
    </table>
    <br>
    <b>Disclaimer</b>

    <p>
    This application is provided <b>as-is</b> without warranty.
    The developer is not responsible for any damage, data loss,
    equipment malfunction, or configuration errors resulting from
    the use of this application.
    </p>

    <p>
    <b>Important:</b> Always verify SNMP write permissions and receiver
    configuration before attempting any configuration changes.
    </p>
    """,
        )

    # ==========================================================
    # STYLE
    # ==========================================================

    def _apply_style(self):
        self.setStyleSheet(f"""
            QMainWindow, QWidget {{
                background: {BG};
                color: {WHITE};
                font-family: "Segoe UI";
                font-size: 10pt;
            }}

            QLabel {{
                background: transparent;
                color: {WHITE};
            }}

            QLabel#mainTitle {{
                font-size: 18pt;
                font-weight: bold;
                color: {WHITE};
            }}

            QLabel#sectionTitle {{
                color: {WHITE};
                font-size: 11pt;
                font-weight: bold;
                padding: 3px 4px;
            }}

            QLabel#mutedText {{ color: {MUTED}; }}
            QLabel#refreshText {{ color: {GREEN}; font-weight: bold; }}
            QLabel#connectionLabel {{ color: {RED}; font-weight: bold; }}
            QLabel#connectionDot {{ color: {RED}; }}
            QLabel#brightnessValue {{ color: {GREEN}; }}

            QTabWidget {{ background: {BG}; }}
            QTabWidget::pane {{
                background: {BG};
                border: none;
            }}
            QTabBar {{ background: {BG}; }}
            QTabBar::tab {{
                background: #0b1013;
                color: #d7dde0;
                padding: 9px 25px;
                margin-right: 2px;
                border: 1px solid #303940;
                border-bottom: none;
                border-top-left-radius: 5px;
                border-top-right-radius: 5px;
                min-width: 105px;
            }}
            QTabBar::tab:selected {{
                background: {BG};
                color: {WHITE};
                border-top: 2px solid {GREEN};
            }}
            QTabBar::tab:hover {{
                background: #161d21;
                color: {WHITE};
            }}

            QLineEdit, QComboBox {{
                background: #0d1317;
                color: {WHITE};
                border: 1px solid #3c474f;
                border-radius: 5px;
                padding: 6px 8px;
            }}
            QLineEdit:focus, QComboBox:hover {{
                border: 1px solid {GREEN};
            }}
            QComboBox QAbstractItemView {{
                background: #0b1013;
                color: {WHITE};
                selection-background-color: #1e2b32;
                selection-color: {WHITE};
            }}

            QPushButton {{
                background: #11191e;
                color: {WHITE};
                border: 1px solid #414d55;
                border-radius: 5px;
                padding: 6px 12px;
                min-height: 27px;
            }}
            QPushButton:hover {{
                background: #1c272d;
                border: 1px solid {GREEN};
            }}
            QPushButton:pressed {{ background: #070b0d; }}
            QPushButton:disabled {{ color: #60686d; background: #0a0e10; }}

            QFrame#frequencyPanel {{
                background: #020303;
                border: 2px solid {GREEN};
                border-radius: 10px;
            }}
            QLabel#frequencyTitle {{ color: {WHITE}; }}
            QLabel#frequencyValue {{
                color: {GREEN};
                background: #000000;
                border: 2px solid {GREEN};
                border-radius: 8px;
            }}

            QFrame#parameterCard {{
                background: #080c0f;
                border: 1px solid #364149;
                border-radius: 8px;
            }}
            QLabel#cardTitle {{
                color: {WHITE};
                background: #050607;
                border: 1px solid #263138;
                border-radius: 5px;
                padding: 3px;
            }}
            QLabel#cardValue {{
                color: {GREEN};
                background: #000000;
                border: 1px solid #20282d;
                border-radius: 5px;
                padding: 3px;
            }}

            QFrame#statusFrame {{
                background: #050708;
                border: 1px solid #46515a;
                border-radius: 8px;
                min-height: 88px;
            }}
            QLabel#statusItem {{
                color: {GREEN};
                background: #000000;
                border: 1px solid #303940;
                border-radius: 5px;
                padding: 8px;
            }}

            QFrame#brightnessFrame {{
                background: #080c0f;
                border: 1px solid #39454d;
                border-radius: 7px;
                min-height: 46px;
            }}

            QSlider::groove:horizontal {{
                height: 7px;
                background: #30383e;
                border-radius: 3px;
            }}
            QSlider::handle:horizontal {{
                width: 17px;
                margin: -5px 0;
                background: {GREEN};
                border-radius: 8px;
            }}
            QSlider::handle:horizontal:hover {{ background: #5aff68; }}

            QTextEdit {{
                background: #020303;
                color: {GREEN};
                border: 1px solid #39434a;
                border-radius: 6px;
                font-family: Consolas;
                font-size: 9pt;
                padding: 5px;
            }}

            QFrame#deviceToolbar {{
                background: #080d10;
                border: 1px solid #39454d;
                border-radius: 6px;
            }}
            QFrame#deviceToolbar QPushButton, QFrame#deviceToolbar QToolButton {{
                background: #11191e;
                color: {WHITE};
                border: 1px solid #414d55;
                border-radius: 4px;
                padding: 7px 12px;
            }}
            QFrame#deviceToolbar QPushButton:hover, QFrame#deviceToolbar QToolButton:hover {{
                background: #1c272d;
                border: 1px solid {GREEN};
            }}

            QTableWidget {{
                background: #050708;
                color: {WHITE};
                gridline-color: #303940;
                border: 1px solid #39454d;
                selection-background-color: #1d2b32;
                selection-color: {WHITE};
                alternate-background-color: #0a0f12;
            }}
            QTableWidget::item {{ padding: 7px; }}
            QHeaderView::section {{
                background: #0b1115;
                color: {WHITE};
                border: 1px solid #303940;
                padding: 8px;
                font-weight: bold;
            }}

            QMenu {{
                background: #0b1013;
                color: {WHITE};
                border: 1px solid #39454d;
                padding: 4px;
            }}
            QMenu::item {{ padding: 7px 24px; }}
            QMenu::item:selected {{ background: #1e2b32; color: {WHITE}; }}

            QScrollArea {{ background: {BG}; border: none; }}
        """)

    # ==========================================================
    # CONNECTED DEVICES TAB
    # ==========================================================

    def create_devices_tab(self):
        layout = QVBoxLayout(self.devicesTab)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        title = QLabel("Connected Devices")
        title.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        layout.addWidget(title)

        toolbar = QFrame()
        toolbar.setObjectName("deviceToolbar")
        toolbarLayout = QHBoxLayout(toolbar)
        toolbarLayout.setContentsMargins(8, 6, 8, 6)
        toolbarLayout.setSpacing(6)

        self.addDeviceButton = QPushButton("Add Device")
        self.addDeviceButton.clicked.connect(self.add_device)
        toolbarLayout.addWidget(self.addDeviceButton)

        self.addRangeButton = QPushButton("Add Range")
        self.addRangeButton.clicked.connect(self.add_range)
        toolbarLayout.addWidget(self.addRangeButton)

        otherButton = QToolButton()
        otherButton.setText("Other Devices ▼")
        otherButton.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        otherButton.setMenu(self.create_other_devices_menu())
        toolbarLayout.addWidget(otherButton)

        self.connectSelectedButton = QPushButton("Connect Selected")
        self.connectSelectedButton.clicked.connect(self.connect_selected_device)
        toolbarLayout.addWidget(self.connectSelectedButton)

        self.removeDeviceButton = QPushButton("Remove")
        self.removeDeviceButton.clicked.connect(self.remove_selected_device)
        toolbarLayout.addWidget(self.removeDeviceButton)

        self.refreshDevicesButton = QPushButton("Refresh")
        self.refreshDevicesButton.clicked.connect(self.refresh_device_history)
        toolbarLayout.addWidget(self.refreshDevicesButton)

        toolbarLayout.addStretch()
        toolbarLayout.addWidget(QLabel("IP Address:"))

        self.deviceIPInput = QLineEdit()
        self.deviceIPInput.setPlaceholderText("10.21.14.30")
        self.deviceIPInput.setFixedWidth(160)
        toolbarLayout.addWidget(self.deviceIPInput)

        layout.addWidget(toolbar)

        filterLayout = QHBoxLayout()
        filterLayout.addWidget(QLabel("Filter:"))
        self.deviceFilter = QLineEdit()
        self.deviceFilter.setPlaceholderText("Search device, IP, status...")
        self.deviceFilter.textChanged.connect(self.filter_devices)
        filterLayout.addWidget(self.deviceFilter)
        layout.addLayout(filterLayout)

        self.deviceHistoryTable = QTableWidget()
        self.deviceHistoryTable.setColumnCount(8)
        self.deviceHistoryTable.setHorizontalHeaderLabels(
            [
                "Name",
                "Frequency / Channel",
                "Modulation",
                "Serial",
                "Version",
                "IP Address",
                "Status",
                "Last Connected",
            ]
        )
        self.deviceHistoryTable.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self.deviceHistoryTable.setSelectionMode(
            QTableWidget.SelectionMode.SingleSelection
        )
        self.deviceHistoryTable.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.deviceHistoryTable.verticalHeader().setVisible(False)
        self.deviceHistoryTable.setAlternatingRowColors(True)
        self.deviceHistoryTable.setMinimumHeight(300)

        h = self.deviceHistoryTable.horizontalHeader()
        for column in range(5):
            h.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        h.setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(7, QHeaderView.ResizeMode.Stretch)

        layout.addWidget(self.deviceHistoryTable)
        self.deviceHistoryTable.cellDoubleClicked.connect(
            lambda row, column: self.connect_selected_device()
        )

        self.refresh_device_history()

    # ==========================================================
    # MDT-STYLE MENU
    # ==========================================================

    def create_other_devices_menu(self):

        menu = QMenu(self)
        menu.addAction("Other RA7203 Devices", self.show_other_ra7203_devices)
        menu.addAction("Transmitters", self.show_transmitters)
        menu.addAction("Receivers", self.show_receivers)
        menu.addSeparator()
        menu.addAction("Export Configuration", self.export_configuration)
        menu.addAction("Import Configuration", self.import_configuration)
        menu.addSeparator()
        menu.addAction("Setup SNMP", self.setup_snmp)
        menu.addAction("Setup Secure Mode", self.setup_secure_mode)
        menu.addAction("Setup Devices", self.setup_devices)
        menu.addSeparator()
        menu.addAction("Upgrade", self.upgrade_devices)
        menu.addAction("Backup Devices", self.backup_devices)
        menu.addAction("Restore Cloned Values", self.restore_cloned_values)
        menu.addSeparator()
        menu.addAction("Generate CSR", self.generate_csr)
        menu.addAction("Upload Certificate", self.upload_certificate)
        menu.addSeparator()
        menu.addAction("Properties", self.device_properties)
        return menu

    def show_other_ra7203_devices(self):
        self.deviceFilter.setText("")
        self.refresh_device_history()

    def show_transmitters(self):
        self.deviceFilter.setText("transmitter")

    def show_receivers(self):
        self.deviceFilter.setText("receiver")

    def export_configuration(self):
        QMessageBox.information(
            self, "Export Configuration", "Configuration export is not implemented yet."
        )

    def import_configuration(self):
        QMessageBox.information(
            self, "Import Configuration", "Configuration import is not implemented yet."
        )

    def setup_snmp(self):
        QMessageBox.information(
            self,
            "Setup SNMP",
            "SNMP settings are taken from config.py / snmp_client_fixed.py.",
        )

    def setup_secure_mode(self):
        QMessageBox.information(
            self,
            "Setup Secure Mode",
            "Use the Jotron MDT SNMP/Secure Mode configuration for this function.",
        )

    def setup_devices(self):
        QMessageBox.information(
            self,
            "Setup Devices",
            "Use Add Device to save another receiver or transmitter.",
        )

    def upgrade_devices(self):
        QMessageBox.information(
            self, "Upgrade", "Firmware upgrade is not implemented in this dashboard."
        )

    def backup_devices(self):
        QMessageBox.information(
            self, "Backup Devices", "Backup is not implemented in this dashboard."
        )

    def restore_cloned_values(self):
        QMessageBox.information(
            self,
            "Restore Cloned Values",
            "Restore is not implemented in this dashboard.",
        )

    def generate_csr(self):
        QMessageBox.information(
            self, "Generate CSR", "CSR generation is not implemented in this dashboard."
        )

    def upload_certificate(self):
        QMessageBox.information(
            self,
            "Upload Certificate",
            "Certificate upload is not implemented in this dashboard.",
        )

    def add_range(self):
        QMessageBox.information(
            self,
            "Add Range",
            "Add Range is reserved for future automatic device discovery.",
        )

    def device_properties(self):
        row = self.deviceHistoryTable.currentRow()
        if row < 0:
            QMessageBox.warning(self, "No Device Selected", "Select a device first.")
            return

        name = self.deviceHistoryTable.item(row, 0).text()
        ip = self.deviceHistoryTable.item(row, 5).text()
        status = self.deviceHistoryTable.item(row, 6).text()
        QMessageBox.information(
            self,
            "Device Properties",
            f"Device: {name}\nIP Address: {ip}\nStatus: {status}",
        )

    # ==========================================================
    # ADD / REMOVE / HISTORY
    # ==========================================================

    def add_device(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Add Device")
        dialog.setFixedWidth(420)

        layout = QFormLayout(dialog)
        nameEdit = QLineEdit()
        ipEdit = QLineEdit()
        typeBox = QComboBox()
        typeBox.addItems(["Receiver", "Transmitter"])

        nameEdit.setPlaceholderText("Example: RA7203 Receiver 1")
        ipEdit.setPlaceholderText("Example: 10.21.14.30")

        layout.addRow("Device Type:", typeBox)
        layout.addRow("Device Name:", nameEdit)
        layout.addRow("IP Address:", ipEdit)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        layout.addWidget(buttons)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        name = nameEdit.text().strip()
        ip = ipEdit.text().strip()
        device_type = typeBox.currentText()

        if not name:
            QMessageBox.warning(self, "Invalid Device", "Enter a device name.")
            return

        try:
            ipaddress.ip_address(ip)
        except ValueError:
            QMessageBox.warning(self, "Invalid IP", "Enter a valid IPv4 address.")
            return

        try:
            devices = load_devices()
            for device in devices:
                if device.get("ip") == ip:
                    QMessageBox.information(
                        self,
                        "Device Already Exists",
                        f"{ip} is already in the device list.",
                    )
                    return

            devices.append(
                {
                    "device": device_type,
                    "name": name,
                    "ip": ip,
                    "status": "Offline",
                    "last_connected": "--",
                }
            )

            from device_history import save_devices

            save_devices(devices)
            self.refresh_device_history()
            self.log(f"Device added: {name} ({ip})")

        except Exception as exc:
            QMessageBox.critical(self, "Add Device Error", str(exc))

    def refresh_device_history(self):
        devices = load_devices()
        self.deviceHistoryTable.setRowCount(0)

        for device in devices:
            row = self.deviceHistoryTable.rowCount()
            self.deviceHistoryTable.insertRow(row)

            device_type = device.get("device", "Receiver")
            name = device.get("name", device_type)
            ip = device.get("ip", "")
            status = device.get("status", "Offline")
            last_connected = device.get("last_connected", "--")

            values = [
                name,
                "--",
                device_type,
                "--",
                "--",
                ip,
                "● Connected" if status == "Connected" else "● Offline",
                last_connected,
            ]

            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                if column == 6:
                    item.setForeground(
                        Qt.GlobalColor.green
                        if status == "Connected"
                        else Qt.GlobalColor.red
                    )
                self.deviceHistoryTable.setItem(row, column, item)

    def filter_devices(self, text):
        text = text.lower().strip()
        for row in range(self.deviceHistoryTable.rowCount()):
            visible = False
            for column in range(self.deviceHistoryTable.columnCount()):
                item = self.deviceHistoryTable.item(row, column)
                if item and text in item.text().lower():
                    visible = True
                    break
            self.deviceHistoryTable.setRowHidden(row, not visible)

    def remove_selected_device(self):
        row = self.deviceHistoryTable.currentRow()
        if row < 0:
            QMessageBox.warning(self, "No Device Selected", "Select a device first.")
            return

        ip_item = self.deviceHistoryTable.item(row, 5)
        if ip_item is None:
            return

        ip = ip_item.text().strip()
        from device_history import save_devices

        save_devices([d for d in load_devices() if d.get("ip") != ip])
        self.refresh_device_history()
        self.log(f"Removed saved device: {ip}")

    # ======================================================
    # DEVICE / IP SELECTION
    # ======================================================

    def device_selection_changed(self, device):
        """Load the default IP from config.py for the selected device."""
        if device == "Receiver":
            self.ipInput.setText(RX_IP)
        elif device == "Transmitter":
            self.ipInput.setText(TX_IP)

    def connect_to_device(self):
        ip = self.ipInput.text().strip()
        if not ip:
            QMessageBox.warning(self, "Invalid IP", "Enter the receiver IP address.")
            return

        try:
            ipaddress.ip_address(ip)
        except ValueError:
            QMessageBox.warning(self, "Invalid IP", "Enter a valid IPv4 address.")
            return

        self.begin_connection(
            ip,
            self.deviceBox.currentText(),
            save_history=True,
            show_result=True,
        )

    def begin_connection(self, ip, device_type, save_history=True, show_result=True):
        self._operation_id += 1
        operation_id = self._operation_id
        self._current_ip = ip
        self._pending_frequency = None
        self._pending_screen_saver = None

        if self._poll_worker is not None and self._poll_worker.isRunning():
            # Old worker is allowed to finish; operation_id prevents it from
            # touching the new device.
            pass

        self.set_connection("connecting")
        self.connectButton.setEnabled(False)
        self.connectSelectedButton.setEnabled(False)

        self.log(f"Connecting to {device_type}: {ip}")

        worker = SNMPConnectionWorker(ip, self)
        self._connection_worker = worker

        def finished(target_ip, success, error):
            if operation_id != self._operation_id or target_ip != self._current_ip:
                return

            self._connection_worker = None
            self.connectButton.setEnabled(True)
            self.connectSelectedButton.setEnabled(True)

            if success:
                self.snmp.set_ip(target_ip)
                self.set_connection(True)

                if save_history:
                    try:
                        add_or_update_device(target_ip, device_type, True)
                    except Exception:
                        pass
                    self.refresh_device_history()

                self.log(f"Connected successfully: {target_ip}")
                self.tabs.setCurrentWidget(self.dashboardTab)
                self.load_data()
            else:
                try:
                    set_device_status(target_ip, False)
                except Exception:
                    pass
                self.set_connection(False)
                self.log(f"Connection failed: {target_ip} - {error}")
                self.refresh_device_history()
                if show_result:
                    QMessageBox.warning(
                        self,
                        "Connection Failed",
                        f"Unable to communicate with:\n\n{target_ip}\n\nSNMP Error:\n{error}",
                    )

        worker.finished.connect(finished)
        worker.finished.connect(worker.deleteLater)
        worker.start()

    def connect_selected_device(self):
        row = self.deviceHistoryTable.currentRow()
        if row < 0:
            QMessageBox.warning(
                self, "No Device Selected", "Please select a device first."
            )
            return

        ip_item = self.deviceHistoryTable.item(row, 5)
        type_item = self.deviceHistoryTable.item(row, 2)
        if ip_item is None:
            return

        ip = ip_item.text().strip()
        device_type = type_item.text().strip() if type_item else "Receiver"
        if device_type not in ("Receiver", "Transmitter"):
            device_type = "Receiver"

        self.deviceBox.setCurrentText(device_type)
        self.ipInput.setText(ip)
        self.begin_connection(ip, device_type, True, True)

    # ==========================================================
    # CONNECTION STATUS
    # ==========================================================

    def set_connection(self, state):
        if state is True or state == "connected":
            self.connectionDot.setStyleSheet(f"color:{GREEN};")
            self.connectionLabel.setText("Connected")
            self.connectionLabel.setStyleSheet(f"color:{GREEN};")
        elif state == "connecting":
            self.connectionDot.setStyleSheet(f"color:{YELLOW};")
            self.connectionLabel.setText("Connecting...")
            self.connectionLabel.setStyleSheet(f"color:{YELLOW};")
        else:
            self.connectionDot.setStyleSheet(f"color:{RED};")
            self.connectionLabel.setText("Offline")
            self.connectionLabel.setStyleSheet(f"color:{RED};")

    # ==========================================================
    # POLLING
    # ==========================================================

    def load_data(self):
        if self._poll_worker is not None and self._poll_worker.isRunning():
            return

        ip = self._current_ip
        if not ip:
            return

        operation_id = self._operation_id
        worker = SNMPPollWorker(ip, self)
        self._poll_worker = worker

        def finished(target_ip, data, error):
            if self._poll_worker is worker:
                self._poll_worker = None

            if operation_id != self._operation_id or target_ip != self._current_ip:
                return

            if error is not None:
                self.set_connection(False)
                try:
                    set_device_status(target_ip, False)
                    self.refresh_device_history()
                except Exception:
                    pass
                self.log(f"SNMP poll failed for {target_ip}: {error}")
                return

            self.set_connection(True)
            try:
                set_device_status(target_ip, True)
                self.refresh_device_history()
            except Exception:
                pass
            self.apply_poll_data(data)

        worker.finished.connect(finished)
        worker.finished.connect(worker.deleteLater)
        worker.start()

    def apply_poll_data(self, data):
        try:
            # ------------------------------------------------------
            # FREQUENCY
            # ------------------------------------------------------
            raw = data.get("frequency")
            current_frequency = None
            if raw is not None:
                try:
                    current_frequency = int(raw)
                except (ValueError, TypeError):
                    pass

            if current_frequency is not None:
                display = current_frequency / 1000.0

                # If a write is pending, do not let an old poll restore the
                # old frequency. Clear the pending value only when the radio
                # actually reports the requested value.
                if self._pending_frequency is not None:
                    if current_frequency == self._pending_frequency:
                        self._pending_frequency = None
                        self.log(f"Receiver confirmed frequency: {display:.3f} MHz")
                    else:
                        # Keep requested value visible while radio catches up.
                        pass
                else:
                    self.frequencyPanel.setValue(f"{display:.3f} MHz")

                if self._pending_frequency is None:
                    self.frequencyInput.setText(f"{display:.3f}")

                if self._pending_frequency is not None:
                    # Keep the requested value visible until confirmation.
                    pending_mhz = self._pending_frequency / 1000.0
                    self.frequencyPanel.setValue(f"{pending_mhz:.3f} MHz")
                    self.frequencyInput.setText(f"{pending_mhz:.3f}")

            # ------------------------------------------------------
            # MONITORING
            # ------------------------------------------------------
            temperature = data.get("temperature")
            self.temperatureCard.setValue(
                "--" if temperature is None else f"{int(temperature)} °C"
            )

            rssi = data.get("rssi")
            if rssi is None:
                self.rssiCard.setValue("--")
            else:
                try:
                    self.rssiCard.setValue(f"{float(rssi):.0f} dBm")
                except (ValueError, TypeError):
                    self.rssiCard.setValue(str(rssi))

            cn = data.get("carrier_noise")
            self.cnCard.setValue("--" if cn is None else str(cn))

            offset = data.get("offset")
            try:
                offset_text = f"{int(offset)} Hz" if offset is not None else "--"
            except (ValueError, TypeError):
                offset_text = str(offset)
            self.offsetCard.setValue(offset_text)

            power_source = data.get("power_source")
            power_text = (
                decode_power_source(power_source) if power_source is not None else "--"
            )
            self.powerSourceCard.setValue(power_text)

            alarm = data.get("alarm")
            alarm_text = decode_alarm(alarm) if alarm is not None else "--"
            self.alarmCard.setValue(alarm_text)

            agc = data.get("agc")
            self.agcCard.setValue("--" if agc is None else str(agc))

            rf_lo = data.get("rf_lo_lock")
            lo_text = decode_lo_lock(rf_lo) if rf_lo is not None else "--"
            self.loMonitorCard.setValue(lo_text)

            # ------------------------------------------------------
            # RECEIVER STATUS
            # ------------------------------------------------------
            self.statusPower.setText(f"POWER: {power_text}")

            if rssi is None:
                self.statusSignal.setText("SIGNAL: --")
            else:
                try:
                    rssi_value = float(rssi)
                    if rssi_value >= -60:
                        quality = "EXCELLENT"
                    elif rssi_value >= -70:
                        quality = "GOOD"
                    elif rssi_value >= -80:
                        quality = "FAIR"
                    elif rssi_value >= -90:
                        quality = "WEAK"
                    else:
                        quality = "VERY WEAK"
                    self.statusSignal.setText(
                        f"SIGNAL: {quality} ({rssi_value:.0f} dBm)"
                    )
                except (ValueError, TypeError):
                    self.statusSignal.setText(f"SIGNAL: {rssi}")

            self.statusLO.setText(f"RF LO: {lo_text}")
            self.statusAlarm.setText(f"ALARM: {alarm_text}")
            self.statusAlarm.setStyleSheet(
                f"color:{GREEN}; background:#000000; border:1px solid #303940; border-radius:5px; padding:8px;"
                if alarm_text == "OK"
                else f"color:{RED}; background:#000000; border:1px solid #303940; border-radius:5px; padding:8px;"
            )

            # ------------------------------------------------------
            # TECHNICAL
            # ------------------------------------------------------
            self.dcInputCard.setValue(self.format_voltage(data.get("dc_input")))
            self.power12Card.setValue(self.format_voltage(data.get("rail_12v")))
            self.power5Card.setValue(self.format_voltage(data.get("rail_5v")))
            self.power3v3Card.setValue(self.format_voltage(data.get("rail_3v3")))
            self.rfLoLockCard.setValue(lo_text)

            lna = data.get("lna_current")
            self.lnaCurrentCard.setValue("--" if lna is None else f"{lna} mA")

            if_current = data.get("if_current")
            self.ifCurrentCard.setValue(
                "--" if if_current is None else f"{if_current} mA"
            )

            self.technicalAgcCard.setValue("--" if agc is None else str(agc))

            # ------------------------------------------------------
            # SCREEN SAVER LEVEL 1..5
            # ------------------------------------------------------
            screen_level = data.get("screen_saver_level")
            if screen_level is not None:
                try:
                    level = int(screen_level)
                    if 1 <= level <= 5:
                        if self._pending_screen_saver is not None:
                            if level == self._pending_screen_saver:
                                self._pending_screen_saver = None
                                self.log(
                                    f"Receiver confirmed screen saver dim level: {level}"
                                )
                        else:
                            self.brightnessSlider.blockSignals(True)
                            self.brightnessSlider.setValue(level)
                            self.brightnessSlider.blockSignals(False)
                            self.brightnessValueLabel.setText(str(level))

                        if self._pending_screen_saver is not None:
                            self.brightnessValueLabel.setText(
                                str(self._pending_screen_saver)
                            )
                except (ValueError, TypeError):
                    pass

            # ------------------------------------------------------
            # TIME / LOG
            # ------------------------------------------------------
            now = datetime.now()
            self.lastUpdateLabel.setText("Last Update: " + now.strftime("%H:%M:%S"))
            self.log(f"Receiver ({self._current_ip}) Updated")

        except Exception as exc:
            print("[DASHBOARD] apply_poll_data error:")
            traceback.print_exc()
            self.log(f"Dashboard error: {exc}")

    # ==========================================================
    # FREQUENCY WRITE
    # ==========================================================

    def set_frequency(self):
        if self._write_worker is not None and self._write_worker.isRunning():
            self.log("A write operation is already in progress.")
            return

        text = self.frequencyInput.text().strip()
        if not text:
            QMessageBox.warning(self, "Invalid Frequency", "Enter a frequency in MHz.")
            return

        try:
            frequency_mhz = float(text)
        except ValueError:
            QMessageBox.warning(self, "Invalid Frequency", "Example: 121.700")
            return

        if not 108.000 <= frequency_mhz <= 137.000:
            QMessageBox.warning(
                self,
                "Invalid Frequency",
                "Enter an aviation VHF frequency between 108.000 and 137.000 MHz.",
            )
            return

        frequency_value = int(round(frequency_mhz * 1000))
        self._pending_frequency = frequency_value
        self.frequencyPanel.setValue(f"{frequency_mhz:.3f} MHz")
        self.frequencyInput.setText(f"{frequency_mhz:.3f}")
        self.setFrequencyButton.setEnabled(False)
        self.log(
            f"Writing frequency {frequency_mhz:.3f} MHz ({frequency_value} kHz)..."
        )

        worker = SNMPWriteWorker(
            self._current_ip,
            "frequency",
            OIDS["frequency"],
            frequency_value,
            self,
        )
        self._write_worker = worker

        def finished(operation, value, ip, success, error):
            if self._write_worker is worker:
                self._write_worker = None
            self.setFrequencyButton.setEnabled(True)

            if ip != self._current_ip:
                return

            if success:
                self.log(f"Frequency SET accepted: {value / 1000:.3f} MHz")
                QTimer.singleShot(250, self.load_data)
            else:
                self._pending_frequency = None
                self.log(f"Frequency SET failed: {error}")
                QMessageBox.critical(
                    self,
                    "Frequency Write Failed",
                    f"The receiver rejected the frequency write.\n\nSNMP Error:\n{error}",
                )
                QTimer.singleShot(100, self.load_data)

        worker.finished.connect(finished)
        worker.finished.connect(worker.deleteLater)
        worker.start()

    # ==========================================================
    # SCREEN SAVER WRITE
    # ==========================================================

    def update_brightness_label(self, value):
        self.brightnessValueLabel.setText(str(value))

    def set_display_brightness(self):
        if self._write_worker is not None and self._write_worker.isRunning():
            self.log("A write operation is already in progress.")
            return

        value = int(self.brightnessSlider.value())
        if not 1 <= value <= 5:
            return

        self._pending_screen_saver = value
        self.brightnessValueLabel.setText(str(value))
        self.brightnessSlider.setEnabled(False)
        self.log(f"Writing screen saver dim level {value}/5...")

        worker = SNMPWriteWorker(
            self._current_ip,
            "screen_saver",
            OIDS["screen_saver_level"],
            value,
            self,
        )
        self._write_worker = worker

        def finished(operation, written_value, ip, success, error):
            if self._write_worker is worker:
                self._write_worker = None
            self.brightnessSlider.setEnabled(True)

            if ip != self._current_ip:
                return

            if success:
                self.log(f"Screen saver dim level SET accepted: {written_value}/5")
                QTimer.singleShot(250, self.load_data)
            else:
                self._pending_screen_saver = None
                self.log(f"Screen saver write failed: {error}")
                QMessageBox.warning(
                    self,
                    "Screen Saver Write Failed",
                    f"Unable to change receiver screen saver dim level.\n\nSNMP Error:\n{error}",
                )
                QTimer.singleShot(100, self.load_data)

        worker.finished.connect(finished)
        worker.finished.connect(worker.deleteLater)
        worker.start()

    # ==========================================================
    # LOG / UTILITIES
    # ==========================================================

    def log(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        line = f"{timestamp}    {message}"
        print(f"[LOG] {line}")
        if hasattr(self, "logBox"):
            self.logBox.append(line)

    @staticmethod
    def format_voltage(value):
        if value is None:
            return "--"
        try:
            return f"{int(value) / 1000:.3f} V"
        except (ValueError, TypeError):
            return str(value)

    # ==========================================================
    # CLOSE
    # ==========================================================

    def closeEvent(self, event):
        self._operation_id += 1
        if hasattr(self, "timer"):
            self.timer.stop()
        event.accept()


# ==========================================================
# STANDALONE
# ==========================================================

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = Dashboard()
    window.show()
    sys.exit(app.exec())
