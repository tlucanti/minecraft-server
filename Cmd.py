import io
import json
import os
import pathlib
import shlex
import subprocess
import time
import yaml

from cprint import *
from Backoff import Backoff

MINUTE_SECS = 60


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
    def cmd(cls, cmd: str | list, check=True, timeout_mins=1, **kwargs) -> int:
        if isinstance(cmd, str):
            cmd = shlex.split(cmd)
        cprint("green", f"> {' '.join(cmd)}")

        try:
            proc = subprocess.run(
                cmd,
                text=True,
                check=check,
                timeout=timeout_mins * MINUTE_SECS,
                **kwargs,
            )
        except subprocess.TimeoutExpired:
            FAIL(f"timed out after {timeout_mins}m running command {cmd}")
            raise
        return proc.returncode

    @classmethod
    def wget(cls, url: str, out: str, timeout_mins=10, backoff_secs=10):
        if pathlib.Path(out).exists():
            FAIL(f"output path {out} exists")
            raise MCFetchError()

        timeout = timeout_mins * MINUTE_SECS
        time_start = time.time()
        prev_file_size = 0

        proc = subprocess.Popen(["wget", url, "-O", out, "--verbose"])
        try:
            while True:
                try:
                    ret = proc.wait(backoff_secs)
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

    @classmethod
    def waitpid(cls, pid: int, timeout_mins=10, backoff_secs=1):
        bo = Backoff(timeout_mins, backoff_secs)
        while True:
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                break
            if bo.timeout():
                FAIL(
                    f"timed out while waiting for pid {pid} after {timeout_mins} minutes"
                )
            bo.backoff()

    @classmethod
    def git_clone(cls, url: str, dst="", timeout_mins=10):
        try:
            Cmd.cmd(
                f"git ls-remote {url} --quiet",
                env={"GIT_TERMINAL_PROMPT": "0"},
                timeout_mins=timeout_mins,
            )
        except subprocess.CalledProcessError:
            FAIL(f"repository {url} does not exist or no internet connection")
            raise
        except subprocess.TimeoutExpired:
            FAIL(f"timed out while checking repository avaliability")
            raise

        try:
            Cmd.cmd(
                f"git clone --depth=1 --progress {url} {dst}",
                env={"GIT_TERMINAL_PROMPT": "0"},
                timeout_mins=timeout_mins,
            )
        except subprocess.CalledProcessError:
            FAIL(f"failed to clone repo")
            raise
        except subprocess.TimeoutExpired:
            FAIL(f"timed out after {timeout_mins}m while cloning repository")
            raise

    @classmethod
    def wait_for_file(cls, fname: str, timeout_mins=1, backoff_secs=0.2):
        bo = Backoff(timeout_mins, backoff_secs)
        while not pathlib.Path(fname).exists():
            if bo.timeout():
                FAIL(f"waiting for file {fname} timed out after {timeout_mins} minutes")
                raise MCFetchError()
            bo.backoff()

    @classmethod
    def wait_for_line(cls, fname: str, line: str, timeout_mins=5, backoff_secs=1):
        bo = Backoff(timeout_mins, backoff_secs)
        while line not in Cmd.fread(fname):
            if bo.timeout():
                FAIL(f"waiting for line {line} timed out after {timeout_mins} minutes")
                raise MCFetchError()
            bo.backoff()
