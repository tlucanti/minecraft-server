import pathlib
import os
import subprocess
from abc import ABC, abstractmethod

from defs import *
from cprint import *
from Cmd import Cmd


class IServer(ABC):
    def __init__(self):
        self.name: str
        self.version: str
        self.launcher: str
        self.folder: str

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

    @abstractmethod
    def save(self):
        pass


class VanillaServer(IServer):
    def __init__(self, name: str, version: str):
        self.name = name
        self.version = version
        self.launcher = LauncherType.VANILLA
        self.folder = f"{Folder.WORLDS}/{name}"

    def prepare(self):
        def convert_config(config: dict[str, str]) -> str:
            return "\n".join(f"{key}={value}" for key, value in config.items())

        with STEP("PREPARE SERVER TO RUN"):
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
            Cmd.fwrite(server_properties_fname, convert_config(config))

    def run(self, log_to_stdout=False):
        with STEP("PREPARE TO START"):
            if self.is_running():
                FAIL(f'server "{self.name}" already running')
                raise MCInvalidOperationError()

            stdin_fname = f"{self.folder}/stdin.fifo"
            stdout_fname = f"{self.folder}/stdout.log"
            history_fname = f"{self.folder}/history.txt"
            core_fname = pathlib.Path(
                f"{Folder.SERVERS}/{LauncherType.VANILLA}/{self.version}.jar"
            ).absolute()

            Cmd.cmd(f"rm -f {stdin_fname}")
            Cmd.cmd(f"mkfifo {stdin_fname}")
            Cmd.cmd(f"touch {history_fname}")

        with STEP("RUNNING COMMAND KEEPER PROCESS"):
            stdin_fd = os.open(stdin_fname, os.O_RDWR | os.O_NONBLOCK)
            stdin_pipe = os.fdopen(stdin_fd, "r")

            stdin_keeper = subprocess.Popen(
                ["tail", "-n0", "-f", history_fname],
                stdout=open(stdin_fname, "w"),
                text=True,
                start_new_session=True,
                close_fds=True,
            )
            if stdin_keeper.returncode is not None:
                FAIL("failed to start stdin keeper process")
                raise MCSystemError()
            Cmd.fwrite(f"{self.folder}/KEEPER_PID", str(stdin_keeper.pid))
            OK(f"command keeper started with pid {stdin_keeper.pid}")

        with STEP("RUNNING SERVER PROCESS"):
            if log_to_stdout:
                stdout = None
            else:
                stdout = open(stdout_fname, "w")
            server_proc = subprocess.Popen(
                [
                    "java",
                    "-server",
                    "-XX:+UseParallelGC",
                    f"-Xms{Java.HEAP}",
                    f"-Xmx{Java.MAX_HEAP}",
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

    def save(self):
        tz = datetime.timezone(datetime.timedelta(hours=3))
        message = f"{datetime.datetime.now(tz)} {self.name}"
        if not pathlib.Path(f"{WORLDS_FOLDER}/.git").exists():
            Cmd.cmd(f"git -C {WORLDS_FOLDER} init")
            Cmd.cmd(f"git -C {WORLDS_FOLDER} commit --allow-empty -m 'initial commit'")
        Cmd.cmd(f"git -C {WORLDS_FOLDER} add --all")
        Cmd.cmd(f'git -C {WORLDS_FOLDER} commit --allow-empty -m "{message}"')

    def stop(self, kill=False):
        server_exists = pathlib.Path(f"{self.folder}/PID").exists()
        keeper_exists = pathlib.Path(f"{self.folder}/KEEPER_PID").exists()

        if not kill and not self.is_running():
            FAIL(f"server {self.name} is not running")
            raise MCInvalidOperationError()

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


class ForgeServer(IServer):
    def __init__(self, name: str, version: str):
        pass


def Server(launcher: str, name: str, version: str):
    if launcher == LauncherType.VANILLA:
        return VanillaServer(name, version)
    elif launcher == LauncherType.FORGE:
        return ForgeServer(name, version)
    else:
        ABORT(f"invalid launcher: {launcher}")
