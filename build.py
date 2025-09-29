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

def run(cmd, suppress_warnings=True):
    print("\n> " + " ".join(cmd))
    if suppress_warnings:
        # PyInstaller çıktısını filtrele - bilinen uyarıları gizle
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, 
                                 universal_newlines=True, bufsize=1)
        
        for line in process.stdout:
            # PySide6 project_lib uyarısını gizle (zararsız)
            if "project_lib" in line and "ModuleNotFoundError" in line:
                continue
            if "Failed to collect submodules for 'PySide6.scripts.deploy_lib'" in line:
                continue
            print(line, end='')
        
        process.wait()
        if process.returncode != 0:
            sys.exit(process.returncode)
    else:
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
    parser.add_argument("--verbose", action="store_true", help="Tüm PyInstaller çıktısını göster")
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
        # Diğer Qt binding'lerini hariç tut (çakışma önlemi)
        "--exclude-module", "PyQt5", 
        "--exclude-module", "PyQt6", 
        "--exclude-module", "tkinter",
    ]

    # GUI uygulaması: konsol açma
    if not args.console:
        cmd.append("--windowed")

    # İkon (varsa)
    if args.icon and os.path.isfile(args.icon):
        cmd.extend(["--icon", args.icon])
        print(f"İkon kullaniliyor: {args.icon}")
    elif args.icon:
        print(f"Uyari: İkon dosyasi bulunamadi: {args.icon}")

    # Giriş dosyası
    cmd.append(entry)

    run(cmd, suppress_warnings=not args.verbose)

    exe = os.path.join("dist", args.name + (".exe" if os.name == "nt" else ""))
    print("\n[OK] Bitti!")
    print(f"Cikti: {exe}")
    print("\nNotlar:")
    print("- Ilk calistirmada 'data/' ve 'photos/' klasorleri exe'nin yaninda otomatik olusur.")
    print("- Fotograflari 'photos/OGRENCINO.jpg' olarak koymalisin.")
    print("- Windows icin Windows'ta, Linux icin Linux'ta build al. (PyInstaller capraz derleme yapmaz.)")

if __name__ == "__main__":
    main()
