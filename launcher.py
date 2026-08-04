import json
import os
from pathlib import Path
import subprocess

import config
import util

def get_classpath(lib, mc_dir: Path):
    cp: list = []

    for i in lib["libraries"]:
        if "rules" in i and not util.rules_say_yes(i["rules"]):
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

def replace_arguments(
        arg: str,
        client_json,
        mc_dir: Path,
        natives_dir: Path,
        classpath: str,
        username: str,
        uuid: str,
        access_token: str,
        game_dir: Path,
) -> str:
    arg = arg.replace("${natives_directory}", str(natives_dir))
    arg = arg.replace("${launcher_name}", config.LAUNCHER_NAME)
    arg = arg.replace("${launcher_version}", config.VERSION)
    arg = arg.replace("${classpath}", classpath)
    arg = arg.replace("${auth_player_name}", username)
    arg = arg.replace("${version_name}", client_json["id"])
    arg = arg.replace("${game_directory}", str(game_dir))
    arg = arg.replace("${assets_root}", str(mc_dir / "assets"))
    arg = arg.replace("${assets_index_name}", client_json["assetIndex"]["id"])
    arg = arg.replace("${auth_uuid}", uuid)
    arg = arg.replace("${auth_access_token}", access_token)
    arg = arg.replace("${user_type}", "msa")
    arg = arg.replace("${version_type}", client_json["type"])
    arg = arg.replace("${user_properties}", "{}")
    arg = arg.replace("${resolution_width}", "854")
    arg = arg.replace("${resolution_height}", "480")
    arg = arg.replace("${game_assets}", str(mc_dir / "assets" / "virtual" / "legacy"))
    arg = arg.replace("${auth_session}", access_token)
    arg = arg.replace("${library_directory}", str(mc_dir / "libraries"))
    arg = arg.replace("${classpath_separator}", os.pathsep)
    return arg

def get_arguments_string(
        client_json: dict,
        mc_dir: Path,
        natives_dir: Path,
        classpath: str,
        username: str,
        uuid: str,
        access_token: str,
        game_dir: Path
) -> list[str]:
    arg_list: list[str] = []

    for arg in client_json["minecraftArguments"].split(" "):
        arg = replace_arguments(arg, client_json, mc_dir, natives_dir, classpath, username, uuid, access_token, game_dir)
        arg_list.append(arg)

    return arg_list

def get_arguments(
        args: list,
        client_json: dict,
        mc_dir: Path,
        natives_dir: Path,
        classpath: str,
        username: str,
        uuid: str,
        access_token: str,
        game_dir: Path
) -> list[str]:
    arg_list: list[str] = []
    for arg in args:
        if isinstance(arg, str):
            arg_list.append(replace_arguments(arg, client_json, mc_dir, natives_dir, classpath, username, uuid, access_token, game_dir))
        else:
            if "compatibilityRules" in arg and not util.rules_say_yes(arg["compatibilityRules"]):
                continue

            if "rules" in arg and not util.rules_say_yes(arg["rules"]):
                continue

            if isinstance(arg["value"], str):
                arg_list.append(replace_arguments(arg["value"], client_json, mc_dir, natives_dir, classpath, username, uuid, access_token, game_dir))
            else:
                for v in arg["value"]:
                    v = replace_arguments(v, client_json, mc_dir, natives_dir, classpath, username, uuid, access_token, game_dir)
                    arg_list.append(v)
    return arg_list

def launch(launch_profile: dict, username: str, uuid: str, access_token: str, mc_dir: Path = util.get_minecraft_path()):
    print("Launching Minecraft...")
    version = launch_profile["version_id"]
    if not (mc_dir / "versions" / version).is_dir():
        raise Exception(f"Version not found")

    with open(mc_dir / "versions" / version / f'{version}.json', "r", encoding="utf-8") as f:
        client_json = json.load(f)

    if "inheritsFrom" in client_json:
        client_json = util.inherit_json(client_json, mc_dir)

    class_path = get_classpath(client_json, mc_dir)
    natives_dir = mc_dir / "versions" / client_json["id"] / "natives"
    game_dir = mc_dir / "tlauncher" / launch_profile["profile_id"]

    command_args: list[str] = []
    if "javaVersion" in client_json:
        java_path = util.get_executable_path(client_json["javaVersion"]["component"], mc_dir)
        if java_path is None:
            command_args.append("java")
        else:
            command_args.append(java_path)
    else:
        command_args.append("java")

    if isinstance(client_json.get("arguments", None), dict):
        if "jvm" in client_json["arguments"]:
            command_args = command_args + get_arguments(client_json["arguments"]["jvm"], client_json, mc_dir, natives_dir, class_path, username, uuid, access_token, game_dir)
        else:
            command_args.append(f"-Djava.library.path={natives_dir}")
            command_args.append("-cp")
            command_args.append(class_path)
    else:
        command_args.append(f"-Djava.library.path={natives_dir}")
        command_args.append("-cp")
        command_args.append(class_path)

    command_args.append(client_json["mainClass"])

    if "minecraftArguments" in client_json:
        command_args = command_args + get_arguments_string(client_json, mc_dir, natives_dir, class_path, username, uuid, access_token, game_dir)
    else:
        command_args = command_args + get_arguments(client_json["arguments"]["game"], client_json, mc_dir, natives_dir, class_path, username, uuid, access_token, game_dir)

    subprocess.run(command_args, cwd=game_dir)