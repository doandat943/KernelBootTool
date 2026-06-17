import sys
import subprocess
import os
import shutil
import tempfile
import zipfile
import platform
import urllib.request
from pathlib import Path
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QLineEdit, QPushButton, QTextEdit, QLabel, QFileDialog,
    QTabWidget
)
from PyQt6.QtCore import QDateTime

MAGISKBOOT_RELEASE = "https://github.com/PinNaCode/magiskboot_build/releases/download/last-ci/"

def magiskboot_asset():
    plat = sys.platform
    m = platform.machine().lower()
    if plat == "win32":
        if m in ("x86_64", "amd64"):
            return "magiskboot-e159716-release-windows-mingw-w64-ucrt-x86_64-standalone.zip"
        if m in ("arm64", "aarch64"):
            return "magiskboot-e159716-release-windows-mingw-w64-ucrt-arm64-standalone.zip"
        return "magiskboot-e159716-release-windows-mingw-w64-msvcrt-i686-standalone.zip"
    if plat == "darwin":
        if m in ("arm64", "aarch64"):
            return "magiskboot-e159716-release-macos-14-arm64-standalone.zip"
        return "magiskboot-e159716-release-macos-14-x86_64-standalone.zip"
    return None

def find_avb_offset(boot_path):
    size = os.path.getsize(boot_path)
    with open(boot_path, 'rb') as f:
        f.seek(-64, 2)
        if f.read(4) == b'AVBf':
            return size - 64
        f.seek(max(0, size - 4096))
        data = f.read()
        idx = data.rfind(b'AVBf')
        if idx >= 0:
            return max(0, size - 4096) + idx
    return size

def extract_section(boot_path, out_path, offset, size):
    with open(boot_path, 'rb') as f, open(out_path, 'wb') as o:
        f.seek(offset)
        o.write(f.read(size))

def read_le32(data, off):
    return int.from_bytes(data[off:off+4], 'little')

class KernelBootTool(QWidget):
    def __init__(self):
        super().__init__()
        self.boot_path = None
        self.work_dir = None
        self.out_path = None
        self.magiskboot = None
        self.anykernel_path = None
        self.orig_boot = None
        self.setup_ui()
        self.check_magiskboot()

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

    def check_magiskboot(self):
        ext = ".exe" if sys.platform == "win32" else ""
        p = Path(tempfile.gettempdir()) / f"magiskboot{ext}"
        if p.exists():
            self.magiskboot = p
            self.log("magiskboot ready")
            return

        asset = magiskboot_asset()
        if not asset:
            self.log(f"Platform {sys.platform}/{platform.machine()} not auto-supported. Install magiskboot manually in PATH.")
            return

        self.log(f"Downloading magiskboot ({asset})...")
        zip_path = p.with_suffix(".zip")
        try:
            urllib.request.urlretrieve(MAGISKBOOT_RELEASE + asset, zip_path)
        except Exception as ex:
            self.log(f"Download failed: {ex}")
            return

        try:
            with zipfile.ZipFile(zip_path, 'r') as z:
                z.extractall(p.parent)
        finally:
            zip_path.unlink(missing_ok=True)
        if sys.platform != "win32":
            p.chmod(0o755)
        self.magiskboot = p
        self.log("magiskboot ready")

    def _save_orig_and_preserved(self, work_dir):
        """Copy original boot to work_dir and extract BÖTT/AVB if present."""
        self.orig_boot = work_dir / "orig.img"
        shutil.copy(self.boot_path, self.orig_boot)
        avb_off = find_avb_offset(self.orig_boot)
        with open(self.orig_boot, 'rb') as f:
            f.seek(0)
            hdr = f.read(1664)
        if len(hdr) < 44:
            return
        kernel_size = read_le32(hdr, 8)
        header_version = read_le32(hdr, 40)
        ramdisk_size = 0
        signature_size = 0
        if header_version >= 3:
            ramdisk_size = read_le32(hdr, 12)
            if header_version >= 4:
                signature_size = read_le32(hdr, 1580)
        page_size = 4096
        kp = (kernel_size + page_size - 1) // page_size
        rp = (ramdisk_size + page_size - 1) // page_size
        sp = (signature_size + page_size - 1) // page_size
        bott_start = page_size * (1 + kp + rp + sp)
        bott_size = avb_off - bott_start
        if bott_size > 0:
            extract_section(self.orig_boot, work_dir / "bott", bott_start, bott_size)
            self.log(f"Saved BÖTT ({bott_size} bytes)")
        if avb_off < os.path.getsize(self.orig_boot):
            avb_size = os.path.getsize(self.orig_boot) - avb_off
            extract_section(self.orig_boot, work_dir / "avb_footer", avb_off, avb_size)
            self.log(f"Saved AVB footer ({avb_size} bytes)")

    def _restore_preserved(self, new_img, work_dir):
        """Append BÖTT and AVB footer to repacked image if magiskboot didn't preserve them."""
        orig_size = os.path.getsize(self.orig_boot)
        cur_size = os.path.getsize(new_img)
        if cur_size >= orig_size - 4096:
            self.log("magiskboot preserved full image")
            return
        missing = orig_size - cur_size
        bott = work_dir / "bott"
        avb = work_dir / "avb_footer"
        bott_size = bott.stat().st_size if bott.exists() else 0
        avb_size = avb.stat().st_size if avb.exists() else 0
        if bott_size + avb_size >= missing - 4096:
            if bott.exists() and bott_size > 0:
                with open(new_img, 'ab') as f:
                    f.write(bott.read_bytes())
                self.log(f"BÖTT re-attached ({bott_size} bytes)")
            if avb.exists() and avb_size > 0:
                with open(new_img, 'ab') as f:
                    f.write(avb.read_bytes())
                self.log(f"AVB footer re-attached ({avb_size} bytes)")
        else:
            self.log(f"Warning: missing {missing} bytes, preserved {bott_size + avb_size}")

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
            self.log("Starting patch process...")
            self.work_dir = Path(tempfile.mkdtemp()) / "work"
            os.makedirs(self.work_dir, exist_ok=True)

            self.log("Unpacking boot.img with magiskboot...")
            self._save_orig_and_preserved(self.work_dir)
            subprocess.run(
                [str(self.magiskboot), "unpack", str(self.orig_boot)],
                cwd=str(self.work_dir), check=True, capture_output=True
            )
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
            subprocess.run(
                [str(self.magiskboot), "repack", str(self.orig_boot), str(out)],
                cwd=str(self.work_dir), check=True, capture_output=True
            )
            self._restore_preserved(out, self.work_dir)
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
            self._save_orig_and_preserved(self.work_dir)
            subprocess.run(
                [str(self.magiskboot), "unpack", str(self.orig_boot)],
                cwd=str(self.work_dir), check=True, capture_output=True
            )
            items = sorted(p.name for p in self.work_dir.iterdir())
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
            subprocess.run(
                [str(self.magiskboot), "repack", str(self.orig_boot), str(out)],
                cwd=str(self.work_dir), check=True, capture_output=True
            )
            self._restore_preserved(out, self.work_dir)
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
