import os
import sys
import shutil
import sqlite3
import datetime
import serial
import serial.tools.list_ports
from PyQt5.QtWidgets import (QApplication, QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
                             QTabWidget, QFileDialog, QLineEdit, QMessageBox, QTableWidget, QTableWidgetItem, QComboBox)
from PyQt5.QtCore import Qt, QTimer

# Folders
os.makedirs("photos", exist_ok=True)
os.makedirs("db", exist_ok=True)
os.makedirs("exports", exist_ok=True)
os.makedirs("sounds", exist_ok=True)

DB_PATH = "db/system.db"

def init_db():
    if not os.path.exists(DB_PATH):
        print("📦 Veritabanı oluşturuluyor...")
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS students (
                id INTEGER PRIMARY KEY,
                card_uid TEXT UNIQUE,
                name TEXT,
                surname TEXT,
                photo_path TEXT,
                can_exit INTEGER DEFAULT 1,
                status TEXT DEFAULT 'Outside',
                last_updated TEXT
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER,
                card_uid TEXT,
                action TEXT,
                timestamp TEXT
            )
        """)
        conn.commit()
        conn.close()
        print("✅ Veritabanı oluşturuldu: db/system.db")
    else:
        print("✅ Veritabanı zaten var.")


class RFIDApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Yurt Giriş/Çıkış Kart Sistemi")
        self.resize(800, 500)
        self.selected_photo_path = None
        self.card_uid = None
        self.serial = None
        self.timer = QTimer()
        self.timer.timeout.connect(self.read_serial)
        init_db()
        self.initUI()

    def initUI(self):
        layout = QVBoxLayout()
        self.tabs = QTabWidget()

        self.tabs.addTab(self.buildScanTab(), "🔄 Giriş/Çıkış")
        self.tabs.addTab(self.buildRegisterTab(), "➕ Öğrenci Ekle")
        self.tabs.addTab(self.buildLogsTab(), "📋 Kayıtlar")

        layout.addWidget(self.tabs)
        self.setLayout(layout)

    def buildScanTab(self):
        tab = QWidget()
        layout = QVBoxLayout()

        self.scan_label = QLabel("Kart bekleniyor...")
        self.scan_label.setAlignment(Qt.AlignCenter)
        self.scan_label.setStyleSheet("font-size: 20px; padding: 20px")

        self.status_display = QLabel("Durum: -")
        self.status_display.setAlignment(Qt.AlignCenter)
        self.status_display.setStyleSheet("font-size: 16px;")

        self.com_port_combo = QComboBox()
        self.com_port_combo.addItems([port.device for port in serial.tools.list_ports.comports()])
        self.com_port_combo.setPlaceholderText("Seri Port Seç")

        self.connect_btn = QPushButton("Bağlan")
        self.connect_btn.clicked.connect(self.connect_serial)

        layout.addWidget(QLabel("Seri Port Seç:"))
        layout.addWidget(self.com_port_combo)
        layout.addWidget(self.connect_btn)
        layout.addWidget(self.scan_label)
        layout.addWidget(self.status_display)
        tab.setLayout(layout)

        self.view_students_btn = QPushButton("📁 Öğrenci Bilgilerini Gör")
        self.view_students_btn.clicked.connect(self.show_all_students)
        layout.addWidget(self.view_students_btn)

        return tab
    
    def show_all_students(self):
        win = QWidget()
        win.setWindowTitle("Tüm Öğrenciler")
        layout = QVBoxLayout()
        table = QTableWidget()
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT * FROM students")
        data = c.fetchall()
        conn.close()
        table.setRowCount(len(data))
        table.setColumnCount(6)
        table.setHorizontalHeaderLabels(["ID", "UID", "Foto", "İzin", "Durum", "Güncelleme"])
        for row, item in enumerate(data):
            for col, val in enumerate(item):
                table.setItem(row, col, QTableWidgetItem(str(val)))
        layout.addWidget(table)
        win.setLayout(layout)
        win.resize(700, 300)
        win.show()
        win.setAttribute(Qt.WA_DeleteOnClose)


    def buildRegisterTab(self):
        tab = QWidget()
        layout = QVBoxLayout()

        self.card_uid_label = QLabel("Kart UID: -")
        self.student_id_input = QLineEdit()
        self.student_id_input.setPlaceholderText("Öğrenci No (örneğin: 18014)")
        self.upload_btn = QPushButton("Fotoğraf Seç")
        self.upload_btn.clicked.connect(self.selectPhoto)
        self.save_btn = QPushButton("Kaydet")
        self.save_btn.clicked.connect(self.save_student)

        layout.addWidget(self.card_uid_label)
        layout.addWidget(self.student_id_input)
        layout.addWidget(self.upload_btn)
        layout.addWidget(self.save_btn)

        tab.setLayout(layout)
        return tab

    def buildLogsTab(self):
        tab = QWidget()
        layout = QVBoxLayout()
        self.log_table = QTableWidget()
        self.log_table.setColumnCount(3)
        self.log_table.setHorizontalHeaderLabels(["Öğrenci No", "İşlem", "Zaman"])

        self.export_btn = QPushButton("Excel'e Aktar")
        layout.addWidget(self.log_table)
        layout.addWidget(self.export_btn)
        tab.setLayout(layout)
        return tab

    def connect_serial(self):
        port = self.com_port_combo.currentText()
        try:
            self.serial = serial.Serial(port, 115200, timeout=1)
            self.scan_label.setText(f"{port} ile bağlantı kuruldu. Kart bekleniyor...")
            self.timer.start(200)
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Seri bağlantı kurulamadı:\n{e}")

    def read_serial(self):
        if self.serial and self.serial.in_waiting > 0:
            uid = self.serial.readline().decode('utf-8').strip()
            if not uid:
                return
            self.card_uid = uid
            self.card_uid_label.setText(f"Kart UID: {uid}")
            self.scan_label.setText(f"Kart Okundu: {uid}")

            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("SELECT id, photo_path, can_exit, status FROM students WHERE card_uid=?", (uid,))
            result = c.fetchone()

            now = datetime.datetime.now().isoformat()
            if result:
                student_id, photo_path, can_exit, current_status = result
                if not can_exit:
                    action = "Rejected"
                    self.status_display.setText("Çıkış izni yok!")
                    self.setStyleSheet("background-color: red;")
                else:
                    new_status = "Inside" if current_status == "Outside" else "Outside"
                    action = "Entry" if new_status == "Inside" else "Exit"
                    c.execute("UPDATE students SET status=?, last_updated=? WHERE id=?", (new_status, now, student_id))
                    self.status_display.setText(f"{action} başarılı ({student_id})")
                    self.setStyleSheet("background-color: green;")
                    if os.path.exists(photo_path):
                        self.show_photo(photo_path)
                c.execute("INSERT INTO logs (student_id, card_uid, action, timestamp) VALUES (?, ?, ?, ?)",
                          (student_id, uid, action, now))
                conn.commit()
            else:
                self.status_display.setText("Kart tanımlı değil!")
                self.setStyleSheet("background-color: red;")
                c.execute("INSERT INTO logs (student_id, card_uid, action, timestamp) VALUES (?, ?, ?, ?)",
                          (-1, uid, "Rejected", now))
                conn.commit()
            conn.close()


    def selectPhoto(self):
        file_dialog = QFileDialog()
        file_path, _ = file_dialog.getOpenFileName(self, "Fotoğraf Seç", "", "Resim Dosyaları (*.png *.jpg *.jpeg)")
        if file_path:
            self.selected_photo_path = file_path
            QMessageBox.information(self, "Başarılı", "Fotoğraf seçildi.")

    def show_photo(self, path):
        pixmap = QPixmap(path)
        if not pixmap.isNull():
            self.photo_display.setPixmap(pixmap.scaled(self.photo_display.size(), Qt.KeepAspectRatio))


    def save_student(self):
        student_id = self.student_id_input.text()
        if not student_id.isdigit() or not self.card_uid or not self.selected_photo_path:
            QMessageBox.warning(self, "Eksik Bilgi", "Lütfen öğrenci no, kart ve fotoğraf seçin.")
            return

        dest_photo = f"photos/{student_id}.jpg"
        shutil.copy(self.selected_photo_path, dest_photo)

        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        try:
            c.execute("INSERT INTO students (id, card_uid, photo_path, last_updated) VALUES (?, ?, ?, ?)",
                      (student_id, self.card_uid, dest_photo, datetime.datetime.now().isoformat()))
            conn.commit()
            QMessageBox.information(self, "Kayıt", "Öğrenci başarıyla kaydedildi.")
            self.student_id_input.clear()
            self.card_uid_label.setText("Kart UID: -")
        except sqlite3.IntegrityError:
            QMessageBox.warning(self, "Hata", "Bu öğrenci veya kart zaten kayıtlı.")
        conn.close()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    win = RFIDApp()
    win.show()
    sys.exit(app.exec_())
