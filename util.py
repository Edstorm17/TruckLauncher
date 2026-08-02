import lzma
import stat
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import hashlib
import json
import platform
import shutil
from pathlib import Path

import requests

_JAVA_MANIFEST_URL = "https://launchermeta.mojang.com/v1/products/java-runtime/2ec0cc96c44e5a76b9c8b7c39df7210883d12871/all.json"

def read_json_file(filename: str):
    with open(filename, 'r') as f:
        return json.load(f)

def download_file(url: str, path: Path, sha1: str | None = None, lzma_compressed: bool | None = False, session: requests.Session | None = None, mc_dir: Path | None = None, overwrite: bool | None = False):
    if path.is_file() and not overwrite:
        if sha1 is None:
            return False
        elif get_sha1_hash(path) == sha1:
            return False

    print("Downloading from", url)

    try:
        Path.mkdir(path.parent, parents=True, exist_ok=True)
    except Exception:
        pass

    if session is None:
        r = requests.get(url, stream=True, headers={"user-agent": get_user_agent()})
    else:
        r = session.get(url, stream=True, headers={"user-agent": get_user_agent()})

    if r.status_code != 200:
        return False

    with open(path, 'wb') as f:
        r.raw.decode_content = True
        if lzma_compressed:
            f.write(lzma.decompress(r.content))
        else:
            shutil.copyfileobj(r.raw, f)

    if sha1 is not None:
        checksum = get_sha1_hash(path)
        if checksum != sha1:
            raise Exception("Invalid checksum", url, path, sha1, checksum)

    return True

_user_agent_cache = "truck-launcher"

def get_user_agent():
    global _user_agent_cache
    if _user_agent_cache is not None:
        return _user_agent_cache
    else:
        return ""

def get_sha1_hash(path: Path) -> str:
    buf_size = 65536
    sha1 = hashlib.sha1()
    with open(path, 'rb') as f:
        while True:
            data = f.read(buf_size)
            if not data:
                break
            sha1.update(data)
    return sha1.hexdigest()


def get_minecraft_path() -> Path:
    home = Path.home()
    if platform.system() == 'Windows':
        mc_dir = home / "AppData" / "Roaming" / ".minecraft"
    elif platform.system() == 'Darwin':
        mc_dir = home / "Library" / "Application Support" / "minecraft"
    elif platform.system() == 'Linux':
        mc_dir = home / ".minecraft"
    else:
        raise Exception("Unsupported platform")

    return mc_dir

def _get_java_platform_string() -> str:
    match platform.system():
        case "Windows":
            if platform.architecture()[0] == "32bit":
                return "windows-x86"
            else:
                return "windows-x64"
        case "Darwin":
            if platform.machine() == "arm64":
                return "mac-os-arm64"
            else:
                return "mac-os"
        case "Linux":
            if platform.architecture()[0] == "32bit":
                return "linux-i386"
            else:
                return "linux"
        case _:
            return "gamecore"

