import sqlite3
import os

# 📁 Veritabanı ve foto klasörü yolları
db_path = r"C:\Users\kagan\Documents\GitHub\APFL-Student-Entry-System\db\system.db"
photo_folder = r"C:\Users\kagan\Documents\GitHub\APFL-Student-Entry-System\db\photo"

def assign_photos():
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("SELECT card_id, name_surname FROM students")
    students = cursor.fetchall()

    updated_count = 0

    for card_id, name in students:
        if not name:
            continue

        file_name = f"{name.lower().strip()}.jpg"
        photo_path = os.path.join(photo_folder, file_name)

        if os.path.exists(photo_path):
            # Göreli yolu veritabanına yaz
            relative_path = os.path.relpath(photo_path, os.path.dirname(db_path))

            cursor.execute('''
            UPDATE students
            SET photo_path = ?
            WHERE card_id = ?
            ''', (relative_path, card_id))
            updated_count += 1
            print(f"✅ Fotoğraf eklendi: {name} → {relative_path}")
        else:
            print(f"⚠️ Foto bulunamadı: {file_name}")

    conn.commit()
    conn.close()
    print(f"\n🎉 Toplam güncellenen öğrenci: {updated_count}")

if __name__ == "__main__":
    assign_photos()
