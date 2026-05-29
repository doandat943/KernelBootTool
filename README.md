# Boot Image Tool

A simple GUI tool for unpacking and repacking Android boot images.

## Features

- Unpack boot.img files
- Replace kernel with custom kernel
- Repack boot images
- Save with timestamp naming

## Requirements

- Python 3.12+
- PyQt6
- mkbootimg tools (downloaded automatically)

## Usage

```bash
./dist/BootImageTool
```

Or run from source:

```bash
python3 boot_image_tool.py
```

## Build from Source

```bash
sudo apt install python3.12-venv
python3 -m venv venv
source venv/bin/activate
pip install pyqt6 pyinstaller
pyinstaller --onefile --windowed --name "BootImageTool" boot_image_tool.py
```

Executable will be in `dist/BootImageTool`.
