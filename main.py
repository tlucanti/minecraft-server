#!/bin/python3

from __future__ import annotations

from abc import abstractmethod, ABCMeta
import argparse
import datetime
import io
import json
import pathlib
import shlex
import subprocess
import yaml
from typing import NoReturn
from collections import OrderedDict

SERVERS_FOLDER = "cores"
WORLDS_FOLDER = "worlds"
DATA_FOLDER = "data"

JAVA_THREADS = 1
JAVA_HEAP = "256M"
JAVA_MAX_HEAP = "1G"

ACTION_CREATE = "CREATE"
ACTION_DELETE = "DELETE"
ACTION_RUN = "RUN"
ACTION_SAVE = "SAVE"
ACTION_LIST = "LIST"
ACTION_UPDATE_VERSIONS = "UPDATE_VERSIONS"
ACTION_LIST_VERSIONS = "LIST_VERSIONS"
ACTION_PREREQUIREMENTS = "PREREQUIREMENTS"

TYPE_VANILLA = "vanilla"
TYPE_FORGE = "forge"


def cprint(color, *args, **kwargs):
    color_table = {
        "red": "\033[0;31m",
        "green": "\033[0;32m",
        "yellow": "\033[0;33m",
        "blue": "\033[0;34m",
        "purple": "\033[0;35m",
        "cyan": "\033[0;36m",
        "white": "\033[0;37m",
        "bred": "\033[1;31m",
        "bgreen": "\033[1;32m",
        "byellow": "\033[1;33m",
        "bblue": "\033[1;34m",
        "bpurple": "\033[1;35m",
        "bcyan": "\033[1;36m",
        "bwhite": "\033[1;37m",
        "reset": "\033[0m",
    }
    print(color_table[color], end="")
    print(*args, **kwargs)
    print(color_table["reset"], end="", flush=True)


def INFO(*args, **kwargs):
    cprint("bblue", "[INFO]:", *args, **kwargs)


def OK(*args, **kwargs):
    cprint("bgreen", "[ OK ]:", *args, **kwargs)


def WARN(*args, **kwargs):
    cprint("byellow", "[WARN]:", *args, **kwargs)


def FAIL(*args, **kwargs):
    cprint("bred", "[FAIL]:", *args, **kwargs)


def ABORT(*args, **kwargs) -> NoReturn:
    cprint("bred", "[INTERNAL_ERROR]:", *args, **kwargs)
    raise RuntimeError()


class Cmd:
    @classmethod
    def fread(cls, fname: str, strip=True) -> str:
        with open(fname) as f:
            txt = f.read()
            if strip:
                txt = txt.strip()
            return txt

    @classmethod
    def freadlines(cls, fname: str, strip=True) -> list[str]:
        lines = Cmd.fread(fname, False).split("\n")
        if strip:
            lines = [l.strip() for l in lines]
        return lines

    @classmethod
    def fwrite(cls, fname: str, text: str):
        with open(fname, "w") as f:
            f.write(text)

    @classmethod
    def jload(cls, text: str) -> dict:
        return yaml.safe_load(io.StringIO(text))

    @classmethod
    def jdump(cls, data: dict, indent=None) -> str:
        return json.dumps(data, indent=indent)

    @classmethod
    def run(cls, cmd: str | list, strip=True) -> str:
        if isinstance(cmd, str):
            cmd = shlex.split(cmd)

        stdout = subprocess.run(cmd, text=True, capture_output=True, check=True).stdout
        if strip:
            stdout = stdout.strip()
        return stdout

    @classmethod
    def cmd(cls, cmd: str | list, check=True, cwd=None) -> int:
        if isinstance(cmd, str):
            cmd = shlex.split(cmd)
        cprint("green", f"> {' '.join(cmd)}")

        proc = subprocess.run(cmd, text=True, check=check, cwd=cwd)
        if check and proc.returncode != 0:
            FAIL(f'failed command "{cmd}"')
            raise subprocess.SubprocessError(f"command return code {proc.returncode}")
        else:
            return proc.returncode


