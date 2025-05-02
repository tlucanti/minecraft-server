from __future__ import annotations

import pathlib
import os
import subprocess
from abc import ABC, abstractmethod

from defs import *
from cprint import *
from Cmd import Cmd
from Saga import Saga


class IServer(ABC):
    def __init__(self):
        self.name: str
        self.version: str
        self.launcher: str
        self.folder: str

    @classmethod
    def create_folder(cls, launcher: str, name: str, version: str) -> IServer:
        """
        create server folder and files:
         - VERSION with server version
         - TYPE with server type "vanilla" or "forge"
        """
        folder = f"{Folder.WORLDS}/{name}"
        with Saga() as saga:
            saga.compensation(lambda: Cmd.cmd(f"rm -rf {folder}"))

            Cmd.cmd(f"mkdir -p {folder}/{Folder.DATA}")
            Cmd.fwrite(f"{folder}/VERSION", version)
            Cmd.fwrite(f"{folder}/TYPE", launcher)

            return cls.get(name)

    @classmethod
    def get(cls, name: str) -> IServer:
        """
        create server object by it's name
        find's server folder, version and type and fill returning object
        """
        folder = f"{Folder.WORLDS}/{name}"
        if not pathlib.Path(folder).exists():
            FAIL(f"server {name} does not exists")
            raise MCNotFoundError()

        launcher = Cmd.fread(f"{folder}/TYPE")
        version = Cmd.fread(f"{folder}/VERSION")

        if launcher == LauncherType.VANILLA:
            return VanillaServer(name, version)
        elif launcher == LauncherType.FORGE:
            return ForgeServer(name, version)
        else:
            ABORT(f"invalid launcher: {launcher}")

    @abstractmethod
    def create_files(self):
        pass

    @abstractmethod
    def run(self, interactive=False):
        pass

    @abstractmethod
    def stop(self, kill: bool):
        pass

    @abstractmethod
    def send_cmd(self, cmd: str):
        pass

    @abstractmethod
    def is_running(self) -> bool:
        pass

    @abstractmethod
    def save(self):
        pass

    def delete(self):
        """
        completely delte server with it's folder
        """
        if self.is_running():
            FAIL("cannot delete running server. stop or kill it first")
            raise MCInvalidOperationError()
        Cmd.cmd(f"rm -rf {self.folder}")


