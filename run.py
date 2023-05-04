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
import hashlib

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
        posix_drive_path = '/Volumes/CIRCUITPY'
        if os.path.exists(posix_drive_path):
            return posix_drive_path
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
    api_url = "https://api.github.com/repos/mechawrench/wificom-lib/releases"
    releases = requests.get(api_url).json()

    latest_release = None
    latest_pre_release = None

    for release in releases:
        if release['prerelease']:
            if latest_pre_release is None:
                latest_pre_release = release
        elif latest_release is None:
            latest_release = release

        if latest_release is not None and latest_pre_release is not None:
            break

    return latest_release, latest_pre_release


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


def download_archive(url, save_path):
    response = requests.get(url, stream=True)
    response.raise_for_status()

    with open(save_path, "wb") as file:
        for chunk in response.iter_content(chunk_size=8192):
            file.write(chunk)

    print(f"Downloaded archive to: {save_path}")

def get_download_url_from_commit_hash(commit_hash):
    bucket_name = 'wificom-lib'
    zip_filename = f"wificom-lib_{commit_hash}_picow.zip"
    key = f"archives/{zip_filename}"
    zip_url = f"https://{bucket_name}.s3.amazonaws.com/{key}"

    try:
        response = requests.head(zip_url)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print("Commit zip file not found - please try another next time.")
        sys.exit()

    return zip_url

def version_tuple(version_str):
    version_str = version_str.lstrip('v').split('-')[0]
    return tuple(map(int, (version_str.split("."))))

def compare_versions(version1, version2):
    return version_tuple(version1) >= version_tuple(version2)

def get_all_releases():
    min_version = "0.9.0"
    api_url = "https://api.github.com/repos/mechawrench/wificom-lib/releases"
    releases = requests.get(api_url).json()
    
    version_regex = re.compile(r"^v?\d+(\.\d+)*(-[a-zA-Z0-9]+)?$")
    valid_releases = [release for release in releases if version_regex.match(release['tag_name']) and compare_versions(release['tag_name'], min_version)]

    return valid_releases


def choose_release(releases):
    print("\nAvailable releases:")
    for i, release in enumerate(releases):
        print(f"{i + 1}. {release['tag_name']} ({'Pre-release' if release['prerelease'] else 'Release'})")
    print("\n")
    selected_index = int(input("Select a release: ")) - 1
    return releases[selected_index]

# ...

print("Available options:")
print("1. Latest Release")
print("2. Install from a specific release")
print("3. Install from commit hash")

selected_option = int(input("\nSelect an option: "))

all_releases = get_all_releases()

if selected_option == 1:
    latest_release, latest_pre_release = valid_releases
    selected_release = latest_release
elif selected_option == 2:
    selected_release = choose_release(all_releases)
elif selected_option == 3:
    commit_hash = input("Enter the commit hash: ")
    selected_release_version = commit_hash
    selected_release_name = f"wificom-lib_{commit_hash}"
    download_url = get_download_url_from_commit_hash(commit_hash)
    tested_circuitpython_version = None
else:
    print("Invalid option selected.")
    sys.exit()

if selected_option != 3:
    selected_release_name = selected_release['name'].replace('/', '_')
    selected_release_version = selected_release['tag_name']
    release_notes = selected_release['body']
    download_url = selected_release['assets'][0]['browser_download_url']
    tested_circuitpython_version = extract_tested_circuitpython_version(release_notes)


circuitpython_version = read_circuitpython_version_from_boot_out(destination_folder)

if tested_circuitpython_version != None and tested_circuitpython_version != circuitpython_version:
    if selected_release_name.endswith("nina.zip"):
        download_link = f"https://adafruit-circuit-python.s3.amazonaws.com/bin/arduino_nano_rp2040_connect/en_US/adafruit-circuitpython-arduino_nano_rp2040_connect-en_US-{tested_circuitpython_version}.uf2"
    elif selected_release_name.endswith("picow.zip"):
        download_link = f"https://adafruit-circuit-python.s3.amazonaws.com/bin/raspberry_pi_pico_w/en_US/adafruit-circuitpython-raspberry_pi_pico_w-en_US-{tested_circuitpython_version}.uf2"

    print(f"Download the tested CircuitPython version here: \n {download_link}\n")
    input("Press Enter to exit...")
    sys.exit()

temp_directory = tempfile.mkdtemp()

urlretrieve(download_url, os.path.join(temp_directory, selected_release_name))

with zipfile.ZipFile(os.path.join(temp_directory, selected_release_name), 'r') as zip_ref:
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
