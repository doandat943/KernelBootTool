import sys
import subprocess
import os
import shutil
import tempfile
import zipfile
from pathlib import Path
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QLineEdit, QPushButton, QTextEdit, QLabel, QFileDialog,
    QTabWidget, QComboBox
)
from PyQt6.QtCore import Qt, QDateTime


class KernelBootTool(QWidget):
    def __init__(self):
        super().__init__()
        self.boot_path = None
        self.work_dir = None
        self.out_path = None
        self.mkbootimg = None
        self.anykernel_path = None
        self.setup_ui()
        self.check_mkbootimg()

    def setup_ui(self):
        self.setWindowTitle("KernelBootTool")
        self.setMinimumSize(800, 600)

        layout = QVBoxLayout()

        title = QLabel("KernelBootTool")
        title.setStyleSheet("font-size: 24px; font-weight: bold;")
        layout.addWidget(title)

        self.tabs = QTabWidget()
        self.tabs.addTab(self.create_normal_tab(), "Normal")
        self.tabs.addTab(self.create_advanced_tab(), "Advanced")
        layout.addWidget(self.tabs)

        layout.addWidget(QLabel("Log"))
        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        layout.addWidget(self.log_area)

        self.setLayout(layout)

    def create_normal_tab(self):
        widget = QWidget()
        layout = QVBoxLayout()

        layout.addWidget(QLabel("Select boot.img and AnyKernel3 zip"))

        boot_layout = QHBoxLayout()
        self.normal_boot_input = QLineEdit()
        self.normal_boot_input.setPlaceholderText("boot.img")
        boot_browse = QPushButton("Open")
        boot_browse.clicked.connect(self.browse_normal_boot)
        boot_layout.addWidget(self.normal_boot_input)
        boot_layout.addWidget(boot_browse)
        layout.addLayout(boot_layout)

        ak_layout = QHBoxLayout()
        self.normal_ak_input = QLineEdit()
        self.normal_ak_input.setPlaceholderText("AnyKernel3.zip")
        ak_browse = QPushButton("Open")
        ak_browse.clicked.connect(self.browse_normal_ak)
        ak_layout.addWidget(self.normal_ak_input)
        ak_layout.addWidget(ak_browse)
        layout.addLayout(ak_layout)

        self.flash_btn = QPushButton("Patch")
        self.flash_btn.setEnabled(False)
        self.flash_btn.clicked.connect(self.patch)

        clean_btn = QPushButton("Clean")
        clean_btn.clicked.connect(self.clean_normal)

        btn_layout = QHBoxLayout()
        btn_layout.addWidget(self.flash_btn)
        btn_layout.addWidget(clean_btn)
        layout.addLayout(btn_layout)

        layout.addStretch()
        widget.setLayout(layout)
        return widget

    def create_advanced_tab(self):
        widget = QWidget()
        layout = QVBoxLayout()

        boot_layout = QHBoxLayout()
        self.adv_boot_input = QLineEdit()
        self.adv_boot_input.setPlaceholderText("boot.img")
        boot_browse = QPushButton("Open")
        boot_browse.clicked.connect(self.browse_adv_boot)
        boot_layout.addWidget(self.adv_boot_input)
        boot_layout.addWidget(boot_browse)
        layout.addLayout(boot_layout)

        kernel_layout = QHBoxLayout()
        self.adv_kernel_input = QLineEdit()
        self.adv_kernel_input.setPlaceholderText("kernel (optional)")
        kernel_browse = QPushButton("Open")
        kernel_browse.clicked.connect(self.browse_adv_kernel)
        kernel_layout.addWidget(self.adv_kernel_input)
        kernel_layout.addWidget(kernel_browse)
        layout.addLayout(kernel_layout)

        btn_layout = QHBoxLayout()
        self.unpack_btn = QPushButton("Unpack")
        self.unpack_btn.setEnabled(False)
        self.unpack_btn.clicked.connect(self.unpack)
        self.repack_btn = QPushButton("Repack")
        self.repack_btn.setEnabled(False)
        self.repack_btn.clicked.connect(self.repack)
        self.save_btn = QPushButton("Save")
        self.save_btn.setEnabled(False)
        self.save_btn.clicked.connect(self.save)
        clean_btn = QPushButton("Clean")
        clean_btn.clicked.connect(self.clean)
        btn_layout.addWidget(self.unpack_btn)
        btn_layout.addWidget(self.repack_btn)
        btn_layout.addWidget(self.save_btn)
        btn_layout.addWidget(clean_btn)
        layout.addLayout(btn_layout)

        layout.addStretch()
        widget.setLayout(layout)
        return widget

    def check_mkbootimg(self):
        p = Path(tempfile.gettempdir()) / "mkbootimg"
        if not p.exists():
            self.log("Downloading mkbootimg...")
            subprocess.run([
                "git", "clone", "--depth", "1",
                "https://android.googlesource.com/platform/system/tools/mkbootimg",
                str(p)
            ], capture_output=True)
        self.mkbootimg = p
        self.log("Ready")

    def log(self, msg):
        self.log_area.append(msg)

    def browse_normal_boot(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select boot.img", "", "Images (*.img *.bin)")
        if path:
            self.boot_path = path
            self.normal_boot_input.setText(path)
            self.flash_btn.setEnabled(bool(self.boot_path and self.anykernel_path))
            self.log(f"Loaded: {Path(path).name}")

    def browse_normal_ak(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select AnyKernel3.zip", "", "Zip (*.zip)")
        if path:
            self.anykernel_path = path
            self.normal_ak_input.setText(path)
            self.flash_btn.setEnabled(bool(self.boot_path and self.anykernel_path))
            self.log(f"Loaded: {Path(path).name}")

    def browse_adv_boot(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select boot.img", "", "Images (*.img *.bin)")
        if path:
            self.boot_path = path
            self.adv_boot_input.setText(path)
            self.unpack_btn.setEnabled(True)
            self.log(f"Loaded: {Path(path).name}")

    def browse_adv_kernel(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select kernel", "", "All files (*)")
        if path:
            self.adv_kernel_input.setText(path)
            self.log(f"Kernel: {Path(path).name}")

    def patch(self):
        if not self.boot_path or not self.anykernel_path:
            return
        try:
            self.log("Starting flash process...")
            self.work_dir = Path(tempfile.mkdtemp()) / "work"
            os.makedirs(self.work_dir, exist_ok=True)

            self.log("Unpacking boot.img...")
            subprocess.run([
                "python3", str(self.mkbootimg / "unpack_bootimg.py"),
                "--boot_img", self.boot_path, "--out", str(self.work_dir)
            ], check=True, capture_output=True)
            self.log("Unpacked boot.img")

            self.log("Extracting kernel from AnyKernel3...")
            ak_dir = self.work_dir / "anykernel"
            os.makedirs(ak_dir, exist_ok=True)
            with zipfile.ZipFile(self.anykernel_path, 'r') as z:
                z.extractall(ak_dir)
            kernel_src = ak_dir / "Image"
            if not kernel_src.exists():
                raise Exception("kernel not found in AnyKernel3")
            shutil.copy(kernel_src, self.work_dir / "kernel")
            self.log("Kernel extracted")

            self.log("Repacking boot.img...")
            out = self.work_dir / "new-boot.img"
            cmd = [
                "python3", str(self.mkbootimg / "mkbootimg.py"),
                "--kernel", str(self.work_dir / "kernel"),
                "--output", str(out)
            ]
            for name in ["kernel_cmdline", "kernel_base"]:
                f = self.work_dir / name
                if f.exists():
                    cmd.extend([f"--{name.replace('_', '-')}", f.read_text().strip()])
            subprocess.run(cmd, check=True, capture_output=True)
            self.log("Repacked")

            timestamp = QDateTime.currentDateTime().toString("yyyyMMdd_HHmmss")
            default_name = f"boot_{timestamp}.img"
            save_path, _ = QFileDialog.getSaveFileName(
                self, "Save boot.img", str(Path(self.boot_path).parent / default_name),
                "Images (*.img *.bin);;All files (*)"
            )
            if save_path:
                shutil.copy(out, save_path)
                self.log(f"Saved: {save_path}")
            else:
                self.log("Save cancelled")

            shutil.rmtree(self.work_dir, ignore_errors=True)
            self.log("Done!")

        except Exception as ex:
            self.log(f"Error: {ex}")

    def unpack(self):
        if not self.boot_path:
            return
        self.log("Unpacking...")
        self.work_dir = Path(tempfile.mkdtemp()) / "work"
        os.makedirs(self.work_dir, exist_ok=True)
        try:
            subprocess.run([
                "python3", str(self.mkbootimg / "unpack_bootimg.py"),
                "--boot_img", self.boot_path, "--out", str(self.work_dir)
            ], check=True, capture_output=True)
            items = sorted(os.listdir(self.work_dir))
            self.log(f"Unpacked: {', '.join(items)}")
            self.repack_btn.setEnabled(True)
        except Exception as ex:
            self.log(f"Error: {ex}")

    def repack(self):
        kernel = self.adv_kernel_input.text().strip()
        if kernel and os.path.exists(kernel):
            shutil.copy(kernel, self.work_dir / "kernel")
            self.log(f"Using kernel: {Path(kernel).name}")
        self.log("Repacking...")
        out = self.work_dir / "new-boot.img"
        try:
            cmd = [
                "python3", str(self.mkbootimg / "mkbootimg.py"),
                "--kernel", str(self.work_dir / "kernel"),
                "--output", str(out)
            ]
            for name in ["kernel_cmdline", "kernel_base"]:
                f = self.work_dir / name
                if f.exists():
                    cmd.extend([f"--{name.replace('_', '-')}", f.read_text().strip()])
            subprocess.run(cmd, check=True, capture_output=True)
            self.out_path = out
            self.log(f"Repacked: {out.name}")
            self.save_btn.setEnabled(True)
        except Exception as ex:
            self.log(f"Error: {ex}")

    def save(self):
        if not self.out_path:
            self.log("Nothing to save. Repack first.")
            return
        timestamp = QDateTime.currentDateTime().toString("yyyyMMdd_HHmmss")
        default_name = f"boot_{timestamp}.img"
        path, _ = QFileDialog.getSaveFileName(
            self, "Save boot.img", str(Path(self.boot_path).parent / default_name),
            "Images (*.img *.bin);;All files (*)"
        )
        if path:
            shutil.copy(self.out_path, path)
            self.log(f"Saved: {path}")

    def clean(self):
        if self.work_dir and os.path.exists(self.work_dir):
            shutil.rmtree(self.work_dir, ignore_errors=True)
        self.boot_path = None
        self.work_dir = None
        self.out_path = None
        self.adv_boot_input.clear()
        self.adv_kernel_input.clear()
        for btn in [self.unpack_btn, self.repack_btn, self.save_btn]:
            btn.setEnabled(False)
        self.log_area.clear()
        self.log("Cleaned")

    def clean_normal(self):
        self.boot_path = None
        self.anykernel_path = None
        self.normal_boot_input.clear()
        self.normal_ak_input.clear()
        self.flash_btn.setEnabled(False)
        self.log_area.clear()
        self.log("Cleaned")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = KernelBootTool()
    window.show()
    sys.exit(app.exec())
