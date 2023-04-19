import os
import shutil
import hashlib
import tempfile
import zipfile
from urllib.request import urlretrieve
import requests
import ctypes
import string
import sys
import re

def get_readme_content(version):
    api_url = f"https://api.github.com/repos/mechawrench/wificom-lib/contents/README.md?ref={version}"
    response = requests.get(api_url).json()
    readme_content = requests.get(response['download_url']).text
    return readme_content

def read_circuitpython_version_from_boot_out(drive_path):
    try:
        with open(os.path.join(drive_path, "boot_out.txt"), "r") as boot_out_file:
            boot_out_content = boot_out_file.read()
        boot_out_version = re.search(r"Adafruit CircuitPython (\d+\.\d+\.\d+) on", boot_out_content)
        if boot_out_version:
            return boot_out_version.group(1)
    except FileNotFoundError:
        pass
    return None

os.system('cls' if os.name == 'nt' else 'clear')
intro = '''\033[32m
Welcome to the WiFiCom Update Installer

This script will help you update your WiFiCom by downloading the
latest version of the wificom-lib and updating the files on the
CIRCUITPY drive. Keep in mind that your own files (secrets.py,
config.py, and board_config.py) will not be affected.

Let's get started!
\033[0m'''
print(intro)

def get_circuitpy_drive():
    if os.name == 'posix':
        return '/Volumes/CIRCUITPY'
    elif os.name == 'nt':
        kernel32 = ctypes.windll.kernel32
        volume_name_buf = ctypes.create_unicode_buffer(1024)
        for letter in string.ascii_uppercase:
            if kernel32.GetVolumeInformationW(f'{letter}:\\', volume_name_buf, 1024, None, None, None, None, 0) != 0:
                if volume_name_buf.value == 'CIRCUITPY':
                    return f"{letter}:\\"
    return None

def is_drive_writable(drive_path):
    return os.access(drive_path, os.W_OK)

def get_valid_releases():
    valid_releases = []
    added_assets = set()
    api_url = "https://api.github.com/repos/mechawrench/wificom-lib/releases"
    releases = requests.get(api_url).json()

    for release in releases:
        if len(release['assets']) == 2:  # Add this condition to check if there are exactly two assets
            for asset in release['assets']:
                if (asset['name'].startswith("wificom-lib") and asset['name'].endswith(".zip") and
                        asset['content_type'] == 'application/zip' and asset['name'] not in added_assets):

                    valid_releases.append({
                        'url': asset['browser_download_url'],
                        'name': asset['name'],
                        'version': release['tag_name'],
                        'notes': release['body']
                    })

                    added_assets.add(asset['name'])

    return valid_releases

def extract_tested_circuitpython_version(release_notes):
    tested_with = re.search(r"Tested with.*?- CircuitPython (\d+\.\d+\.\d+)", release_notes, re.DOTALL)
    if tested_with:
        return tested_with.group(1)
    return None
    valid_releases = []
    api_url = "https://api.github.com/repos/mechawrench/wificom-lib/releases"
    releases = requests.get(api_url).json()
    
    for release in releases:
        for asset in release['assets']:
            if asset['name'].startswith("wificom-lib") and asset['name'].endswith(".zip") and asset['content_type'] == 'application/zip':
                valid_releases.append({
                    'url': asset['browser_download_url'],
                    'name': asset['name'],
                    'version': release['tag_name']
                })
    
    return valid_releases

destination_folder = get_circuitpy_drive()

if destination_folder is None:
    print("CIRCUITPY drive not found")
    input("Press Enter to exit...")
    sys.exit()

if not is_drive_writable(destination_folder):
    print("The CIRCUITPY drive is read-only.")
    print("Please enter drive mode and restart the program.")
    input("Press Enter to exit...")
    sys.exit()

valid_releases = get_valid_releases()

print("Available releases:")
for index, release in enumerate(valid_releases):
    print(f"{index + 1}. {release['version']} - {release['name']}")

selected_release = int(input("\nSelect a release number to install: ")) - 1
selected_release_version = valid_releases[selected_release]['version']
release_notes = valid_releases[selected_release]['notes']

tested_circuitpython_version = extract_tested_circuitpython_version(release_notes)
circuitpython_version = read_circuitpython_version_from_boot_out(destination_folder)

if circuitpython_version is None:
    print(f"\nWarning: boot_out.txt not found. Skipping CircuitPython version validation.  Please make sure you are using the correct version (CircuitPython {tested_circuitpython_version}).")
    print(f"Download the tested CircuitPython version here: \n https://circuitpython.org/board/raspberry_pi_pico_w/en/{tested_circuitpython_version}\n")
elif tested_circuitpython_version != circuitpython_version:
    print(f"\nThe CircuitPython version on your device ({circuitpython_version}) does not match the tested version ({tested_circuitpython_version}).")
    print(f"Download the tested CircuitPython version here: \n https://circuitpython.org/board/raspberry_pi_pico_w/en/{tested_circuitpython_version}\n")
    input("Press Enter to continue (not recommended) or Ctrl+C to exit...")
    sys.exit()

temp_directory = tempfile.mkdtemp()

urlretrieve(valid_releases[selected_release]['url'], os.path.join(temp_directory, valid_releases[selected_release]['name']))

with zipfile.ZipFile(os.path.join(temp_directory, valid_releases[selected_release]['name']), 'r') as zip_ref:
    extract_path = os.path.join(temp_directory, "extracted")
    zip_ref.extractall(extract_path)

source_folder = extract_path

def delete_untracked_files(source_folder, destination_folder):
    skip_files = {'secrets.py', 'config.py', 'board_config.py', 'boot_out.txt'}
    archive_files = set()
    for root, dirs, files in os.walk(source_folder):
        for file in files:
            archive_files.add(os.path.relpath(os.path.join(root, file), source_folder))
    destination_files = set()
    for root, dirs, files in os.walk(destination_folder):
        for file in files:
            if file not in skip_files:
                abs_path = os.path.join(root, file)
                destination_files.add(os.path.relpath(abs_path, destination_folder))

    untracked_files = destination_files - archive_files
    for file in untracked_files:
        abs_path = os.path.join(destination_folder, file)
        try:
            os.remove(abs_path)
        except FileNotFoundError:
            pass

delete_untracked_files(source_folder, destination_folder)

def copy_file_if_not_exists(src, dest):
    if not os.path.exists(dest):
        shutil.copy(src, dest)
    else:
        print(f"Skipping existing file: {os.path.basename(dest)}")

copy_file_if_not_exists(os.path.join(source_folder, 'board_config.py'), os.path.join(destination_folder, 'board_config.py'))
copy_file_if_not_exists(os.path.join(source_folder, 'config.py'), os.path.join(destination_folder, 'config.py'))

for root, dirs, files in os.walk(source_folder):
    files = [f for f in files if not f.startswith('.')]
    dirs[:] = [d for d in dirs if not (d.startswith('.') and d != 'lib')]
    
    for file in files:
        source_path = os.path.join(root, file)
        relative_path = os.path.relpath(source_path, source_folder)
        destination_path = os.path.join(destination_folder, relative_path)

        os.makedirs(os.path.dirname(destination_path), exist_ok=True)
        shutil.copy(source_path, destination_path)

shutil.rmtree(temp_directory)

success = '''\033[32m
Successfully Installed/Updated your WiFiCom!  Please eject the drive and restart your device.

Ensure you've updated secrets.py before getting started.

Enjoy!
\033[0m'''
print(success)
input("Press Enter to exit...")
