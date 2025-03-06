from io import BytesIO
from enum import Enum
import configparser
import argparse
import platform
import requests
import hashlib
import zipfile
import shutil
import sys
import os

class ExitResult(Enum):
    BOPIMO_NOT_INSTALLED = -10
    FETCH_LATEST_FAILED = -9
    UPDATE_CHECK_FAILED = -8
    DOWNLOAD_FAILED = -7
    EXTRACTION_FAILED = -6
    UNINSTALL_FAILED = -5
    REINSTALL_FAILED = -4
    UPDATE_FAILED = -3
    INSTALL_FAILED = -2
    FAILED = -1
    SUCCESS = 0
    UNKNOWN = 1
    INSTALL_SUCCESS = 2
    UPDATE_SUCCESS = 3
    REINSTALL_SUCCESS = 4
    UNINSTALL_SUCCESS = 5
    UNCHANGED = 10

# Parser
parser = argparse.ArgumentParser(
    prog='Bopimod! Installer',
    description='Installs/Updates Bopimod. A Mod Loader for Bopimo! based on GUMM'
)
parser.add_argument('-s', '--silent', action='store_true')
parser.add_argument('-r', '--reinstall', action='store_true')
parser.add_argument('-u', '--uninstall', action='store_true')
parser.add_argument('--skip-bopistrap', action='store_true')
parser.add_argument('--quick-exit', action='store_true')
run_args = parser.parse_args()

INSTALLER_VERSION = "1.0.0"
LATEST_RELEASE_CHECKSUM = "edf957097e576a06760dd933c8c6395445b56236f7f2360b089858ff33417da7"
OS = platform.system()

# Paths
if OS == "Windows":
    PATH = os.path.join(os.environ["APPDATA"], "Bopimo!", "Client").replace("\\", "/")
elif OS == "Linux":
    PATH = os.path.join(os.environ["HOME"], ".local", "share", "Bopimo!", "Client").replace("\\", "/")

# Funcs
def fetch_latest_release(release_type="file"):
    response = requests.get("https://bopimod.com/latest_release.json")
    if response.status_code == 200:
        if release_type == "file":
            rzip = requests.get(response.json()["file"])
            if rzip.status_code == 200:
                file_content = rzip.content
                if hashlib.sha256(file_content).hexdigest() != LATEST_RELEASE_CHECKSUM:
                    sys.exit(ExitResult.DOWNLOAD_FAILED.value)
                return zipfile.ZipFile(BytesIO(file_content), "r")
            sys.exit(ExitResult.DOWNLOAD_FAILED.value)
        return response.json()["version"]
    sys.exit(ExitResult.FETCH_LATEST_FAILED.value)

def update_config(section, key, value):
    config_path = os.path.join(PATH, "override.cfg")
    config = configparser.ConfigParser()
    config.optionxform = str  # Preserve case sensitivity
    config.read(config_path)

    before = config.get(section, key, fallback=None)
    config.set(section, key, value)

    if before:
        print(f'Updated [{section}]: {key} = {value} (was {before})')
    else:
        print(f'Added [{section}]: {key} = {value}')

    with open(config_path, 'w') as configfile:
        config.write(configfile)

def get_config_section(section):
    config_path = os.path.join(PATH, "override.cfg")
    config = configparser.ConfigParser()
    config.optionxform = str
    config.read(config_path)
    return config[section]

def get_config_value(section, key):
    config_path = os.path.join(PATH, "override.cfg")
    config = configparser.ConfigParser()
    config.optionxform = str
    config.read(config_path)
    return config[section][key]

def has_bopistrap():
    if OS != "Windows":
        return False
    return os.path.exists(os.path.join(os.environ["LOCALAPPDATA"], "Bopistrap", "Client"))

def is_installed():
    return (
        os.path.exists(os.path.join(PATH, "override.cfg")) and
        os.path.exists(os.path.join(PATH, "GUMM_mod_loader.tscn"))
    )

