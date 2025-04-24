import sqlite3
import os


db_path = r"C:\Users\kagan\Documents\GitHub\APFL-Student-Entry-System\db\system.db"
name_path = r"C:\Users\kagan\Desktop\name.txt"  

def assign_names():
    
    with open(name_path, 'r', encoding='utf-8') as f:
        lines = [line.strip() for line in f if line.strip()]

    students = []
    for line in lines:
        *name_parts, student_no = line.split()
        name_surname = ' '.join(name_parts)
        students.append((name_surname, student_no))

    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("SELECT card_id FROM students ORDER BY rowid ASC")
    card_ids = [row[0] for row in cursor.fetchall()]

    if len(students) > len(card_ids):
        print("❗ Uyarı: name.txt'deki öğrenci sayısı, veritabanındaki kartlardan fazla!")
        students = students[:len(card_ids)]  

    
    for i, card_id in enumerate(card_ids[:len(students)]):
        name_surname, student_no = students[i]
        cursor.execute('''
        UPDATE students
        SET name_surname = ?, student_no = ?
        WHERE card_id = ?
        ''', (name_surname, student_no, card_id))
        print(f"✅ {card_id} → {name_surname} ({student_no})")

    conn.commit()
    conn.close()
    print("🎉 Tüm öğrenciler başarıyla eşleştirildi.")

if __name__ == "__main__":
    assign_names()
