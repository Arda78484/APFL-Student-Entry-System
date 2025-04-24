import sqlite3
import os


db_path = r"C:\Users\kagan\Documents\GitHub\APFL-Student-Entry-System\db\system.db"
txt_path = r"C:\Users\kagan\Desktop\kart_İD.txt"


def import_card_ids(file_path):
    if not os.path.exists(file_path):
        print("❌ TXT dosyası bulunamadı:", file_path)
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    with open(file_path, 'r', encoding='utf-8') as file:
        for line in file:
            
            card_id = line.strip().replace(' ', '').lower()

            if card_id == '':
                continue  

            try:
                cursor.execute('''
                INSERT INTO students (card_id, name_surname, student_no, photo_path)
                VALUES (?, '', '', '')
                ''', (card_id,))
                print(f"✅ Eklendi: {card_id}")
            except sqlite3.IntegrityError:
                print(f"⚠️ Zaten ekli: {card_id}")

    conn.commit()
    conn.close()
    print("🎉 Tüm kart ID’leri başarıyla işlendi.")


if __name__ == "__main__":
    import_card_ids(txt_path)
