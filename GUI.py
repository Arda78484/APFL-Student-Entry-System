# -*- coding: utf-8 -*-
"""
Ankara Pursaklar Fen Lisesi - Okul Giriş Çıkış Kart Sistemi
PySide6 tek dosya uygulama

Gereksinimler:
  pip install PySide6 pandas openpyxl
Klasörler:
  data/students.db     (otomatik)
  photos/<NUMARA>.jpg  (fotoğraflar)
  logos/images.png     (okul logosu)
"""

import os, sys, sqlite3
from datetime import datetime, time

from PySide6.QtCore import Qt, QTimer, QDate, QEvent, QSortFilterProxyModel
from PySide6.QtGui import QPixmap, QStandardItemModel, QStandardItem, QTransform
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel, QPushButton, QHBoxLayout, QVBoxLayout,
    QSplitter, QListWidget, QListWidgetItem, QLineEdit, QMessageBox, QDialog, QFormLayout,
    QComboBox, QFileDialog, QTableView, QToolButton, QStyle, QHeaderView, QDateEdit,
    QTimeEdit, QCheckBox, QGridLayout, QTabWidget, QInputDialog
)

# pandas (opsiyonel)
try:
    import pandas as pd
except Exception:
    pd = None

# PIL/Pillow for EXIF handling
try:
    from PIL import Image, ExifTags
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

APP_TITLE = "Ankara Pursaklar Fen Lisesi - Okul Giriş Çıkış Kart Sistemi"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
PHOTOS_DIR = os.path.join(BASE_DIR, "photos")
LOGO_PATH = os.path.join(BASE_DIR, "logos", "images.png")
DB_PATH = os.path.join(DATA_DIR, "students.db")

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(PHOTOS_DIR, exist_ok=True)

