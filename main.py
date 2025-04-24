# main.py
import sys
import os
import shutil
import datetime
import traceback # Hata ayıklama için eklendi
from PyQt5.QtWidgets import (QApplication, QWidget, QLabel, QPushButton, QVBoxLayout,
                             QHBoxLayout, QTabWidget, QFileDialog, QLineEdit,
                             QMessageBox, QTableWidget, QTableWidgetItem, QComboBox,
                             QSpacerItem, QSizePolicy, QGridLayout, QHeaderView, QDialog,
                             QAbstractItemView)
# Ensure all necessary QtCore and QtGui imports are present
from PyQt5.QtCore import QObject, pyqtSignal, QThread, pyqtSlot, QModelIndex, Qt, QMetaObject, QTimer # QTimer eklendi (opsiyonel kullanım için)

from PyQt5.QtGui import QPixmap, QIcon

# Import custom modules
# Ensure db.py and card_reader_controller.py are in the same directory or accessible via PYTHONPATH
try:
    from db import DatabaseManager, DB_PATH, PHOTOS_DIR
    from card_reader_controller import CardReaderController
except ImportError as e:
     print(f"Import Error: {e}. Make sure db.py and card_reader_controller.py are present.")
     # Optionally show a message box and exit
     app = QApplication([]) # Need an app instance for QMessageBox
     QMessageBox.critical(None, "Eksik Modül Hatası", f"Program başlatılamadı: {e}\nLütfen 'db.py' ve 'card_reader_controller.py' dosyalarının programla aynı dizinde olduğundan emin olun.")
     sys.exit(1)


# Define directories (ensure they exist)
# It's generally better practice to define these paths relative to the script
# or use application data directories, but for simplicity:
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PHOTOS_DIR_ABS = os.path.join(BASE_DIR, "photos") # Use absolute path for photo storage
DB_DIR_ABS = os.path.join(BASE_DIR, "db")
EXPORTS_DIR_ABS = os.path.join(BASE_DIR, "exports")
SOUNDS_DIR_ABS = os.path.join(BASE_DIR, "sounds")

os.makedirs(PHOTOS_DIR_ABS, exist_ok=True)
os.makedirs(DB_DIR_ABS, exist_ok=True) # db.py will likely handle this too via DB_PATH
os.makedirs(EXPORTS_DIR_ABS, exist_ok=True)
os.makedirs(SOUNDS_DIR_ABS, exist_ok=True)

# Define constants
ESP_BAUD_RATE = 9600 # Match the ESP32 code's BAUD_RATE

