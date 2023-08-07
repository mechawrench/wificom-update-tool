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
import hashlib
from tqdm import tqdm
import send2trash


progress = None

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
        input("Press Enter to exit...")
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
    try:
        releases = requests.get(api_url).json()

        latest_release = None
        latest_pre_release = None

        if isinstance(releases, list):
            for release in releases:
                if isinstance(release, dict) and 'prerelease' in release:
                    if release['prerelease']:
                        if latest_pre_release is None:
                            latest_pre_release = release
                    elif latest_release is None:
                        latest_release = release

                    if latest_release is not None and latest_pre_release is not None:
                        break

            return latest_release, latest_pre_release
        else:
            print("Error: Invalid response from the GitHub API.")
            input("Press Enter to exit...")
            sys.exit()

    except requests.exceptions.RequestException as e:
        print("Error: Internet connection is not available or could not connect to the server.")
        input("Press Enter to exit...")
        sys.exit()


def is_drive_writable(drive_path):
    if os.name == 'nt':
        try:
            test_file = os.path.join(drive_path, 'wificom_installer_test.txt')
            with open(test_file, 'w') as f:
                f.write('test')
            os.remove(test_file)
            return True
        except PermissionError:
            return False
    else:
        return os.access(drive_path, os.W_OK)


def download_archive(url, save_path):
    try:
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
    except requests.exceptions.RequestException as e:
        print("Error occurred while downloading the file: ", e)
        input("Press Enter to exit...")
        sys.exit()


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
        input("Press Enter to exit...")
        sys.exit()

    return zip_url


def version_tuple(version_str):
    version_str = version_str.lstrip('v').split('-')[0]
    return tuple(map(int, (version_str.split("."))))


def compare_versions(version1, version2):
    return version_tuple(version1) >= version_tuple(version2)


def get_all_releases():
    min_version = "0.10.0"
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
        input("Press Enter to exit...")
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
        print(f"\nWarning: The version you are installing does not include a recommended version of CircuitPython.")
        print(f"\nPlease check on Discord/GitHub for a recommended version.")
        decision = input("Type 'Yes' to continue anyways or Press Enter to exit... ").lower()
        
        if decision != 'yes':
            sys.exit()
    else:
        recommended_circuitpython_version = get_recommended_circuitpython_version(sources_json_path, board_id, device_type)

        if recommended_circuitpython_version != circuitpython_version:
            print(f"\nThe recommended CircuitPython version for this release is {recommended_circuitpython_version} while you have {circuitpython_version} installed.")
            print(f"\nIt is advised to upgrade/downgrade your CircuitPython version.")
            if(board_id == 'arduino_nano_rp2040_connect'):
                print("If you are using the Arduino Nano RP2040 Connect, you can download the necessary UF2 file from here:\n")
                print("https://adafruit-circuit-python.s3.amazonaws.com/bin/arduino_nano_rp2040_connect/en_US/adafruit-circuitpython-arduino_nano_rp2040_connect-en_US-" + recommended_circuitpython_version + ".uf2\n")
            elif board_id == 'raspberry_pi_pico_w':
                print("If you are using the Raspberry Pi Pico W, you can download the necessary UF2 file from here:\n")
                print("https://adafruit-circuit-python.s3.amazonaws.com/bin/raspberry_pi_pico_w/en_US/adafruit-circuitpython-raspberry_pi_pico_w-en_US-" + recommended_circuitpython_version + ".uf2\n")
            decision = input("Type 'Yes' to continue anyways or Press Enter to exit... ").lower()
            
            if decision != 'yes':
                shutil.rmtree(temp_directory)
                sys.exit()


def copy_file_if_not_exists(src, dest):
    if not os.path.exists(dest):
        shutil.copy(src, dest)
    else:
        print(f"\nSkipping existing file: {os.path.basename(dest)}")


def print_welcome_message():
    intro = '''\nWelcome to the WiFiCom Update/Installer Tool!

    This script will help you update your WiFiCom by downloading the
    latest version of the wificom-lib and updating the files on the
    CIRCUITPY drive. Keep in mind that your own files (secrets.py,
    config.py, and board_config.py) will not be affected.

    Let's get started!\n'''
    print(intro)


def print_success_message():
    success = '''\nSuccessfully Installed/Updated your WiFiCom!  Please eject the drive and restart your device.

    Ensure you've updated secrets.py before getting started.

    Enjoy!\n'''
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
        input("Press Enter to exit...")
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
        input("Press Enter to exit...")
        sys.exit()

    return selected_release, download_url


def choose_specific_release(all_releases):
    print("\nAvailable releases:")
    for index, release in enumerate(all_releases):
        print(f"{index + 1}. {release['name']} ({release['tag_name']})")
    print("\n")
    selected_index = int(input("Select a release: ")) - 1
    return all_releases[selected_index]


