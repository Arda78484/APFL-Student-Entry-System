import os
import re

# Dosyaların bulunduğu klasör
klasor = "C:/Users/ardac/Downloads/ogrenci_fotolar"  # Buraya dosyaların olduğu klasör yolunu yaz

atlanan_dosyalar = []

for dosya in os.listdir(klasor):
    if dosya.lower().endswith((".jpg", ".jpeg")):
        # Dosya adındaki numarayı bul (büyük/küçük harf duyarsız)
        match = re.search(r"(\d+)\.jpe?g$", dosya, re.IGNORECASE)
        if match:
            numara = match.group(1)
            yeni_ad = numara + ".jpg"
            eski_yol = os.path.join(klasor, dosya)
            yeni_yol = os.path.join(klasor, yeni_ad)
            
            # Eğer dosya zaten bu isimde değilse
            if dosya != yeni_ad:
                # Çakışma varsa alternatif isim üret
                if os.path.exists(yeni_yol):
                    counter = 1
                    while True:
                        alternatif_ad = f"{numara}_{counter}.jpg"
                        alternatif_yol = os.path.join(klasor, alternatif_ad)
                        if not os.path.exists(alternatif_yol):
                            os.rename(eski_yol, alternatif_yol)
                            print(f"CONFLICT RESOLVED: {dosya} -> {alternatif_ad}")
                            atlanan_dosyalar.append(f"{dosya} -> {alternatif_ad} (conflict resolved)")
                            break
                        counter += 1
                else:
                    os.rename(eski_yol, yeni_yol)
                    print(f"{dosya} -> {yeni_ad}")
            else:
                print(f"ALREADY CORRECT: {dosya}")

print("\n" + "="*50)
print("CONFLICTED/RENAMED FILES:")
print("="*50)
for dosya in atlanan_dosyalar:
    print(dosya)
print(f"\nTotal conflicted files: {len(atlanan_dosyalar)}")
