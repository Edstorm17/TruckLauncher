import json
import os
import platform
from pathlib import Path
import subprocess

BRAND = 'TLauncher'

def debug(st):
    if os.getenv("DEBUG") is not None:
        print(st)

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

def get_classpath(lib, mc_dir: Path):
    cp: list = []

    for i in lib["libraries"]:
        if not should_use_library(i):
            continue

        name = i["name"]
        if "@" in name:
            name, suffix = name.split("@")
        else:
            suffix = "jar"

        parts = name.split(":")
        lib_domain, lib_name, lib_version = parts[0:3]
        lib_path = mc_dir / "libraries" / Path(*lib_domain.split(".")) / lib_name / lib_version

        lib_file_base = f"{lib_name}-{lib_version}{''.join(map(lambda p: f'-{p}', parts[3:]))}"

        cp.append(lib_path / f'{lib_file_base}.{suffix}')

        native = get_natives_string(i)
        if native != "":
            cp.append(lib_path / f'{lib_file_base}-{native}.{suffix}')

    # Game Jar
    if "jar" in lib:
        cp.append(mc_dir / "versions" / lib["jar"] / f'{lib["jar"]}.jar')
    else:
        cp.append(mc_dir / "versions" / lib["id"] / f'{lib["id"]}.jar')
    return os.pathsep.join(str(p) for p in cp)

def launch(version, username, uuid, access_token):
    mc_dir = get_minecraft_path()
    natives_dir = mc_dir / "versions" / version / "natives"
    if not os.path.isfile(os.path.join(mc_dir, 'versions', version, f'{version}.json')):
        raise Exception("Version not found")
    with open(os.path.join(mc_dir, 'versions', version, f'{version}.json'), "r", encoding="utf-8") as f:
        client_json = json.load(f)

    class_path = get_classpath(client_json, mc_dir)
    main_class = client_json["mainClass"]
    version_type = client_json["type"]
    asset_index = client_json["assetIndex"]["id"]

    debug(class_path)
    debug(main_class)
    debug(version_type)
    debug(asset_index)

    subprocess.call([
        'java', # To check
        f'-Djava.library.path={natives_dir}',
        f'-Dminecraft.launcher.brand={BRAND}',
        '-Dminecraft.launcher.version=2.1',
        '-XX:HeapDumpPath=MojangTricksIntelDriversForPerformance_javaw.exe_minecraft.exe.heapdump',
        '-Xmx4G',
        '-cp',
        class_path,
        main_class,
        '--username',
        username,
        '--version',
        version,
        '--gameDir',
        mc_dir,
        '--assetsDir',
        os.path.join(mc_dir, 'assets'),
        '--assetIndex',
        asset_index,
        '--uuid',
        uuid,
        '--accessToken',
        access_token,
        '--versionType',
        'release'
    ])



