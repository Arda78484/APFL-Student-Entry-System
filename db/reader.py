from main import get_student_by_card_id
card_id_from_rfid = "d22e2f72"  
result = get_student_by_card_id(card_id_from_rfid)
if result:
    name, number = result
    print(f"✅ Öğrenci bulundu: {name} ({number})")
else:
    print("❌ Bu kart ID'ye ait öğrenci yok.")
