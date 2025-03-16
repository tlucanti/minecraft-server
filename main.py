#!/bin/python3

from __future__ import annotations

import argparse
import datetime
import io
import json
import pathlib
import shlex
import subprocess
import yaml
from typing import NoReturn

SERVERS_FOLDER = "servers"
WORLDS_FOLDER = "worlds"
DATA_FOLDER = "data"

JAVA_THREADS = 1
JAVA_HEAP = "256M"
JAVA_MAX_HEAP = "1G"


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


class Requirements:
    def update_versions(self):
        def convert():
            d = {}
            for line in Cmd.freadlines("gist/minecraft-server-jar-downloads.md")[2:]:
                _, version, server, _, _ = line.split("|")
                if server.strip().lower() == "not found":
                    continue
                d[version.strip()] = server.strip()
            return Cmd.jdump(d, indent=4)

        cprint("yellow", "UPDATING VERSIONS")
        url = "https://gist.github.com/77a982a7503669c3e1acb0a0cf6127e9.git"
        Cmd.cmd("rm -rf gist")
        Cmd.cmd(f"git clone --depth=1 --progress {url} gist")
        Cmd.fwrite("versions.json", convert())
        Cmd.cmd("rm -rf gist")
        print()

    def download_prerequirements(self):
        cprint("yellow", "DOWNLOADING PREREQUIREMENTS")
        Cmd.cmd("sudo apt-get update")
        Cmd.cmd("sudo apt-get install -y openjdk-21-jdk-headless")
        print()

    def list_versions(self):
        cprint("yellow", "SUPPORTED VERSIONS")
        j = yaml.load(Cmd.fread("versions.json"))
        print("\n".join(j.keys()))

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


class Server:
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


def create_server(name: str, version: str) -> Server:
    cprint("yellow", f"CREATING SERVER {name}")
    folder = f"{WORLDS_FOLDER}/{name}"
    if pathlib.Path(folder).exists():
        FAIL(f'server "{name}" already exists')
        raise RuntimeError()

    Cmd.cmd(f"mkdir -p {folder}/{DATA_FOLDER}")
    Cmd.fwrite(f"{folder}/VERSION", version)

    OK(f'created server "{name}" with version "{version}"')
    print()

    return Server(name, version)


def find_server(name: str, announce=True) -> Server:
    if announce:
        cprint("yellow", f"FINDING SERVER {name}")

    folder = f"{WORLDS_FOLDER}/{name}"
    if not pathlib.Path(folder).exists():
        cprint("bred", f"server {name} does not exists")
        raise RuntimeError()

    version = Cmd.fread(f"{folder}/VERSION")

    OK(f'found server "{name}" with version "{version}"')
    if announce:
        print()

    return Server(name, version)


def save_server(name: str):
    cprint("yellow", f'SAVING SERVER "{name}"')
    server = find_server(name, announce=False)
    server.save()


def main():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers()

    create = subparsers.add_parser("create", help="create new server")
    create.add_argument("name")
    create.add_argument("version")
    create.set_defaults(action="create")

    run = subparsers.add_parser("run", help="run existing server")
    run.add_argument("name")
    run.set_defaults(action="run")

    save = subparsers.add_parser("save", help="save existing server to repository")
    save.add_argument("name")
    save.set_defaults(action="save")

    parser.add_argument("--list-versions", action="store_true")
    parser.add_argument("--update-versions", action="store_true")
    parser.add_argument("--prerequirements", action="store_true")

    args = parser.parse_args()
    print(args)

    req = Requirements()
    if args.update_versions:
        req.update_versions()
    if args.prerequirements:
        req.download_prerequirements()
    if args.list_versions:
        req.list_versions()
        return

    if args.action == "create":
        server = create_server(args.name, args.version)
    elif args.action == "save":
        save_server(args.name)
        return
    elif args.action == "run":
        server = find_server(args.name)
    else:
        ABORT(f"invalid action: {args.action}")

    req.download_server(server.version)

    if args.action != "run":
        return

    server.prepare()
    server.run()


if __name__ == "__main__":
    main()
