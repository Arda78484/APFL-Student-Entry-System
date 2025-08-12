# build.py
import argparse, os, sys, shutil, subprocess

def find(entry):
    if os.path.isfile(entry):
        return entry
    # fallback: GUI.py varsayılanı
    if os.path.isfile("GUI.py"):
        return "GUI.py"
    print("Hata: Entry (giriş) dosyası bulunamadı.")
    sys.exit(1)

def run(cmd):
    print("\n> " + " ".join(cmd))
    r = subprocess.run(cmd)
    if r.returncode != 0:
        sys.exit(r.returncode)

def main():
    parser = argparse.ArgumentParser(description="Okul Kart Sistemi - Build")
    parser.add_argument("--entry", default="GUI.py", help="Giriş dosyası (varsayılan: GUI.py)")
    parser.add_argument("--name", default="OkulKartSistemi", help="Çıktı adı")
    parser.add_argument("--console", action="store_true", help="Konsol penceresini açık bırak")
    parser.add_argument("--clean", action="store_true", help="Önce build/dist temizle")
    parser.add_argument("--icon", default="", help="İkon dosyası (ico/ico, icns, png)")
    args = parser.parse_args()

    entry = find(args.entry)

    # PyInstaller var mı?
    if not shutil.which("pyinstaller"):
        print("Hata: PyInstaller kurulmamış. Şu komutla kur:\n  pip install pyinstaller")
        sys.exit(1)

    if args.clean:
        for p in ("build", "dist", f"{args.name}.spec"):
            if os.path.isdir(p):
                shutil.rmtree(p, ignore_errors=True)
            elif os.path.isfile(p):
                os.remove(p)

    # Ortak bayraklar
    cmd = [
        "pyinstaller",
        "--noconfirm",
        "--clean",
        "--onefile",
        "--name", args.name,
        # PySide6 tüm kaynak/binary’leri topla (plugin, qml, imageformats vs.)
        "--collect-all", "PySide6",
    ]

    # GUI uygulaması: konsol açma
    if not args.console:
        cmd.append("--windowed")

    # İkon (varsa)
    if args.icon:
        cmd.extend(["--icon", args.icon])

    # Giriş dosyası
    cmd.append(entry)

    run(cmd)

    exe = os.path.join("dist", args.name + (".exe" if os.name == "nt" else ""))
    print("\n✅ Bitti!")
    print(f"Çıktı: {exe}")
    print("\nNotlar:")
    print("- İlk çalıştırmada 'data/' ve 'photos/' klasörleri exe’nin yanında otomatik oluşur.")
    print("- Fotoğrafları 'photos/OGRENCINO.jpg' olarak koymalısın.")
    print("- Windows için Windows’ta, Linux için Linux’ta build al. (PyInstaller çapraz derleme yapmaz.)")

if __name__ == "__main__":
    main()
