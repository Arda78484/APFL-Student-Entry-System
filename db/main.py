import sqlite3

db_path = r"C:\Users\kagan\Documents\GitHub\APFL-Student-Entry-System\db\system.db"

def get_student_by_card_id(card_id):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute('''
    SELECT name_surname, student_no
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
    card_id_input = input("Kart ID'yi girin: ")
    result = get_student_by_card_id(card_id_input)
    if result:
        print(f"\n👤 Ad Soyad: {result[0]}\n📘 Öğrenci No: {result[1]}")
    else:
        print("❌ Kart bulunamadı.")
