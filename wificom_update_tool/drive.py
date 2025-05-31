import ctypes
import getpass
import os
import re

def find_circuitpy_drive():
    if os.name == "posix":
        for posix_drive_path in [
            "/Volumes/CIRCUITPY",
            f"/media/{getpass.getuser()}/CIRCUITPY",
            f"/run/media/{getpass.getuser()}/CIRCUITPY",
        ]:
            if os.path.exists(posix_drive_path):
                return posix_drive_path
    elif os.name == "nt":
        kernel32 = ctypes.windll.kernel32
        volume_name_buf = ctypes.create_unicode_buffer(1024)
        for letter in string.ascii_uppercase:
            if kernel32.GetVolumeInformationW(f"{letter}:\\", volume_name_buf, 1024, None, None, None, None, 0) != 0:
                if volume_name_buf.value == "CIRCUITPY":
                    return f"{letter}:\\"
    return None

def is_drive_writable(drive_path):
    if os.name == "nt":
        try:
            test_file = os.path.join(drive_path, "wificom_updater_test.txt")
            with open(test_file, "w") as f:
                f.write("test")
            os.remove(test_file)
            return True
        except PermissionError:
            return False
    else:
        return os.access(drive_path, os.W_OK)

def read_boot_out(drive_path):
    file_path = os.path.join(drive_path, "boot_out.txt")
    with open(file_path) as f:
        boot_out_content = f.read()
    match = re.search(r"Adafruit CircuitPython ([0-9a-z\-\.]+) on", boot_out_content)
    if match is None:
        raise ValueError("CircuitPython version not found")
    circuitpython_version = match.group(1).strip()
    match = re.search(r"Board ID:(.+)", boot_out_content)
    if match is None:
        raise ValueError("Board ID not found")
    board_id = match.group(1).strip()
    return (circuitpython_version, board_id)