# ===================== Veritabanı =====================
class Database:
    def __init__(self, path: str):
        self.path = path
        self._ensure()

    def _ensure(self):
        with sqlite3.connect(self.path) as con:
            cur = con.cursor()
            # students
            cur.execute("""
                CREATE TABLE IF NOT EXISTS students (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    number TEXT UNIQUE NOT NULL,
                    first_name TEXT NOT NULL,
                    last_name TEXT NOT NULL,
                    class TEXT NOT NULL,
                    card_id TEXT UNIQUE,
                    penalized INTEGER DEFAULT 0,
                    student_type TEXT DEFAULT 'Evci',   -- 'Evci' veya 'Yurtçu'
                    is_personnel INTEGER DEFAULT 0     -- 0=öğrenci, 1=personel
                )
            """)
            # logs
            cur.execute("""
                CREATE TABLE IF NOT EXISTS logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_number TEXT NOT NULL,
                    action TEXT NOT NULL, -- 'Giriş', 'Çıkış', 'Yasak'
                    ts TEXT NOT NULL
                )
            """)
            # migration: ensure columns exist
            cur.execute("PRAGMA table_info(students)")
            cols = {r[1]: r for r in cur.fetchall()}
            if "penalized" not in cols:
                cur.execute("ALTER TABLE students ADD COLUMN penalized INTEGER DEFAULT 0")
            if "student_type" not in cols:
                cur.execute("ALTER TABLE students ADD COLUMN student_type TEXT DEFAULT 'Evci'")
            if "is_personnel" not in cols:
                cur.execute("ALTER TABLE students ADD COLUMN is_personnel INTEGER DEFAULT 0")
            # if card_id accidentally NOT NULL, make it NULLable (copy table)
            notnull = cols.get("card_id", (None,)*6)[3] if cols else 0
            if notnull == 1:
                cur.executescript("""
                    BEGIN TRANSACTION;
                    CREATE TABLE students_new (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        number TEXT UNIQUE NOT NULL,
                        first_name TEXT NOT NULL,
                        last_name TEXT NOT NULL,
                        class TEXT NOT NULL,
                        card_id TEXT UNIQUE,
                        penalized INTEGER DEFAULT 0,
                        student_type TEXT DEFAULT 'Evci'
                    );
                    INSERT INTO students_new(id, number, first_name, last_name, class, card_id, penalized, student_type)
                        SELECT id, number, first_name, last_name, class, NULLIF(card_id,''), COALESCE(penalized,0), COALESCE(student_type,'Evci')
                        FROM students;
                    DROP TABLE students;
                    ALTER TABLE students_new RENAME TO students;
                    COMMIT;
                """)

            # market_hours (profil bazlı)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS market_hours (
                    profile TEXT,     -- 'Evci'/'Yurtçu'
                    day INTEGER,      -- 0=Mon .. 6=Sun
                    start_time TEXT,  -- 'HH:MM' (NULL => tamamen yasak)
                    end_time   TEXT,
                    PRIMARY KEY(profile, day)
                )
            """)
            # Seed if empty
            cur.execute("SELECT COUNT(*) FROM market_hours")
            if cur.fetchone()[0] < 14:
                cur.execute("DELETE FROM market_hours")
                for prof in ("Evci","Yurtçu"):
                    for d in range(7):
                        cur.execute("INSERT OR REPLACE INTO market_hours(profile, day, start_time, end_time) VALUES(?,?,?,?)",
                                    (prof, d, None, None))
            con.commit()

    # ---- Öğrenciler ----
    def add_student(self, number, first_name, last_name, klass, card_id=None, penalized=0, student_type='Evci', is_personnel=0):
        with sqlite3.connect(self.path) as con:
            con.execute(
                "INSERT INTO students(number, first_name, last_name, class, card_id, penalized, student_type, is_personnel) VALUES(?,?,?,?,?,?,?,?)",
                (number, first_name, last_name, klass, card_id if card_id else None, int(penalized), student_type, int(is_personnel)),
            )
            con.commit()

    def bulk_add_students(self, rows):
        # rows: (number, first, last, class, card_id_or_None, penalized, student_type, is_personnel)
        with sqlite3.connect(self.path) as con:
            con.executemany(
                "INSERT OR REPLACE INTO students(number, first_name, last_name, class, card_id, penalized, student_type, is_personnel) VALUES(?,?,?,?,?,?,?,?)",
                rows,
            )
            con.commit()

    def all_students(self):
        with sqlite3.connect(self.path) as con:
            cur = con.cursor()
            cur.execute("""
                SELECT number, first_name, last_name, class, card_id, COALESCE(penalized,0),
                       COALESCE(student_type,'Evci'), COALESCE(is_personnel,0)
                FROM students ORDER BY number
            """)
            return cur.fetchall()

    def update_student_field(self, number, field, value):
        assert field in ("number","first_name","last_name","class","card_id","penalized","student_type","is_personnel")
        with sqlite3.connect(self.path) as con:
            cur = con.cursor()
            if field in ("penalized", "is_personnel"):
                cur.execute(f"UPDATE students SET {field}=? WHERE number=?", (int(value), number))
            elif field == "card_id":
                cur.execute("UPDATE students SET card_id=? WHERE number=?", (value if value else None, number))
            else:
                cur.execute(f"UPDATE students SET {field}=? WHERE number=?", (value, number))
            con.commit()

    def find_student_by_card(self, card_id):
        with sqlite3.connect(self.path) as con:
            cur = con.cursor()
            cur.execute("""
                SELECT number, first_name, last_name, COALESCE(penalized,0), COALESCE(student_type,'Evci'), COALESCE(is_personnel,0)
                FROM students WHERE card_id=?
            """, (card_id,))
            return cur.fetchone()

    def get_penalized(self, number):
        with sqlite3.connect(self.path) as con:
            cur = con.cursor()
            cur.execute("SELECT COALESCE(penalized,0) FROM students WHERE number=?", (number,))
            r = cur.fetchone()
            return int(r[0]) if r else 0

    # ---- Loglar ----
    def add_log(self, student_number, action):
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with sqlite3.connect(self.path) as con:
            con.execute("INSERT INTO logs(student_number, action, ts) VALUES(?,?,?)", (student_number, action, ts))
            con.commit()
        return ts

    def last_action_for_student(self, student_number, include_blocked=False):
        """Öğrencinin son işlemi. include_blocked=False -> 'Yasak' yok sayılır."""
        with sqlite3.connect(self.path) as con:
            cur = con.cursor()
            if include_blocked:
                cur.execute("SELECT action FROM logs WHERE student_number=? ORDER BY ts DESC LIMIT 1", (student_number,))
            else:
                cur.execute("""SELECT action FROM logs
                               WHERE student_number=? AND action IN ('Giriş','Çıkış')
                               ORDER BY ts DESC LIMIT 1""", (student_number,))
            row = cur.fetchone()
            return row[0] if row else None

    def last_n_logs(self, action, n=10):
        with sqlite3.connect(self.path) as con:
            cur = con.cursor()
            cur.execute("SELECT student_number, action, ts FROM logs WHERE action=? ORDER BY ts DESC LIMIT ?", (action, n))
            return cur.fetchall()

    def all_logs(self):
        with sqlite3.connect(self.path) as con:
            cur = con.cursor()
            cur.execute("SELECT student_number, action, ts FROM logs ORDER BY ts DESC")
            return cur.fetchall()

    def logs_on_date(self, date_str):
        with sqlite3.connect(self.path) as con:
            cur = con.cursor()
            cur.execute("SELECT student_number, action, ts FROM logs WHERE substr(ts,1,10)=? ORDER BY ts ASC", (date_str,))
            return cur.fetchall()

    # ---- Personel fonksiyonları ----
    def all_personnel(self):
        with sqlite3.connect(self.path) as con:
            cur = con.cursor()
            cur.execute("""
                SELECT number, first_name, last_name, class, card_id, COALESCE(penalized,0),
                       COALESCE(student_type,'Evci'), COALESCE(is_personnel,0)
                FROM students WHERE is_personnel=1 ORDER BY number
            """)
            return cur.fetchall()

    def personnel_logs(self):
        with sqlite3.connect(self.path) as con:
            cur = con.cursor()
            cur.execute("""
                SELECT l.student_number, l.action, l.ts 
                FROM logs l 
                JOIN students s ON s.number = l.student_number 
                WHERE s.is_personnel = 1 
                ORDER BY l.ts DESC
            """)
            return cur.fetchall()

    def last_n_student_logs(self, action, n=10):
        """Sadece öğrenci logları (personel hariç)"""
        with sqlite3.connect(self.path) as con:
            cur = con.cursor()
            cur.execute("""
                SELECT l.student_number, l.action, l.ts 
                FROM logs l 
                JOIN students s ON s.number = l.student_number 
                WHERE l.action=? AND s.is_personnel = 0 
                ORDER BY l.ts DESC LIMIT ?
            """, (action, n))
            return cur.fetchall()

    # ---- Market hours (profil bazlı) ----
    def get_day_interval(self, profile, weekday):  # 0=Mon..6=Sun
        with sqlite3.connect(self.path) as con:
            cur = con.cursor()
            cur.execute("SELECT start_time, end_time FROM market_hours WHERE profile=? AND day=?", (profile, weekday))
            row = cur.fetchone()
            return row if row else (None, None)

    def set_day_interval(self, profile, weekday, start_str_or_none, end_str_or_none):
        with sqlite3.connect(self.path) as con:
            con.execute("INSERT OR REPLACE INTO market_hours(profile, day, start_time, end_time) VALUES(?,?,?,?)",
                        (profile, weekday, start_str_or_none, end_str_or_none))
            con.commit()

# ===================== Görsel Öğeler =====================
class PersonItem(QWidget):
    def __init__(self, number, name_surname, timestamp, large=False, highlight_red=False):
        super().__init__()
        h = QHBoxLayout(self); h.setContentsMargins(12,12,12,12)
        pic_size = 160 if large else 64
        name_style = "font-weight:800;font-size:28px;" if large else "font-weight:600;font-size:18px;"
        ts_style = "color:gray;font-size:18px;" if large else "color:gray;font-size:14px;"
        border = "border:3px solid red;border-radius:8px;" if highlight_red and large else "border:none;"
        self.setStyleSheet(border)

        pic = QLabel(); pic.setFixedSize(pic_size, pic_size)
        pm = self._load_image_with_rotation(os.path.join(PHOTOS_DIR, f"{number}.jpg"), pic_size)
        pic.setPixmap(pm)

        v = QVBoxLayout()
        name = QLabel(name_surname); name.setStyleSheet(name_style)
        ts = QLabel(timestamp); ts.setStyleSheet(ts_style)
        v.addWidget(name); v.addWidget(ts)

        h.addWidget(pic); h.addLayout(v)

    def _load_image_with_rotation(self, image_path, size):
        """Load image and apply rotation for common orientations"""
        if not os.path.exists(image_path):
            pm = QPixmap(size, size)
            pm.fill(Qt.lightGray)
            return pm

        pm = QPixmap(image_path)
        if pm.isNull():
            pm = QPixmap(size, size)
            pm.fill(Qt.lightGray)
            return pm

        # Check if image needs rotation (simple heuristic for 3000x4000 images)
        if pm.width() > pm.height() and pm.width() >= 3000:
            # Likely a rotated portrait image, rotate 90 degrees clockwise
            transform = QTransform()
            transform.rotate(90)
            pm = pm.transformed(transform)

        pm = pm.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        return pm

# ===================== Öğrenci Ekle =====================
class AddStudentDialog(QDialog):
    def __init__(self, db: Database, parent=None):
        super().__init__(parent)
        self.db = db
        self.setWindowTitle("Öğrenci Ekle")
        form = QFormLayout(self)

        self.le_number = QLineEdit()
        self.le_first  = QLineEdit()
        self.le_last   = QLineEdit()
        self.cb_class  = QComboBox()
        classes = [f"{g}/{s}" for g in ("9","10","11","12") for s in ("A","B","C","D","E")]
        self.cb_class.addItems(classes)
        self.cb_type   = QComboBox(); self.cb_type.addItems(["Evci","Yurtçu"])
        self.le_card   = QLineEdit()  # opsiyonel

        form.addRow("Numarası (Unique)", self.le_number)
        form.addRow("Adı", self.le_first)
        form.addRow("Soyadı", self.le_last)
        form.addRow("Sınıfı", self.cb_class)
        form.addRow("Tipi", self.cb_type)     # Evci/Yurtçu
        form.addRow("Kart ID (opsiyonel)", self.le_card)

        # RFID Enter'ı yut
        self.le_card.installEventFilter(self); self.le_card.setFocus()

        box = QHBoxLayout()
        btn_cancel = QPushButton("Vazgeç"); btn_ok = QPushButton("Kaydet")
        for b in (btn_ok, btn_cancel): b.setAutoDefault(False); b.setDefault(False)
        btn_cancel.clicked.connect(self.reject); btn_ok.clicked.connect(self.save)
        box.addStretch(1); box.addWidget(btn_cancel); box.addWidget(btn_ok)
        form.addRow(box)

    def eventFilter(self, obj, event):
        if obj is self.le_card and event.type() == QEvent.KeyPress:
            if event.key() in (Qt.Key_Return, Qt.Key_Enter): return True
        return super().eventFilter(obj, event)

    def save(self):
        try:
            number = self.le_number.text().strip()
            first  = self.le_first.text().strip()
            last   = self.le_last.text().strip()
            klass  = self.cb_class.currentText()
            stype  = self.cb_type.currentText()
            card   = self.le_card.text().strip()
            if not all([number, first, last, klass, stype]):
                QMessageBox.warning(self, "Eksik", "Numara, Ad, Soyad, Sınıf, Tip zorunlu.")
                return
            self.db.add_student(number, first, last, klass, card if card else None, 0, stype)
            QMessageBox.information(self, "Tamam", "Öğrenci eklendi.")
            self.accept()
        except sqlite3.IntegrityError as e:
            QMessageBox.critical(self, "Hata", f"Benzersiz alan çakışması: {e}")
        except Exception as e:
            QMessageBox.critical(self, "Hata", str(e))

# ===================== Personel Ekle =====================
class AddPersonnelDialog(QDialog):
    def __init__(self, db: Database, parent=None):
        super().__init__(parent)
        self.db = db
        self.setWindowTitle("Personel Ekle")
        form = QFormLayout(self)

        self.le_number = QLineEdit()
        self.le_first  = QLineEdit()
        self.le_last   = QLineEdit()
        self.le_position = QLineEdit()  # Pozisyon/Bölüm
        self.le_card   = QLineEdit()    # opsiyonel

        form.addRow("Numarası (Benzersiz)", self.le_number)
        form.addRow("Adı", self.le_first)
        form.addRow("Soyadı", self.le_last)
        form.addRow("Pozisyon/Bölüm", self.le_position)
        form.addRow("Kart ID", self.le_card)

        # RFID Enter'ı yut
        self.le_card.installEventFilter(self); self.le_card.setFocus()

        box = QHBoxLayout()
        btn_cancel = QPushButton("Vazgeç"); btn_ok = QPushButton("Kaydet")
        for b in (btn_ok, btn_cancel): b.setAutoDefault(False); b.setDefault(False)
        btn_cancel.clicked.connect(self.reject); btn_ok.clicked.connect(self.save)
        box.addStretch(1); box.addWidget(btn_cancel); box.addWidget(btn_ok)
        form.addRow(box)

    def eventFilter(self, obj, event):
        if obj is self.le_card and event.type() == QEvent.KeyPress:
            if event.key() in (Qt.Key_Return, Qt.Key_Enter): return True
        return super().eventFilter(obj, event)

    def save(self):
        try:
            number = self.le_number.text().strip()
            first  = self.le_first.text().strip()
            last   = self.le_last.text().strip()
            position = self.le_position.text().strip()
            card   = self.le_card.text().strip()
            if not all([number, first, last, position, card]):
                QMessageBox.warning(self, "Eksik", "Numara, Ad, Soyad, Pozisyon ve Kart ID zorunlu.")
                return
            self.db.add_student(number, first, last, position, card if card else None, 0, "Evci", 1)  # is_personnel=1
            QMessageBox.information(self, "Tamam", "Personel eklendi.")
            self.accept()
        except sqlite3.IntegrityError as e:
            QMessageBox.critical(self, "Hata", f"Benzersiz alan çakışması: {e}")
        except Exception as e:
            QMessageBox.critical(self, "Hata", str(e))

# ===================== Öğrenci Menüsü =====================
class StudentsModel(QStandardItemModel):
    HEADERS = ["Numara","Ad","Soyad","Sınıf","Kart ID","Cezalı","Tip"]
    def __init__(self, db: Database):
        super().__init__()
        self.db = db
        self.setColumnCount(len(self.HEADERS))
        self.setHorizontalHeaderLabels(self.HEADERS)
        self._load()

    def _load(self):
        self.setRowCount(0)
        for number, first, last, klass, card, penalized, stype, is_personnel in self.db.all_students():
            # Sadece öğrencileri göster (personel değil)
            if is_personnel:
                continue
            row = [
                QStandardItem(str(number)),
                QStandardItem(first),
                QStandardItem(last),
                QStandardItem(klass),
                QStandardItem("" if card is None else str(card)),
                QStandardItem(""),
                QStandardItem(stype or "Evci"),
            ]
            for i, it in enumerate(row):
                it.setEditable(True if i != 5 else False)
            # checkbox (Cezalı)
            chk = row[5]; chk.setCheckable(True)
            chk.setCheckState(Qt.Checked if int(penalized) else Qt.Unchecked)
            self.appendRow(row)

    def flags(self, index):
        fl = super().flags(index)
        if index.column()==5:
            return fl | Qt.ItemIsUserCheckable | Qt.ItemIsEnabled | Qt.ItemIsSelectable
        return fl | Qt.ItemIsEditable

class StudentMenuDialog(QDialog):
    def __init__(self, db: Database, parent=None):
        super().__init__(parent)
        self.db = db
        self.setWindowTitle("Öğrenci Menüsü")
        self.resize(900, 560)

        v = QVBoxLayout(self)

        # Üst: arama + butonlar
        top = QHBoxLayout()
        self.search = QLineEdit(); self.search.setPlaceholderText("Öğrenci No ile ara…")
        top.addWidget(self.search); top.addStretch(1)
        self.btn_add  = QToolButton(); self.btn_add.setText("Öğrenci Ekle")
        self.btn_bulk = QToolButton(); self.btn_bulk.setText("Çoklu Öğrenci Ekle (Excel)")
        self.btn_add.setIcon(self.style().standardIcon(QStyle.SP_DialogYesButton))
        self.btn_bulk.setIcon(self.style().standardIcon(QStyle.SP_DialogOpenButton))
        self.btn_add.clicked.connect(self.open_add); self.btn_bulk.clicked.connect(self.bulk_import)
        top.addWidget(self.btn_add); top.addWidget(self.btn_bulk)

        # Tablo
        self.model = StudentsModel(self.db)
        self.proxy = QSortFilterProxyModel(self); self.proxy.setSourceModel(self.model)
        self.proxy.setFilterKeyColumn(0); self.proxy.setFilterCaseSensitivity(Qt.CaseInsensitive)

        self.table = QTableView(); self.table.setModel(self.proxy)
        self.table.setSortingEnabled(True)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        v.addLayout(top); v.addWidget(self.table)

        self.search.textChanged.connect(self.proxy.setFilterFixedString)
        self.model.itemChanged.connect(self._cell_changed)

    def _cell_changed(self, item: QStandardItem):
        try:
            row = item.row()
            number = self.model.item(row, 0).text().strip()
            col = item.column()
            if col == 5:
                self.db.update_student_field(number, "penalized", 1 if item.checkState()==Qt.Checked else 0)
            elif col == 0:
                self.db.update_student_field(number, "number", item.text().strip())
            elif col == 1:
                self.db.update_student_field(number, "first_name", item.text().strip())
            elif col == 2:
                self.db.update_student_field(number, "last_name", item.text().strip())
            elif col == 3:
                self.db.update_student_field(number, "class", item.text().strip())
            elif col == 4:
                self.db.update_student_field(number, "card_id", item.text().strip())
            elif col == 6:
                val = item.text().strip()
                if val not in ("Evci","Yurtçu"):
                    QMessageBox.warning(self, "Uyarı", "Tip sadece 'Evci' veya 'Yurtçu' olabilir.")
                    self.model._load(); return
                self.db.update_student_field(number, "student_type", val)
        except sqlite3.IntegrityError as e:
            QMessageBox.critical(self, "Hata", f"Kayıt güncellenemedi: {e}")
            self.model._load()
        except Exception as e:
            QMessageBox.critical(self, "Hata", str(e))
            self.model._load()

    def open_add(self):
        dlg = AddStudentDialog(self.db, self)
        if dlg.exec(): self.model._load()

    def bulk_import(self):
        if pd is None:
            QMessageBox.critical(self, "Pandas Yok", "Excel içe aktarma için pandas/openpyxl kurulmalı.")
            return
        path, _ = QFileDialog.getOpenFileName(self, "Excel Dosyası Seç", os.path.expanduser("~"), "Excel (*.xlsx)")
        if not path: return
        try:
            df = pd.read_excel(path)
            required = ["Ad","Soyad","Numara","Sınıf"]
            for col in required:
                if col not in df.columns:
                    QMessageBox.warning(self,"Kolon Hatası", f"Gerekli kolon eksik: {col}")
                    return
            rows=[]
            for _, r in df.iterrows():
                num = str(r["Numara"]).strip()
                first = str(r["Ad"]).strip()
                last = str(r["Soyad"]).strip()
                klass = str(r["Sınıf"]).strip()
                card = str(r["KartID"]).strip() if "KartID" in df.columns and not pd.isna(r["KartID"]) else None
                penal = r["Cezalı"] if "Cezalı" in df.columns else 0
                penal = 1 if str(penal).strip().lower() in ("1","true","evet","yes","✓","x") else 0
                stype = str(r["Tip"]).strip() if "Tip" in df.columns and not pd.isna(r["Tip"]) else "Evci"
                if stype not in ("Evci","Yurtçu"): stype = "Evci"
                rows.append((num, first, last, klass, card, penal, stype, 0))
            self.db.bulk_add_students(rows)
            QMessageBox.information(self, "Tamam", f"{len(rows)} öğrenci içe aktarıldı.")
            self.model._load()
        except Exception as e:
            QMessageBox.critical(self, "Hata", str(e))

# ===================== Personel Menüsü =====================
class PersonnelModel(QStandardItemModel):
    HEADERS = ["Numara","Ad","Soyad","Pozisyon","Kart ID"]
    def __init__(self, db: Database):
        super().__init__()
        self.db = db
        self.setColumnCount(len(self.HEADERS))
        self.setHorizontalHeaderLabels(self.HEADERS)
        self._load()

    def _load(self):
        self.setRowCount(0)
        for number, first, last, position, card, penalized, stype, is_personnel in self.db.all_personnel():
            row = [
                QStandardItem(str(number)),
                QStandardItem(first),
                QStandardItem(last),
                QStandardItem(position),
                QStandardItem("" if card is None else str(card)),
            ]
            for it in row:
                it.setEditable(True)
            self.appendRow(row)

class PersonnelMenuDialog(QDialog):
    def __init__(self, db: Database, parent=None):
        super().__init__(parent)
        self.db = db
        self.setWindowTitle("Personel Menüsü")
        self.resize(900, 560)

        v = QVBoxLayout(self)

        # Üst: arama + butonlar
        top = QHBoxLayout()
        self.search = QLineEdit(); self.search.setPlaceholderText("Personel No ile ara…")
        top.addWidget(self.search); top.addStretch(1)
        self.btn_add = QToolButton(); self.btn_add.setText("Personel Ekle")
        self.btn_export = QToolButton(); self.btn_export.setText("Personel Logları Excel İndir")
        self.btn_add.setIcon(self.style().standardIcon(QStyle.SP_DialogYesButton))
        self.btn_export.setIcon(self.style().standardIcon(QStyle.SP_DialogSaveButton))
        self.btn_add.clicked.connect(self.open_add)
        self.btn_export.clicked.connect(self.export_personnel_logs)
        top.addWidget(self.btn_add); top.addWidget(self.btn_export)

        # Personel tablosu
        self.model = PersonnelModel(self.db)
        self.proxy = QSortFilterProxyModel(self); self.proxy.setSourceModel(self.model)
        self.proxy.setFilterKeyColumn(0); self.proxy.setFilterCaseSensitivity(Qt.CaseInsensitive)

        self.table = QTableView(); self.table.setModel(self.proxy)
        self.table.setSortingEnabled(True)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        # Personel logları
        log_layout = QVBoxLayout()
        log_layout.addWidget(QLabel("Personel Giriş-Çıkış Logları"))
        self.log_table = QTableView()
        self.log_table.setSortingEnabled(True)
        self.refresh_logs()
        
        v.addLayout(top)
        v.addWidget(self.table)
        v.addLayout(log_layout)
        v.addWidget(self.log_table)

        self.search.textChanged.connect(self.proxy.setFilterFixedString)
        self.model.itemChanged.connect(self._cell_changed)

    def _cell_changed(self, item: QStandardItem):
        try:
            row = item.row()
            number = self.model.item(row, 0).text().strip()
            col = item.column()
            if col == 0:
                self.db.update_student_field(number, "number", item.text().strip())
            elif col == 1:
                self.db.update_student_field(number, "first_name", item.text().strip())
            elif col == 2:
                self.db.update_student_field(number, "last_name", item.text().strip())
            elif col == 3:
                self.db.update_student_field(number, "class", item.text().strip())
            elif col == 4:
                self.db.update_student_field(number, "card_id", item.text().strip())
        except sqlite3.IntegrityError as e:
            QMessageBox.critical(self, "Hata", f"Kayıt güncellenemedi: {e}")
            self.model._load()
        except Exception as e:
            QMessageBox.critical(self, "Hata", str(e))
            self.model._load()

    def open_add(self):
        dlg = AddPersonnelDialog(self.db, self)
        if dlg.exec(): 
            self.model._load()
            self.refresh_logs()

    def refresh_logs(self):
        model = QStandardItemModel()
        model.setHorizontalHeaderLabels(["Numara","İşlem","Tarih-Saat"])
        for number, action, ts in self.db.personnel_logs():
            model.appendRow([QStandardItem(number), QStandardItem(action), QStandardItem(ts)])
        self.log_table.setModel(model)

    def export_personnel_logs(self):
        if pd is None:
            QMessageBox.critical(self, "Pandas Yok", "Excel dışa aktarma için pandas/openpyxl kurulmalı.")
            return
        
        rows = self.db.personnel_logs()
        if not rows:
            QMessageBox.information(self, "Kayıt Yok", "Personel logları bulunamadı.")
            return
        
        df = pd.DataFrame(rows, columns=["Numara","İşlem","Tarih-Saat"])
        defname = f"personel_loglari_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        
        save_path, _ = QFileDialog.getSaveFileName(self, "Personel Logları Excel olarak kaydet", defname, "Excel (*.xlsx)")
        if save_path:
            try:
                df.to_excel(save_path, index=False)
                QMessageBox.information(self, "Başarılı", f"Personel logları Excel kaydedildi:\n{save_path}")
            except Exception as e:
                QMessageBox.critical(self, "Hata", str(e))

# ===================== Market Hours Dialog (Evci/Yurtçu) =====================
DAYS_TR = ["Pazartesi","Salı","Çarşamba","Perşembe","Cuma","Cumartesi","Pazar"]

class MarketHoursDialog(QDialog):
    def __init__(self, db: Database, parent=None):
        super().__init__(parent)
        self.db = db
        self.setWindowTitle("Çarşı Saatlerini Düzenle (Evci / Yurtçu)")
        self.resize(640, 420)
        v = QVBoxLayout(self)

        self.tabs = QTabWidget()
        self._tab_data = {}  # profile -> (checks, starts, ends)

        for profile in ("Evci","Yurtçu"):
            w = QWidget(); g = QGridLayout(w)
            checks, starts, ends = [], [], []
            for i, day in enumerate(DAYS_TR):
                lbl = QLabel(day)
                chk = QCheckBox("İzinli")
                st = QTimeEdit(); st.setDisplayFormat("HH:mm")
                en = QTimeEdit(); en.setDisplayFormat("HH:mm")
                g.addWidget(lbl, i, 0)
                g.addWidget(chk, i, 1)
                g.addWidget(QLabel("Başlangıç"), i, 2); g.addWidget(st, i, 3)
                g.addWidget(QLabel("Bitiş"), i, 4);     g.addWidget(en, i, 5)
                s, e = self.db.get_day_interval(profile, i)
                if s and e:
                    hh, mm = map(int, s.split(":")); st.setTime(time(hh, mm))
                    hh, mm = map(int, e.split(":")); en.setTime(time(hh, mm))
                    chk.setChecked(True)
                else:
                    chk.setChecked(False); st.setEnabled(False); en.setEnabled(False)
                chk.toggled.connect(lambda on, st=st, en=en: (st.setEnabled(on), en.setEnabled(on)))
                checks.append(chk); starts.append(st); ends.append(en)
            self.tabs.addTab(w, profile)
            self._tab_data[profile] = (checks, starts, ends)
        v.addWidget(self.tabs)

        btns = QHBoxLayout()
        b_cancel = QPushButton("Vazgeç"); b_save = QPushButton("Kaydet")
        b_cancel.clicked.connect(self.reject); b_save.clicked.connect(self.save)
        btns.addStretch(1); btns.addWidget(b_cancel); btns.addWidget(b_save)
        v.addLayout(btns)

    def save(self):
        try:
            for profile, (checks, starts, ends) in self._tab_data.items():
                for d in range(7):
                    if checks[d].isChecked():
                        st = starts[d].time(); en = ends[d].time()
                        s = f"{st.hour():02d}:{st.minute():02d}"
                        e = f"{en.hour():02d}:{en.minute():02d}"
                        self.db.set_day_interval(profile, d, s, e)
                    else:
                        self.db.set_day_interval(profile, d, None, None)  # tamamen yasak
            QMessageBox.information(self, "Kaydedildi", "Çarşı saatleri güncellendi.")
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Hata", str(e))

# ===================== Gelişmiş Excel Dialog =====================
class AdvancedExportDialog(QDialog):
    def __init__(self, db: Database, parent=None):
        super().__init__(parent)
        self.db = db
        self.setWindowTitle("Excel Oluştur (Gelişmiş)")
        self.resize(420, 240)
        v = QVBoxLayout(self)

        form = QFormLayout()
        self.cb_type = QComboBox(); self.cb_type.addItems(["Tümü","Evci","Yurtçu"])
        self.cb_only_blocked = QCheckBox("Sadece Yasaklı İşlemler")
        self.start_date = QDateEdit(); self.start_date.setCalendarPopup(True); self.start_date.setDate(QDate.currentDate())
        self.end_date   = QDateEdit(); self.end_date.setCalendarPopup(True);   self.end_date.setDate(QDate.currentDate())
        form.addRow("Tip:", self.cb_type)
        form.addRow("Başlangıç Tarihi:", self.start_date)
        form.addRow("Bitiş Tarihi:", self.end_date)
        form.addRow(self.cb_only_blocked)
        v.addLayout(form)

        btns = QHBoxLayout()
        b_cancel = QPushButton("Vazgeç"); b_ok = QPushButton("Excel Oluştur")
        b_cancel.clicked.connect(self.reject); b_ok.clicked.connect(self.export_excel)
        btns.addStretch(1); btns.addWidget(b_cancel); btns.addWidget(b_ok)
        v.addLayout(btns)

    def export_excel(self):
        if pd is None:
            QMessageBox.critical(self, "Pandas Yok", "Excel dışa aktarma için pandas/openpyxl kurulmalı.")
            return
        d1 = self.start_date.date().toString("yyyy-MM-dd")
        d2 = self.end_date.date().toString("yyyy-MM-dd")
        only_blocked = self.cb_only_blocked.isChecked()
        stype = self.cb_type.currentText()

        with sqlite3.connect(DB_PATH) as con:
            cur = con.cursor()
            q = ("SELECT l.student_number, l.action, l.ts, COALESCE(s.student_type,'Evci') as stype "
                 "FROM logs l JOIN students s ON s.number=l.student_number "
                 "WHERE substr(l.ts,1,10) BETWEEN ? AND ? ")
            params = [d1, d2]
            if only_blocked:
                q += "AND l.action='Yasak' "
            if stype in ("Evci","Yurtçu"):
                q += "AND COALESCE(s.student_type,'Evci')=? "
                params.append(stype)
            q += "ORDER BY l.ts ASC"
            cur.execute(q, params)
            rows = cur.fetchall()

        if not rows:
            QMessageBox.information(self, "Kayıt Yok", "Seçtiğin filtrelerle kayıt bulunamadı.")
            return

        df = pd.DataFrame(rows, columns=["Numara","İşlem","Tarih-Saat","Tip"])
        defname = f"rapor_{d1}_{d2}"
        if only_blocked: defname += "_yasakli"
        if stype in ("Evci","Yurtçu"): defname += f"_{stype.lower()}"
        defname += ".xlsx"

        save_path, _ = QFileDialog.getSaveFileName(self, "Excel olarak kaydet", defname, "Excel (*.xlsx)")
        if not save_path: return
        try:
            df.to_excel(save_path, index=False)
            QMessageBox.information(self, "Tamam", f"Excel kaydedildi:\n{save_path}")
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Hata", str(e))

# ===================== Giriş-Çıkış Menüsü =====================
class LogsDialog(QDialog):
    def __init__(self, db: Database, parent=None):
        super().__init__(parent)
        self.db = db
        self.setWindowTitle("Giriş-Çıkış Menüsü")
        self.resize(980, 600)

        v = QVBoxLayout(self)
        top = QHBoxLayout()
        top.addStretch(1)
        self.date_edit = QDateEdit(); self.date_edit.setCalendarPopup(True); self.date_edit.setDate(QDate.currentDate())
        self.cb_blocked_only = QCheckBox("Sadece Yasaklılar")
        self.btn_export = QPushButton("Seçilen Tarih İçin Excel İndir")
        self.btn_export.clicked.connect(self.export_excel)
        self.btn_hours  = QPushButton("Çarşı Saatlerini Düzenle")
        self.btn_hours.clicked.connect(self.open_hours)
        self.btn_export_adv = QPushButton("Excel Oluştur (Gelişmiş)")
        self.btn_export_adv.clicked.connect(self.open_export_advanced)

        top.addWidget(QLabel("Tarih:")); top.addWidget(self.date_edit)
        top.addWidget(self.cb_blocked_only)
        top.addWidget(self.btn_export)
        top.addWidget(self.btn_hours)
        top.addWidget(self.btn_export_adv)

        self.table = QTableView()
        self.table.setSortingEnabled(True)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        v.addLayout(top); v.addWidget(self.table)
        self.refresh_table()

    def refresh_table(self):
        model = QStandardItemModel(); model.setHorizontalHeaderLabels(["Numara","İşlem","Tarih-Saat"])
        for number, action, ts in self.db.all_logs():
            model.appendRow([QStandardItem(number), QStandardItem(action), QStandardItem(ts)])
        self.table.setModel(model)

    def export_excel(self):
        if pd is None:
            QMessageBox.critical(self, "Pandas Yok", "Excel dışa aktarma için pandas/openpyxl kurulmalı.")
            return
        date_str = self.date_edit.date().toString("yyyy-MM-dd")
        rows = self.db.logs_on_date(date_str)
        if self.cb_blocked_only.isChecked():
            rows = [r for r in rows if r[1] == "Yasak"]
        if not rows:
            QMessageBox.information(self, "Kayıt Yok",
                                    f"{date_str} tarihinde {'yasaklı ' if self.cb_blocked_only.isChecked() else ''}kayıt bulunamadı.")
            return
        df = pd.DataFrame(rows, columns=["Numara","İşlem","Tarih-Saat"])
        defname = f"rapor_{date_str}{'_yasakli' if self.cb_blocked_only.isChecked() else ''}.xlsx"
        save_path, _ = QFileDialog.getSaveFileName(self, "Excel olarak kaydet", defname, "Excel (*.xlsx)")
        if save_path:
            try:
                df.to_excel(save_path, index=False)
                QMessageBox.information(self, "Başarılı", f"Excel kaydedildi:\n{save_path}")
            except Exception as e:
                QMessageBox.critical(self, "Hata", str(e))

    def open_hours(self):
        dlg = MarketHoursDialog(self.db, self)
        if dlg.exec():
            QMessageBox.information(self, "Bilgi", "Yeni saatler uygulanmaya başladı.")

    def open_export_advanced(self):
        AdvancedExportDialog(self.db, self).exec()

# ===================== Ana Pencere =====================
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.db = Database(DB_PATH)
        self.setWindowTitle(APP_TITLE)
        self.resize(1280, 720)
        self._last_scanned = None   # (number, action)

        central = QWidget(); self.setCentralWidget(central)
        root = QVBoxLayout(central)

        # ---------- Üst: Logo + büyük başlık + menüler ----------
        header = QHBoxLayout()

        left = QHBoxLayout()
        logo_lbl = QLabel()
        pm = QPixmap(LOGO_PATH)
        if not pm.isNull():
            pm = pm.scaledToHeight(64, Qt.SmoothTransformation)
            logo_lbl.setPixmap(pm)
            logo_lbl.setFixedHeight(64)
        else:
            logo_lbl.setFixedSize(64, 64)

        title = QLabel(APP_TITLE)
        title.setStyleSheet("font-size:26px; font-weight:800;")
        left.addWidget(logo_lbl); left.addSpacing(12); left.addWidget(title)

        header.addLayout(left)
        header.addStretch(1)

        btn_personnel = QPushButton("Personel Menüsü")
        btn_students = QPushButton("Öğrenci Menüsü")
        btn_logs = QPushButton("Giriş-Çıkış Menüsü")
        btn_personnel.clicked.connect(self.open_personnel); btn_students.clicked.connect(self.open_students); btn_logs.clicked.connect(self.open_logs)
        header.addWidget(btn_personnel); header.addWidget(btn_students); header.addWidget(btn_logs)

        root.addLayout(header)
        root.addSpacing(12)  # başlıkla listeler arası boşluk

        # ---------- Orta: üç liste ----------
        splitter = QSplitter(Qt.Horizontal)
        # Sol: Giriş
        left = QVBoxLayout(); leftw = QWidget(); leftw.setLayout(left)
        ltitle = QLabel("Giren Öğrenciler (Son 10)"); ltitle.setStyleSheet("font-weight:600;")
        self.list_in = QListWidget()
        left.addWidget(ltitle); left.addWidget(self.list_in)
        # Orta: Çıkış
        mid = QVBoxLayout(); midw = QWidget(); midw.setLayout(mid)
        mtitle = QLabel("Çıkan Öğrenciler (Son 10)"); mtitle.setStyleSheet("font-weight:600;")
        self.list_out = QListWidget()
        mid.addWidget(mtitle); mid.addWidget(self.list_out)
        # Sağ: Yasaklı
        right = QVBoxLayout(); rightw = QWidget(); rightw.setLayout(right)
        rtitle = QLabel("Yasaklı Denemeler (Son 10)"); rtitle.setStyleSheet("font-weight:600;")
        self.list_blocked = QListWidget()
        right.addWidget(rtitle); right.addWidget(self.list_blocked)

        splitter.addWidget(leftw); splitter.addWidget(midw); splitter.addWidget(rightw)
        splitter.setSizes([1,1,1])

        # ---------- Alt: RFID giriş ----------
        self.rfid_input = QLineEdit(); self.rfid_input.setPlaceholderText("Kartı okutun…")
        self.rfid_input.returnPressed.connect(self.handle_card)
        self.rfid_input.setClearButtonEnabled(True); self.rfid_input.setMaximumWidth(360)

        bottom = QHBoxLayout()
        bottom.addWidget(QLabel("Kart ID:")); bottom.addWidget(self.rfid_input); bottom.addStretch(1)

        root.addWidget(splitter)
        root.addLayout(bottom)

        self.refresh_lists()
        self._focus_timer = QTimer(self); self._focus_timer.timeout.connect(lambda: self.rfid_input.setFocus())
        self._focus_timer.start(2000); self.rfid_input.setFocus()

    # ----- Listeleri yenile -----
    def refresh_lists(self):
        self.list_in.clear(); self.list_out.clear(); self.list_blocked.clear()
        # Girişler (sadece öğrenciler)
        for idx, (number, action, ts) in enumerate(self.db.last_n_student_logs("Giriş", 10)):
            name = self._name_of(number)
            item = QListWidgetItem()
            highlight = (self._last_scanned == (number, "Giriş")) and (idx == 0) and self.db.get_penalized(number)
            widget = PersonItem(number, name, ts, large=(idx==0), highlight_red=bool(highlight))
            item.setSizeHint(widget.sizeHint())
            self.list_in.addItem(item); self.list_in.setItemWidget(item, widget)
        # Çıkışlar (sadece öğrenciler)
        for idx, (number, action, ts) in enumerate(self.db.last_n_student_logs("Çıkış", 10)):
            name = self._name_of(number)
            item = QListWidgetItem()
            highlight = (self._last_scanned == (number, "Çıkış")) and (idx == 0) and self.db.get_penalized(number)
            widget = PersonItem(number, name, ts, large=(idx==0), highlight_red=bool(highlight))
            item.setSizeHint(widget.sizeHint())
            self.list_out.addItem(item); self.list_out.setItemWidget(item, widget)
        # Yasaklılar (sadece öğrenciler)
        for idx, (number, action, ts) in enumerate(self.db.last_n_student_logs("Yasak", 10)):
            name = self._name_of(number)
            item = QListWidgetItem()
            highlight = (self._last_scanned == (number, "Yasak")) and (idx == 0)
            widget = PersonItem(number, name, ts, large=(idx==0), highlight_red=bool(highlight))
            item.setSizeHint(widget.sizeHint())
            self.list_blocked.addItem(item); self.list_blocked.setItemWidget(item, widget)

    def _name_of(self, number):
        with sqlite3.connect(DB_PATH) as con:
            cur = con.cursor()
            cur.execute("SELECT first_name, last_name FROM students WHERE number=?", (number,))
            row = cur.fetchone()
            if row:
                return f"{row[0]} {row[1]} ({number})"
            return f"Numara: {number}"

    def _beep_n_times(self, n=1, interval_ms=180):
        QApplication.beep()
        if n > 1:
            QTimer.singleShot(interval_ms, lambda: self._beep_n_times(n-1, interval_ms))

    def _is_within_market_hours(self, profile):
        now = datetime.now()
        wd = now.weekday()  # 0..6
        st, en = self.db.get_day_interval(profile, wd)
        if not st or not en:
            return False
        h1, m1 = map(int, st.split(":")); h2, m2 = map(int, en.split(":"))
        t1 = time(h1, m1); t2 = time(h2, m2); now_t = now.time()
        if t1 <= t2:
            return t1 <= now_t <= t2
        else:
            # gece taşması (22:00-02:00 gibi)
            return (now_t >= t1) or (now_t <= t2)

    def handle_card(self):
        card = self.rfid_input.text().strip(); self.rfid_input.clear()
        if not card: return
        stu = self.db.find_student_by_card(card)
        if not stu:
            # Kart tanımsız: öğrenci numarasına ata
            num, ok = QInputDialog.getText(self, "Kart Atama", "Bu kart tanımsız.\nKartı atamak için öğrenci numarasını girin:")
            num = (num or "").strip()
            if not (ok and num): return
            try:
                self.db.update_student_field(num, "card_id", card)
                QMessageBox.information(self, "Kart Atandı", f"Kart {num} numaralı öğrenciye atandı.")
            except sqlite3.IntegrityError as e:
                QMessageBox.critical(self, "Hata", f"Kart atanamadı: {e}")
            return

        number, first, last, penalized, stype, is_personnel = stu

        # Personel ise sadece log tut, ekranda gösterme
        if is_personnel:
            last_action = self.db.last_action_for_student(number)
            next_action = "Çıkış" if last_action == "Giriş" else "Giriş"
            ts = self.db.add_log(number, next_action)
            self.statusBar().showMessage(f"Personel {first} {last} için {next_action} kaydedildi ({ts}).", 3000)
            return

        # Öğrenci işlemleri: Çarşı saat kontrolü (profil: Evci/Yurtçu)
        within = self._is_within_market_hours(stype)
        if not within:
            ts = self.db.add_log(number, "Yasak")
            self._last_scanned = (number, "Yasak")
            if int(penalized):
                self._beep_n_times(4, 180)
            self.statusBar().showMessage(f"{first} {last} için YASAK deneme ({ts}).", 5000)
            self.refresh_lists()
            return

        # Saat içi => normal toggle
        last_action = self.db.last_action_for_student(number)
        next_action = "Çıkış" if last_action == "Giriş" else "Giriş"
        ts = self.db.add_log(number, next_action)
        self._last_scanned = (number, next_action)
        if int(penalized):
            self._beep_n_times(4, 180)
        self.statusBar().showMessage(f"{first} {last} için {next_action} kaydedildi ({ts}).", 5000)
        self.refresh_lists()

    def open_personnel(self):
        PersonnelMenuDialog(self.db, self).exec()
        if not stu:
            # Kart tanımsız: öğrenci numarasına ata
            num, ok = QInputDialog.getText(self, "Kart Atama", "Bu kart tanımsız.\nKartı atamak için öğrenci numarasını girin:")
            num = (num or "").strip()
            if not (ok and num): return
            try:
                self.db.update_student_field(num, "card_id", card)
                QMessageBox.information(self, "Kart Atandı", f"Kart {num} numaralı öğrenciye atandı.")
            except sqlite3.IntegrityError as e:
                QMessageBox.critical(self, "Hata", f"Kart atanamadı: {e}")
            return

        number, first, last, penalized, stype, is_personnel = stu

        # Personel ise sadece log tut, ekranda gösterme
        if is_personnel:
            last_action = self.db.last_action_for_student(number)
            next_action = "Çıkış" if last_action == "Giriş" else "Giriş"
            ts = self.db.add_log(number, next_action)
            self.statusBar().showMessage(f"Personel {first} {last} için {next_action} kaydedildi ({ts}).", 3000)
            return

        # Öğrenci işlemleri: Çarşı saat kontrolü (profil: Evci/Yurtçu)
        within = self._is_within_market_hours(stype)
        if not within:
            ts = self.db.add_log(number, "Yasak")
            self._last_scanned = (number, "Yasak")
            if int(penalized):
                self._beep_n_times(4, 180)
            self.statusBar().showMessage(f"{first} {last} için YASAK deneme ({ts}).", 5000)
            self.refresh_lists()
            return

        # Saat içi => normal toggle
        last_action = self.db.last_action_for_student(number)
        next_action = "Çıkış" if last_action == "Giriş" else "Giriş"
        ts = self.db.add_log(number, next_action)
        self._last_scanned = (number, next_action)
        if int(penalized):
            self._beep_n_times(4, 180)
        self.statusBar().showMessage(f"{first} {last} için {next_action} kaydedildi ({ts}).", 5000)
        self.refresh_lists()

    def open_personnel(self):
        PersonnelMenuDialog(self.db, self).exec()
        
    def open_students(self):
        StudentMenuDialog(self.db, self).exec()
        self.refresh_lists()

    def open_logs(self):
        LogsDialog(self.db, self).exec()
        self.refresh_lists()

# ===================== Çalıştır =====================
def main():
    app = QApplication(sys.argv)
    w = MainWindow(); w.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
