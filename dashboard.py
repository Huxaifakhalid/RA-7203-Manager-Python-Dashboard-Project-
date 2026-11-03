# ==========================================================
# dashboard.py (Part 1)
# ==========================================================

from PySide6.QtWidgets import (
    QWidget,
    QLabel,
    QPushButton,
    QLineEdit,
    QTextEdit,
    QComboBox,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QMessageBox,
    QFrame,
)

from PySide6.QtCore import Qt, QTimer

from widgets import (
    FrequencyDisplay,
    ValueCard,
    AlarmCard,
    StatusIndicator,
)


class ReceiverPanel(QFrame):
    def __init__(self):
        super().__init__()
        self.setFrameShape(QFrame.Shape.Box)
        self.setStyleSheet("""
            QFrame {
                background:#181b1f;
                border:2px solid #444;
                border-radius:10px;
            }
        """)

        title = QLabel("Receiver Panel")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size:16px;font-weight:bold;color:#ffffff;")

        self.powerLabel = QLabel("Power: OFF")
        self.powerLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.powerLabel.setStyleSheet("font-size:13px;color:#ff8c00;")

        self.signalBars = []
        barsLayout = QHBoxLayout()
        barsLayout.setSpacing(4)
        for _ in range(5):
            bar = QLabel()
            bar.setFixedSize(14, 24)
            bar.setStyleSheet("background:#333;border-radius:4px;")
            barsLayout.addWidget(bar)
            self.signalBars.append(bar)

        self.alarmLabel = QLabel("Alarm: OK")
        self.alarmLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.alarmLabel.setStyleSheet("font-size:13px;color:#00ff00;")

        layout = QVBoxLayout()
        layout.addWidget(title)
        layout.addSpacing(8)
        layout.addWidget(self.powerLabel)
        layout.addLayout(barsLayout)
        layout.addSpacing(8)
        layout.addWidget(self.alarmLabel)
        self.setLayout(layout)

    def set_power(self, source):

        source = str(source).upper()

        if source == "AC":

            self.powerLabel.setText("Power: AC")

            self.powerLabel.setStyleSheet("font-size:13px;color:#00ff00;")

        elif source == "DC":

            self.powerLabel.setText("Power: DC")

            self.powerLabel.setStyleSheet("font-size:13px;color:#00ff00;")

        else:

            self.powerLabel.setText("Power: OFF")

            self.powerLabel.setStyleSheet("font-size:13px;color:#ff4f4f;")

    def set_signal(self, level: int):
        level = max(0, min(5, int(level)))
        for index, bar in enumerate(self.signalBars, start=1):
            if index <= level:
                bar.setStyleSheet("background:#00c853;border-radius:4px;")
            else:
                bar.setStyleSheet("background:#333;border-radius:4px;")

    def set_alarm(self, active: bool):
        if active:
            self.alarmLabel.setText("Alarm: ACTIVE")
            self.alarmLabel.setStyleSheet("font-size:13px;color:#ff4f4f;")
        else:
            self.alarmLabel.setText("Alarm: OK")
            self.alarmLabel.setStyleSheet("font-size:13px;color:#00ff00;")


from snmp_client import client

from decoder import (
    decode_frequency,
    decode_rssi,
    decode_cn,
    decode_offset,
    decode_alarm,
    decode_mode,
    decode_state,
    decode_temperature,
    decode_power_source,
    decode_voltage_mv,
    decode_lo_lock,
    decode_offset,
)

from logger import logger

from config import (
    RX_IP,
    TX_IP,
    REFRESH_TIME,
)

# ==========================================================
# CHANGE THESE OIDs TO MATCH YOUR RADIO
# ==========================================================

# ==========================================================
# READ-ONLY RADIO TELEMETRY
# ==========================================================