class IRequirements(metaclass=ABCMeta):
    def download_prerequirements(self):
        cprint("yellow", "DOWNLOADING PREREQUIREMENTS")
        Cmd.cmd("sudo apt-get update")
        Cmd.cmd("sudo apt-get install -y openjdk-21-jdk-headless")
        print()

    @abstractmethod
    def update_versions(self):
        pass

    @abstractmethod
    def list_versions(self, show_snapshots: bool):
        pass

    @abstractmethod
    def download_server(self, version: str) -> str:
        pass

    def _filter_version(self, version: str) -> bool:
        split = version.split(".")
        if len(split) not in (2, 3):
            return True
        return not all(v.isdigit() for v in split)


class VanillaRequirements(IRequirements):
    def update_versions(self):
        def convert() -> str:
            d = OrderedDict()
            for line in Cmd.freadlines("gist/minecraft-server-jar-downloads.md")[2:]:
                _, version, url, _, _ = line.split("|")
                url = url.strip()
                version = version.strip()
                if url.lower() == "not found":
                    continue
                d[version] = url

            return Cmd.jdump(d, indent=4)

        cprint("yellow", "UPDATING VANILLA VERSIONS")
        url = "https://gist.github.com/77a982a7503669c3e1acb0a0cf6127e9.git"
        Cmd.cmd("rm -rf gist")
        Cmd.cmd(f"git clone --depth=1 --progress {url} gist")
        Cmd.fwrite("versions.vanilla.json", convert())
        Cmd.cmd("rm -rf gist")
        print()

    def list_versions(self, show_snapshots: bool):
        cprint("yellow", "SUPPORTED VANILLA VERSIONS")
        try:
            versions = Cmd.fread("versions.vanilla.json")
        except FileNotFoundError:
            FAIL("versions.vanilla.json not found. rerun with --update-versions")
            raise

        for line in reversed(versions.splitlines()[1:-1]):
            v = line.split(":", maxsplit=1)[0].replace('"', "").strip()
            if not show_snapshots and self._filter_version(v):
                continue
            print(v)

    def download_server(self, version: str) -> str:
        cprint("yellow", "GETTING SERVER JAR")
        Cmd.cmd(f"mkdir -p {SERVERS_FOLDER}")

        fname = f"{SERVERS_FOLDER}/{version}.jar"
        if pathlib.Path(fname).exists():
            OK(f'existing server: "{fname}"')
            print()
            return fname

        if not pathlib.Path("versions.json").exists():
            FAIL(f"versions.json not found. rerun with --update-versions")
            raise RuntimeError()
        versions = Cmd.jload(Cmd.fread("versions.json"))

        url = versions.get(version)
        if url is None:
            FAIL(f'version "{version}" not found')
            raise RuntimeError()

        INFO(f'downloading server "{fname}"')
        INFO(f"url: {url}")

        if Cmd.cmd(f'wget --verbose "{url}" -O "{fname}"', check=False):
            FAIL("FAILED TO DOWNLOAD SERVER")
            Cmd.cmd(f'rm -f "{fname}"')
            raise RuntimeError()

        print()
        return fname


class ForgeRequirements(IRequirements):
    def update_versions(self):
        cprint("yellow", "UPDATING FORGE VERSIONS")
        url = "https://files.minecraftforge.net/net/minecraftforge/forge/promotions_slim.json"
        versions_raw = Cmd.run(f"curl {url}")
        versions = Cmd.jload(versions_raw)

        filtered = OrderedDict()
        for version in reversed(versions["promos"]):
            ver, _ = version.split("-")
            if self._filter_version(ver):
                continue
            if f"{version}-recommended" in versions:
                filtered[version] = f"{version}-recommended"
            else:
                filtered[version] = f"{version}-latest"

        Cmd.fwrite("versions.forge.json", Cmd.jdump(filtered))
        print()

    def list_versions(self, show_snapshots: bool):
        cprint("yellow", "SUPPORTED FORGE VERSIONS")
        j = Cmd.jload(Cmd.fread("versions.forge.json"))
        print("\n".join(j.keys()))

    def download_server(self, version: str) -> str:
        return ""


