import ctypes
import json
import os
import re
import requests
import shutil
import string
import sys
import tempfile
import zipfile

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

def read_board_info(file_path: str) -> str:
    with open(file_path, 'r') as file:
        return file.read()

def extract_board_id(board_info: str):
    board_id_search = re.search(r'Board ID:(.+)', board_info)
    
    if board_id_search:
        board_id = board_id_search.group(1).strip()
        return board_id
    else:
        print("Board ID not found. Exiting...")
        sys.exit()

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

def is_drive_writable(drive_path):
    if os.name == 'nt':
        try:
            test_file = os.path.join(drive_path, 'test.txt')
            with open(test_file, 'w') as f:
                f.write('test')
            os.remove(test_file)
            return True
        except PermissionError:
            return False
    else:
        return os.access(drive_path, os.W_OK)

def extract_all_from_archive(archive_path, extract_path):
    with zipfile.ZipFile(archive_path, 'r') as zip_ref:
        total_files = len(zip_ref.infolist())
        extracted_files = 0
        for file_info in zip_ref.infolist():
            if not any(part.startswith(".") for part in file_info.filename.split("/")):
                zip_ref.extract(file_info, extract_path)
                extracted_files += 1
                print(f"Extracting: {extracted_files}/{total_files} files", end='\r')

    print("\nExtraction completed.")

def delete_folders_in_lib(destination_folder, lib_folders_to_delete):
    lib_path = os.path.join(destination_folder, "lib")
    for folder in lib_folders_to_delete:
        folder_path = os.path.join(lib_path, folder)
        try:
            if os.path.exists(folder_path) and os.path.isdir(folder_path) and not any(part.startswith(".") for part in folder_path.split("/")):
                shutil.rmtree(folder_path)
        except Exception as e:
            print(f"An error occurred while deleting {folder_path}: {e}")


def get_folders_in_lib(zip_file_path):
    with zipfile.ZipFile(zip_file_path, 'r') as zip_ref:
        lib_folders = set()
        for file_info in zip_ref.infolist():
            if file_info.filename.startswith("lib/") and file_info.is_dir() and not any(part.startswith(".") for part in file_info.filename.split("/")):
                folder_name = file_info.filename.split('/')[1]
                lib_folders.add(folder_name)
        return lib_folders

def download_archive(url, save_path):
    response = requests.get(url, stream=True)
    response.raise_for_status()
    total_bytes = int(response.headers.get('content-length', 0))

    bytes_downloaded = 0

    with open(save_path, "wb") as file:
        for chunk in response.iter_content(chunk_size=8192):
            file.write(chunk)
            bytes_downloaded += len(chunk)
            print_download_progress(bytes_downloaded, total_bytes)

    print("\nDownload completed.")

    return save_path

def get_recommended_circuitpython_version(sources_json_path, board_id, device_type):
    with open(sources_json_path, 'r') as f:
        sources = json.load(f)

    recommended_version = sources['circuitpython'].get('picow' if device_type == 'raspberry_pi_pico_w' else 'nina')
    return recommended_version

def get_latest_commit():
    api_url = "https://api.github.com/repos/mechawrench/wificom-lib/commits"
    response = requests.get(api_url).json()
    latest_commit_hash = response[0]['sha']
    return latest_commit_hash, response[0]

def get_specific_commit(commit_hash):
    api_url = "https://api.github.com/repos/mechawrench/wificom-lib/commits/" + commit_hash
    response = requests.get(api_url).json()
    latest_commit_hash = response
    return latest_commit_hash, response

def get_resource_identifier(resource):
    if 'sha' in resource:
        return resource['sha']
    elif 'name' in resource:
        return resource['name']
    else:
        return 'default_value'

def get_download_url_from_commit_hash(resource, device_type):
    bucket_name = 'wificom-lib'
    device_suffix = '_picow.zip' if device_type == 'raspberry_pi_pico_w' else '_nina.zip'

    zip_filename =  bucket_name + '_' + get_resource_identifier(resource) + device_suffix

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

def save_installed_commit_hash(commit_hash, destination_folder):
    installed_version_file = os.path.join(destination_folder, 'wificom_installed_version.txt')
    with open(installed_version_file, 'w') as f:
        f.write(commit_hash)

def extract_device_type(board_id: str):
    if 'arduino_nano_rp2040_connect' in board_id:
        return 'arduino_nano_rp2040_connect'
    elif 'raspberry_pi_pico_w' in board_id:
        return 'raspberry_pi_pico_w'
    else:
        print("Invalid board ID. Exiting...")
        sys.exit()
        