# --- Dialog for Student Details ---
class StudentDetailDialog(QDialog):
    """A Dialog to show student details including photo."""
    def __init__(self, student_data, parent=None):
        super().__init__(parent)
        # Use f-string safely with .get() providing default values
        self.setWindowTitle(f"Öğrenci Detayı - {student_data.get('name', '')} {student_data.get('surname', '')}".strip())
        self.setMinimumSize(400, 350) # Increased height slightly

        layout = QGridLayout(self)

        # --- Photo Display ---
        self.photo_label = QLabel("Fotoğraf Yükleniyor...")
        self.photo_label.setFixedSize(150, 200)
        self.photo_label.setAlignment(Qt.AlignCenter)
        self.photo_label.setStyleSheet("border: 1px solid gray; background-color: #f0f0f0;")
        layout.addWidget(self.photo_label, 0, 0, 7, 1) # Span more rows to align better

        photo_path = student_data.get('photo_path')
        # Use absolute path when checking/loading photo
        if photo_path and os.path.exists(os.path.join(BASE_DIR, photo_path)):
            pixmap = QPixmap(os.path.join(BASE_DIR, photo_path))
            if not pixmap.isNull():
                # Use SmoothTransformation for better scaling quality
                self.photo_label.setPixmap(pixmap.scaled(self.photo_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
            else:
                self.photo_label.setText("Fotoğraf\nYüklenemedi") # Multi-line
        else:
             self.photo_label.setText("Fotoğraf\nYok") # Multi-line

        # --- Student Info Labels ---
        row = 0
        info_map = [
            ('id', "Öğrenci No:"), ('card_uid', "Kart UID:"),
            ('name', "Ad:"), ('surname', "Soyad:"),
            ('status', "Durum:"), ('can_exit', "Çıkış İzni:"),
            ('last_updated', "Son Güncelleme:")
        ]
        for key, label_text in info_map:
            layout.addWidget(QLabel(f"<b>{label_text}</b>"), row, 1, Qt.AlignTop) # Align label top

            value = student_data.get(key, 'N/A') # Default to 'N/A' if key missing

            if key == 'can_exit':
                value_text = "Var" if value == 1 else "Yok"
            elif key == 'last_updated' and value not in (None, 'N/A'):
                 try:
                     # Attempt to parse and format timestamp
                     dt_obj = datetime.datetime.fromisoformat(str(value))
                     value_text = dt_obj.strftime('%Y-%m-%d %H:%M:%S')
                 except (ValueError, TypeError):
                     value_text = str(value) # Fallback to string representation
            else:
                value_text = str(value)

            value_label = QLabel(value_text)
            value_label.setWordWrap(True) # Allow wrapping for long UIDs or paths
            layout.addWidget(value_label, row, 2, Qt.AlignTop) # Align value top
            row += 1

        # --- Close Button ---
        layout.setRowStretch(row, 1) # Push button down
        close_button = QPushButton("Kapat")
        close_button.clicked.connect(self.accept) # Close dialog on click
        layout.addWidget(close_button, row + 1, 1, 1, 2) # Span button across info columns

        self.setLayout(layout)


# --- Main Application Window ---
class MainWindow(QWidget):
    """Main application window for the RFID system."""
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Yurt Giriş/Çıkış Kart Sistemi")
        self.setMinimumSize(800, 600)
        self.setGeometry(100, 100, 850, 650) # Initial position and size

        # --- State Variables ---
        self.selected_photo_path = None # Stores the full path from file dialog
        self.current_card_uid_for_registration = None

        # --- Initialize Backend Components ---
        try:
            # Use absolute path for DB manager
            db_full_path = os.path.join(DB_DIR_ABS, "system.db")
            self.db_manager = DatabaseManager(db_path=db_full_path)
            self.card_reader = CardReaderController()
        except Exception as e:
             QMessageBox.critical(self, "Başlatma Hatası", f"Veritabanı veya kart okuyucu başlatılamadı: {e}\n{traceback.format_exc()}")
             # Exit gracefully if critical components fail
             # Need to ensure QApplication exists if called very early
             # If __init__ fails, maybe raise exception instead?
             # For now, we assume QApplication exists or handle it in main block
             sys.exit(1)

        # --- Initialize UI ---
        self.initUI()

        # --- Connect Signals from Controller ---
        self.card_reader.cardRead.connect(self.handle_card_read)
        self.card_reader.statusUpdate.connect(self.update_serial_status)
        self.card_reader.errorOccurred.connect(self.show_error_message)
        self.card_reader.commandAckReceived.connect(self.handle_command_ack)

        # --- Load Initial Data ---
        # Use invokeMethod to ensure UI is ready before populating tables
        QMetaObject.invokeMethod(self, "refresh_student_table", Qt.QueuedConnection)
        QMetaObject.invokeMethod(self, "refresh_log_table", Qt.QueuedConnection)

    def initUI(self):
        """Sets up the main UI layout and tabs."""
        main_layout = QVBoxLayout(self)
        self.tabs = QTabWidget()

        # Create and add tabs
        self.tabs.addTab(self._build_scan_tab(), "🔄 Giriş/Çıkış")
        self.tabs.addTab(self._build_register_tab(), "➕ Öğrenci Kayıt")
        self.tabs.addTab(self._build_students_tab(), "👥 Öğrenciler")
        self.tabs.addTab(self._build_logs_tab(), "📋 Kayıtlar")

        main_layout.addWidget(self.tabs)
        self.setLayout(main_layout)

    # ==========================================================
    # Tab Building Methods (Implementations from previous response)
    # ==========================================================
    def _build_scan_tab(self):
        """Builds the 'Scan' (Giriş/Çıkış) tab UI elements."""
        tab = QWidget()
        # Ana layout: Sol taraf bilgiler, sağ taraf fotoğraf için 2 sütunlu olabilir
        main_h_layout = QHBoxLayout(tab)

        # Sol taraf: Bağlantı ve durum bilgileri
        left_v_layout = QVBoxLayout()
        left_grid_layout = QGridLayout() # Port ve butonlar için Grid

        row = 0
        left_grid_layout.addWidget(QLabel("Seri Port:"), row, 0)
        self.com_port_combo = QComboBox()
        self.com_port_combo.setMinimumWidth(150)
        self.refresh_com_ports()
        left_grid_layout.addWidget(self.com_port_combo, row, 1) # Grid'de 1. sütun

        self.refresh_ports_btn = QPushButton("Yenile")
        self.refresh_ports_btn.setToolTip("Seri port listesini yenile")
        self.refresh_ports_btn.clicked.connect(self.refresh_com_ports)
        left_grid_layout.addWidget(self.refresh_ports_btn, row, 2) # Grid'de 2. sütun

        row += 1
        self.connect_btn = QPushButton("Bağlan")
        self.connect_btn.setCheckable(True)
        self.connect_btn.setToolTip("Seçili seri porta bağlan/bağlantıyı kes")
        self.connect_btn.clicked.connect(self.toggle_serial_connection)
        left_grid_layout.addWidget(self.connect_btn, row, 0, 1, 3) # Grid'de 3 sütunu kapla

        left_v_layout.addLayout(left_grid_layout) # Grid'i sol dikey layout'a ekle

        self.scan_status_label = QLabel("Durum: Bağlantı bekleniyor...")
        self.scan_status_label.setAlignment(Qt.AlignCenter)
        self.scan_status_label.setStyleSheet(
            "font-size: 16px; padding: 15px; border: 1px solid #ccc; "
            "background-color: #f8f8f8; border-radius: 5px; min-height: 50px;"
        )
        self.scan_status_label.setWordWrap(True)
        left_v_layout.addWidget(self.scan_status_label)

        self.last_scan_label = QLabel("Son Kart: -")
        self.last_scan_label.setAlignment(Qt.AlignCenter)
        self.last_scan_label.setStyleSheet("font-size: 20px; padding: 10px; font-weight: bold;")
        left_v_layout.addWidget(self.last_scan_label)

        self.system_check_btn = QPushButton("⚙️ Sistem Kontrol")
        self.system_check_btn.setToolTip("Bağlı ESP cihazına kontrol sinyali gönderir")
        self.system_check_btn.clicked.connect(self._perform_system_check)
        self.system_check_btn.setEnabled(False)
        left_v_layout.addWidget(self.system_check_btn)

        left_v_layout.addStretch(1) # Sol tarafı yukarı ittir
        main_h_layout.addLayout(left_v_layout, 1) # Sol tarafı ana layout'a ekle (esneme faktörü 1)

        # Sağ taraf: Fotoğraf görüntüleme alanı
        right_v_layout = QVBoxLayout()
        photo_container_label = QLabel("Öğrenci Fotoğrafı") # Başlık
        photo_container_label.setAlignment(Qt.AlignCenter)
        right_v_layout.addWidget(photo_container_label)

        self.scan_photo_display = QLabel()
        self.scan_photo_display.setFixedSize(200, 266) # Fotoğraf için boyut (3:4 oranına yakın)
        self.scan_photo_display.setAlignment(Qt.AlignCenter)
        self.scan_photo_display.setStyleSheet(
            "border: 2px dashed #aaa; background-color: #e0e0e0; border-radius: 5px;"
            "color: #555; font-style: italic;"
        )
        self.scan_photo_display.setText("Kart Okutunuz") # Başlangıç metni
        right_v_layout.addWidget(self.scan_photo_display)
        right_v_layout.addStretch(1) # Fotoğrafı yukarı ittir

        main_h_layout.addLayout(right_v_layout, 0) # Sağ tarafı ana layout'a ekle (esnemez)

        tab.setLayout(main_h_layout) # Ana layout'u sekme widget'ına ata
        return tab
    
    def _clear_scan_photo(self):
        """Clears the photo display on the scan tab."""
        self.scan_photo_display.clear() # Pixmap'i temizle
        self.scan_photo_display.setText("Kart Okutunuz") # Varsayılan metni ayarla
        self.scan_photo_display.setStyleSheet(
            "border: 2px dashed #aaa; background-color: #e0e0e0; border-radius: 5px;"
            "color: #555; font-style: italic;"
        )
    
    def _build_register_tab(self):
        """Builds the 'Register Student' (Öğrenci Kayıt) tab UI elements."""
        tab = QWidget()
        layout = QGridLayout(tab)
        default_uid_text = "- (Giriş/Çıkış sekmesinden bağlanıp kart okutun)"
        row = 0
        layout.addWidget(QLabel("<b>Okunan Kart UID:</b>"), row, 0)
        self.reg_card_uid_label = QLabel(default_uid_text)
        self.reg_card_uid_label.setStyleSheet("font-style: italic; color: gray;")
        self.reg_card_uid_label.setWordWrap(True)
        layout.addWidget(self.reg_card_uid_label, row, 1, 1, 2)
        row += 1
        layout.addWidget(QLabel("<b>Öğrenci No:</b>"), row, 0)
        self.reg_student_id_input = QLineEdit()
        self.reg_student_id_input.setPlaceholderText("Sayısal numara (örn: 2025001)")
        layout.addWidget(self.reg_student_id_input, row, 1, 1, 2)
        row += 1
        layout.addWidget(QLabel("<b>Ad:</b>"), row, 0)
        self.reg_student_name_input = QLineEdit()
        self.reg_student_name_input.setPlaceholderText("Öğrencinin adı")
        layout.addWidget(self.reg_student_name_input, row, 1, 1, 2)
        row += 1
        layout.addWidget(QLabel("<b>Soyad:</b>"), row, 0)
        self.reg_student_surname_input = QLineEdit()
        self.reg_student_surname_input.setPlaceholderText("Öğrencinin soyadı")
        layout.addWidget(self.reg_student_surname_input, row, 1, 1, 2)
        row += 1
        self.reg_upload_btn = QPushButton("Fotoğraf Seç")
        self.reg_upload_btn.clicked.connect(self._select_photo)
        layout.addWidget(self.reg_upload_btn, row, 0)
        self.reg_photo_preview_label = QLabel("Fotoğraf\nSeçilmedi")
        self.reg_photo_preview_label.setAlignment(Qt.AlignCenter)
        self.reg_photo_preview_label.setFixedSize(100, 133)
        self.reg_photo_preview_label.setStyleSheet("border: 1px dashed gray; background-color: #f0f0f0; border-radius: 3px;")
        layout.addWidget(self.reg_photo_preview_label, row, 1, 2, 1)
        self.reg_selected_photo_label = QLabel("")
        self.reg_selected_photo_label.setWordWrap(True)
        layout.addWidget(self.reg_selected_photo_label, row, 2)
        row += 2
        self.reg_save_btn = QPushButton("✅ Öğrenciyi Kaydet")
        self.reg_save_btn.setStyleSheet("font-weight: bold; padding: 10px; background-color: #d4edda; border-radius: 5px;")
        self.reg_save_btn.clicked.connect(self._save_student)
        layout.addWidget(self.reg_save_btn, row, 0, 1, 3)
        layout.setRowStretch(row + 1, 1)
        layout.setColumnStretch(2, 1)
        tab.setLayout(layout)
        return tab

    def _build_students_tab(self):
        """Builds the tab for viewing and managing students (Öğrenciler)."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        action_layout = QHBoxLayout()
        refresh_btn = QPushButton("🔄 Listeyi Yenile")
        refresh_btn.setToolTip("Öğrenci listesini veritabanından yeniden yükle")
        refresh_btn.clicked.connect(self.refresh_student_table)
        delete_btn = QPushButton("❌ Seçili Öğrenciyi Sil")
        delete_btn.setToolTip("Tablodan seçili olan öğrenciyi sil")
        delete_btn.clicked.connect(self._delete_selected_student)
        action_layout.addWidget(refresh_btn)
        action_layout.addWidget(delete_btn)
        action_layout.addStretch(1)
        layout.addLayout(action_layout)
        self.student_table = QTableWidget()
        column_headers = ["Öğrenci No", "Kart UID", "Ad", "Soyad", "Foto Path", "Çıkış İzni", "Durum", "Son Güncelleme"]
        self.student_table.setColumnCount(len(column_headers))
        self.student_table.setHorizontalHeaderLabels(column_headers)
        self.student_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.student_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.student_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.student_table.verticalHeader().setVisible(False)
        self.student_table.setAlternatingRowColors(True)
        self.student_table.setSortingEnabled(True)
        header = self.student_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Interactive)
        header.setSectionResizeMode(2, QHeaderView.Interactive)
        header.setSectionResizeMode(3, QHeaderView.Interactive)
        header.setSectionResizeMode(4, QHeaderView.Stretch)
        header.setSectionResizeMode(7, QHeaderView.ResizeToContents)
        self.student_table.doubleClicked.connect(self._show_student_details)
        layout.addWidget(self.student_table)
        tab.setLayout(layout)
        return tab

    def _build_logs_tab(self):
        """Builds the 'Logs' (Kayıtlar) tab UI elements."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        action_layout = QHBoxLayout()
        refresh_btn = QPushButton("🔄 Kayıtları Yenile")
        refresh_btn.setToolTip("Giriş/çıkış kayıtlarını veritabanından yeniden yükle")
        refresh_btn.clicked.connect(self.refresh_log_table)
        export_btn = QPushButton("⬇️ Excel'e Aktar (TODO)")
        export_btn.setToolTip("Tüm kayıtları bir Excel dosyasına aktar")
        export_btn.clicked.connect(self._export_logs)
        export_btn.setEnabled(False)
        action_layout.addWidget(refresh_btn)
        action_layout.addWidget(export_btn)
        action_layout.addStretch(1)
        layout.addLayout(action_layout)
        self.log_table = QTableWidget()
        column_headers = ["Zaman", "Öğrenci No", "Ad Soyad", "İşlem", "Kart UID"]
        self.log_table.setColumnCount(len(column_headers))
        self.log_table.setHorizontalHeaderLabels(column_headers)
        self.log_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.log_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.log_table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.log_table.verticalHeader().setVisible(False)
        self.log_table.setAlternatingRowColors(True)
        self.log_table.setSortingEnabled(True)
        header = self.log_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.Interactive)
        header.setSectionResizeMode(4, QHeaderView.Interactive)
        layout.addWidget(self.log_table)
        tab.setLayout(layout)
        return tab

    # ==========================================================
    # UI Update and Refresh Methods (Implementations from previous response)
    # ==========================================================

    @pyqtSlot(str)
    def update_serial_status(self, message):
        """Updates the status label and button states, clears photo on disconnect."""
        self.scan_status_label.setText(f"Durum: {message}")
        is_connected = message.startswith("✅ Bağlandı:")

        self.connect_btn.setChecked(is_connected)
        self.connect_btn.setText("Bağlantıyı Kes" if is_connected else "Bağlan")
        self.system_check_btn.setEnabled(is_connected) # Enable check button only when connected

        if not is_connected:
             # Bağlantı kesildiğinde veya hata olduğunda temizle
             self.last_scan_label.setText("Son Kart: -")
             self._clear_scan_photo()

    @pyqtSlot(str)
    def show_error_message(self, message):
        """Displays an error message box and logs it."""
        print(f"ERROR displayed: {message}") # Log error to console as well
        # Avoid showing redundant disconnect messages if UI already shows disconnected
        if "Seri bağlantı kapandı" in message and not self.card_reader.is_connected() and not self.connect_btn.isChecked():
             print("Suppressed redundant disconnect error message.")
             return
        QMessageBox.warning(self, "Hata", message)
        # Optionally update status label too, though statusUpdate signal is preferred
        # self.scan_status_label.setText(f"Durum: Hata Oluştu!")

    @pyqtSlot(str)
    def handle_command_ack(self, ack_command):
        """Handles acknowledgment messages (like 'CHECK_OK') from the ESP32."""
        print(f"DEBUG: Main: ACK received: {ack_command}")
        if ack_command == "CHECK_OK":
            # Give positive feedback
            QMessageBox.information(self, "Sistem Kontrolü Başarılı",
                                    "ESP32 cihazı sistem kontrol komutunu başarıyla yanıtladı.")
            self.scan_status_label.setText("Durum: Sistem kontrolü başarılı.")
            # Revert status after a delay?
            # QTimer.singleShot(3000, lambda: self.update_serial_status(f"✅ Bağlandı: {self.com_port_combo.currentText()}"))
        else:
            # Show unknown ACK
             self.scan_status_label.setText(f"Durum: Bilinmeyen onay alındı: {ack_command}")
             QMessageBox.warning(self, "Bilinmeyen Onay", f"ESP32'den beklenmeyen bir onay mesajı alındı: {ack_command}")

    @pyqtSlot() # Explicitly mark as slot for invokeMethod connection
    def refresh_com_ports(self):
        """Refreshes the list of available COM ports in the combo box."""
        current_port = self.com_port_combo.currentText()
        self.com_port_combo.clear()
        ports = self.card_reader.list_ports()
        if ports:
            self.com_port_combo.addItems(ports)
            # Try to re-select previous port if still available
            index = self.com_port_combo.findText(current_port)
            if index != -1:
                self.com_port_combo.setCurrentIndex(index)
            else:
                 self.com_port_combo.setCurrentIndex(-1) # No selection
                 self.com_port_combo.setPlaceholderText("Seri Port Seç")
        else:
            self.com_port_combo.setPlaceholderText("Port bulunamadı")

    @pyqtSlot() # invokeMethod ile çağrıldığı için slot olarak işaretlemek iyi olabilir
    def refresh_log_table(self):
        """Fetches logs from DB and updates the log table."""
        print("DEBUG: Main: Refreshing log table...")
        try:
            logs = self.db_manager.get_all_logs()
            self.log_table.setSortingEnabled(False)
            self.log_table.setRowCount(len(logs))

            for row, log_entry in enumerate(logs):
                # Format timestamp
                timestamp_str = "N/A"
                try:
                    # Use dictionary-style access: log_entry['column_name']
                    ts_val = log_entry['timestamp']
                    if ts_val:
                        dt_obj = datetime.datetime.fromisoformat(ts_val)
                        timestamp_str = dt_obj.strftime('%Y-%m-%d %H:%M:%S')
                except (ValueError, TypeError, KeyError):
                    timestamp_str = str(log_entry['timestamp'] if 'timestamp' in log_entry else 'Hata') # Fallback

                # Combine name/surname safely using direct access + 'or'
                student_name = f"{log_entry['name'] or ''} {log_entry['surname'] or ''}".strip()
                if not student_name: student_name = "-"

                # Populate cells using direct access
                self.log_table.setItem(row, 0, QTableWidgetItem(timestamp_str))
                self.log_table.setItem(row, 1, QTableWidgetItem(str(log_entry['student_id'] if 'student_id' in log_entry else 'N/A')))
                self.log_table.setItem(row, 2, QTableWidgetItem(student_name))
                self.log_table.setItem(row, 3, QTableWidgetItem(log_entry['action'] if 'action' in log_entry else 'N/A'))
                self.log_table.setItem(row, 4, QTableWidgetItem(log_entry['card_uid'] if 'card_uid' in log_entry else 'N/A'))

            self.log_table.setSortingEnabled(True)
        except Exception as e:
             print(f"ERROR: Failed to refresh log table: {e}")
             traceback.print_exc()
             self.show_error_message(f"Kayıt tablosu yenilenirken hata oluştu: {e}")


    @pyqtSlot()
    def refresh_student_table(self):
        """Fetches student data and updates the student table using direct key access."""
        print("DEBUG: Main: Refreshing student table...")
        try:
            students = self.db_manager.get_all_students()
            self.student_table.setSortingEnabled(False)
            self.student_table.setRowCount(len(students))

            for row, student in enumerate(students):
                # Format timestamp safely
                timestamp_str = "N/A"
                try:
                    lu_val = student['last_updated'] # Direct access
                    if lu_val:
                         dt_obj = datetime.datetime.fromisoformat(lu_val)
                         timestamp_str = dt_obj.strftime('%Y-%m-%d %H:%M:%S')
                except (ValueError, TypeError, KeyError):
                     timestamp_str = str(student['last_updated'] if student and 'last_updated' in student else 'Hata')

                # Populate cells using direct access and providing defaults
                try:
                    # Assume 'id' exists (PRIMARY KEY)
                    student_id_val = student['id']
                    self.student_table.setItem(row, 0, QTableWidgetItem(str(student_id_val)))
                except (KeyError, IndexError) as e:
                    print(f"ERROR: Missing 'id' in student row {row}: {e} - Data: {student}")
                    self.student_table.setItem(row, 0, QTableWidgetItem("HATA")) # Indicate error

                # Assume 'card_uid' exists (NOT NULL UNIQUE)
                self.student_table.setItem(row, 1, QTableWidgetItem(student['card_uid'] or 'HATA'))
                self.student_table.setItem(row, 2, QTableWidgetItem(student['name'] or '')) # Allow empty name
                self.student_table.setItem(row, 3, QTableWidgetItem(student['surname'] or '')) # Allow empty surname
                self.student_table.setItem(row, 4, QTableWidgetItem(student['photo_path'] or '')) # Allow empty path
                # Use default from schema if key missing (though unlikely for default cols)
                can_exit_val = student['can_exit'] if 'can_exit' in student else 1 # Default 1=Var
                self.student_table.setItem(row, 5, QTableWidgetItem("Var" if can_exit_val == 1 else "Yok"))
                status_val = student['status'] if 'status' in student else 'Outside' # Default 'Outside'
                self.student_table.setItem(row, 6, QTableWidgetItem(status_val))
                self.student_table.setItem(row, 7, QTableWidgetItem(timestamp_str))

            self.student_table.setSortingEnabled(True)
        except Exception as e:
             print(f"ERROR: Failed to refresh student table: {e}")
             traceback.print_exc()
             # self.show_error_message(f"Öğrenci tablosu yenilenirken hata oluştu: {e}")


    def _clear_registration_form(self):
        """Clears the input fields and state for the registration tab."""
        default_uid_text = "- (Giriş/Çıkış sekmesinden bağlanıp kart okutun)"
        self.reg_student_id_input.clear()
        self.reg_student_name_input.clear()
        self.reg_student_surname_input.clear()
        self.reg_card_uid_label.setText(default_uid_text)
        self.reg_card_uid_label.setStyleSheet("font-style: italic; color: gray;")
        self.reg_photo_preview_label.setText("Fotoğraf\nSeçilmedi")
        self.reg_photo_preview_label.setPixmap(QPixmap()) # Clear pixmap
        self.reg_selected_photo_label.clear()
        self.selected_photo_path = None
        self.current_card_uid_for_registration = None
        print("DEBUG: Main: Registration form cleared.")


    # ==========================================================
    # Action Methods / Slots (Implementations from previous response, including completed handle_card_read)
    # ==========================================================

    @pyqtSlot()
    def toggle_serial_connection(self):
        """Handles Connect/Disconnect button clicks."""
        if self.connect_btn.isChecked(): # User wants to connect
            port = self.com_port_combo.currentText()
            if port:
                print(f"DEBUG: Main: Connect button clicked. Connecting to {port} at {ESP_BAUD_RATE}...")
                # Pass the correct baud rate
                self.card_reader.connect(port, baud_rate=ESP_BAUD_RATE)
            else:
                self.show_error_message("Lütfen bağlanmak için geçerli bir port seçin.")
                self.connect_btn.setChecked(False) # Revert button state if no port selected
        else: # User wants to disconnect
            print("DEBUG: Main: Disconnect button clicked.")
            self.card_reader.disconnect()

    @pyqtSlot()
    def _perform_system_check(self):
        """Sends the system check command to the controller."""
        print("DEBUG: Main: System Check button clicked.")
        self.scan_status_label.setText("Durum: Sistem kontrol komutu gönderiliyor...")
        # Call the specific controller method
        self.card_reader.system_check()


    @pyqtSlot(str)
    def handle_card_read(self, uid):
        """
        Handles CLEANED card UIDs received from the controller.
        Updates the UI and performs actions based on the active tab.
        Displays student photo on the scan tab if available.
        """
        print(f"DEBUG: Main: Cleaned UID Received: {uid}")
        current_tab_index = self.tabs.currentIndex()
        current_tab_text = self.tabs.tabText(current_tab_index)
        print(f"DEBUG: Main: Active Tab: '{current_tab_text}' for UID {uid}")

        if "Giriş/Çıkış" in current_tab_text:
            print(f"DEBUG: Main: Processing UID {uid} for Scan Tab")
            self.last_scan_label.setText(f"Son Kart: {uid}") # Update UID label

            try:
                student = self.db_manager.get_student_by_uid(uid)
                if student: # --- Known Student ---
                    student_id = student['id']
                    display_name = f"{student['name'] or ''} {student['surname'] or ''}".strip() or f"ID: {student_id}"
                    current_status = student['status']
                    can_exit = student['can_exit']

                    # --- Load and Display Photo ---
                    photo_rel_path = student['photo_path']
                    photo_abs_path = ""
                    if photo_rel_path:
                        # Construct absolute path assuming relative path starts from BASE_DIR
                        photo_abs_path = os.path.join(BASE_DIR, photo_rel_path)

                    if photo_abs_path and os.path.exists(photo_abs_path):
                        pixmap = QPixmap(photo_abs_path)
                        if not pixmap.isNull():
                            self.scan_photo_display.setPixmap(
                                pixmap.scaled(self.scan_photo_display.size(),
                                              Qt.KeepAspectRatio, Qt.SmoothTransformation)
                            )
                            self.scan_photo_display.setStyleSheet("border: 1px solid green;") # Indicate found
                        else:
                            print(f"WARN: Invalid image file at {photo_abs_path}")
                            self._clear_scan_photo()
                            self.scan_photo_display.setText("Fotoğraf\nHatalı")
                    else:
                        print(f"WARN: Photo path not found or empty: '{photo_abs_path}' (Relative: '{photo_rel_path}')")
                        self._clear_scan_photo()
                        self.scan_photo_display.setText("Fotoğraf\nYok")
                    # -----------------------------

                    # --- Perform Entry/Exit Logic ---
                    action, new_status, log_action, success = "", "", "", False
                    # ... (Mevcut giriş/çıkış mantığı buraya gelecek - DEĞİŞİKLİK YOK) ...
                    if current_status == 'Outside':
                        action, new_status, log_action = "Giriş", 'Inside', "Entry"
                        success = self.db_manager.update_student_status(uid, new_status)
                    elif current_status == 'Inside':
                        action = "Çıkış"
                        if can_exit == 1:
                            new_status, log_action = 'Outside', "Exit"
                            success = self.db_manager.update_student_status(uid, new_status)
                        else: # Denied Exit
                            log_action = "Denied Exit"
                            self.db_manager.add_log(student_id, uid, log_action)
                            self.scan_status_label.setText(f"❌ Çıkış Reddedildi: {display_name} (İzin Yok)")
                            self.show_error_message(f"{display_name} için çıkış izni bulunmuyor.")
                            return # Stop further processing for denied exit
                    else: # Unexpected status
                         print(f"WARN: Invalid status '{current_status}' for student {display_name}")
                         self.scan_status_label.setText(f"❓ Durum Belirsiz: {display_name} ({current_status})")
                         self.db_manager.add_log(student_id, uid, f"Invalid Status Scan ({current_status})")
                         self.refresh_log_table()
                         return # Stop

                    # --- Update UI based on DB operation result ---
                    if success:
                        self.db_manager.add_log(student_id, uid, log_action)
                        self.scan_status_label.setText(f"✅ {action} Başarılı: {display_name} ({new_status})")
                        self.refresh_log_table()
                        self.refresh_student_table()
                    else: # DB update failed
                        self.scan_status_label.setText(f"⚠️ DB Hatası: {display_name} durumu güncellenemedi.")
                        self.db_manager.add_log(student_id, uid, f"{log_action} DB FAILED")
                        self.refresh_log_table()
                        # Fotoğrafı temizlemeye gerek yok, öğrenci hala biliniyor

                else: # --- Unknown Card UID ---
                     self._clear_scan_photo() # Clear photo for unknown card
                     self.scan_status_label.setText(f"❓ Bilinmeyen Kart: {uid}")
                     self.db_manager.add_log(student_id=None, card_uid=uid, action="Unknown Card Scan")
                     self.refresh_log_table()

            except Exception as e:
                 self._clear_scan_photo() # Clear photo on error
                 print(f"ERROR: Error during entry/exit logic for UID {uid}: {e}")
                 traceback.print_exc()
                 self.show_error_message(f"Giriş/çıkış işlemi sırasında hata oluştu: {e}")
                 self.scan_status_label.setText("Durum: İşlem Hatası!")

        elif "Öğrenci Kayıt" in current_tab_text:
            # ... (Öğrenci Kayıt sekmesi mantığı aynı kalacak) ...
            print(f"DEBUG: Main: Processing UID {uid} for Register Tab")
            self.current_card_uid_for_registration = uid
            self.reg_card_uid_label.setText(f"{uid} (Kayıt için seçildi)")
            self.reg_card_uid_label.setStyleSheet("font-weight: bold; color: green;")
            QMessageBox.information(self, "Kart Seçildi", f"Kart UID ({uid}) kayıt için alındı.\nLütfen öğrenci bilgilerini girip kaydedin.")
            self._clear_scan_photo() # Başka sekmedeyken fotoğrafı temizle

        else:
            # ... (Diğer sekmeler için mantık aynı kalacak) ...
            print(f"DEBUG: Main: Card scanned ({uid}) on unhandled tab '{current_tab_text}'. Ignoring.")
            self._clear_scan_photo() # Başka sekmedeyken fotoğrafı temizle


    def _select_photo(self):
        """Opens a file dialog to select a student photo."""
        options = QFileDialog.Options()
        # Use current directory or a specific 'source_photos' directory?
        start_dir = "" # Or specify path
        file_path, _ = QFileDialog.getOpenFileName(self,
                                                   "Öğrenci Fotoğrafı Seç",
                                                   start_dir,
                                                   "Resim Dosyaları (*.png *.jpg *.jpeg *.bmp);;Tüm Dosyalar (*)",
                                                   options=options)
        if file_path:
            # Check file size? (Optional)
            # try:
            #     if os.path.getsize(file_path) > MAX_PHOTO_SIZE:
            #         self.show_error_message("Fotoğraf boyutu çok büyük.")
            #         return
            # except OSError: pass # Ignore size check error

            self.selected_photo_path = file_path # Store the full source path
            base_name = os.path.basename(file_path)
            self.reg_selected_photo_label.setText(f"Seçilen: ...{base_name if len(base_name) < 30 else base_name[:12]+'...'+base_name[-12:]}")

            # Show preview
            pixmap = QPixmap(file_path)
            if not pixmap.isNull():
                self.reg_photo_preview_label.setPixmap(
                    pixmap.scaled(self.reg_photo_preview_label.size(),
                                  Qt.KeepAspectRatio, Qt.SmoothTransformation)
                )
            else: # Invalid image file selected
                self.reg_photo_preview_label.setText("Önizleme\nYok")
                self.reg_selected_photo_label.clear()
                self.selected_photo_path = None # Invalidate selection
                QMessageBox.warning(self,"Geçersiz Resim", "Seçilen dosya geçerli bir resim dosyası olarak yüklenemedi.")


    def _save_student(self):
        """Validates input and saves the new student to the database."""
        print("DEBUG: Main: Save student requested.")
        # --- Get Inputs ---
        student_id_str = self.reg_student_id_input.text().strip()
        name = self.reg_student_name_input.text().strip()
        surname = self.reg_student_surname_input.text().strip()
        card_uid = self.current_card_uid_for_registration # Should be cleaned UID
        photo_source_path = self.selected_photo_path # Full path from dialog

        # --- Input Validation ---
        if not student_id_str.isdigit():
            QMessageBox.warning(self, "Eksik/Hatalı Bilgi", "Lütfen geçerli bir sayısal öğrenci numarası girin.")
            return
        student_id = int(student_id_str)

        if not name or not surname:
             QMessageBox.warning(self, "Eksik Bilgi", "Lütfen öğrencinin adını ve soyadını eksiksiz girin.")
             return

        if not card_uid: # Check if a card was scanned for registration
            QMessageBox.warning(self, "Eksik Bilgi", "Lütfen 'Okunan Kart UID' alanına bir kart okutarak geçerli bir UID seçin.")
            return

        if not photo_source_path or not os.path.exists(photo_source_path):
            QMessageBox.warning(self, "Eksik Bilgi", "Lütfen geçerli bir öğrenci fotoğrafı seçin.")
            return

        # --- Prepare Photo Destination ---
        # Store relative path in DB for portability
        try:
            _, ext = os.path.splitext(photo_source_path)
            if not ext: ext = ".jpg" # Default extension if none found
            # Ensure filename is safe (though student_id is integer)
            safe_filename = f"{student_id}{ext.lower()}"
            # Relative path from BASE_DIR to PHOTOS_DIR_ABS content
            relative_photo_path = os.path.join(os.path.basename(PHOTOS_DIR_ABS), safe_filename)
            # Absolute destination path for copying
            absolute_dest_path = os.path.join(PHOTOS_DIR_ABS, safe_filename)
            print(f"DEBUG: Main: Photo destination (abs): {absolute_dest_path}")
            print(f"DEBUG: Main: Photo path for DB (rel): {relative_photo_path}")
        except Exception as e:
             print(f"ERROR: Failed to prepare photo path: {e}")
             self.show_error_message(f"Fotoğraf yolu hazırlanırken hata: {e}")
             return


        # --- Copy Photo ---
        try:
            # Ensure destination directory exists (should be handled at start, but double-check)
            os.makedirs(os.path.dirname(absolute_dest_path), exist_ok=True)
            shutil.copy(photo_source_path, absolute_dest_path)
            print(f"DEBUG: Main: Photo copied: {photo_source_path} -> {absolute_dest_path}")
        except Exception as e:
            QMessageBox.critical(self, "Dosya Hatası", f"Fotoğraf kopyalanamadı: {e}\nKaynak: {photo_source_path}\nHedef: {absolute_dest_path}")
            print(f"ERROR: Photo copy failed: {e}")
            traceback.print_exc()
            return # Stop if photo cannot be copied

        # --- Save to Database ---
        # Pass the *relative* path to the DB manager
        success, message = self.db_manager.add_student(student_id, card_uid, name, surname, relative_photo_path)

        if success:
            QMessageBox.information(self, "Kayıt Başarılı", message)
            self._clear_registration_form() # Clear form on success
            # Refresh tables to show new student
            self.refresh_student_table()
            self.refresh_log_table() # Show registration log
        else:
            QMessageBox.warning(self, "Kayıt Hatası", f"Öğrenci kaydedilemedi:\n{message}")
            # --- Optional: Clean up copied photo if DB insert failed ---
            # It might be better to leave the photo for manual check, or try to delete
            # if os.path.exists(absolute_dest_path):
            #    try:
            #        os.remove(absolute_dest_path)
            #        print(f"DEBUG: Main: Removed photo {absolute_dest_path} after failed DB insert.")
            #    except OSError as del_err:
            #        print(f"WARN: Could not remove photo {absolute_dest_path} after failed DB insert: {del_err}")


    @pyqtSlot(QModelIndex)
    def _show_student_details(self, index):
        """Shows the StudentDetailDialog for the double-clicked student row."""
        if not index.isValid(): return
        row = index.row()
        try:
            student_id_item = self.student_table.item(row, 0)
            if not student_id_item: return
            student_id = int(student_id_item.text())

            # --- Reconstruct data using direct index access from table ---
            student_data = {}
            headers_map = { # Map column index to key name
                0: "id", 1: "card_uid", 2: "name", 3: "surname",
                4: "photo_path", 5: "can_exit_str", 6: "status", 7: "last_updated"
            }
            num_cols = self.student_table.columnCount() # Get actual column count
            for col in range(num_cols):
                 header_key = headers_map.get(col) # Get key name for this column index
                 if header_key: # Only process if we have a mapped key
                     table_item = self.student_table.item(row, col)
                     student_data[header_key] = table_item.text() if table_item else None
                 else:
                     print(f"WARN: No key mapping for column index {col} in _show_student_details")


            # --- Convert specific fields ---
            # Use .get() safely on the DICTIONARY now
            student_data['can_exit'] = 1 if student_data.get('can_exit_str') == "Var" else 0
            student_data['id'] = student_id # Use the ID we already got safely

            dialog = StudentDetailDialog(student_data, self)
            dialog.exec_()

        except (ValueError, TypeError, IndexError, Exception) as e:
             print(f"ERROR: Failed to show student details for row {row}: {e}")
             traceback.print_exc()
             self.show_error_message(f"Öğrenci detayları gösterilirken bir hata oluştu: {e}")



    @pyqtSlot()
    def _delete_selected_student(self):
        """Deletes the student selected in the student table after confirmation."""
        selected_rows = self.student_table.selectionModel().selectedRows()
        if not selected_rows:
            QMessageBox.warning(self, "Seçim Yapılmadı", "Lütfen silmek istediğiniz öğrenciyi tablodan seçin.")
            return

        try:
            selected_row = selected_rows[0].row()
            student_id_item = self.student_table.item(selected_row, 0) # ID sütunu (index 0)

            # ID hücresinin varlığını ve içeriğinin sayısal olup olmadığını kontrol et
            if not student_id_item:
                 QMessageBox.critical(self, "Hata", "Seçili satırdan öğrenci numarası alınamadı.")
                 return

            student_id_text = student_id_item.text()
            if not student_id_text or not student_id_text.isdigit():
                QMessageBox.critical(self, "Geçersiz Satır",
                                     f"Seçili satır geçerli bir öğrenci numarası ('{student_id_text}') içermiyor.\n"
                                     "Lütfen tabloyu yenileyip tekrar deneyin.")
                return

            # Güvenle integer'a çevir
            student_id = int(student_id_text)

            # Kalan bilgileri al (hata olasılığı daha düşük)
            student_name_item = self.student_table.item(selected_row, 2)
            student_surname_item = self.student_table.item(selected_row, 3)
            name = student_name_item.text() if student_name_item else ""
            surname = student_surname_item.text() if student_surname_item else ""
            full_name = f"{name} {surname}".strip()
            display_name = full_name if full_name else f"ID: {student_id}"

            # Onay dialog
            reply = QMessageBox.question(self, "Öğrenci Silme Onayı",
                                         f"'{display_name}' adlı öğrenciyi silmek istediğinizden emin misiniz?\n"
                                         f"Bu işlem geri alınamaz ve öğrencinin fotoğrafı da silinecektir.",
                                         QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

            if reply == QMessageBox.Yes:
                print(f"DEBUG: Main: Attempting to delete student ID: {student_id}")
                success, message = self.db_manager.delete_student(student_id)
                if success:
                    QMessageBox.information(self, "Silme Başarılı", message)
                    self.refresh_student_table()
                    self.refresh_log_table()
                else:
                    QMessageBox.warning(self, "Silme Hatası", f"Öğrenci silinemedi:\n{message}")
        except (ValueError, TypeError, Exception) as e: # Yakalanabilecek diğer hatalar
            print(f"ERROR: Error during student deletion process: {e}")
            traceback.print_exc()
            self.show_error_message(f"Öğrenci silinirken bir hata oluştu: {e}")


    def _export_logs(self):
        """Placeholder for exporting log data to Excel."""
        # TODO: Implement using pandas or openpyxl
        QMessageBox.information(self, "Yapılacaklar", "Excel'e aktarma özelliği henüz eklenmemiştir.")


    def closeEvent(self, event):
        """Ensure serial connection is closed when the window closes."""
        print("DEBUG: Main: Close event triggered.")
        # Request cleanup from controller (which includes disconnect)
        self.card_reader.cleanup()
        # Accept the event to close the window
        event.accept()


# ==========================================================
# Main Execution Block
# ==========================================================
if __name__ == '__main__':
    # Enable high DPI scaling for better visuals if supported
    # QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True) # Before QApplication
    # QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)   # Before QApplication

    app = QApplication(sys.argv)

    # Optional: Apply a style (Fusion looks good on most platforms)
    # app.setStyle('Fusion')

    # --- Critical Error Handling during Init ---
    # If backend components failed in MainWindow.__init__, sys.exit might have been called.
    # We wrap the MainWindow creation in a try block just in case.
    try:
        win = MainWindow()
        win.show()
    except Exception as init_err:
         print(f"FATAL: Unhandled exception during MainWindow initialization: {init_err}")
         traceback.print_exc()
         QMessageBox.critical(None, "Kritik Hata", f"Uygulama başlatılırken kritik bir hata oluştu:\n{init_err}")
         sys.exit(1) # Exit if window creation fails

    sys.exit(app.exec_())