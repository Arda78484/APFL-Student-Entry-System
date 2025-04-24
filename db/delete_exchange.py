import sqlite3

db_path = r"C:\Users\kagan\Documents\GitHub\APFL-Student-Entry-System\db\system.db"

def fix_broken_entry():
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # 1️⃣ Bozuk olanı sil (boşluklu karakterlerle eşleşsin diye LIKE kullanalım)
    cursor.execute("DELETE FROM students WHERE card_id LIKE '%d2%2e%2f%72%'")
    print(f"🗑️ Bozuk giriş silindi. Etkilenen kayıt sayısı: {cursor.rowcount}")

    # 2️⃣ Doğru olanı yeniden ekle
    try:
        cursor.execute('''
        INSERT INTO students (card_id, name_surname, student_no, photo_path)
        VALUES (?, ?, ?, ?)
        ''', ('d22e2f72', 'burakhan madan', '18090', ''))
        print("✅ Doğru kart ID başarıyla yeniden eklendi.")
    except sqlite3.IntegrityError:
        print("⚠️ 'd22e2f72' zaten var. Güncelleniyor...")

        cursor.execute('''
        UPDATE students
        SET name_surname = ?, student_no = ?, photo_path = ?
        WHERE card_id = ?
        ''', ('burakhan madan', '18090', '', 'd22e2f72'))
        print("✅ Güncelleme tamamlandı.")

    conn.commit()
    conn.close()
    print("🎉 Düzeltme işlemi başarıyla tamamlandı.")

if __name__ == "__main__":
    fix_broken_entry()
