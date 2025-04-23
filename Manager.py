import pathlib

from defs import *
from cprint import *
from Server import *
from Enviroment import *


def _get(name: str) -> IServer:
    folder = f"{Folder.WORLDS}/{name}"
    if not pathlib.Path(folder).exists():
        FAIL(f"server {name} does not exists")
        raise MCNotFoundError()

    launcher = Cmd.fread(f"{folder}/TYPE")
    version = Cmd.fread(f"{folder}/VERSION")

    return Server(launcher, name, version)


def _iter_servers():
    if not pathlib.Path(Folder.WORLDS).exists():
        return
    for server in pathlib.Path(Folder.WORLDS).iterdir():
        yield _get(server.name)


def _create_empty_server(launcher: str, name: str, version: str) -> IServer:
    with STEP(f"CREATING {launcher.upper()} SERVER {name}"):
        folder = f"{Folder.WORLDS}/{name}"
        if pathlib.Path(folder).exists():
            FAIL(f'server "{name}" already exists')
            raise MCInvalidOperationError()

        try:
            Cmd.cmd(f"mkdir -p {folder}/{Folder.DATA}")
            Cmd.fwrite(f"{folder}/VERSION", version)
            Cmd.fwrite(f"{folder}/TYPE", launcher)

            OK(f'created {launcher} server "{name}" with version "{version}"')
            print()

            return _get(name)
        except Exception:
            Cmd.cmd(f"rm -rf {folder}")
            raise


def create_server(launcher: str, name: str, version: str):
    env = Enviroment(launcher)

    with _create_empty_server(launcher, name, version) as server:
        with download_
    server = _create_empty_server(launcher, name, version)
    at_fail(lambda: delete_server(name))

    env.download_server(server.version)
        server.prepare()
    except Exception:
        raise


def find_server(name: str, announce=True) -> IServer:
    if announce:
        cprint("yellow", f'FINDING SERVER "{name}"')

    server = _get(name)
    OK(
        f'found {server.launcher} server "{server.name}" with version "{server.version}"'
    )
    print()
    return server


def list_servers():
    for server in _iter_servers():
        if server.is_running():
            running = "server running"
        else:
            running = "server not running"
        print(f"{server.name} {server.launcher} {server.version} ({running})")


def list_running_servers():
    pass


def save_server(name: str):
    cprint("yellow", f'SAVING SERVER "{name}"')
    server = find_server(name, announce=False)
    server.save()


def delete_server(name: str, force: bool = False):
    cprint("yellow", f'DELETING SERVER "{name}"')
    server = find_server(name, announce=False)
    if server.is_running():
        if force:
            WARN("deleting running server")
            server.stop(kill=True)
        else:
            FAIL("cannot delete running server. stop or kill it first")
            raise RuntimeError()
    Cmd.cmd(f"rm -rf {server.folder}")
    OK(f"deleted server {name}")