RADIO_SCREEN = {
    # --------------------------------------
    # Receiver operating parameters
    # --------------------------------------
    "Frequency": "1.3.6.1.4.1.22154.3.1.2.3.4.0",
    "Mode": "1.3.6.1.4.1.22154.3.1.2.3.1.0",
    "State": "1.3.6.1.4.1.22154.3.1.2.3.2.0",
    # --------------------------------------
    # Power
    # --------------------------------------
    "Power12V": "1.3.6.1.4.1.22154.3.1.2.5.2.3.2.0",
    "Power5V": "1.3.6.1.4.1.22154.3.1.2.5.2.3.3.0",
    "Power3V3": "1.3.6.1.4.1.22154.3.1.2.5.2.3.4.0",
    "PowerTemperature": "1.3.6.1.4.1.22154.3.1.2.5.2.3.5.0",
    "PowerSource": "1.3.6.1.4.1.22154.3.1.2.5.2.3.7.0",
    "PowerDCInput": "1.3.6.1.4.1.22154.3.1.2.5.2.3.8.0",
    # --------------------------------------
    # RF receiver
    # --------------------------------------
    "RfLoLock": "1.3.6.1.4.1.22154.3.1.2.5.2.2.2.0",
    "RfLnaCurrent": "1.3.6.1.4.1.22154.3.1.2.5.2.2.4.0",
    "RfIfCurrent": "1.3.6.1.4.1.22154.3.1.2.5.2.2.5.0",
    # --------------------------------------
    # Receiver signal
    # --------------------------------------
    "VAgc": "1.3.6.1.4.1.22154.3.1.2.5.2.5.3.0",
    "RSSI": "1.3.6.1.4.1.22154.3.1.2.5.2.5.4.0",
    "Offset": "1.3.6.1.4.1.22154.3.1.2.5.2.5.9.0",
    "CarrierNoise": "1.3.6.1.4.1.22154.3.1.2.5.2.5.10.0",
    # --------------------------------------
    # Alarm
    # --------------------------------------
    "Alarm": "1.3.6.1.4.1.22154.3.1.2.5.2.7.0",
}

# ==========================================================
# READ / WRITE CONFIGURATION OIDs
# ==========================================================

RADIO_CONFIG = {
    # Read / Write
    "DisplayIntensity": "1.3.6.1.4.1.22154.3.1.2.2.3.5.3.0",
    # Read / Write
    "ScreenSaverLevel": "1.3.6.1.4.1.22154.3.1.2.2.3.5.13.0",
}

# ==========================================================
# DASHBOARD
# ==========================================================


