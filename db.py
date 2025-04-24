# db.py
import sqlite3
import os
import datetime
import shutil # Keep for potential future use, like backup

DB_DIR = "db"
DB_PATH = os.path.join(DB_DIR, "system.db")
PHOTOS_DIR = "photos"

class DatabaseManager:
    """Handles all database operations for the RFID application."""

    def __init__(self, db_path=DB_PATH):
        """
        Initializes the DatabaseManager.

        Args:
            db_path (str): The path to the SQLite database file.
        """
        self.db_path = db_path
        self._ensure_db_directory()
        self.init_db()

    def _ensure_db_directory(self):
        """Ensures the database directory exists."""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

    def _connect(self):
        """Establishes a connection to the database."""
        try:
            conn = sqlite3.connect(self.db_path)
            # Return rows as dictionary-like objects for easier access
            conn.row_factory = sqlite3.Row
            return conn
        except sqlite3.Error as e:
            print(f"❌ Database connection error: {e}")
            return None

    def init_db(self):
        """Initializes the database schema if it doesn't exist."""
        if not os.path.exists(self.db_path):
            print("📦 Veritabanı oluşturuluyor...")
            conn = self._connect()
            if conn:
                try:
                    with conn: # Use context manager for automatic commit/rollback
                        c = conn.cursor()
                        # Students table
                        c.execute("""
                            CREATE TABLE IF NOT EXISTS students (
                                id INTEGER PRIMARY KEY,      -- Öğrenci No (Student Number)
                                card_uid TEXT UNIQUE NOT NULL, -- Unique Card ID
                                name TEXT,                   -- Student Name (Added for completeness, can be fetched later)
                                surname TEXT,                -- Student Surname (Added for completeness)
                                photo_path TEXT,             -- Path to student's photo
                                can_exit INTEGER DEFAULT 1,  -- Permission to exit (1=Yes, 0=No)
                                status TEXT DEFAULT 'Outside', -- Current status ('Inside' or 'Outside')
                                last_updated TEXT            -- ISO format timestamp of last status change
                            )
                        """)
                        # Logs table
                        c.execute("""
                            CREATE TABLE IF NOT EXISTS logs (
                                id INTEGER PRIMARY KEY AUTOINCREMENT,
                                student_id INTEGER,          -- References students.id
                                card_uid TEXT,               -- Card UID used for the action
                                action TEXT,                 -- 'Entry' or 'Exit' or 'Denied Entry/Exit' or 'Registration'
                                timestamp TEXT,              -- ISO format timestamp of the log event
                                FOREIGN KEY (student_id) REFERENCES students (id)
                            )
                        """)
                    print(f"✅ Veritabanı oluşturuldu: {self.db_path}")
                except sqlite3.Error as e:
                    print(f"❌ Veritabanı tablo oluşturma hatası: {e}")
                finally:
                    conn.close()
        else:
            print(f"✅ Veritabanı zaten var: {self.db_path}")

    def add_student(self, student_id, card_uid, name, surname, photo_path):
        """Adds a new student to the database."""
        conn = self._connect()
        if not conn: return False, "Veritabanı bağlantı hatası."

        now = datetime.datetime.now().isoformat()
        try:
            with conn:
                conn.execute(
                    """
                    INSERT INTO students (id, card_uid, name, surname, photo_path, last_updated, status, can_exit)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (student_id, card_uid, name, surname, photo_path, now, 'Outside', 1) # Initial status
                )
            # Log the registration
            self.add_log(student_id=student_id, card_uid=card_uid, action="Registration")
            print(f"✅ Öğrenci eklendi: ID={student_id}, UID={card_uid}")
            return True, "Öğrenci başarıyla kaydedildi."
        except sqlite3.IntegrityError:
            print(f"⚠️ Öğrenci eklenemedi: ID ({student_id}) veya Kart UID ({card_uid}) zaten kayıtlı.")
            return False, "Bu öğrenci numarası veya kart zaten kayıtlı."
        except sqlite3.Error as e:
            print(f"❌ Öğrenci ekleme hatası: {e}")
            return False, f"Veritabanı hatası: {e}"
        finally:
            conn.close()

    def get_student_by_uid(self, card_uid):
        """Retrieves student details by their card UID."""
        conn = self._connect()
        if not conn: return None

        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM students WHERE card_uid = ?", (card_uid,))
            student = cursor.fetchone()
            return student # Returns a Row object or None
        except sqlite3.Error as e:
            print(f"❌ Öğrenci UID ile getirme hatası ({card_uid}): {e}")
            return None
        finally:
            conn.close()

    def get_all_students(self):
        """Retrieves all students from the database."""
        conn = self._connect()
        if not conn: return []

        try:
            cursor = conn.cursor()
            cursor.execute("SELECT id, card_uid, name, surname, photo_path, can_exit, status, last_updated FROM students ORDER BY id")
            students = cursor.fetchall()
            return students # Returns a list of Row objects
        except sqlite3.Error as e:
            print(f"❌ Tüm öğrencileri getirme hatası: {e}")
            return []
        finally:
            conn.close()

    def update_student_status(self, card_uid, new_status, can_exit=None):
        """Updates the status and last_updated timestamp for a student."""
        conn = self._connect()
        if not conn: return False

        now = datetime.datetime.now().isoformat()
        try:
            with conn:
                if can_exit is not None: # Optionally update exit permission
                    conn.execute(
                        "UPDATE students SET status = ?, last_updated = ?, can_exit = ? WHERE card_uid = ?",
                        (new_status, now, can_exit, card_uid)
                    )
                else:
                     conn.execute(
                        "UPDATE students SET status = ?, last_updated = ? WHERE card_uid = ?",
                        (new_status, now, card_uid)
                    )
            print(f"🔄 Öğrenci durumu güncellendi: UID={card_uid}, Durum={new_status}")
            return True
        except sqlite3.Error as e:
            print(f"❌ Öğrenci durumu güncelleme hatası ({card_uid}): {e}")
            return False
        finally:
            conn.close()

    def add_log(self, student_id, card_uid, action):
        """Adds an entry to the logs table."""
        conn = self._connect()
        if not conn: return False

        timestamp = datetime.datetime.now().isoformat()
        try:
            with conn:
                conn.execute(
                    "INSERT INTO logs (student_id, card_uid, action, timestamp) VALUES (?, ?, ?, ?)",
                    (student_id, card_uid, action, timestamp)
                )
            # print(f"📋 Log eklendi: ID={student_id}, Aksiyon={action}") # Optional: Can be noisy
            return True
        except sqlite3.Error as e:
            print(f"❌ Log ekleme hatası: {e}")
            return False
        finally:
            conn.close()

    def get_all_logs(self):
        """Retrieves all log entries, joining with student info."""
        conn = self._connect()
        if not conn: return []

        try:
            cursor = conn.cursor()
            # Join logs with students to get name/surname if needed, otherwise just use student_id
            cursor.execute("""
                SELECT l.timestamp, l.card_uid, l.student_id, s.name, s.surname, l.action
                FROM logs l
                LEFT JOIN students s ON l.student_id = s.id
                ORDER BY l.timestamp DESC
            """)
            logs = cursor.fetchall()
            return logs # Returns list of Row objects
        except sqlite3.Error as e:
            print(f"❌ Tüm logları getirme hatası: {e}")
            return []
        finally:
            conn.close()

    # --- Add other necessary methods like delete_student, update_student_info etc. ---
    def delete_student(self, student_id):
        """Deletes a student and their associated photo."""
        conn = self._connect()
        if not conn: return False, "Veritabanı bağlantı hatası."

        try:
            # First, get the photo path to delete the file
            cursor = conn.cursor()
            cursor.execute("SELECT photo_path FROM students WHERE id = ?", (student_id,))
            result = cursor.fetchone()
            photo_path = result['photo_path'] if result else None

            with conn:
                # Delete logs associated with the student first (optional, depends on policy)
                # conn.execute("DELETE FROM logs WHERE student_id = ?", (student_id,))
                # Delete the student record
                deleted_rows = conn.execute("DELETE FROM students WHERE id = ?", (student_id,)).rowcount

            if deleted_rows > 0:
                # If deletion was successful, try removing the photo
                if photo_path and os.path.exists(photo_path):
                    try:
                        os.remove(photo_path)
                        print(f"🗑️ Fotoğraf silindi: {photo_path}")
                    except OSError as e:
                        print(f"⚠️ Fotoğraf silinemedi ({photo_path}): {e}")
                print(f"🗑️ Öğrenci silindi: ID={student_id}")
                return True, "Öğrenci başarıyla silindi."
            else:
                print(f"⚠️ Öğrenci bulunamadı veya silinemedi: ID={student_id}")
                return False, "Silinecek öğrenci bulunamadı."

        except sqlite3.Error as e:
            print(f"❌ Öğrenci silme hatası (ID={student_id}): {e}")
            return False, f"Veritabanı hatası: {e}"
        finally:
            conn.close()