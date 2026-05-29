# KernelBootTool

A simple GUI tool for unpacking and repacking Android boot images for KernelSU/SUSFS.

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
./dist/KernelBootTool
```

Or run from source:

```bash
python3 kernel_boot_tool.py
```

## Build from Source

```bash
sudo apt install python3.12-venv
python3 -m venv venv
source venv/bin/activate
pip install pyqt6 pyinstaller
pyinstaller --onefile --windowed --name "KernelBootTool" kernel_boot_tool.py
```

Executable will be in `dist/KernelBootTool`.