def download_and_extract_latest(selected_release, download_url, temp_directory):
    print("Downloading the latest release...\n")
    archive_path = os.path.join(temp_directory, f"wificom-lib_{selected_release.get('parents')[0]['sha'] if 'parents' in selected_release else selected_release['tag_name']}.zip")
    download_archive(download_url, archive_path)

    print("Extracting files...\n")
    with zipfile.ZipFile(archive_path, 'r') as zip_ref:
        zip_ref.extractall(temp_directory)

    # Close the file before attempting to remove the temporary directory
    zip_ref.close()

    os.remove(archive_path)

    return archive_path


def count_files_in_directory(directory, ignore_files=[]):
    total_files = 0
    for root, _, files in os.walk(directory):
        for file in files:
            if not any(file.startswith(ignore) for ignore in ignore_files):
                total_files += 1
    return total_files

def delete_empty_directories(directory, source_folder):
    source_subdirectories = set()
    for root, dirs, _ in os.walk(os.path.join(source_folder, "lib"), topdown=False):
        for d in dirs:
            source_subdirectories.add(os.path.relpath(os.path.join(root, d), source_folder))

    for root, dirs, _ in os.walk(directory, topdown=False):
        for d in dirs:
            dir_path = os.path.join(root, d)
            rel_dir_path = os.path.relpath(dir_path, directory)
            if rel_dir_path != '.' and rel_dir_path not in source_subdirectories and not os.listdir(dir_path):
                try:
                    shutil.rmtree(dir_path)
                except OSError:
                    pass

def get_file_hash(file_path):
    BLOCK_SIZE = 65536
    hasher = hashlib.sha256()

    with open(file_path, 'rb') as file:
        while True:
            data = file.read(BLOCK_SIZE)
            if not data:
                break
            hasher.update(data)

    return hasher.hexdigest()

def files_match(file1, file2):
    BLOCK_SIZE = 65536
    hasher1 = hashlib.sha256()
    hasher2 = hashlib.sha256()

    if not os.path.exists(file1) or not os.path.exists(file2):
        return False

    with open(file1, 'rb') as f1, open(file2, 'rb') as f2:
        while True:
            block1 = f1.read(BLOCK_SIZE)
            block2 = f2.read(BLOCK_SIZE)

            if not block1 and not block2:
                break

            if block1 != block2:
                return False

            hasher1.update(block1)
            hasher2.update(block2)

    return hasher1.hexdigest() == hasher2.hexdigest()

def count_files_in_directory(directory, ignore_files=[]):
    total_files = 0
    for root, _, files in os.walk(directory):
        for file in files:
            if not any(file.startswith(ignore) for ignore in ignore_files) and not file.startswith('.'):
                total_files += 1
    return total_files

def count_added_and_modified_files(source_folder, destination_folder):
    added_files = 0
    modified_files = 0

    for root, _, files in os.walk(source_folder):
        for file in files:
            if file not in ['adafruit_requests.py', 'adafruit_displayio_ssd1306.py']:
                dest_file = os.path.join(destination_folder, os.path.relpath(root, source_folder), file)
                if not os.path.exists(dest_file):
                    added_files += 1
                elif not files_match(os.path.join(root, file), dest_file):
                    modified_files += 1

    return added_files, modified_files

def copy_files_to_destination(destination_folder, source_folder):
    global progress  # Use the global progress bar here

    ensure_lib_directory(destination_folder)

    lib_source_folder = os.path.join(source_folder, 'lib')
    lib_destination_folder = os.path.join(destination_folder, 'lib')

    deleted_files = []
    modified_files = []
    added_files = []

    # Delete files named adafruit_requests.py or adafruit_displayio_ssd1306.py permanently in lib_destination_folder
    for root, dirs, files in os.walk(lib_destination_folder, topdown=False):
        for file in files:
            if file in ['adafruit_requests.py', 'adafruit_displayio_ssd1306.py']:
                file_path = os.path.join(root, file)
                os.remove(file_path)
                deleted_files.append(file_path)
        for dir in dirs:
            dir_path = os.path.join(root, dir)
            if not os.path.basename(dir).startswith('.') and not os.path.islink(dir_path) and not os.listdir(dir_path):
                os.rmdir(dir_path, onerror=handle_rmtree_error)

    # Count the number of added and modified files in the lib folder
    added_files_count, modified_files_count = count_added_and_modified_files(lib_source_folder, lib_destination_folder)

    # Count the root files in the destination folder (excluding temporary files and hidden files)
    root_files_count = count_files_in_directory(destination_folder, ignore_files=['lib', '.TemporaryItems', '.Trashes'])

    total_files = added_files_count + modified_files_count + root_files_count

    progress = tqdm(total=total_files, desc="Copying files")

    # Copy files from lib_source_folder to lib_destination_folder
    copied_files_count = 0
    for _ in copy_files_from_source(lib_source_folder, lib_destination_folder):
        copied_files_count += 1
        if copied_files_count <= added_files_count:
            added_files.append(_)
        else:
            modified_files.append(_)

    progress.close()  # Close the progress bar after copying is completed

    # Delete any empty directories
    delete_empty_directories(destination_folder, source_folder)

    print("File copying completed.")
    print(f"Added files: {len(added_files)}")
    print(f"Modified files: {len(modified_files)}")
    print(f"Deleted files: {len(deleted_files)}")

    return added_files, modified_files, deleted_files