class Dashboard(QWidget):

    def __init__(self):

        super().__init__()

        self.setWindowTitle("RA7203 Receiver Dashboard")

        self.resize(900, 650)

        self.setStyleSheet("""

            QWidget{

                background:#202225;
                color:white;
                font-size:12px;

            }

            QPushButton{

                background:#2f3136;
                color:white;
                padding:8px;
                border-radius:6px;

            }

            QPushButton:hover{

                background:#3b3e44;

            }

            QLineEdit{

                background:#2b2b2b;
                color:white;
                padding:6px;

            }

            QTextEdit{

                background:#181818;
                color:#00ff00;

            }

            QComboBox{

                background:#2b2b2b;
                color:white;
                padding:5px;

            }

        """)

        mainLayout = QVBoxLayout(self)

        # =====================================================
        # HEADER
        # =====================================================

        header = QHBoxLayout()

        title = QLabel("RA7203 Receiver Dashboard")

        title.setStyleSheet("""
            font-size:22px;
            font-weight:bold;
        """)

        self.status = StatusIndicator()

        self.deviceBox = QComboBox()

        self.deviceBox.addItems(
            [
                "Receiver",
                "Transmitter",
            ]
        )

        self.deviceBox.currentIndexChanged.connect(self.change_device)

        header.addWidget(title)

        header.addStretch()

        header.addWidget(self.deviceBox)

        header.addWidget(self.status)

        mainLayout.addLayout(header)

        # =====================================================
        # FREQUENCY DISPLAY
        # =====================================================

        self.frequencyDisplay = FrequencyDisplay()

        mainLayout.addWidget(self.frequencyDisplay)

        # =====================================================
        # FREQUENCY EDIT
        # =====================================================

        freqLayout = QHBoxLayout()

        self.freqEdit = QLineEdit()

        self.freqEdit.setPlaceholderText("118500")

        self.writeButton = QPushButton("Set Frequency")

        self.writeButton.clicked.connect(self.write_frequency)

        freqLayout.addWidget(self.freqEdit)

        freqLayout.addWidget(self.writeButton)

        mainLayout.addLayout(freqLayout)

        # =====================================================
        # VALUE CARDS
        # =====================================================

        grid = QGridLayout()

        # ==========================================================
        # RECEIVER MONITORING CARDS
        # ==========================================================

        self.tempCard = ValueCard("Temperature")
        self.rssiCard = ValueCard("RSSI")
        self.powerSourceCard = ValueCard("Power Source")
        self.dcInputCard = ValueCard("DC Input")

        self.power12Card = ValueCard("12V Rail")
        self.power5Card = ValueCard("5V Rail")
        self.power3v3Card = ValueCard("3.3V Rail")

        self.rfLoLockCard = ValueCard("RF LO Lock")
        self.lnaCurrentCard = ValueCard("LNA Current")
        self.ifCurrentCard = ValueCard("IF Current")
        self.agcCard = ValueCard("AGC")

        self.cnCard = ValueCard("Carrier / Noise")
        self.offsetCard = ValueCard("Offset")
        self.alarmCard = ValueCard("Alarm")
        self.receiverPanel = ReceiverPanel()

        # =====================================================
        # EVENT LOG
        # =====================================================

        self.eventLog = QTextEdit()
        self.eventLog.setReadOnly(True)

        self.eventLog.setMinimumHeight(120)

        self.eventLog.setStyleSheet("""
            QTextEdit {
                background-color: #111111;
                color: #00ff00;
                border: 1px solid #555555;
                padding: 6px;
                font-size: 13px;
            }
        """)
        # ==========================================================
        # RECEIVER PANEL GRID
        # ==========================================================

        cardsLayout = QGridLayout()
        cardsLayout.setSpacing(8)

        # Row 0
        cardsLayout.addWidget(self.tempCard, 0, 0)
        cardsLayout.addWidget(self.rssiCard, 0, 1)
        cardsLayout.addWidget(self.powerSourceCard, 0, 2)
        cardsLayout.addWidget(self.dcInputCard, 0, 3)

        # Row 1
        cardsLayout.addWidget(self.power12Card, 1, 0)
        cardsLayout.addWidget(self.power5Card, 1, 1)
        cardsLayout.addWidget(self.power3v3Card, 1, 2)
        cardsLayout.addWidget(self.rfLoLockCard, 1, 3)

        # Row 2
        cardsLayout.addWidget(self.lnaCurrentCard, 2, 0)
        cardsLayout.addWidget(self.ifCurrentCard, 2, 1)
        cardsLayout.addWidget(self.agcCard, 2, 2)
        cardsLayout.addWidget(self.cnCard, 2, 3)

        # Row 3
        cardsLayout.addWidget(self.offsetCard, 3, 0)
        cardsLayout.addWidget(self.alarmCard, 3, 1, 1, 3)

        mainLayout.addLayout(cardsLayout)

        # =====================================================
        # ALARM
        # =====================================================

        self.alarmCard = AlarmCard()

        # mainLayout.addWidget(self.alarmCard)
        # mainLayout.addWidget(self.tempCard)
        # mainLayout.addWidget(self.powerSourceCard)
        # mainLayout.addWidget(self.dcInputCard)

        mainGrid = QGridLayout()

        mainGrid.setSpacing(8)

        # =====================================================
        # ROW 0
        # =====================================================

        mainGrid.addWidget(self.tempCard, 0, 0)

        mainGrid.addWidget(self.powerSourceCard, 0, 1)

        mainGrid.addWidget(self.dcInputCard, 0, 2)

        # =====================================================
        # ROW 1
        # =====================================================

        mainGrid.addWidget(self.rssiCard, 1, 0)

        mainGrid.addWidget(self.cnCard, 1, 1)

        mainGrid.addWidget(self.offsetCard, 1, 2)

        # =====================================================
        # ROW 2
        # =====================================================

        mainGrid.addWidget(self.rfLoLockCard, 2, 0)

        mainGrid.addWidget(self.lnaCurrentCard, 2, 1)

        mainGrid.addWidget(self.ifCurrentCard, 2, 2)

        # =====================================================
        # ROW 3
        # =====================================================

        mainGrid.addWidget(self.agcCard, 3, 0)

        mainGrid.addWidget(self.power12Card, 3, 1)

        mainGrid.addWidget(self.power5Card, 3, 2)

        mainLayout.addWidget(self.receiverPanel)
        mainLayout.addWidget(self.alarmCard)
        mainLayout.addWidget(self.eventLog)

        # =====================================================
        # TECHNICAL PARAMETERS
        # =====================================================

        technicalLayout = QGridLayout()
        technicalLayout.setSpacing(8)

        # -----------------------------
        # POWER RAILS
        # -----------------------------

        technicalLayout.addWidget(self.dcInputCard, 0, 0)

        technicalLayout.addWidget(self.power12Card, 0, 1)

        technicalLayout.addWidget(self.power5Card, 0, 2)

        technicalLayout.addWidget(self.power3v3Card, 0, 3)

        # -----------------------------
        # RF STATUS
        # -----------------------------

        technicalLayout.addWidget(self.rfLoLockCard, 1, 0)

        technicalLayout.addWidget(self.lnaCurrentCard, 1, 1)

        technicalLayout.addWidget(self.ifCurrentCard, 1, 2)

        technicalLayout.addWidget(self.agcCard, 1, 3)

        mainLayout.addLayout(technicalLayout)
        # =====================================================
        # EVENT LOG
        # =====================================================

        logTitle = QLabel("Event Log")

        logTitle.setStyleSheet("""
            font-size:16px;
            font-weight:bold;
        """)

        mainLayout.addWidget(logTitle)

        self.logBox = QTextEdit()

        self.logBox.setReadOnly(True)

        self.logBox.setMaximumHeight(160)

        mainLayout.addWidget(self.logBox)

        # =====================================================
        # TIMER
        # =====================================================

        self.timer = QTimer()

        self.timer.timeout.connect(self.load_data)

        # self.timer.start(REFRESH_TIME * 1000)

        self.change_device()

        self.load_data()

    # ==========================================================
    # dashboard.py (Part 2)
    # ==========================================================

    # =====================================================
    # DEVICE CHANGE
    # =====================================================

    def change_device(self):

        if self.deviceBox.currentIndex() == 0:

            client.set_ip(RX_IP)

            logger.add("Receiver Selected")

        else:

            client.set_ip(TX_IP)

            logger.add("Transmitter Selected")

        self.update_log()

    # =====================================================
    # WRITE FREQUENCY
    # =====================================================

    def write_frequency(self):

        text = self.freqEdit.text().strip()

        if text == "":

            QMessageBox.warning(self, "Input Error", "Enter Frequency")

            return

        try:

            value = int(float(text) * 1000)
            print(f"Writing frequency {value}")
        except Exception:

            QMessageBox.warning(self, "Input Error", "Invalid Frequency")

            return

        success, error = client.write(RADIO_SCREEN["Frequency"], value)

        if success:

            logger.add(f"Frequency changed to {text} MHz")

            QMessageBox.information(self, "Success", "Frequency Updated")

            self.load_data()

        else:

            logger.add(f"Write Failed : {error}")

            QMessageBox.critical(self, "SNMP Error", str(error))

        self.update_log()

    def write_display_intensity(self):

        value = self.displayIntensitySpin.value()

        success, error = client.write(RADIO_CONFIG["DisplayIntensity"], value)

        if success:
            logger.add(f"Display intensity changed to {value}")
        else:
            logger.add(f"Display intensity write failed: {error}")

        self.update_log()

    def load_data(self):

        import traceback

        try:

            # =====================================================
            # FREQUENCY — PRIMARY CONNECTION TEST
            # =====================================================

            freq, errFreq = client.read(RADIO_SCREEN["Frequency"])

            if errFreq is None:

                self.frequencyDisplay.setValue(decode_frequency(freq))

                # Radio is reachable
                self.status.connected()

            else:

                self.frequencyDisplay.setValue("--")
                self.status.disconnected()

                return

            # =====================================================
            # TEMPERATURE
            # =====================================================

            temp, errTemp = client.read(RADIO_SCREEN["PowerTemperature"])

            if errTemp is None:
                self.tempCard.setValue(decode_temperature(temp))
            else:
                self.tempCard.setValue("--")

            # =====================================================
            # RSSI
            # =====================================================

            rssi, errRssi = client.read(RADIO_SCREEN["RSSI"])

            if errRssi is None:

                self.rssiCard.setValue(decode_rssi(rssi))

                try:

                    rssi_val = float(rssi)

                    if rssi_val > -60:
                        level = 5

                    elif rssi_val > -70:
                        level = 4

                    elif rssi_val > -80:
                        level = 3

                    elif rssi_val > -90:
                        level = 2

                    elif rssi_val > -100:
                        level = 1

                    else:
                        level = 0

                except (ValueError, TypeError):

                    level = 0

                if hasattr(self, "receiverPanel"):
                    self.receiverPanel.set_signal(level)

            else:

                self.rssiCard.setValue("--")

                if hasattr(self, "receiverPanel"):
                    self.receiverPanel.set_signal(0)

            # =====================================================
            # CARRIER / NOISE
            # =====================================================

            cn, errCN = client.read(RADIO_SCREEN["CarrierNoise"])

            if errCN is None:

                self.cnCard.setValue(decode_cn(cn))

            else:

                self.cnCard.setValue("--")

            # =====================================================
            # OFFSET
            # =====================================================

            offset, errOffset = client.read(RADIO_SCREEN["Offset"])

            if errOffset is None:

                self.offsetCard.setValue(decode_offset(offset))

            else:

                self.offsetCard.setValue("--")

            # =====================================================
            # POWER SOURCE
            # =====================================================

            powerSource, errPower = client.read(RADIO_SCREEN["PowerSource"])

            if errPower is None:

                source = decode_power_source(powerSource)

                self.powerSourceCard.setValue(source)

                if hasattr(self, "receiverPanel"):

                    self.receiverPanel.set_power(source in ("AC", "DC"))

            else:

                self.powerSourceCard.setValue("--")

            # =====================================================
            # DC INPUT
            # =====================================================

            dcInput, errDC = client.read(RADIO_SCREEN["PowerDCInput"])

            if errDC is None:

                self.dcInputCard.setValue(decode_voltage_mv(dcInput))

            else:

                self.dcInputCard.setValue("--")

            # =====================================================
            # 12V
            # =====================================================

            power12, err12 = client.read(RADIO_SCREEN["Power12V"])

            if err12 is None:

                self.power12Card.setValue(decode_voltage_mv(power12))

            else:

                self.power12Card.setValue("--")

            # =====================================================
            # 5V
            # =====================================================

            power5, err5 = client.read(RADIO_SCREEN["Power5V"])

            if err5 is None:

                self.power5Card.setValue(decode_voltage_mv(power5))

            else:

                self.power5Card.setValue("--")

            # =====================================================
            # 3.3V
            # =====================================================

            power33, err33 = client.read(RADIO_SCREEN["Power3V3"])

            if err33 is None:

                self.power3v3Card.setValue(decode_voltage_mv(power33))

            else:

                self.power3v3Card.setValue("--")

            # =====================================================
            # RF LO LOCK
            # =====================================================

            loLock, errLo = client.read(RADIO_SCREEN["RfLoLock"])

            if errLo is None:

                self.rfLoLockCard.setValue(decode_lo_lock(loLock))

            else:

                self.rfLoLockCard.setValue("--")

            # =====================================================
            # LNA CURRENT
            # =====================================================

            lnaCurrent, errLna = client.read(RADIO_SCREEN["RfLnaCurrent"])

            if errLna is None:

                self.lnaCurrentCard.setValue(f"{lnaCurrent} mA")

            else:

                self.lnaCurrentCard.setValue("--")

            # =====================================================
            # IF CURRENT
            # =====================================================

            ifCurrent, errIf = client.read(RADIO_SCREEN["RfIfCurrent"])

            if errIf is None:

                self.ifCurrentCard.setValue(f"{ifCurrent} mA")

            else:

                self.ifCurrentCard.setValue("--")

            # =====================================================
            # AGC
            # =====================================================

            agc, errAgc = client.read(RADIO_SCREEN["VAgc"])

            if errAgc is None:

                self.agcCard.setValue(str(agc))

            else:

                self.agcCard.setValue("--")

            # =====================================================
            # SUCCESS
            # =====================================================

            self.status.connected()

            logger.add("Receiver Updated")

            self.update_log()

        except Exception:

            traceback.print_exc()

            self.status.disconnected()

    # =====================================================
    # UPDATE EVENT LOG
    # =====================================================

    def update_log(self):
        self.logBox.clear()

        for event in logger.get_events():
            self.logBox.append(event)

        # except Exception as e:
        # print("Event log update error:", e)

        # self.logBox.setPlainText("\n".join(logger.get_events()))

    # =====================================================
    # CLOSE EVENT
    # =====================================================

    def closeEvent(self, event):

        self.timer.stop()

        event.accept()


class EventLogger:

    def __init__(self):
        self.events = []

    def add(self, message):
        timestamp = QTime.currentTime().toString("HH:mm:ss")
        self.events.append(f"{timestamp}  {message}")

    def get_events(self):
        return list(self.events)
