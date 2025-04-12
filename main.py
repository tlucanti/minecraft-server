#!/bin/python3

from __future__ import annotations

import argparse
import datetime
import io
import json
import os
import pathlib
import shlex
import subprocess
import yaml
import time
from abc import abstractmethod, ABCMeta
from collections import OrderedDict
from typing import NoReturn

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
ACTION_STOP = "STOP"
ACTION_KILL = "KILL"
ACTION_LIST = "LIST"
ACTION_LIST_RUNNING = "LIST_RUNNING"
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
    def fappend(cls, fname: str, text: str):
        with open(fname, "a") as f:
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
        cprint("yellow", "GETTING VANILLA SERVER JAR")
        folder = f"{SERVERS_FOLDER}/{TYPE_VANILLA}"
        Cmd.cmd(f"mkdir -p {folder}")

        fname = f"{folder}/{version}.jar"
        if pathlib.Path(fname).exists():
            OK(f'existing server: "{fname}"')
            print()
            return fname

        if not pathlib.Path(f"versions.{TYPE_VANILLA}.json").exists():
            FAIL(f"versions.{TYPE_VANILLA}.json not found. run update-versions command")
            raise RuntimeError()
        versions = Cmd.jload(Cmd.fread(f"versions.{TYPE_VANILLA}.json"))

        url = versions.get(version)
        if url is None:
            FAIL(f'version "{version}" not found. run list-versions command')
            raise RuntimeError()

        INFO(f'downloading {TYPE_VANILLA} server "{fname}"')
        INFO(f"url: {url}")

        if Cmd.cmd(f'wget --verbose "{url}" -O "{fname}"', check=False):
            FAIL("FAILED TO DOWNLOAD VANILLA SERVER")
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


class IServer(metaclass=ABCMeta):
    def __init__(self):
        self.name = None
        self.version = None
        self.launcher = None
        self.folder = None

    @abstractmethod
    def save(self):
        pass

    @abstractmethod
    def prepare(self):
        pass

    @abstractmethod
    def run(self, log_to_stdout: bool):
        pass

    @abstractmethod
    def stop(self, kill: bool = False):
        pass

    @abstractmethod
    def is_running(self) -> bool:
        pass


class VanillaServer(IServer):
    def __init__(self, name: str, version: str):
        self.name = name
        self.version = version
        self.launcher = TYPE_VANILLA
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

    def run(self, log_to_stdout=False):
        cprint("yellow", "PREPARE VANILLA ENVIROMENT")

        if self.is_running():
            FAIL(f'server "{self.name}" already running')
            raise RuntimeError()

        stdin_fname = f"{self.folder}/stdin.fifo"
        stdout_fname = f"{self.folder}/stdout.log"
        history_fname = f"{self.folder}/history.txt"
        core_fname = str(
            pathlib.Path(
                f"{SERVERS_FOLDER}/{TYPE_VANILLA}/{self.version}.jar"
            ).absolute()
        )
        FAIL(self.version)
        FAIL(core_fname)

        Cmd.cmd(f"rm -f {stdin_fname}")
        Cmd.cmd(f"mkfifo {stdin_fname}")
        Cmd.cmd(f"touch {history_fname}")

        print()
        cprint("yellow", "RUNNING COMMAND KEEPER PROCESS")

        stdin_fd = os.open(stdin_fname, os.O_RDWR | os.O_NONBLOCK)
        stdin_pipe = os.fdopen(stdin_fd, "r")

        stdin_keeper = subprocess.Popen(
            ["tail", "-n0", "-f", history_fname],
            stdout=open(stdin_fname, "w"),
            text=True,
            start_new_session=True,
            close_fds=True,
        )
        Cmd.fwrite(f"{self.folder}/KEEPER_PID", str(stdin_keeper.pid))
        OK(f"command keeper started with pid {stdin_keeper.pid}")

        print()
        cprint("yellow", "RUNNING SERVER PROCESS")
        if log_to_stdout:
            stdout = None
            stderr = None
        else:
            stdout = open(stdout_fname, "w")
            stderr = subprocess.STDOUT
        FAIL(core_fname)
        server_proc = subprocess.Popen(
            [
                "java",
                "-server",
                "-XX:+UseParallelGC",
                f"-Xms{JAVA_HEAP}",
                f"-Xmx{JAVA_MAX_HEAP}",
                "-jar",
                core_fname,
                "nogui",
            ],
            cwd=f"{self.folder}/{DATA_FOLDER}",
            stdin=stdin_pipe,
            stdout=stdout,
            stderr=stderr,
            text=True,
            start_new_session=True,
            close_fds=True,
        )
        Cmd.fwrite(f"{self.folder}/PID", str(server_proc.pid))
        OK(f"server started with pid {stdin_keeper.pid}")

    def stop(self, kill=False):
        server_exists = pathlib.Path(f"{self.folder}/PID").exists()
        keeper_exists = pathlib.Path(f"{self.folder}/KEEPER_PID").exists()

        if not kill and not self.is_running():
            FAIL(f"server {self.name} is not running")
            raise RuntimeError()

        if server_exists:
            pid = Cmd.fread(f"{self.folder}/PID")
            if kill:
                cprint("red", "KILLING SERVER")
                INFO(f"found server process with pid {pid}")
                Cmd.cmd(f"kill {pid}", check=False)
            else:
                cprint("yellow", "STOPPING SERVER")
                INFO(f"found server process with pid {pid}")
                self.send_cmd("/stop")
            Cmd.cmd(f"rm {self.folder}/PID")
        else:
            WARN("server process not running")

        time.sleep(5)
        if keeper_exists:
            if kill:
                cprint("red", "KILLING KEEPER PROCESS")
            else:
                cprint("yellow", "STOPPING KEEPER PROCESS")
            print()
            keeper_pid = Cmd.fread(f"{self.folder}/KEEPER_PID")
            INFO(f"found keeper process with pid {keeper_pid}")
            Cmd.cmd(f"kill {keeper_pid}", check=False)
            Cmd.cmd(f"rm {self.folder}/KEEPER_PID")
        else:
            WARN("keeper process not running")

    def send_cmd(self, cmd: str):
        INFO(f'sending command "{cmd}" to server {self.name}')
        Cmd.fappend(f"{self.folder}/history.txt", cmd)

    def is_running(self):
        server_exists = pathlib.Path(f"{self.folder}/PID").exists()
        keeper_exists = pathlib.Path(f"{self.folder}/KEEPER_PID").exists()
        return server_exists or keeper_exists


