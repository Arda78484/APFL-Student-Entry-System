import sys
import serial
import serial.tools.list_ports
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel, QPushButton, QComboBox
from PyQt5.QtGui import QColor, QPalette
from PyQt5.QtCore import QTimer

class RFIDApp(QWidget):
    def __init__(self):
        print("App started!")
        super().__init__()
        self.setWindowTitle("RFID Reader")
        self.resize(400, 200)

        layout = QVBoxLayout()

        self.status_label = QLabel("Status: Waiting for card...")
        self.status_label.setStyleSheet("font-size: 18px;")
        layout.addWidget(self.status_label)

        self.card_label = QLabel("Card ID: ")
        layout.addWidget(self.card_label)

        self.port_combo = QComboBox()
        self.detect_ports()
        layout.addWidget(self.port_combo)

        self.connect_button = QPushButton("Connect")
        self.connect_button.clicked.connect(self.connect_serial)
        layout.addWidget(self.connect_button)

        self.setLayout(layout)
        self.serial = None

        self.timer = QTimer()
        self.timer.timeout.connect(self.read_serial)

        self.set_color("blue")  # Initial color

    def detect_ports(self):
        ports = serial.tools.list_ports.comports()
        for port in ports:
            self.port_combo.addItem(port.device)

    def connect_serial(self):
        port = self.port_combo.currentText()
        try:
            self.serial = serial.Serial(port, 115200, timeout=0.5)
            self.status_label.setText("Connected! Waiting for card...")
            self.set_color("blue")
            self.timer.start(100)
        except Exception as e:
            self.status_label.setText(f"Failed to connect: {e}")
            self.set_color("red")

    def read_serial(self):
        if self.serial and self.serial.in_waiting > 0:
            try:
                data = self.serial.readline().decode('utf-8').strip()
                if "Bulundu" in data:
                    self.set_color("yellow")
                elif "Kart ID" in data:
                    self.card_label.setText(data)
                    self.set_color("green")
            except:
                pass

    def set_color(self, color):
        palette = self.palette()
        if color == "blue":
            palette.setColor(QPalette.Window, QColor(0, 0, 255))
        elif color == "yellow":
            palette.setColor(QPalette.Window, QColor(255, 255, 0))
        elif color == "green":
            palette.setColor(QPalette.Window, QColor(0, 255, 0))
        elif color == "red":
            palette.setColor(QPalette.Window, QColor(255, 0, 0))
        self.setPalette(palette)

if __name__ == "__main__":
    print("Launching GUI...")
    app = QApplication(sys.argv)
    window = RFIDApp()
    window.show()
    sys.exit(app.exec_())
