import sqlite3
import os

# Veritabanı yolunu belirle (projene göre düzenlenebilir)
db_path = os.path.join(os.path.dirname(__file__), 'system.db')  # db klasöründeyse: 'db/system.db'

# Bağlantı kur ve tabloyu oluştur
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Tablonun doğru şekilde oluşturulması
cursor.execute('''
CREATE TABLE IF NOT EXISTS students (
    card_id TEXT PRIMARY KEY,
    name_surname TEXT,
    student_no TEXT,
    photo_path TEXT
)
''')

conn.commit()
conn.close()

print("✅ 'students' tablosu başarıyla oluşturuldu.")
