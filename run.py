import ctypes
import hashlib
import json
import os
import re
import requests
import shutil
import string
import sys
import tempfile
import webbrowser
import zipfile

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
    # Extract board ID using regular expression
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
        posix_drive_path = f"/run/media/{os.getlogin()}/CIRCUITPY"
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
            test_file = os.path.join(drive_path, 'wificom_updater_test.txt')
            with open(test_file, 'w') as f:
                f.write('test')
            os.remove(test_file)
            return True
        except PermissionError:
            return False
    else:
        return os.access(drive_path, os.W_OK)

def download_archive(url, save_path):
    response = requests.get(url, stream=True)
    response.raise_for_status()

    with open(save_path, "wb") as file:
        for chunk in response.iter_content(chunk_size=8192):
            file.write(chunk)

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
        sys.exit()

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
            uf2_url = f"https://adafruit-circuit-python.s3.amazonaws.com/bin/{board_id}/en_US/adafruit-circuitpython-{board_id}-en_US-{recommended_circuitpython_version}.uf2"
            print(f"\nThe recommended CircuitPython version for this release is {recommended_circuitpython_version} while you have {circuitpython_version} installed.")
            print("It is advised to upgrade/downgrade your CircuitPython version.")
            print("You can download the necessary UF2 file from here:")
            print(uf2_url)
            print("\n1. Download UF2 file (opens in a browser)")
            print("2. Continue anyway with currently-installed CircuitPython version")
            print("3. Exit")
            selected_option = int(input("\nSelect an option: "))
            if selected_option == 1:
                webbrowser.open_new_tab(uf2_url)
                sys.exit()
            elif selected_option == 2:
                return
            else:
                sys.exit()

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
    Successfully installed/updated your WiFiCom!

    Ensure you've updated secrets.py before getting started.
    If this is your first time:
      * Create an account and a "new WiFiCom" on wificom.dev
      * Go to "Credentials Download" on the page that appears,
        and follow the instructions there.

    Please eject (safely remove) the drive from your computer, then:
    * Full units in "Drive Mode": choose an option from the menu
    * Screenless units / "Dev Mode": disconnect and reconnect power
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

def get_selected_release_and_url(selected_option, device_type):
    download_url = None
    selected_release = None

    if selected_option == 1:
        latest_release, latest_pre_release = get_valid_releases()
        selected_release = latest_release
    elif selected_option == 2:
        all_releases = get_all_releases()
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

def extract_all_from_archive(archive_path, extract_path):
    with zipfile.ZipFile(archive_path, 'r') as zip_ref:
        zip_ref.extractall(extract_path)

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

def copy_files_to_destination(destination_folder, extract_path):
    src_lib_folder = os.path.join(extract_path, "lib")
    dst_lib_folder = os.path.join(destination_folder, "lib")

    for item_name in os.listdir(src_lib_folder):
        src_item = os.path.join(src_lib_folder, item_name)
        dst_item = os.path.join(dst_lib_folder, item_name)
        if os.path.isdir(src_item):
            if os.path.exists(dst_item):
                shutil.rmtree(dst_item, ignore_errors=True)
            shutil.copytree(src_item, dst_item)
        elif os.path.isfile(src_item):
            shutil.copy2(src_item, dst_item)

    for item in os.listdir(extract_path):
        src_item = os.path.join(extract_path, item)
        dst_item = os.path.join(destination_folder, item)
        if os.path.isfile(src_item):
            if item in ('config.py', 'board_config.py'):
                if not os.path.exists(dst_item):
                    shutil.copy2(src_item, dst_item)
            else:
                shutil.copy2(src_item, dst_item)


def main():
    os.system('cls' if os.name == 'nt' else 'clear')
    print_welcome_message()

    destination_folder = get_circuitpy_drive()
    if destination_folder is None:
        print("CIRCUITPY drive not found.")
        input("Press Enter to exit...")
        sys.exit()
    if not is_drive_writable(destination_folder):
        print("CIRCUITPY drive is read-only. Please use Drive mode on the WiFiCom.")
        input("Press Enter to exit...")
        sys.exit()

    circuitpython_version = read_circuitpython_version_from_boot_out(destination_folder)

    selected_option = get_user_option()

    print("Checking...")
    boot_out_path = os.path.join(destination_folder, "boot_out.txt")
    board_info = read_board_info(boot_out_path)
    board_id = extract_board_id(board_info)
    device_type = extract_device_type(board_id)

    selected_release, download_url = get_selected_release_and_url(selected_option, device_type)

    temp_directory = tempfile.mkdtemp()
    archive_path = download_archive(download_url, os.path.join(temp_directory, selected_release.get('sha', selected_release.get('name', '')).replace('/', '_')))
    extract_path = os.path.join(temp_directory, "extracted")
    extract_all_from_archive(archive_path, extract_path)

    sources_json_path = os.path.join(extract_path, 'sources.json')
    check_circuitpython_key(sources_json_path, board_id, device_type, circuitpython_version)

    print("Writing...")
    copy_files_to_destination(destination_folder, extract_path)

    shutil.rmtree(temp_directory)

    save_installed_commit_hash(selected_release.get('sha', selected_release.get('name', '')), destination_folder)

    print_success_message()

    input("Press Enter to exit...")

if __name__ == "__main__":
    main()