def ForgeServer(IServer):
    def __init__(self, name: str, version: str):
        pass


class ServerCreator:
    def iter_servers(self):
        for server in pathlib.Path(WORLDS_FOLDER).iterdir():
            yield self.get(server.name)

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

        return self.get(name)

    def get(self, name: str) -> IServer:
        folder = f"{WORLDS_FOLDER}/{name}"
        if not pathlib.Path(folder).exists():
            FAIL(f"server {name} does not exists")
            raise RuntimeError()

        version = Cmd.fread(f"{folder}/VERSION")
        launcher = Cmd.fread(f"{folder}/TYPE")

        if launcher == TYPE_VANILLA:
            return VanillaServer(name, version)
        elif launcher == TYPE_FORGE:
            return ForgeServer(name, version)
        else:
            ABORT(f"invalid launcher: {launcher}")

    def find_server(self, name: str, announce=True) -> IServer:
        if announce:
            cprint("yellow", f'FINDING SERVER "{name}"')

        server = self.get(name)
        OK(
            f'found {server.launcher} server "{server.name}" with version "{server.version}"'
        )
        print()
        return server

    def list_servers(self):
        for server in self.iter_servers():
            if server.is_running():
                running = "server running"
            else:
                running = "server not running"
            print(f"{server.name} {server.launcher} {server.version} ({running})")

    def list_running_servers(self):
        pass

    def save_server(self, name: str):
        cprint("yellow", f'SAVING SERVER "{name}"')
        server = self.find_server(name, announce=False)
        server.save()

    def delete_server(self, name: str, force: bool = False):
        cprint("yellow", f'DELETING SERVER "{name}"')
        server = self.find_server(name, announce=False)
        if server.is_running():
            if force:
                WARN("deleting running server")
                server.stop(kill=True)
            else:
                FAIL("cannot delete running server. stop or kill it first")
                raise RuntimeError()
        Cmd.cmd(f"rm -rf {server.folder}")
        OK(f"deleted server {name}")


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
    delete.add_argument("--force", action="store_true")
    add_name_option(delete)
    delete.set_defaults(action=ACTION_DELETE)

    run = subparsers.add_parser("run", help="run existing server")
    run.add_argument("--log-to-stdout", action="store_true")
    add_name_option(run)
    run.set_defaults(action=ACTION_RUN)

    save = subparsers.add_parser("save", help="save existing server to repository")
    add_name_option(save)
    save.set_defaults(action=ACTION_SAVE)

    stop = subparsers.add_parser("stop", help="stop running server")
    add_name_option(stop)
    stop.set_defaults(action=ACTION_STOP)

    kill = subparsers.add_parser("kill", help="kill running server without saving")
    add_name_option(kill)
    kill.set_defaults(action=ACTION_KILL)

    list_servers = subparsers.add_parser("list", help="list existing serveers")
    list_servers.set_defaults(action=ACTION_LIST)

    list_running = subparsers.add_parser("ps", help="list running servers")
    list_running.set_defaults(action=ACTION_LIST_RUNNING)

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
        creator.delete_server(args.name, args.force)

    elif args.action == ACTION_RUN:
        server = creator.find_server(args.name)
        server.run(log_to_stdout=args.log_to_stdout)

    elif args.action == ACTION_SAVE:
        server = creator.find_server(args.name)
        server.save()

    elif args.action == ACTION_STOP:
        server = creator.find_server(args.name)
        server.stop()

    elif args.action == ACTION_KILL:
        server = creator.find_server(args.name)
        server.stop(kill=True)

    elif args.action == ACTION_LIST:
        creator.list_servers()

    elif args.action == ACTION_LIST_RUNNING:
        creator.list_running_servers()

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