def Requirements(launcher: str) -> IRequirements:
    if launcher == TYPE_VANILLA:
        return VanillaRequirements()
    elif launcher == TYPE_FORGE:
        return ForgeRequirements()
    else:
        ABORT(f"invalid launcher: {launcher}")


class IServer:
    def save(self):
        pass

    def prepare(self):
        pass

    def run(self):
        pass


class VanillaServer(IServer):
    def __init__(self, name: str, version: str):
        self.name = name
        self.version = version
        self.folder = f"{WORLDS_FOLDER}/{name}"

    def save(self):
        tz = datetime.timezone(datetime.timedelta(hours=3))
        message = f"{datetime.datetime.now(tz)} {self.name}"
        if not pathlib.Path(f"{WORLDS_FOLDER}/.git").exists():
            Cmd.cmd(f"git -C {WORLDS_FOLDER} init")
            Cmd.cmd(f"git -C {WORLDS_FOLDER} commit --allow-empty -m 'initial commit'")
        Cmd.cmd(f"git -C {WORLDS_FOLDER} add --all")
        Cmd.cmd(f'git -C {WORLDS_FOLDER} commit --allow-empty -m "{message}"')

    def prepare(self):
        def convert_config(config: dict[str, str]) -> str:
            return "\n".join(f"{key}={value}" for key, value in config.items())

        cprint("yellow", "PREPARE SERVER TO RUN")
        INFO("accepting eula")
        Cmd.fwrite(f"{self.folder}/{DATA_FOLDER}/eula.txt", "eula=true")

        local_config_fname = f"{self.folder}/config.json"
        server_properties_fname = f"{self.folder}/{DATA_FOLDER}/server.properties"

        base_config = Cmd.jload(Cmd.fread("server.properties.json"))
        global_config = Cmd.jload(Cmd.fread("config.json"))
        local_config = {}
        if pathlib.Path(local_config_fname).exists():
            local_config = Cmd.jload(Cmd.fread(local_config_fname))
        local_config |= {"level-name": self.name}

        # global config overrides base properties
        # local config overrides global config and base config
        config = base_config | global_config | local_config
        Cmd.fwrite(server_properties_fname, convert_config(config))
        print()

    def run(self):
        cprint("yellow", "RUNNING SERVER")

        cwd = f"{self.folder}/{DATA_FOLDER}"
        server = str(pathlib.Path(f"servers/{self.version}.jar").absolute())

        Cmd.cmd(
            [
                "java",
                "-server",
                "-XX:+UseParallelGC",
                f"-Xms{JAVA_HEAP}",
                f"-Xmx{JAVA_MAX_HEAP}",
                "-jar",
                server,
                "nogui",
            ],
            cwd=cwd,
        )


def ForgeServer(IServer):
    def __init__(self, name: str, version: str):
        pass


