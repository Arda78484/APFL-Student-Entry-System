#include <SPI.h>
#include <MFRC522.h>

// Pin Tanımlamaları (NodeMCU veya benzeri için D pinleri)
#define SS_PIN   D4 // Slave Select Pini (SDA/SS olarak da geçer)
#define RST_PIN  D0 // Reset Pini (isteğe bağlı, bazı modüllerde gerekli)

#define R_PIN    D15 // Kırmızı LED Pini 
#define G_PIN    D14 // Yeşil LED Pini 
#define B_PIN    D13 // Mavi LED Pini 
#define BUZZER_PIN D12 // Buzzer Pini 

// MFRC522 nesnesi oluşturma
MFRC522 mfrc522(SS_PIN, RST_PIN);

// Seri iletişim için Baud Rate (Python ile aynı olmalı)
#define BAUD_RATE 9600

// Komutlar
#define CMD_SYSTEM_CHECK "SYS_CHECK"
#define ACK_CHECK_OK     "CMD:CHECK_OK"
#define PREFIX_UID       "UID:"

// Helper: Kart UID'sini boşluksuz, büyük harf HEX string olarak alır
String getCardUID() {
  String uidString = "";
  uidString.reserve(mfrc522.uid.size * 2); // Bellek ayırma optimizasyonu
  for (byte i = 0; i < mfrc522.uid.size; i++) {
    // Her byte'ı HEX'e çevir, gerekirse başına '0' ekle
    if (mfrc522.uid.uidByte[i] < 0x10) {
      uidString += "0";
    }
    uidString += String(mfrc522.uid.uidByte[i], HEX);
  }
  uidString.toUpperCase(); // Büyük harfe çevir
  return uidString;
}

// Helper: RGB LED rengini ayarlar (HIGH = Yanık, LOW = Sönük varsayımı)
// Not: Eğer ortak anot LED ise HIGH/LOW ters çevrilmeli
void setColor(bool r, bool g, bool b) {
  digitalWrite(R_PIN, r ? HIGH : LOW);
  digitalWrite(G_PIN, g ? HIGH : LOW);
  digitalWrite(B_PIN, b ? HIGH : LOW);
}

// Helper: Kısa bir bip sesi çalar
void beep(int frequency = 1000, int duration = 100) {
  tone(BUZZER_PIN, frequency, duration);
}

// Helper: Sistem kontrolü için özel ses ve ışık efekti
void playSystemCheckSequence() {
  setColor(LOW, LOW, HIGH); // Mavi yanık
  beep(1500, 150);          // Daha farklı bir bip sesi
  delay(150);
  beep(1800, 100);
  delay(100);
  // Seri porta onay mesajı gönder
  Serial.println(ACK_CHECK_OK);
  delay(500); // Mavi ışığın biraz görünür kalması için bekle
  setColor(LOW, LOW, LOW); // Işıkları kapat (veya bekleme rengine dön)
}

void setup() {
  // Seri iletişimi başlat
  Serial.begin(BAUD_RATE);
  Serial.println("\nESP32 RFID Reader Initializing...");

  // SPI iletişimini başlat
  SPI.begin();
  // MFRC522'yi başlat
  mfrc522.PCD_Init();
  delay(4); // Opsiyonel: Başlatma sonrası kısa bekleme
  mfrc522.PCD_DumpVersionToSerial(); // Versiyon bilgisini yazdır (opsiyonel)
  Serial.println("RFID Reader ready.");

  // Pin modlarını ayarla
  pinMode(R_PIN, OUTPUT);
  pinMode(G_PIN, OUTPUT);
  pinMode(B_PIN, OUTPUT);
  pinMode(BUZZER_PIN, OUTPUT);

  // Başlangıç durumu: Işıklar kapalı
  setColor(LOW, LOW, LOW);
  digitalWrite(BUZZER_PIN, LOW); // Buzzer kapalı

  // Başlangıçta kısa bir onay sesi çal
  beep(800, 50);
  delay(50);
  beep(1200, 50);
}

void loop() {
  // --- 1. Gelen Komutları Kontrol Et ---
  if (Serial.available() > 0) {
    String command = Serial.readStringUntil('\n');
    command.trim(); // Başındaki/sonundaki boşlukları temizle
    Serial.print("Received Command: "); Serial.println(command); // Gelen komutu logla

    if (command.equalsIgnoreCase(CMD_SYSTEM_CHECK)) {
       playSystemCheckSequence();
    } else {
       Serial.println("ERR:Unknown command"); // Bilinmeyen komut
    }
  }

  // --- 2. Yeni Kart Kontrol Et ---
  // Yeni kart yoksa veya okuma başarılı değilse PICC'yi uykuya almayı deneyebiliriz
  if (!mfrc522.PICC_IsNewCardPresent() || !mfrc522.PICC_ReadCardSerial()) {
    // İsteğe bağlı: Enerji tasarrufu için PICC'yi beklemeye al
    // mfrc522.PICC_HaltA(); // Bu sonraki okumayı etkileyebilir, dikkatli kullanın
    setColor(LOW, LOW, LOW); // Kart yokken ışıklar sönük
    delay(50); // CPU'yu çok yormamak için kısa bekleme
    return; // Döngünün başına dön
  }

  // --- 3. Kart Okundu ve Başarılı ---
  setColor(LOW, HIGH, LOW); // Yeşil - Kart okundu

  // UID'yi al
  String cardUID = getCardUID();

  // UID'yi belirli bir formatta seri porta gönder
  Serial.print(PREFIX_UID);
  Serial.println(cardUID);

  // Başarı sesi çal
  beep(900, 120);  // İlk bip sesi (Frekans: 900Hz, Süre: 120ms)
  delay(70);       // Sesler arasında kısa bir duraklama
  beep(1200, 100); // İkinci bip sesi (Frekans: 1200Hz, Süre: 100ms)

  // Kartı iletişimden çıkar (Halt) - sonraki okuma için önemli
  mfrc522.PICC_HaltA();
  // PCD (okuyucu) antenini kapatıp açmak bazen takılmaları önler (opsiyonel)
  // mfrc522.PCD_AntennaOff();
  // delay(10);
  // mfrc522.PCD_AntennaOn();

  delay(1000); // Aynı kartın hemen tekrar okunmasını engellemek için bekleme
  setColor(LOW, LOW, LOW); // Işıkları kapat
}