class VanillaServer(IServer):
    def __init__(self, name: str, version: str):
        self.name = name
        self.version = version
        self.launcher = LauncherType.VANILLA
        self.folder = f"{Folder.WORLDS}/{name}"

    def create_files(self):
        def convert_config(config: dict[str, str]) -> str:
            return "\n".join(f"{key}={value}" for key, value in config.items())

        INFO("accepting eula")
        Cmd.fwrite(f"{self.folder}/{Folder.DATA}/eula.txt", "eula=true")

        local_config_fname = f"{self.folder}/config.json"
        server_properties_fname = f"{self.folder}/{Folder.DATA}/server.properties"

        base_config = Cmd.jload(Cmd.fread("server.properties.json"))
        global_config = Cmd.jload(Cmd.fread("config.json"))
        local_config = {}
        if pathlib.Path(local_config_fname).exists():
            local_config = Cmd.jload(Cmd.fread(local_config_fname))
        local_config |= {"level-name": self.name}

        # config override order:
        # base config <- global config <- local config
        config = base_config | global_config | local_config
        INFO("creating server config")
        Cmd.fwrite(server_properties_fname, convert_config(config))

    def run(self, interactive=False):
        if self.is_running():
            FAIL(f'server "{self.name}" already running')
            raise MCInvalidOperationError()

        stdin_fname = f"{self.folder}/stdin.fifo"
        stdout_fname = f"{self.folder}/stdout.log"
        history_fname = f"{self.folder}/history.txt"
        keeper_pid_fname = f"{self.folder}/KEEPER_PID"
        java_pid_fname = f"{self.folder}/PID"
        core_fname = pathlib.Path(
            f"{Folder.SERVERS}/{LauncherType.VANILLA}/{self.version}.jar"
        ).absolute()

        with Saga() as saga:
            with STEP("prepare to start"):
                saga.compensation(
                    lambda: Cmd.cmd(f"rm -f {stdin_fname} {history_fname}")
                )
                Cmd.cmd(f"rm -f {stdin_fname}")
                Cmd.cmd(f"mkfifo {stdin_fname}")
                Cmd.cmd(f"touch {history_fname}")

            if not interactive:
                with STEP("running stdin keeper process"):
                    stdin_fd = os.open(stdin_fname, os.O_RDWR | os.O_NONBLOCK)
                    stdin_pipe = os.fdopen(stdin_fd, "w")
                    saga.compensation(lambda: stdin_pipe.close())

                    stdin_keeper = subprocess.Popen(
                        ["tail", "-n0", "-f", history_fname],
                        stdout=stdin_pipe,
                        text=True,
                        start_new_session=True,
                        close_fds=True,
                    )
                    try:
                        stdin_keeper.wait(0.2)
                    except subprocess.TimeoutExpired:
                        pass
                    if stdin_keeper.returncode is not None:
                        FAIL("failed to start stdin keeper process")
                        raise MCSystemError()

                    saga.compensation(lambda: stdin_keeper.kill())
                    saga.compensation(lambda: Cmd.cmd(f"rm -f {keeper_pid_fname}"))
                    Cmd.fwrite(keeper_pid_fname, str(stdin_keeper.pid))
                    OK(f"command keeper started with pid {stdin_keeper.pid}")

            with STEP("running server process"):
                if interactive:
                    stdin = None
                    stdout = None
                else:
                    stdin = open(stdin_fname, "r")
                    stdout = open(stdout_fname, "w")

                cmd = [
                    "java",
                    "-server",
                    "-XX:+UseParallelGC",
                    f"-Xms{Java.HEAP}",
                    f"-Xmx{Java.MAX_HEAP}",
                    "-jar",
                    core_fname,
                    "nogui",
                ]
                server_proc = subprocess.Popen(
                    cmd,
                    cwd=f"{self.folder}/{Folder.DATA}",
                    stdin=stdin,
                    stdout=stdout,
                    stderr=stdout,
                    text=True,
                    # start_new_session=True,
                    close_fds=True,
                )
                try:
                    server_proc.wait(0.5)
                except subprocess.TimeoutExpired:
                    pass
                if server_proc.returncode is not None:
                    FAIL(
                        f"failed to start server process (returncode: {server_proc.returncode})"
                    )
                    INFO(f"stdout:\n{Cmd.fread(stdout_fname)}")
                    raise MCSystemError()

                saga.compensation(lambda: server_proc.kill())
                saga.compensation(lambda: Cmd.cmd(f"rm -f {java_pid_fname}"))
                Cmd.fwrite(f"{self.folder}/PID", str(server_proc.pid))
                OK(f"server started with pid {server_proc.pid}")

            with STEP("waiting server online"):
                Cmd.wait_for_line(stdout_fname, "Done")
                OK("server online")

                if interactive:
                    server_proc.wait()

    def save(self):
        tz = datetime.timezone(datetime.timedelta(hours=3))
        message = f"{datetime.datetime.now(tz)} {self.name}"
        if not pathlib.Path(f"{WORLDS_FOLDER}/.git").exists():
            Cmd.cmd(f"git -C {WORLDS_FOLDER} init")
            Cmd.cmd(f"git -C {WORLDS_FOLDER} commit --allow-empty -m 'initial commit'")
        Cmd.cmd(f"git -C {WORLDS_FOLDER} add --all")
        Cmd.cmd(f'git -C {WORLDS_FOLDER} commit --allow-empty -m "{message}"')

    def stop(self, kill=False):
        if not self.is_running():
            FAIL(f"server {self.name} is not running")
            raise MCInvalidOperationError()

        with STEP("stopping server process"):
            pid = Cmd.fread(f"{self.folder}/PID")
            if kill:
                INFO(f"found server process with pid {pid}")
                Cmd.cmd(f"kill {pid}", check=False)
            else:
                INFO(f"found server process with pid {pid}")
                self.send_cmd("stop")

        with STEP("waiting server to stop"):
            Cmd.waitpid(int(pid))
            Cmd.cmd(f"rm {self.folder}/PID")

        with STEP("stopping keeper process"):
            keeper_pid = Cmd.fread(f"{self.folder}/KEEPER_PID")
            INFO(f"found keeper process with pid {keeper_pid}")
            Cmd.cmd(f"kill {keeper_pid}", check=False)
            Cmd.cmd(f"rm {self.folder}/KEEPER_PID")

    def send_cmd(self, cmd: str):
        if not self.is_running():
            FAIL(f"server {self.name} is not running")
            raise MCInvalidOperationError()

        INFO(f'sending command "{cmd}" to server {self.name}')
        Cmd.fappend(f"{self.folder}/history.txt", cmd + "\n")

    def is_running(self):
        server_exists = pathlib.Path(f"{self.folder}/PID").exists()
        keeper_exists = pathlib.Path(f"{self.folder}/KEEPER_PID").exists()
        return server_exists or keeper_exists


class ForgeServer(IServer):
    def __init__(self, name: str, version: str):
        pass

    def create_files(self):
        pass

    def run(self, log_to_stdout: bool):
        pass

    def stop(self, kill: bool = False):
        pass

    def is_running(self) -> bool:
        return False

    def save(self):
        pass