class ServerCreator:
    def create_server(self, launcher: str, name: str, version: str) -> IServer:
        cprint("yellow", f"CREATING {launcher.upper()} SERVER {name}")
        folder = f"{WORLDS_FOLDER}/{name}"
        if pathlib.Path(folder).exists():
            FAIL(f'server "{name}" already exists')
            raise RuntimeError()

        Cmd.cmd(f"mkdir -p {folder}/{DATA_FOLDER}")
        Cmd.fwrite(f"{folder}/VERSION", version)
        Cmd.fwrite(f"{folder}/TYPE", launcher)

        OK(f'created {launcher} server "{name}" with version "{version}"')
        print()

        if launcher == TYPE_VANILLA:
            return VanillaServer(name, version)
        elif launcher == TYPE_FORGE:
            return ForgeServer(name, version)
        else:
            ABORT(f"invalid launcher: {launcher}")

    def find_server(self, name: str, announce=True) -> IServer:
        if announce:
            cprint("yellow", f"FINDING SERVER {name}")

        folder = f"{WORLDS_FOLDER}/{name}"
        if not pathlib.Path(folder).exists():
            cprint("bred", f"server {name} does not exists")
            raise RuntimeError()

        version = Cmd.fread(f"{folder}/VERSION")
        launcher = Cmd.fread(f"{folder}/TYPE")

        OK(f'found {launcher} server "{name}" with version "{version}"')
        if announce:
            print()

        if launcher == TYPE_VANILLA:
            return VanillaServer(name, version)
        elif launcher == TYPE_FORGE:
            return ForgeServer(name, version)
        else:
            ABORT(f"invalid launcher: {launcher}")

    def list_servers(self):
        for server in pathlib.Path(WORLDS_FOLDER).iterdir():
            name = server.name
            version = Cmd.fread(f"{server}/VERSION")
            launcher = Cmd.fread(f"{server}/TYPE")
            print(f"{name} {launcher} {version}")

    def save_server(self, name: str):
        cprint("yellow", f'SAVING SERVER "{name}"')
        server = self.find_server(name, announce=False)
        server.save()

    def delete_server(self, name: str):
        cprint("yellow", f'DELETING SERVER "{name}"')
        server = self.find_server(name, announce=False)
        Cmd.cmd(f"rm -rf {server.folder}")


def main():
    def add_name_option(subparser):
        subparser.add_argument("--name", required=True)

    def add_launcher_option(subparser):
        subparser.add_argument(
            "--launcher", choices=["vanilla", "forge"], required=True
        )

    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(required=True)

    create = subparsers.add_parser("create", help="create new server")
    create.add_argument("--version", required=True)
    add_name_option(create)
    add_launcher_option(create)
    create.set_defaults(action=ACTION_CREATE)

    delete = subparsers.add_parser("delete", help="delete server")
    add_name_option(delete)
    delete.set_defaults(action=ACTION_DELETE)

    run = subparsers.add_parser("run", help="run existing server")
    add_name_option(run)
    run.set_defaults(action=ACTION_RUN)

    save = subparsers.add_parser("save", help="save existing server to repository")
    add_name_option(save)
    save.set_defaults(action=ACTION_SAVE)

    list_servers = subparsers.add_parser("list", help="list existing serveers")
    list_servers.set_defaults(action=ACTION_LIST)

    update_versions = subparsers.add_parser(
        "update-versions", help="update list of avaliable versions"
    )
    add_launcher_option(update_versions)
    update_versions.set_defaults(action=ACTION_UPDATE_VERSIONS)

    list_versions = subparsers.add_parser(
        "list-versions", help="list avaliable versions"
    )
    list_versions.add_argument(
        "--show-snapshots", action="store_true", help="also show snapshot versions"
    )
    add_launcher_option(list_versions)
    list_versions.set_defaults(action=ACTION_LIST_VERSIONS)

    prerequirements = subparsers.add_parser(
        "prerequirements", help="install prerequirements"
    )
    prerequirements.set_defaults(action=ACTION_PREREQUIREMENTS)

    args = parser.parse_args()

    creator = ServerCreator()

    if args.action == ACTION_CREATE:
        req = Requirements(args.launcher)
        server = creator.create_server(args.launcher, args.name, args.version)
        req.download_server(server.version)
        server.prepare()

    elif args.action == ACTION_DELETE:
        creator.delete_server(args.name)

    elif args.action == ACTION_RUN:
        server = creator.find_server(args.name)
        server.run()

    elif args.action == ACTION_SAVE:
        server = creator.find_server(args.name)
        server.save()

    elif args.action == ACTION_LIST:
        creator.list_servers()

    elif args.action == ACTION_UPDATE_VERSIONS:
        req = Requirements(args.launcher)
        req.update_versions()

    elif args.action == ACTION_LIST_VERSIONS:
        req = Requirements(args.launcher)
        req.list_versions(args.show_snapshots)

    elif args.action == ACTION_PREREQUIREMENTS:
        req = Requirements(args.launcher)
        req.download_prerequirements()

    else:
        ABORT(f"invalid action: {args.action}")


if __name__ == "__main__":
    main()
