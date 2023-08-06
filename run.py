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


# GitHub API Functions

def get_readme_content(version):
    api_url = f"https://api.github.com/repos/mechawrench/wificom-lib/contents/README.md?ref={version}"
    response = requests.get(api_url).json()
    readme_content = requests.get(response['download_url']).text
    return readme_content

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

def get_recommended_circuitpython_version(sources_json_path, board_id, device_type):
    with open(sources_json_path, 'r') as f:
        sources = json.load(f)

    recommended_version = sources['circuitpython'].get('picow' if device_type == 'raspberry_pi_pico_w' else 'nina')
    return recommended_version

def compare_versions(version1, version2):
    return version_tuple(version1) >= version_tuple(version2)


# CircuitPython Functions

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


# File Handling Functions

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

def ensure_lib_directory(destination_folder):
    lib_path = os.path.join(destination_folder, "lib")
    if not os.path.exists(lib_path):
        os.makedirs(lib_path)


def copy_file_if_not_exists(src, dest):
    if not os.path.exists(dest):
        shutil.copy(src, dest)
    else:
        print(f"\nSkipping existing file: {os.path.basename(dest)}")

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
            if not any(file.startswith(ignore) for ignore in ignore_files):
                total_files += 1
    return total_files


# Download and Update Functions

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

def copy_files_to_destination(destination_folder, source_folder):
    lib_folder = os.path.join(destination_folder, 'lib')
    os.makedirs(lib_folder, exist_ok=True)

    source_to_dest_mapping = {}
    ignore_files = ["boot_out.txt", "secrets.py", "config.py", "board_config.py"]

    for root, _, files in os.walk(source_folder):
        for file in files:
            src_file = os.path.join(root, file)
            if root.startswith(os.path.join(source_folder, "lib")) and not any(file.startswith(ignore) for ignore in ignore_files):
                dest_file = os.path.join(destination_folder, os.path.relpath(src_file, source_folder))
                source_to_dest_mapping[src_file] = dest_file

    copied_files = []
    skipped_files = []

    total_files = len(source_to_dest_mapping)
    for src_file, dest_file in source_to_dest_mapping.items():
        dest_subdir = os.path.dirname(dest_file)
        os.makedirs(dest_subdir, exist_ok=True)

        if os.path.exists(dest_file) and os.path.isfile(dest_file) and os.path.isfile(src_file):
            skipped_files.append(dest_file)
        else:
            if os.path.isdir(src_file):
                shutil.copytree(src_file, dest_file, dirs_exist_ok=True)
            else:
                shutil.copy2(src_file, dest_file)
            copied_files.append(dest_file)

        print(f"Checking: {len(copied_files) + len(skipped_files)}/{total_files} files", end='\r')

    print("\nFile copying completed.")
    print(f"Total files copied: {len(copied_files)}")
    print(f"Total files skipped: {len(skipped_files)}")

    # Remove .py files in destination/libs/ if corresponding .mpy file exists in source/libs/ and lib/directory exists in source_folder/libs
    for root, _, files in os.walk(os.path.join(source_folder, "lib")):
        for file in files:
            if file.endswith(".mpy"):
                destination_file_path = os.path.join(lib_folder, os.path.relpath(root, os.path.join(source_folder, "lib")), file[:-4] + ".py")
                if os.path.exists(destination_file_path):
                    os.remove(destination_file_path)

    # Post-processing step to delete folders inside lib in the destination that don't exist in the source files
    for root, dirs, _ in os.walk(lib_folder, topdown=False):
        relative_path = os.path.relpath(root, lib_folder)
        if relative_path and not os.listdir(root):  # Check if the directory is empty and not the root lib folder
            shutil.rmtree(root)


# User Interaction Functions

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

def choose_specific_release(all_releases):
    print("\nAvailable releases:")
    for index, release in enumerate(all_releases):
        print(f"{index + 1}. {release['name']} ({release['tag_name']})")
    print("\n")
    selected_index = int(input("Select a release: ")) - 1
    return all_releases[selected_index]


# Helper Functions

