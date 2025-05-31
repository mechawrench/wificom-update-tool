import os
import sys
import traceback
import webbrowser

from wificom_update_tool import drive
from wificom_update_tool import flash
from wificom_update_tool import github

try:
    from update_tool_version import UPDATE_TOOL_VERSION
except ImportError:
    UPDATE_TOOL_VERSION = None

def do_menu(options):
    for (number, description) in enumerate(options + ["Exit"], start=1):
        print(str(number) + ". " + description)
    print()
    exit_option = len(options) + 1
    while(True):
        choice_text = input("Enter a number to select an option: ")
        try:
            choice = int(choice_text)
        except ValueError:
            continue
        if choice >= 1 and choice < exit_option:
            break
        if choice == exit_option:
            sys.exit()
    print()
    return choice

def print_welcome_message():
    if UPDATE_TOOL_VERSION is None:
        version_string = "!"
    elif len(UPDATE_TOOL_VERSION) <= 16:
        version_string = f" {UPDATE_TOOL_VERSION}!"
    else:
        version_string = f"!\n    {UPDATE_TOOL_VERSION}"
    intro = f"""\033[32m
    Welcome to the WiFiCom Update/Installer Tool{version_string}

    This script will help you update your WiFiCom by downloading the
    latest version of the wificom-lib and updating the files on the
    CIRCUITPY drive. Keep in mind that your own files (secrets.py,
    config.py, and board_config.py) will not be affected.

    Let's get started!
    \033[0m"""
    print(intro)

def choose_wificom_version():
    selected_option = do_menu([
        "Install/Update to the latest release",
        "Install/Update to a specific release",
        "Install/Update from main",
        "Install/Update from a specific commit",
    ])
    if selected_option == 1:
        selected_release = github.get_latest_release()
        return selected_release["tag_name"]
    elif selected_option == 2:
        all_releases = github.get_supported_releases()
        selected_release = choose_specific_release(all_releases)
        return selected_release["tag_name"]
    elif selected_option == 3:
         selected_commit = github.get_specific_commit("main")
         return selected_commit["sha"]
    else:
        commit_hash = input("Enter the commit hash or branch name: ")
        selected_commit = github.get_specific_commit(commit_hash)
        return selected_commit["sha"]

def choose_specific_release(all_releases):
    print("\nAvailable releases:")
    options = [f"{release['name']} ({release['tag_name']})" for release in all_releases]
    selected_index = do_menu(options) - 1
    return all_releases[selected_index]

def extract_sources_info(sources_json, commit_ref, board_id):
    if "boards" in sources_json:
        file_stem = "wificom-firmware"
        if board_id in sources_json["boards"]:
            build_id = sources_json["boards"][board_id]
        else:
            build_id = "default"
        recommended_circuitpython = sources_json["builds"][build_id]["circuitpython"]
    else:
        file_stem = "wificom-lib"
        build_id = "picow" if board_id == "raspberry_pi_pico_w" else "nina"
        recommended_circuitpython = sources_json["circuitpython"][build_id]
    zip_url = f"https://wificom-lib.s3.amazonaws.com/archives/{file_stem}_{commit_ref}_{build_id}.zip"
    return (recommended_circuitpython, zip_url)

def check_circuitpython_version(actual, recommended, board_id):
    if actual != recommended:
        uf2_url = f"https://adafruit-circuit-python.s3.amazonaws.com/bin/{board_id}/en_US/adafruit-circuitpython-{board_id}-en_US-{recommended}.uf2"
        print(f"\nThe recommended CircuitPython version for this release is {recommended} while you have {actual} installed.")
        print("It is advised to upgrade/downgrade your CircuitPython version.")
        print("You can download the necessary UF2 file from here:")
        print(uf2_url)
        selected_option = do_menu([
            "Download UF2 file (opens in a browser)",
            "Continue anyway with currently-installed CircuitPython version",
        ])
        if selected_option == 1:
            webbrowser.open_new_tab(uf2_url)
            sys.exit()
        else:
            return

def check_board_config(destination_folder):
    board_config_path = os.path.join(destination_folder, "board_config.py")
    if not os.path.exists(board_config_path):
        return
    with open(board_config_path) as f:
        board_config_text = f.read()
    if "wificom" in board_config_text:
        return
    print("It looks like you have an incompatible board_config.py")
    print("If you are using the default pins, you can safely delete it.")
    selected_option = do_menu(["Delete board_config.py"])
    if selected_option == 1:
        os.remove(board_config_path)

def save_installed_commit_hash(commit_hash, destination_folder):
    installed_version_file = os.path.join(destination_folder, "wificom_installed_version.txt")
    with open(installed_version_file, "w") as f:
        f.write(commit_hash)

def print_success_message():
    success = """\033[32m
    Successfully installed/updated your WiFiCom!

    If you intend to use WiFi, ensure you've updated secrets.py
    If this is your first time:
      * Create an account and a "new WiFiCom" on wificom.dev
      * Go to "Credentials Download" on the page that appears,
        and follow the instructions there.

    Please eject (safely remove) the drive from your computer, then:
    * Full units in "Drive Mode": choose an option from the menu
    * Screenless units / "Dev Mode": disconnect and reconnect power
    \033[0m"""
    print(success)

def main():
    os.system("cls" if os.name == "nt" else "clear")
    print_welcome_message()
    destination_folder = drive.find_circuitpy_drive()
    if destination_folder is None:
        print("CIRCUITPY drive not found.")
        input("Press Enter to exit...")
        sys.exit()
    if not drive.is_drive_writable(destination_folder):
        print("CIRCUITPY drive is read-only. Please use Drive mode on the WiFiCom.")
        input("Press Enter to exit...")
        sys.exit()
    try:
        (circuitpython_version, board_id) = drive.read_boot_out(destination_folder)
    except (FileNotFoundError, ValueError) as e:
        print("Cannot read CircuitPython info: " + str(e))
        input("Press Enter to exit...")
        sys.exit()
    wificom_version = choose_wificom_version()
    sources_json = github.get_sources_json(wificom_version)
    (recommended_circuitpython, zip_url) = extract_sources_info(sources_json, wificom_version, board_id)
    check_circuitpython_version(circuitpython_version, recommended_circuitpython, board_id)
    check_board_config(destination_folder)
    print("Downloading and writing...")
    flash.run_flash(destination_folder, zip_url)
    save_installed_commit_hash(wificom_version, destination_folder)
    print_success_message()

def main_wrap():
    try:
        main()
    except KeyboardInterrupt:
        print("\nControl-C exits from console apps.")
    except Exception:
        print("An error occurred:\n")
        traceback.print_exc(limit=6, chain=False)
    input("\nPress Enter to exit...")

if __name__ == "__main__":
    main_wrap()