def compare_versions(version_a, version_b):
    a = list(map(int, version_a.split('.')))
    b = list(map(int, version_b.split('.')))

    if a[0] < b[0]:
        return "Major"
    if a[1] < b[1]:
        return "Minor"
    if a[2] < b[2]:
        return "Patch"
    return None

def remove_file(path):
    if os.path.exists(path):
        os.remove(path)
        print(f'Removed file: {path}')

def remove_folder(path):
    if os.path.exists(path):
        shutil.rmtree(path)
        print(f'Removed folder: {path}')

def install(skip_bopistrap=False):
    modloader = fetch_latest_release("file")
    if modloader:
        print(f'Installing to "{PATH}"')
        modloader.extractall(PATH)
        update_config('application', 'run/main_scene', f'"{PATH}GUMM_mod_loader.tscn"')
        update_config('application', 'boot_splash/image', f'"{PATH}ModdedIcon.png"')

        if has_bopistrap() and not skip_bopistrap:
            bopistrap_client_path = os.path.join(os.environ["LOCALAPPDATA"], "Bopistrap", "Client").replace("\\", "/")
            print(f'Creating symlink for Bopistrap')
            remove_file(os.path.join(bopistrap_client_path, "override.cfg"))
            os.symlink(os.path.join(PATH, "override.cfg"), os.path.join(bopistrap_client_path, "override.cfg"), target_is_directory=False)

        return True
    return False

def update():
    autoloads = get_config_section('autoload')
    install(True)
    for autoload, value in autoloads.items():
        update_config("autoload", autoload, value)

def uninstall():
    if has_bopistrap():
        bopistrap_client_path = os.path.join(os.environ["LOCALAPPDATA"], "Bopistrap", "Client").replace("\\", "/")
        remove_file(os.path.join(bopistrap_client_path, "override.cfg"))

    remove_folder(os.path.join(PATH, "mods"))
    remove_file(os.path.join(PATH, "ModdedIcon.png"))
    remove_file(os.path.join(PATH, "override.cfg"))
    remove_file(os.path.join(PATH, "GUMM_mod_loader.tscn"))

# Main
def main():
    if not os.path.exists(PATH):
        print('Bopimo! is not installed.')
        sys.exit(ExitResult.BOPIMO_NOT_INSTALLED.value)

    if is_installed() and not run_args.reinstall:
        if not run_args.uninstall:
            print(f'Bopimo! Mod Loader Updater v{INSTALLER_VERSION}')
            bopimod_version = get_config_value("modloader", "version_string")[1:-1]
            latest_version = fetch_latest_release("version")

            print(f'Installed Version: v{bopimod_version}')
            print(f'Latest Version: v{latest_version}')

            update_type = compare_versions(bopimod_version.split('-')[0], latest_version)
            if update_type:
                print(f'New {update_type} update found!')
                update()
                print('Bopimod has been updated.')
                sys.exit(ExitResult.UPDATE_SUCCESS.value)
            else:
                print('No updates found.')
                sys.exit(ExitResult.UNCHANGED.value)

        print('Uninstalling Bopimod...')
        uninstall()
        print('Bopimod has been removed.')
        sys.exit(ExitResult.UNINSTALL_SUCCESS.value)

    if run_args.reinstall:
        print('Reinstalling Bopimod...')
        install()
        sys.exit(ExitResult.REINSTALL_SUCCESS.value)

    if not run_args.uninstall:
        print(f'Bopimo! Mod Loader Installer v{INSTALLER_VERSION}')
        install(run_args.skip_bopistrap)
        print('Bopimod has been installed.')
        sys.exit(ExitResult.INSTALL_SUCCESS.value)

    print('Nothing to uninstall. If there is an install, consider reinstalling the mod loader.')
    sys.exit(ExitResult.UNCHANGED.value)

if __name__ == "__main__":
    main()
