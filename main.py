#!/bin/python3

from __future__ import annotations

import shlex
import subprocess
import json
import argparse
import pathlib
from typing import Any

SERVERS_FOLDER = "servers"
WORLDS_FOLDER = "worlds"


def cprint(color, *args, **kwargs):
    color_table = {
        "black": "\033[0;30m",
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
    def run(cls, cmd: str | list, strip=True) -> str:
        if isinstance(cmd, str):
            cmd = shlex.split(cmd)

        stdout = subprocess.run(cmd, text=True, capture_output=True, check=True).stdout
        if strip:
            stdout = stdout.strip()
        return stdout

    @classmethod
    def cmd(cls, cmd: str | list, check=True) -> int:
        if isinstance(cmd, str):
            cmd = shlex.split(cmd)
        cprint("green", f"> {' '.join(cmd)}")

        proc = subprocess.run(cmd, text=True, check=check)
        if check and proc.returncode != 0:
            cprint("bred", f'[FAIL]:failed command "{cmd}"')
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
            return json.dumps(d, indent=4)

        cprint("yellow", "UPDATING VERSIONS")
        url = "https://gist.github.com/77a982a7503669c3e1acb0a0cf6127e9.git"
        Cmd.cmd("rm -rf gist")
        Cmd.cmd(f"git clone --depth=1 --progress {url} gist")
        Cmd.fwrite("versions.json", convert())
        Cmd.cmd("rm -rf gist")
        print()

    def download_prerequirements(self):
        cprint("yellow", "DOWNLOADING PREREQUIREMENTS")
        Cmd.cmd("apt-get update")
        Cmd.cmd("apt-get install -y openjdk-21-jdk-headless")
        print()

    def list_versions(self):
        cprint("yellow", "SUPPORTED VERSIONS")
        j = json.loads(Cmd.fread("versions.json"))
        print("\n".join(j.keys()))

    def download_server(self, version: str) -> str:
        cprint("yellow", "GETTING SERVER JAR")
        Cmd.cmd(f"mkdir -p {SERVERS_FOLDER}")

        fname = f"{SERVERS_FOLDER}/{version}.jar"
        if pathlib.Path(fname).exists():
            cprint("bgreen", f'[ OK ]: existing server: "{fname}"')
            print()
            return fname

        if not pathlib.Path("versions.json").exists():
            cprint(
                "bred", f"[FAIL]: versions.json not found. rerun with --update-versions"
            )
            raise RuntimeError()
        versions = json.loads(Cmd.fread("versions.json"))

        url = versions.get(version)
        if url is None:
            cprint("bred", f'[FAIL]: version "{version}" not found')
            raise RuntimeError()

        cprint("bblue", f'[INFO]: downloading server "{fname}"')
        cprint("bblue", f"[INFO]: url: {url}")

        if Cmd.cmd(f'wget --verbose "{url}" -O "{fname}"', check=False):
            cprint("bred", f"[FAIL]: FAILED TO DOWNLOAD SERVER")
            Cmd.cmd(f'rm -f "{fname}"')
            raise RuntimeError()

        print()
        return fname


class Server:
    def __init__(self, name: str, version: str):
        self.name = name
        self.version = version
        self.folder = f"{WORLDS_FOLDER}/{name}"

    def accept_eula(self):
        cprint("yellow", "ACCEPTING EULA")
        Cmd.fwrite(f"{self.folder}/eula.txt", "eula=true")
        print()


def create_server(args: Any) -> Server:
    cprint("yellow", f"CREATING SERVER {args.name}")
    folder = f"{WORLDS_FOLDER}/{args.name}"
    if pathlib.Path(folder).exists():
        cprint("bred", f'[FAIL]: "server {args.name} already exists')
        raise RuntimeError()

    Cmd.cmd(f"mkdir -p {folder}")
    Cmd.fwrite(f"{folder}/VERSION", args.version)

    cprint(
        "green", f'[ OK ]: created server "{args.name}" with version "{args.version}"'
    )
    print()

    return Server(args.name, args.version)


def find_server(args: Any) -> Server:
    cprint("yellow", f"FINDING SERVER {args.name}")
    folder = f"{WORLDS_FOLDER}/{args.name}"
    if not pathlib.Path(folder).exists():
        cprint("bred", f"server {args.name} does not exists")
        raise RuntimeError()

    version = Cmd.fread(f"{folder}/VERSION")

    cprint("green", f'[ OK ]: found server "{args.name}" with version "{args.version}"')
    print()

    return Server(args.name, version)


def main():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers()

    create = subparsers.add_parser("create", help="create new server")
    create.add_argument("name")
    create.add_argument("version")
    create.set_defaults(func=create_server)

    run = subparsers.add_parser("run", help="run existing server")
    run.add_argument("name")
    run.set_defaults(action=find_server)

    parser.add_argument("--list-versions", action="store_true")
    parser.add_argument("--update-versions", action="store_true")
    parser.add_argument("--prerequirements", action="store_true")

    args = parser.parse_args()

    req = Requirements()
    if args.update_versions:
        req.update_versions()
    if args.prerequirements:
        req.download_prerequirements()
    if args.list_versions:
        req.list_versions()
        return

    server = args.func(args)
    req.download_server(server.version)
    server.accept_eula()


if __name__ == "__main__":
    main()
