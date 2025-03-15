#!/bin/python3

import shlex
import subprocess
import textwrap
import json
import argparse


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
    def cmd(cls, cmd: str | list):
        if isinstance(cmd, str):
            cmd = shlex.split(cmd)
        print(f"> {' '.join(cmd)}")

        proc = subprocess.run(cmd, text=True, check=False)
        if proc.returncode != 0:
            print(f'failed command "{cmd}":')
            raise subprocess.SubprocessError(f"command return code {proc.returncode}")


def update_versions():
    def convert():
        d = {}
        for line in Cmd.freadlines("gist/minecraft-server-jar-downloads.md")[2:]:
            _, version, server, _, _ = line.split("|")
            if server.strip().lower() == "not found":
                continue
            d[version.strip()] = server.strip()
        return json.dumps(d, indent=4)

    print("UPDATING VERSIONS")
    url = "https://gist.github.com/77a982a7503669c3e1acb0a0cf6127e9.git"
    Cmd.cmd("rm -rf gist")
    Cmd.cmd(f"git clone --depth=1 --progress {url} gist")
    Cmd.fwrite("versions.json", convert())
    Cmd.cmd("rm -rf gist")


def main():
    parser = argparse.ArgumentParser()
    args = parser.parse_args()

    update_versions()


if __name__ == "__main__":
    main()