def install_java_runtime(java_version: str, mc_dir: Path, max_workers: int | None = None):
    manifest_data = requests.get(_JAVA_MANIFEST_URL, headers={"user-agent": get_user_agent()}).json()
    platform_string = _get_java_platform_string()

    if java_version not in manifest_data[platform_string]:
        raise Exception("Java version not found", java_version)

    if len(manifest_data[platform_string][java_version]) == 0:
        return

    platform_manifest = requests.get(manifest_data[platform_string][java_version][0]["manifest"]["url"], headers={"user-agent": get_user_agent()}).json()
    base_path = mc_dir / "runtime" / java_version / platform_string / java_version
    session = requests.session()
    file_list: list[str] = []

    def install_runtime_file(key: str, value):
        current_path = base_path / key

        if value["type"] == "file":
            if "lzma" in value["downloads"]:
                download_file(value["downloads"]["lzma"]["url"], current_path, sha1=value["downloads"]["raw"]["sha1"], session=session, lzma_compressed=True)
            else:
                download_file(value["downloads"]["raw"]["url"], current_path, sha1=value["downloads"]["raw"]["sha1"], session=session)

            if value["executable"]:
                current_path.chmod(current_path.stat().st_mode | stat.S_IEXEC)
            file_list.append(key)
        elif value["type"] == "link":
            current_path.parent.mkdir(parents=True, exist_ok=True)

            try:
                current_path.symlink_to(value["target"])
            except Exception:
                pass

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(install_runtime_file, key, value)
            for key, value in platform_manifest["files"].items()
        ]
        for future in futures:
            future.result()

    version_path = mc_dir / "runtime" / java_version / platform_string / ".version"
    with open(version_path, "w", encoding="utf-8") as f:
        f.write(manifest_data[platform_string][java_version][0]["version"]["name"])

    sha1_path = mc_dir / "runtime" / java_version / platform_string / f"{java_version}.sha1"
    with open(sha1_path, "w", encoding="utf-8") as f:
        for current_file in file_list:
            current_path = base_path / current_file
            ctime = current_path.stat().st_ctime_ns
            sha1 = get_sha1_hash(current_path)
            f.write(f"{current_file} /#// {sha1} {ctime}\n")

def get_executable_path(java_version: str, mc_directory):
    java_base_path = mc_directory / "runtime" / java_version / _get_java_platform_string() / java_version
    java_path = java_base_path / "bin" / "java.exe"
    if java_path.is_file():
        return java_path
    java_path = java_base_path / "jre.bundle" / "Contents" / "Home" / "bin" / "java.exe"
    if java_path.is_file():
        return java_path
    else:
        return None

def should_use_library(lib):
    def rule_says_yes(rule):
        use_lib = None

        if rule["action"] == "allow":
            use_lib = False
        elif rule["action"] == "disallow":
            use_lib = True

        if "os" in rule:
            for key, value in rule["os"].items():
                _os = platform.system()
                if key == "name":
                    if value == "windows" and _os != "Windows":
                        return use_lib
                    elif value == "osx" and _os != "Darwin":
                        return use_lib
                    elif value == "linux" and _os != "Linux":
                        return use_lib

        return not use_lib

    if not "rules" in lib:
        return True

    for i in lib["rules"]:
        if rule_says_yes(i):
            return True

    return False

def get_natives_string(lib):
    if platform.architecture()[0] == "64bit":
        arch = "64"
    elif platform.architecture()[0] == "32bit":
        arch = "32"
    else:
        raise Exception("Architecture not supported")

    natives_file = ""
    if not "natives" in lib:
        return natives_file

    if "windows" in lib["natives"] and platform.system() == "Windows":
        natives_file = lib["natives"]["windows"].replace("${arch}", arch)
    elif "osx" in lib["natives"] and platform.system() == "Darwin":
        natives_file = lib["natives"]["osx"].replace("${arch}", arch)
    elif "linux" in lib["natives"] and platform.system() == "Linux":
        natives_file = lib["natives"]["linux"].replace("${arch}", arch)
    else:
        raise Exception("Platform not supported")

    return natives_file

def get_vanilla_versions_list() -> list:
    versions_json = requests.get("https://launchermeta.mojang.com/mc/game/version_manifest_v2.json").json()
    return versions_json["versions"]

def get_fabric_versions_list() -> list:
    versions_json = requests.get("https://meta.fabricmc.net/v2/versions/game").json()
    return versions_json

def get_fabric_loader_list() -> list:
    loader_json = requests.get("https://meta.fabricmc.net/v2/versions/loader/").json()
    return loader_json

def get_installed_versions(mc_dir: Path) -> list:
    versions: list = []
    for version in (mc_dir / "versions").iterdir():
        if not (version / f"{version.name}.json").is_file():
            continue

        with open(version / f"{version.name}.json", "r", encoding="utf-8") as f:
            client_json = json.load(f)

        try:
            release_time = datetime.fromisoformat(client_json["releaseTime"])
        except ValueError:
            release_time = datetime.fromtimestamp(0)

        versions.append({"id": client_json["id"], "type": client_json["type"], "release_time": release_time})
    return versions
