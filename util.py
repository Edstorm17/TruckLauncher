import io
import lzma
import re
import stat
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import hashlib
import json
import platform
import shutil
from pathlib import Path
import xml.etree.ElementTree as ET
import zipfile

import requests
import unicodedata

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
    except FileExistsError:
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

def get_sha1_hash(file: Path | io.BufferedIOBase) -> str:
    buf_size = 65536
    sha1 = hashlib.sha1()
    def _get_hash(fi: io.BufferedIOBase):
        while True:
            data = fi.read(buf_size)
            if not data:
                break
            sha1.update(data)
        return sha1.hexdigest()

    if isinstance(file, io.BufferedIOBase):
        return _get_hash(file)
    else:
        with open(file, 'rb') as f:
            return _get_hash(f)

def extract_to_dest(zf: zipfile.ZipFile, filename: str, dest_path: Path):
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    with zf.open(filename) as source, open(dest_path, "wb") as target:
        target.write(source.read())

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

def rules_say_yes(rules):
    def rule_says_yes(rule):
        use = None

        if rule["action"] == "allow":
            use = False
        elif rule["action"] == "disallow":
            use = True

        if "os" in rule:
            for key, value in rule["os"].items():
                _os = platform.system()
                _arch = platform.architecture()[0]
                if key == "name":
                    if value == "windows" and _os != "Windows":
                        return use
                    elif value == "osx" and _os != "Darwin":
                        return use
                    elif value == "linux" and _os != "Linux":
                        return use
                elif key == "arch":
                    if value == "x86" and _arch != "32bit":
                        return use
                elif key == "version":
                    if not re.match(value, get_os_version()):
                        return use

        if "features" in rule:
            for key in rule["features"].keys():
                if key == "has_custom_resolution":
                    return use
                elif key == "is_demo_user":
                    return use
                elif key == "has_quick_plays_support":
                    return use
                elif key == "is_quick_play_singleplayer":
                    return use
                elif key == "is_quick_play_multiplayer":
                    return use
                elif key == "is_quick_play_realms":
                    return use

        return not use

    for i in rules:
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

def _get_lib_name_without_version(lib) -> str:
    return ":".join(lib["name"].split(":")[:-1])

def inherit_json(original_json: dict, mc_dir: Path) -> dict:
    inherit_version = original_json["inheritsFrom"]

    with open(mc_dir / "versions" / inherit_version / f"{inherit_version}.json", "r") as f:
        new_json = json.load(f)

    original_libs: dict[str, bool] = {}
    for current_lib in original_json.get("libraries", []):
        lib_name = _get_lib_name_without_version(current_lib)
        original_libs[lib_name] = True

    lib_list = original_json.get("libraries", [])
    for current_lib in new_json.get("libraries", []):
        lib_name = _get_lib_name_without_version(current_lib)
        if lib_name not in original_libs:
            lib_list.append(current_lib)

    new_json["libraries"] = lib_list

    for key, value in original_json.items():
        if key == "libraries":
            continue

        if isinstance(value, list) and isinstance(new_json.get(key, None), list):
            new_json[key] = value + new_json[key]
        elif isinstance(value, dict) and isinstance(new_json.get(key, None), dict):
            for a, b in value.items():
                if isinstance(b, list):
                    new_json[key][a] = b + new_json[key][a]
        else:
            new_json[key] = value

    return new_json

def get_vanilla_versions_list() -> list:
    versions_json = requests.get("https://launchermeta.mojang.com/mc/game/version_manifest_v2.json").json()
    return versions_json["versions"]

def get_fabric_versions_list() -> list:
    versions_json = requests.get("https://meta.fabricmc.net/v2/versions/game").json()
    return versions_json

def get_fabric_loader_list() -> list:
    loaders_json = requests.get("https://meta.fabricmc.net/v2/versions/loader").json()
    return loaders_json

def get_forge_versions() -> dict[str, list[str]]:
    versions_xml = ET.fromstring(requests.get("https://maven.minecraftforge.net/net/minecraftforge/forge/maven-metadata.xml").text)
    versions = [v.text for v in versions_xml.findall(".//version")]
    versions_dict = {}
    for version in versions:
        parts = version.split("-")
        game_ver = parts[0]
        loader_ver = "-".join(parts[1:])
        versions_dict[game_ver] = versions_dict.get(game_ver, []) + [loader_ver]
    return versions_dict

def sort_versions(versions: list[str]) -> list[str]:
    return sorted(versions, key=lambda x: [int(i) for i in x.split("-")[0].split("_")[0].split(".")], reverse=True)

def get_installed_versions(mc_dir: Path = get_minecraft_path()) -> list:
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

def get_launch_profiles(mc_dir: Path = get_minecraft_path()) -> list:
    path = mc_dir / "tlauncher" / "launch_profiles.json"
    if not path.is_file():
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def get_launch_profile_by_name(name: str) -> dict | None:
    return next((profile for profile in get_launch_profiles() if profile.get("profile_name") == name), None)

def add_launch_profile(name: str, version_id: str, mc_dir: Path = get_minecraft_path()):
    profiles = get_launch_profiles(mc_dir)

    profile_id = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    profile_id = profile_id.lower()
    profile_id = re.sub(r"[^a-z0-9-_.]", "-", profile_id)
    profile_id = re.sub(r"-+", "-", profile_id).strip("-")

    if not profile_id.strip():
        return False
    if any(profile.get("profile_id") == profile_id or profile.get("profile_name") == name for profile in profiles):
        return False

    profiles.append({
        "profile_name": name,
        "profile_id": profile_id,
        "version_id": version_id,
        "last_use_time": datetime.now().isoformat()
    })

    path = mc_dir / "tlauncher" / "launch_profiles.json"
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except FileExistsError:
        pass

    with open(path, "w", encoding="utf-8") as f:
        json.dump(profiles, f, indent=4)

    return True

def get_os_version() -> str:
    if platform.system() == "Windows":
        ver = sys.getwindowsversion()
        return f"{ver.major}.{ver.minor}"
    elif platform.system() == "Darwin":
        return ""
    else:
        return platform.uname().release