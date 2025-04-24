from main import get_student_by_card_id
import os

card_id = "d22e2f72"  

result = get_student_by_card_id(card_id)

if result:
    name, number, photo = result
    print(f"✅ Öğrenci Bilgisi:")
    print(f"Ad Soyad : {name}")
    print(f"Numara   : {number}")
    print(f"Fotoğraf : {photo}")

    
    if os.path.exists(photo):
        print("🖼️ Fotoğraf dosyası bulundu.")
    else:
        print("⚠️ Fotoğraf yolu veritabanında var ama dosya bulunamadı!")
else:
    print("❌ Bu kart ID'ye ait öğrenci yok.")
