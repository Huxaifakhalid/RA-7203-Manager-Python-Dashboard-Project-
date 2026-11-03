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

    def set_power(self, on: bool):
        if on:
            self.powerLabel.setText("Power: ON")
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
    decode_temperature,
    decode_voltage_mv,
    decode_power_source,
    decode_rssi,
    decode_lo_lock,
    decode_cn,
    decode_offset,
    decode_alarm,
    decode_agc,
    decode_mode,
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

RADIO_SCREEN = {
    "Frequency": "1.3.6.1.4.1.22154.3.1.2.3.4.0",
    "RSSI": "1.3.6.1.4.1.22154.3.1.2.5.2.5.4.0",
    "CarrierNoise": "1.3.6.1.4.1.22154.3.1.2.5.2.5.10.0",
    "Offset": "1.3.6.1.4.1.22154.3.1.2.5.2.5.9.0",
    "Alarm": "1.3.6.1.4.1.22154.3.1.2.5.2.7.0",
    "Mode": "1.3.6.1.4.1.22154.3.1.2.3.1.0",
    "State": "1.3.6.1.4.1.22154.3.1.2.3.2.0",
    "Temperature": "1.3.6.1.4.1.22154.3.1.2.5.2.3.5.0",
    "Voltage": "1.3.6.1.4.1.22154.3.1.2.5.2.3.7.0",
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

        self.tempCard = ValueCard("Temperature")

        self.powerCard = ValueCard("RF Power")

        self.voltageCard = ValueCard("Voltage")

        self.rssiCard = ValueCard("RSSI")

        self.cnCard = ValueCard("Carrier Noise")

        self.offsetCard = ValueCard("Offset")

        grid.addWidget(self.tempCard, 0, 0)

        grid.addWidget(self.powerCard, 0, 1)

        grid.addWidget(self.voltageCard, 0, 2)

        grid.addWidget(self.rssiCard, 1, 0)

        grid.addWidget(self.cnCard, 1, 1)

        grid.addWidget(self.offsetCard, 1, 2)

        self.receiverPanel = ReceiverPanel()
        grid.addWidget(self.receiverPanel, 0, 3, 2, 1)

        mainLayout.addLayout(grid)

        # =====================================================
        # ALARM
        # =====================================================

        self.alarmCard = AlarmCard()

        mainLayout.addWidget(self.alarmCard)

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

    # =====================================================
    # LOAD DATA
    # ====================================================

    def load_data(self):
        freq, errFreq = client.read(RADIO_SCREEN["Frequency"])

        print("Frequency from SNMP:", freq)

        text = decode_frequency(freq)

        print("Decoded:", text)

        temp, errTemp = client.read(RADIO_SCREEN["Temperature"])

        voltage, errVoltage = client.read(RADIO_SCREEN["Voltage"])

        print("Temperature =", temp)
        print("Voltage =", voltage)

        self.frequencyDisplay.setValue(text)

        print("Label now contains:", self.frequencyDisplay.value.text())

        print("Setting status CONNECTED")
        self.status.connected()

        print("Setting receiver power ON")
        self.receiverPanel.set_power(True)

        if errTemp is None:
            self.tempCard.setValue(temp)
        else:
            self.tempCard.setValue("--")

        if errVoltage is None:
            self.voltageCard.setValue(voltage)
        else:
            self.voltageCard.setValue("--")

    # def load_data(self):
    #     import traceback

    #     try:

    #         # freq, err1 = client.read(RADIO_SCREEN["Frequency"])
    #         freq, errFreq = client.read(RADIO_SCREEN["Frequency"])
    #         if errFreq is None:
    #             text = decode_frequency(freq)

    #             print("Decoded =", text)
    #             print("Widget before =", self.frequencyDisplay.text())

    #             self.frequencyDisplay.setValue(text)

    #             print("Widget after =", self.frequencyDisplay.text())
    #             # self.frequencyDisplay.setValue(decode_frequency(freq))
    #             self.frequencyDisplay.setText("121.700 MHz")
    #             self.frequencyDisplay.repaint()
    #         rssi, errRssi = client.read(RADIO_SCREEN["RSSI"])
    #         cn, errCN = client.read(RADIO_SCREEN["CarrierNoise"])
    #         offset, errOffset = client.read(RADIO_SCREEN["Offset"])
    #         alarm, errAlarm = client.read(RADIO_SCREEN["Alarm"])
    #         mode, errMode = client.read(RADIO_SCREEN["Mode"])
    #         state, errState = client.read(RADIO_SCREEN["State"])

    #         if errFreq:
    #             self.status.disconnected()
    #             return

    #         self.status.connected()
    #         self.receiverPanel.set_power(True)

    #         # print(f"Reading frequency {freq}")
    #         print("Reading frequency", freq)

    #         value = decode_frequency(freq)

    #         print("Decoded =", value)

    #         self.frequencyDisplay.setValue(value)

    #         self.frequencyDisplay.repaint()
    #         self.frequencyDisplay.update()

    #         QApplication.processEvents()

    #         print("Widget updated")

    #         print("GUI updated")
    #         # Update each widget independently

    #         if errRssi is None:
    #             self.rssiCard.setValue(decode_rssi(rssi))
    #             try:
    #                 rssi_val = float(rssi)
    #                 if rssi_val > -60:
    #                     signal_level = 5
    #                 elif rssi_val > -70:
    #                     signal_level = 4
    #                 elif rssi_val > -80:
    #                     signal_level = 3
    #                 elif rssi_val > -90:
    #                     signal_level = 2
    #                 elif rssi_val > -100:
    #                     signal_level = 1
    #                 else:
    #                     signal_level = 0
    #             except (ValueError, TypeError):
    #                 signal_level = 0
    #             self.receiverPanel.set_signal(signal_level)
    #         else:
    #             self.rssiCard.setValue("--")
    #             self.receiverPanel.set_signal(0)

    #         if errCN is None:
    #             self.cnCard.setValue(decode_cn(cn))
    #         else:
    #             self.cnCard.setValue("--")

    #         if errOffset is None:
    #             self.offsetCard.setValue(decode_offset(offset))
    #         else:
    #             self.offsetCard.setValue("--")

    #         # if errMode is None:
    #         #     self.modeCard.setValue(decode_mode(mode))
    #         # else:
    #         #     self.modeCard.setValue("--")

    #         # if errState is None:
    #         #     self.stateCard.setValue(decode_state(state))
    #         # else:
    #         #     self.stateCard.setValue("--")

    #         if errAlarm is None:
    #             alarm_text = decode_alarm(alarm)
    #             self.alarmCard.setAlarm(alarm_text)
    #             alarm_active = not any(
    #                 token in str(alarm_text).lower()
    #                 for token in ["no alarm", "none", "0", "ok"]
    #             )
    #             self.receiverPanel.set_alarm(alarm_active)
    #         else:
    #             self.alarmCard.setAlarm("--")
    #             self.receiverPanel.set_alarm(False)

    #         # These OIDs are not known yet
    #         self.tempCard.setValue("--")
    #         self.powerCard.setValue("--")
    #         self.voltageCard.setValue("--")

    #         logger.add("Receiver Updated")

    #     except Exception:
    #         traceback.print_exc()
    #         self.status.disconnected()

    #     self.update_log()

    # =====================================================
    # UPDATE EVENT LOG
    # =====================================================

    def update_log(self):

        self.logBox.clear()

        self.logBox.setPlainText("\n".join(logger.get_events()))

    # =====================================================
    # CLOSE EVENT
    # =====================================================

    def closeEvent(self, event):

        self.timer.stop()

        event.accept()
