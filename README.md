# Student Card Project

This project is a Python application built using PyQt5. Below are the instructions to build the application.

## Build Instructions

To build the application, run the following command:

```bash
python -m PyInstaller --noconfirm --onefile --windowed \
    --add-data "C:/Users/ardac/AppData/Local/Programs/Python/Python312/Lib/site-packages/PyQt5/Qt5/plugins/platforms;platforms" \
    --add-binary "C:/Users/ardac/AppData/Local/Programs/Python/Python312/Lib/site-packages/PyQt5/Qt5/bin/Qt5Core.dll;." \
    --add-binary "C:/Users/ardac/AppData/Local/Programs/Python/Python312/Lib/site-packages/PyQt5/Qt5/bin/Qt5Gui.dll;." \
    --add-binary "C:/Users/ardac/AppData/Local/Programs/Python/Python312/Lib/site-packages/PyQt5/Qt5/bin/Qt5Widgets.dll;." \
    v1.py
```

## Notes

- Ensure that all paths to the PyQt5 dependencies are correct.
- Replace `v1.py` with the name of your main Python script if it differs.
- The `--add-data` and `--add-binary` flags are used to include necessary Qt5 plugins and binaries.

## Requirements

- Python 3.12
- PyQt5
- PyInstaller

For more details, refer to the official [PyInstaller documentation](https://pyinstaller.org/).