def extract_sources_json(zip_file_path, extract_path):
    with zipfile.ZipFile(zip_file_path, 'r') as zip_ref:
        zip_ref.extract("sources.json", extract_path)

def choose_release(releases):
    print("\nAvailable releases:")
    for i, release in enumerate(releases):
        print(f"{i + 1}. {release['tag_name']} ({'Pre-release' if release['prerelease'] else 'Release'})")
    print("\n")
    selected_index = int(input("Select a release: ")) - 1
    return releases[selected_index]

def print_download_progress(bytes_downloaded, total_bytes):
    progress = int((bytes_downloaded / total_bytes) * 100)
    print(f"Downloading: {progress}% ({bytes_downloaded}/{total_bytes} bytes)", end='\r')



def check_circuitpython_key(sources_json_path, board_id, device_type, circuitpython_version):
    with open(sources_json_path, 'r') as f:
        sources = json.load(f)
    
    if 'circuitpython' not in sources:
        print("\nWarning: The version you are installing does not include a recommended version of CircuitPython.")
        print("Please check on Discord/GitHub for a recommended version.")
        decision = input("Type 'Yes' to continue anyways or press Enter to exit: ").lower()
        
        if decision != 'yes':
            sys.exit()
    else:
        recommended_circuitpython_version = get_recommended_circuitpython_version(sources_json_path, board_id, device_type)

        if recommended_circuitpython_version != circuitpython_version:
            print(f"\nThe recommended CircuitPython version for this release is {recommended_circuitpython_version} while you have {circuitpython_version} installed.")
            print("It is advised to upgrade/downgrade your CircuitPython version.")
            if(board_id == 'arduino_nano_rp2040_connect'):
                print("If you are using the Arduino Nano RP2040 Connect, you can download the latest UF2 file from here:")
                print("https://adafruit-circuit-python.s3.amazonaws.com/bin/arduino_nano_rp2040_connect/en_US/adafruit-circuitpython-arduino_nano_rp2040_connect-en_US-" + recommended_circuitpython_version + ".uf2")
            elif board_id == 'raspberry_pi_pico_w':
                print("If you are using the Raspberry Pi Pico W, you can download the latest UF2 file from here:")
                print("https://adafruit-circuit-python.s3.amazonaws.com/bin/raspberry_pi_pico_w/en_US/adafruit-circuitpython-raspberry_pi_pico_w-en_US-" + recommended_circuitpython_version + ".uf2")
            decision = input("Type 'Yes' to continue anyways or press Enter to exit: ").lower()
            
            if decision != 'yes':
                shutil.rmtree(temp_directory)
                sys.exit()

def copy_file_if_not_exists(src, dest):
    if not os.path.exists(dest):
        shutil.copy(src, dest)
    else:
        print(f"\nSkipping existing file: {os.path.basename(dest)}")

def print_welcome_message():
    intro = '''\033[32m
    Welcome to the WiFiCom Update/Installer Tool!

    This script will help you update your WiFiCom by downloading the
    latest version of the wificom-lib and updating the files on the
    CIRCUITPY drive. Keep in mind that your own files (secrets.py,
    config.py, and board_config.py) will not be affected.

    Let's get started!
    \033[0m'''
    print(intro)

def print_success_message():
    success = '''\033[32m
    Successfully Installed/Updated your WiFiCom!  Please eject the drive and restart your device.

    Ensure you've updated secrets.py before getting started.

    Enjoy!
    \033[0m'''
    print(success)

def get_user_option():
    print("Available options:")
    print("1. Install/Update to the latest release")
    print("2. Install/Update to a specific release")
    print("3. Install/Update from the latest commit hash")
    print("4. Install/Update from a specific commit hash")

    selected_option = int(input("\nSelect an option: "))
    return selected_option

def get_download_url(release, device_type):
    assets = release['assets']
    for asset in assets:
        if device_type in asset['name']:
            return asset['browser_download_url']
    return None

def get_selected_release_and_url(selected_option, valid_releases, all_releases, device_type):
    download_url = None
    selected_release = None

    if selected_option == 1:
        latest_release, latest_pre_release = valid_releases
        selected_release = latest_release
    elif selected_option == 2:
        selected_release = choose_specific_release(all_releases)
    elif selected_option == 3:
         [selected_release_version, selected_release] = get_latest_commit()
         selected_release_name = f"wificom-lib_{selected_release_version}"
         download_url = get_download_url_from_commit_hash(selected_release, device_type)
    elif selected_option == 4:
        commit_hash = input("Enter the commit hash: ")
        [selected_release_version, selected_release] = get_specific_commit(commit_hash)
        download_url = get_download_url_from_commit_hash(selected_release, device_type)
    else:
        print("Invalid option selected. Exiting.")
        sys.exit()

    if(selected_option <= 2):
        assets = selected_release['assets']
        search_str = "picow" if device_type == "raspberry_pi_pico_w" else "nina"

        for asset in assets:
            if search_str in asset['name']:
                download_url = asset['browser_download_url']
                break

    if download_url is None:
        print(f"No download URL found for the selected release and device type ({device_type}). Exiting.")
        sys.exit()

    return selected_release, download_url

