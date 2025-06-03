import os
import requests
import shutil
import tempfile
import zipfile

def download_archive(url, save_path):
    response = requests.get(url, stream=True)
    response.raise_for_status()
    with open(save_path, "wb") as file:
        for chunk in response.iter_content(chunk_size=8192):
            file.write(chunk)

def extract_all_from_archive(archive_path, extract_path):
    with zipfile.ZipFile(archive_path, "r") as zip_ref:
        zip_ref.extractall(extract_path)

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
            if item in ("config.py", "board_config.py", "digiroms.txt"):
                if not os.path.exists(dst_item):
                    shutil.copy2(src_item, dst_item)
            else:
                shutil.copy2(src_item, dst_item)

def run_flash(target_directory, download_url):
    temp_directory = tempfile.mkdtemp()
    archive_path = os.path.join(temp_directory, "download.zip")
    download_archive(download_url, archive_path)
    extract_path = os.path.join(temp_directory, "extracted")
    extract_all_from_archive(archive_path, extract_path)
    copy_files_to_destination(target_directory, extract_path)
    shutil.rmtree(temp_directory)
