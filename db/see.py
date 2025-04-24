import sqlite3

db_path = r"C:\Users\kagan\Documents\GitHub\APFL-Student-Entry-System\db\system.db"

def view_students():
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("SELECT card_id, name_surname, student_no, photo_path FROM students")
    rows = cursor.fetchall()

    print("📋 Veritabanındaki Öğrenciler:")
    print("-" * 50)
    for row in rows:
        print(f"Kart ID : {row[0]}")
        print(f"Ad Soyad: {row[1]}")
        print(f"Numara  : {row[2]}")
        print(f"Foto    : {row[3]}")
        print("-" * 50)

    conn.close()

if __name__ == "__main__":
    view_students()