def choose_specific_release(all_releases):
    print("\nAvailable releases:")
    for index, release in enumerate(all_releases):
        print(f"{index + 1}. {release['name']} ({release['tag_name']})")

    selected_index = int(input("\nEnter the number of the release you want to install: ")) - 1

    if 0 <= selected_index < len(all_releases):
        return all_releases[selected_index]
    else:
        print("Invalid selection. Exiting.")
        sys.exit()

def is_hidden_file(file_name):
    return file_name.startswith("._")

def copy_files_to_destination(destination_folder, extract_path):
    src_lib_folder = os.path.join(extract_path, "lib")
    dst_lib_folder = os.path.join(destination_folder, "lib")

    total_files = len(os.listdir(src_lib_folder))
    copied_files = 0

    for item in os.listdir(src_lib_folder):
        src_item = os.path.join(src_lib_folder, item)
        dst_item = os.path.join(dst_lib_folder, item)

        if is_hidden_file(item):
            continue

        try:
            if os.path.isdir(src_item):
                if os.path.exists(dst_item):
                    shutil.rmtree(dst_item)
                shutil.copytree(src_item, dst_item)
            elif os.path.isfile(src_item):
                shutil.copy2(src_item, dst_item)
            copied_files += 1
            print(f"Copying: {copied_files}/{total_files} files", end='\r')
        except Exception as e:
            print(f"An error occurred while copying {src_item} to {dst_item}: {e}")

    print("\nCopying completed.")

def remove_hidden_files(drive_path):
    if os.path.exists(drive_path):
        for root, dirs, files in os.walk(drive_path, topdown=False):
            for file_name in files:
                if file_name.startswith("._"):
                    file_path = os.path.join(root, file_name)
                    try:
                        os.remove(file_path)
                    except Exception as e:
                        print(f"Error while removing unused hidden file {file_path}: {e}")
            for dir_name in dirs:
                if dir_name.startswith("._"):
                    dir_path = os.path.join(root, dir_name)
                    try:
                        os.rmdir(dir_path)
                    except Exception as e:
                        print(f"Error while removing {dir_path}: {e}")

if __name__ == "__main__":
    os.system('cls' if os.name == 'nt' else 'clear')

    destination_folder = get_circuitpy_drive()
    if destination_folder is None:
        print("CIRCUITPY drive not found. Exiting...")
        sys.exit()

    if not is_drive_writable(destination_folder):
        print("CIRCUITPY drive is read-only. Please make sure the drive is writable and try again.")
        sys.exit()
    
    print_welcome_message()

    remove_hidden_files(destination_folder)

    destination_folder = get_circuitpy_drive()
    circuitpython_version = read_circuitpython_version_from_boot_out(destination_folder)
    
    valid_releases = get_valid_releases()
    selected_option = get_user_option()
    all_releases = get_all_releases()

    boot_out_path = os.path.join(destination_folder, "boot_out.txt")
    board_info = read_board_info(boot_out_path)
    board_id = extract_board_id(board_info)
    device_type = extract_device_type(board_id)

    selected_release, download_url = get_selected_release_and_url(selected_option, valid_releases, all_releases, device_type)

    temp_directory = tempfile.mkdtemp()
    
    archive_path = download_archive(download_url, os.path.join(temp_directory, selected_release.get('sha', selected_release.get('name', '')).replace('/', '_')))

    print("\nDownloading archive completed.")

    print("\nDeleted unnecessary folders in lib directory.")

    extract_path = os.path.join(temp_directory, "extracted")
    extract_all_from_archive(archive_path, extract_path)

    print("\nArchive extraction completed.")

    sources_json_path = os.path.join(extract_path, 'sources.json')
    check_circuitpython_key(sources_json_path, board_id, device_type, circuitpython_version)

    lib_folders_to_delete = get_folders_in_lib(archive_path)
    delete_folders_in_lib(destination_folder, lib_folders_to_delete)

    copy_files_to_destination(destination_folder, extract_path)

    print("\nFiles copying completed.")

    shutil.rmtree(temp_directory)

    save_installed_commit_hash(selected_release.get('sha', selected_release.get('name', '')), destination_folder)

    print_success_message()

    input("Press Enter to exit...")
