import json
import os
import platform
from pathlib import Path
import subprocess
import util

BRAND = 'TLauncher'

def debug(st):
    if os.getenv("DEBUG") is not None:
        print(st)

def get_classpath(lib, mc_dir: Path):
    cp: list = []

    for i in lib["libraries"]:
        if not util.should_use_library(i):
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

        native = util.get_natives_string(i)
        if native != "":
            if "downloads" in i and "path" in i["downloads"]["classifiers"][native]:
                cp.append(mc_dir / "libraries" / i["downloads"]["classifiers"][native]["path"])
            else:
                cp.append(lib_path / f'{lib_file_base}-{native}.{suffix}')

    # Game Jar
    if "jar" in lib:
        cp.append(mc_dir / "versions" / lib["jar"] / f'{lib["jar"]}.jar')
    else:
        cp.append(mc_dir / "versions" / lib["id"] / f'{lib["id"]}.jar')
    return os.pathsep.join(str(p) for p in cp)

def launch(version, username, uuid, access_token):
    print("Launching Minecraft...")
    mc_dir = util.get_minecraft_path()
    if not os.path.isdir(mc_dir / "versions" / version):
        raise Exception(f"Version not found")

    with open(mc_dir / "versions" / version / f'{version}.json', "r", encoding="utf-8") as f:
        client_json = json.load(f)

    if "javaVersion" in client_json:
        java_path = util.get_executable_path(client_json["javaVersion"]["component"], mc_dir)
        if java_path is None:
            java_path = "java"
    else:
        java_path = "java"

    natives_dir = mc_dir / "versions" / client_json["id"] / "natives"
    class_path = get_classpath(client_json, mc_dir)
    main_class = client_json["mainClass"]
    version_type = client_json["type"]
    asset_index = client_json["assetIndex"]["id"]

    debug(class_path)
    debug(main_class)
    debug(version_type)
    debug(asset_index)

    print(java_path)
    subprocess.call([
        java_path,
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
        'release',
        '--userType',
        'msa'
    ])



