import io
import json
import pathlib
import shlex
import subprocess
import time
import yaml

from cprint import *


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
        return proc.returncode

    @classmethod
    def wget(cls, url: str, out: str, backoff: int = 10, timeout: int = 100):
        if pathlib.Path(out).exists():
            FAIL(f"output path {out} exists")
            raise MCFetchError()

        time_start = time.time()
        prev_file_size = 0

        proc = subprocess.Popen(["wget", url, "-O", out, "--verbose"])
        try:
            while True:
                try:
                    ret = proc.wait(backoff)
                    if ret:
                        FAIL(f"failed to download from url: {url}")
                        raise MCFetchError()
                    else:
                        break

                except subprocess.TimeoutExpired:
                    if not pathlib.Path(out).exists():
                        FAIL(f"failed to connect to url: {url}")
                        raise MCFetchError()

                    file_size = pathlib.Path(out).stat().st_size
                    if file_size == prev_file_size:
                        FAIL(f"file downloading is stuck, aborting")
                        proc.kill()
                        raise MCFetchError()
                    prev_file_size = file_size

                    if time.time() - time_start > timeout:
                        FAIL(f"downloading timed out after {timeout} seconds")
                        raise MCFetchError()

        except Exception:
            Cmd.cmd(f"rm -f {out}")
            raise
