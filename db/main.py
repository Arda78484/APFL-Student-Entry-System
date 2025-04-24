import sqlite3
import os

db_path = os.path.join(os.path.dirname(__file__), 'system.db')

def get_student_by_card_id(card_id):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute('''
    SELECT name_surname, student_no, photo_path
    FROM students
    WHERE REPLACE(card_id, ' ', '') = ?
    ''', (card_id.replace(' ', '').lower(),))

    result = cursor.fetchone()
    conn.close()

    if result:
        return result  
    else:
        return None


if __name__ == "__main__":
    card_id_input = input("Kart ID girin: ")
    result = get_student_by_card_id(card_id_input)
    if result:
        print(f"\n👤 Ad Soyad: {result[0]}\n🎓 Numara: {result[1]}\n🖼️ Foto: {result[2]}")
    else:
        print("❌ Kart bulunamadı.")
