import pathlib
from abc import ABC, abstractmethod
from collections import OrderedDict

from Cmd import Cmd
from Saga import Saga
from cprint import *
from defs import *


class IEnviroment(ABC):
    @classmethod
    def download_dependencies(cls):
        with STEP("downloading dependencies"):
            Cmd.cmd("sudo apt-get update", timeout_mins=10)
            Cmd.cmd(
                "sudo apt-get install -y openjdk-21-jdk-headlessxx", timeout_mins=10
            )

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


class VanillaEnviroment(IEnviroment):
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

        with STEP("updating vanilla version list"):
            with Saga() as saga:
                url = "https://gist.github.com/77a982a7503669c3e1acb0a0cf6127e9.git"

                Cmd.git_clone(url, "gist", timeout_mins=1)
                saga.defer(lambda: Cmd.cmd("rm -rf gist"))

                saga.compensation(lambda: Cmd.cmd(f"rm -f {Fname.VERSIONS_VANILLA}"))
                Cmd.fwrite(Fname.VERSIONS_VANILLA, convert())

    def check_update_versions(self):
        if not pathlib.Path(Fname.VERSIONS_VANILLA).exists():
            INFO(f"{Fname.VERSIONS_VANILLA} not found. updating vanilla versions")
            self.update_versions()

    def list_versions(self, show_snapshots: bool):
        self.check_update_versions()

        # parsing file directly instead of json lib to keep release order
        versions = Cmd.fread(Fname.VERSIONS_VANILLA)
        for line in reversed(versions.splitlines()[1:-1]):
            v = line.split(":", maxsplit=1)[0].replace('"', "").strip()
            if not show_snapshots and self._filter_version(v):
                continue
            print(v)

    def download_server(self, version: str) -> str:
        folder = f"{Folder.SERVERS}/{LauncherType.VANILLA}"
        Cmd.cmd(f"mkdir -p {folder}")

        core_fname = f"{folder}/{version}.jar"
        if pathlib.Path(core_fname).exists():
            OK(f'existing server: "{core_fname}"')
            return core_fname

        self.check_update_versions()
        versions = Cmd.jload(Cmd.fread(Fname.VERSIONS_VANILLA))

        url = versions.get(version)
        if url is None:
            FAIL(f'version "{version}" not found. run list-versions command')
            raise MCNotFoundError()

        INFO(f'downloading {LauncherType.VANILLA} server "{core_fname}"')
        INFO(f"url: {url}")

        Cmd.wget(url, core_fname)
        return core_fname


# class ForgeEnviroment(IEnviroment):
#    def update_versions(self):
#        cprint("yellow", "UPDATING FORGE VERSIONS")
#        url = "https://files.minecraftforge.net/net/minecraftforge/forge/promotions_slim.json"
#        versions_raw = Cmd.run(f"curl {url}")
#        versions = Cmd.jload(versions_raw)
#
#        filtered = OrderedDict()
#        for version in reversed(versions["promos"]):
#            ver, _ = version.split("-")
#            if self._filter_version(ver):
#                continue
#            if f"{version}-recommended" in versions:
#                filtered[version] = f"{version}-recommended"
#            else:
#                filtered[version] = f"{version}-latest"
#
#        Cmd.fwrite("versions.forge.json", Cmd.jdump(filtered))
#        print()
#
#    def list_versions(self, show_snapshots: bool):
#        cprint("yellow", "SUPPORTED FORGE VERSIONS")
#        j = Cmd.jload(Cmd.fread("versions.forge.json"))
#        print("\n".join(j.keys()))
#
#    def download_server(self, version: str) -> str:
#        return ""


def Enviroment(launcher: str) -> IEnviroment:
    if launcher == LauncherType.VANILLA:
        return VanillaEnviroment()
    elif launcher == LauncherType.FORGE:
        return ForgeRequirements()
    else:
        ABORT(f"invalid launcher: {launcher}")
