import pathlib

from defs import *
from cprint import *
from Server import *
from Enviroment import *
from Saga import Saga


def iter_servers():
    if not pathlib.Path(Folder.WORLDS).exists():
        return
    for server in pathlib.Path(Folder.WORLDS).iterdir():
        yield IServer.get(server.name)


def create_server(launcher: str, name: str, version: str):
    with Saga() as saga:
        folder = f"{Folder.WORLDS}/{name}"
        if pathlib.Path(folder).exists():
            FAIL(f"server {name} already exists")
            raise MCInvalidOperationError()

        with STEP("downloading server jar"):
            Enviroment(launcher).download_server(version)

        with STEP("creating server folder"):
            INFO(f'server type: "{launcher}"')
            INFO(f'server name: "{name}"')
            INFO(f'server version: "{version}"')

            saga.compensation(lambda: Cmd.cmd(f"rm -rf {folder}"))
            server = IServer.create_folder(launcher, name, version)

        with STEP("creating server files"):
            server.create_files()

        OK(f'{launcher} server "{name}" created successfully')


def delete_server(name: str):
    with STEP(f'finding server "{name}"'):
        server = IServer.get(name)

    with STEP(f'deleting server "{name}"'):
        server.delete()


def run_server(name: str, interactive):
    with STEP(f'finding server "{name}"'):
        server = IServer.get(name)

    server.run(interactive)


def stop_server(name: str):
    with STEP(f'finding server "{name}"'):
        server = IServer.get(name)

    server.stop(kill=False)


def send_cmd(name: str, cmd: str):
    with STEP(f'finding server "{name}"'):
        server = IServer.get(name)

    server.send_cmd(cmd)


def backup_server(name: str):
    pass


def restore_server(name: str):
    pass


def list_servers(only_running=False):
    for server in iter_servers():
        if server.is_running():
            running_msg = "server running"
        else:
            running_msg = "server not running"
            if only_running:
                continue
        print(f"{server.name} {server.launcher} {server.version} ({running_msg})")


def save_server(name: str):
    cprint("yellow", f'SAVING SERVER "{name}"')
    server = find_server(name, announce=False)
    server.save()


def update_versions(launcher: str):
    Enviroment(launcher).update_versions()


def download_dependencies():
    IEnviroment.download_dependencies()
