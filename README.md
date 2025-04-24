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
## File Structure

Below is the file structure of the project:

```
student_card_project/
├── main/
│   ├── __init__.py
│   ├── ui/
│   │   ├── main_window.ui
│   │   └── student_card.ui
│   ├── resources/
│   │   ├── icons/
│   │   │   ├── add_icon.png
│   │   │   └── delete_icon.png
│   │   └── styles.qss
│   └── logic/
│       ├── __init__.py
│       ├── card_logic.py
│       └── database.py
├── tests/
│   ├── test_card_logic.py
│   └── test_database.py
├── v1.py
├── README.md
└── requirements.txt
```

- `main/`: Contains the core application logic, UI files, and resources.
- `tests/`: Contains unit tests for the application.
- `v1.py`: The main entry point of the application.
- `requirements.txt`: Lists the Python dependencies for the project.
- `README.md`: Documentation for the project.