def version_tuple(version_str):
    version_str = version_str.lstrip('v').split('-')[0]
    return tuple(map(int, (version_str.split("."))))

def print_download_progress(bytes_downloaded, total_bytes):
    progress = int((bytes_downloaded / total_bytes) * 100)
    print(f"Downloading: {progress}% ({bytes_downloaded}/{total_bytes} bytes)", end='\r')


# Main Function

def main():
    os.system('cls' if os.name == 'nt' else 'clear')

    destination_folder = get_circuitpy_drive()
    if destination_folder is None:
        print("CIRCUITPY drive not found. Exiting...")
        decision = input("Press Enter to exit...")
        sys.exit()

    print_welcome_message()

    sources_json_path = os.path.join(tempfile.gettempdir(), 'sources.json')
    shutil.copy2('sources.json', sources_json_path)

    # 1. Check if the board_info.txt file exists and extract the board_id
    board_info_path = os.path.join(destination_folder, 'board_info.txt')
    if os.path.exists(board_info_path):
        board_info = read_board_info(board_info_path)
        board_id = extract_board_id(board_info)
    else:
        print("board_info.txt not found in the CIRCUITPY drive. Exiting...")
        input("Press Enter to exit...")
        sys.exit()

    # 2. Fetch the recommended CircuitPython version from sources.json
    device_type = 'raspberry_pi_pico_w' if 'pico_w' in board_id else 'adafruit_nina_w'
    recommended_circuitpython_version = get_recommended_circuitpython_version(sources_json_path, board_id, device_type)

    # 3. Check the current CircuitPython version on the CIRCUITPY drive
    current_circuitpython_version = read_circuitpython_version_from_boot_out(destination_folder)
    print(f"Current CircuitPython version: {current_circuitpython_version}")

    # 4. Compare the current version with the recommended version
    if current_circuitpython_version:
        if compare_versions(current_circuitpython_version, recommended_circuitpython_version):
            print("\nYour CircuitPython version is up to date.")
            input("Press Enter to exit...")
            sys.exit()
    else:
        print("\nCould not determine the current CircuitPython version. Please ensure that CircuitPython is installed correctly on your device.")
        input("Press Enter to exit...")
        sys.exit()

    # 5. Fetch the latest and latest_pre-release from the GitHub repository
    latest_release, latest_pre_release = get_valid_releases()

    if not latest_release and not latest_pre_release:
        print("\nError: No releases found in the GitHub repository.")
        input("Press Enter to exit...")
        sys.exit()

    # 6. Determine the most recent release (latest_pre_release if available, otherwise latest_release)
    selected_release = latest_pre_release if latest_pre_release else latest_release
    selected_version_type = "Latest Pre-release" if latest_pre_release else "Latest Release"

    # 7. Display the selected release information
    print(f"\n{selected_version_type} - {selected_release['name']} ({selected_release['tag_name']})\n")
    print(f"Release Notes:\n{selected_release['body']}")

    # 8. Ask the user if they want to proceed with installation
    proceed_installation = input("\nDo you want to install/update to this release? (yes/no): ")
    if proceed_installation.lower() != 'yes':
        print("Exiting...")
        input("Press Enter to exit...")
        sys.exit()

    # 9. Download the wificom-lib archive for the selected release
    download_url = get_download_url_from_commit_hash(selected_release, device_type)
    temp_directory = tempfile.mkdtemp()

    try:
        archive_path = download_and_extract_latest(selected_release, download_url, temp_directory)
    except Exception as e:
        print("\nAn error occurred while downloading and extracting the latest release.")
        print("Error:", e)
        input("Press Enter to exit...")
        shutil.rmtree(temp_directory)
        sys.exit()

    # 10. Copy the necessary files to the CIRCUITPY drive
    try:
        copy_files_to_destination(destination_folder, temp_directory)
    except Exception as e:
        print("\nAn error occurred while copying the files to the CIRCUITPY drive.")
        print("Error:", e)
        input("Press Enter to exit...")
        shutil.rmtree(temp_directory)
        sys.exit()

    shutil.rmtree(temp_directory)

    print_success_message()
    input("Press Enter to exit...")

if __name__ == "__main__":
    main()