def copy_files_from_source(source_folder, destination_folder):
    total_files = sum(len(files) for _, _, files in os.walk(source_folder))

    for root, dirs, files in os.walk(source_folder):
        for file in files:
            if file not in ['adafruit_requests.py', 'adafruit_displayio_ssd1306.py']:
                dest_file = os.path.join(destination_folder, os.path.relpath(root, source_folder), file)
                os.makedirs(os.path.dirname(dest_file), exist_ok=True)
                shutil.copy2(os.path.join(root, file), dest_file)
                yield
                total_files -= 1
                progress.update(1)

    # Count the root files in the destination folder (excluding temporary files and hidden files)
    root_files_count = count_files_in_directory(destination_folder, ignore_files=['lib', '.TemporaryItems', '.Trashes'])
    for _ in range(root_files_count):
        progress.update(1)

def delete_empty_directories(directory, source_folder):
    source_subdirectories = set()
    for root, dirs, _ in os.walk(os.path.join(source_folder, "lib"), topdown=False):
        for d in dirs:
            source_subdirectories.add(os.path.relpath(os.path.join(root, d), source_folder))
    source_subdirectories.add('.Trashes');
    source_subdirectories.add('.TemporaryItems');

    deleted_directories = []
    for root, dirs, _ in os.walk(directory, topdown=False):
        for d in dirs:
            dir_path = os.path.join(root, d)
            rel_dir_path = os.path.relpath(dir_path, directory)
            if rel_dir_path != '.' and rel_dir_path not in source_subdirectories and not os.listdir(dir_path):
                try:
                    shutil.rmtree(dir_path)
                    deleted_directories.append(dir_path)
                except OSError:
                    pass

def handle_rmtree_error(func, path, exc_info):
    # Handle errors when deleting files/folders that might not exist
    # or have special characters in their names
    if not os.path.exists(path):
        return
    try:
        func(path)
    except OSError:
        pass

def ensure_lib_directory(destination_folder):
    lib_path = os.path.join(destination_folder, "lib")
    if not os.path.exists(lib_path):
        os.makedirs(lib_path)


def main():
    os.system('cls' if os.name == 'nt' else 'clear')

    destination_folder = get_circuitpy_drive()
    if destination_folder is None:
        print("CIRCUITPY drive not found. Exiting...")
        decision = input("Press Enter to exit... ").lower()
        sys.exit()

    print_welcome_message()

    if not is_drive_writable(destination_folder):
        print("CIRCUITPY drive is read-only. Please use Drive mode on the WiFiCom.")        
        decision = input("Press Enter to exit... ").lower()
        sys.exit()

    destination_folder = get_circuitpy_drive()
    circuitpython_version = read_circuitpython_version_from_boot_out(destination_folder)

    try:
        valid_releases = get_valid_releases()
        selected_option = get_user_option()
        all_releases = get_all_releases()
    except requests.exceptions.RequestException as e:
        print("Error: Internet connection is not available or could not connect to the server.")
    
        input("Press Enter to exit...")
        sys.exit()

    boot_out_path = os.path.join(destination_folder, "boot_out.txt")
    board_info = read_board_info(boot_out_path)
    board_id = extract_board_id(board_info)
    device_type = extract_device_type(board_id)

    try:
        selected_release, download_url = get_selected_release_and_url(selected_option, valid_releases, all_releases, device_type)

        temp_directory = tempfile.mkdtemp()

        zip_download = download_and_extract_latest(selected_release, download_url, temp_directory)
    except requests.exceptions.RequestException as e:
        print("Error: Internet connection is not available or could not connect to the server.")
        input("Press Enter to exit...")
        sys.exit()

    sources_json_path = os.path.join(temp_directory, 'sources.json')
    check_circuitpython_key(sources_json_path, board_id, device_type, circuitpython_version)

    ensure_lib_directory(destination_folder)

    copy_files_to_destination(destination_folder, temp_directory)

    shutil.rmtree(temp_directory)

    save_installed_commit_hash(selected_release.get('sha', selected_release.get('name', '')), destination_folder)

    print_success_message()

    input("Press Enter to exit...")


if __name__ == "__main__":
    main()
