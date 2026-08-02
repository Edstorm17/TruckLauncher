import io
import json
import shutil
import zipfile
from pathlib import Path
from typing import Literal
import requests
from concurrent.futures import ThreadPoolExecutor

import util

def extract_natives_file(file: Path, extract_path: Path, extract_data: dict[Literal["exclude"], list[str]]):
    try:
        extract_path.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass

    with zipfile.ZipFile(file, "r") as zf:
        for i in zf.namelist():
            for e in extract_data["exclude"]:
                if i.startswith(e):
                    break
                else:
                    zf.extract(i, extract_path)

def install_libraries(id: str, libraries: list, mc_dir, max_workers: int | None = None):
    session = requests.Session()

    def download_library(lib):
        if not util.should_use_library(lib):
            return

        path = mc_dir / "libraries"
        if "url" in lib:
            if lib["url"].endswith("/"):
                download_url = lib["url"][:-1]
            else:
                download_url = lib["url"]
        else:
            download_url = "https://libraries.minecraft.net"

        try:
            lib_domain, lib_name, lib_version = lib["name"].split(":")[0:3]
        except ValueError:
            return

        path = path / Path(*lib_domain.split(".")) / lib_name / lib_version
        download_url += "/" + lib_domain.replace(".", "/")

        try:
            lib_version, extension = lib_version.split("@")
        except ValueError:
            extension = "jar"

        jar_file = f"{lib_name}-{lib_version}.{extension}"
        download_url = f"{download_url}/{lib_name}/{lib_version}/{jar_file}"
        native = util.get_natives_string(lib)

        if native != "":
            jar_file_native = f"{lib_name}-{lib_version}-{native}.jar"

        try:
            util.download_file(download_url, path / jar_file, session=session, mc_dir=mc_dir)
        except Exception:
            pass

        if "downloads" not in lib:
            if "extract" in lib:
                extract_natives_file(path / jar_file_native, mc_dir / "versions" / id / "natives", lib["extract"])
            return

        if "artifact" in lib["downloads"] and lib["downloads"]["artifact"]["url"] != "" and "path" in lib["downloads"]["artifact"]:
            util.download_file(lib["downloads"]["artifact"]["url"], mc_dir / "libraries" / lib["downloads"]["artifact"]["path"], sha1=lib["downloads"]["artifact"]["sha1"], session=session, mc_dir=mc_dir )
        if native != "":
            util.download_file(lib["downloads"]["classifiers"][native]["url"], path / jar_file_native, lib["downloads"]["classifiers"][native]["sha1"], session=session, mc_dir=mc_dir)
            extract_natives_file(path / jar_file_native, mc_dir / "versions" / id / "natives", lib.get("extract", {"exclude": []}))

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(download_library, lib) for lib in libraries]
        for future in futures:
            future.result()

def install_assets(client_json: dict, mc_dir: Path, max_workers: int | None = None):
    if "assetIndex" not in client_json:
        return

    session = requests.Session()

    util.download_file(client_json["assetIndex"]["url"], mc_dir / "assets" / "indexes" / f"{client_json["assets"]}.json", sha1=client_json["assetIndex"]["sha1"], session=session)
    with open(mc_dir / "assets" / "indexes" / f"{client_json['assets']}.json") as f:
        asset_data = json.load(f)

    assets = set(obj["hash"] for obj in asset_data["objects"].values())

    def download_asset(filehash: str):
        util.download_file(f"https://resources.download.minecraft.net/{filehash[:2]}/{filehash}", mc_dir / "assets" / "objects" / filehash[:2] / filehash, sha1=filehash, session=session, mc_dir=mc_dir)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(download_asset, filehash) for filehash in assets]
        for future in futures:
            future.result()

def install_version(version: str, mc_dir: Path, url: str | None = None, sha1: str | None = None):
    if url:
        util.download_file(url, mc_dir / "versions" / version / f"{version}.json", sha1=sha1, mc_dir=mc_dir)

    with open(mc_dir / "versions" / version / f"{version}.json", "r", encoding="utf-8") as f:
        client_json = json.load(f)

    install_libraries(client_json["id"], client_json["libraries"], mc_dir)
    install_assets(client_json, mc_dir)

    if "downloads" in client_json:
        util.download_file(client_json["downloads"]["client"]["url"], mc_dir / "versions" / client_json["id"] / f"{client_json["id"]}.jar", sha1=client_json["downloads"]["client"]["sha1"], mc_dir=mc_dir)

    if "javaVersion" in client_json:
        util.install_java_runtime(client_json["javaVersion"]["component"], mc_dir)

def install_vanilla_json(version: str, mc_dir: Path = util.get_minecraft_path()):
    vanilla_versions = util.get_vanilla_versions_list()
    for v in vanilla_versions:
        if v["id"] == version:
            util.download_file(v["url"], mc_dir / "versions" / version / f"{version}.json", v["sha1"])
            return
    raise Exception("Couldn't find version to install")

def install_fabric_json(mc_version: str, loader_version: str, mc_dir: Path = util.get_minecraft_path()):
    url = f"https://meta.fabricmc.net/v2/versions/loader/{mc_version}/{loader_version}/profile/json"

    print("Downloading from", url)
    r = requests.get(url, stream=True, headers={"user-agent": util.get_user_agent()})

    if r.status_code != 200:
        raise Exception("Error installing fabric version")

    client_json = r.json()
    path = mc_dir / "versions" / client_json["id"] / f"{client_json['id']}.json"

    try:
        Path.mkdir(path.parent, parents=True, exist_ok=True)
    except Exception:
        pass

    with open(path, "w") as f:
        buffer = io.StringIO(json.dumps(client_json))
        shutil.copyfileobj(buffer, f)

def install(version: str, mc_dir: Path = util.get_minecraft_path()):
    print("Installing Minecraft", version)
    if (mc_dir / "versions" / version / f"{version}.json").is_file():
        install_version(version, mc_dir)
        return
    versions = requests.get("https://launchermeta.mojang.com/mc/game/version_manifest_v2.json").json()
    for ver in versions["versions"]:
        if ver["id"] == version:
            install_version(version, mc_dir, url=ver["url"], sha1=ver["sha1"])
            return
    raise Exception("Version not found")