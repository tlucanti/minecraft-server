import pathlib
from abc import ABC, abstractmethod
from collections import OrderedDict

from Cmd import Cmd
from cprint import *
from defs import *


class IEnviroment(ABC):
    def download_dependencies(self):
        with STEP("DOWNLOADING DEPENDENCIES"):
            Cmd.cmd("sudo apt-get update")
            Cmd.cmd("sudo apt-get install -y openjdk-21-jdk-headless")

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

        with STEP("UPDATING VANILLA VERSIONS"):

            try:
                url = "https://gist.github.com/77a982a7503669c3e1acb0a0cf6127e9.git"
                Cmd.cmd(f"git clone --depth=1 --progress {url} gist")
                Cmd.fwrite(Fname.VERSIONS_VANILLA, convert())
            except Exception:
                Cmd.cmd(f"rm -f {Fname.VERSIONS_VANILLA}")
                raise
            finally:
                Cmd.cmd("rm -rf gist")

    def check_update_versions(self):
        if not pathlib.Path(Fname.VERSIONS_VANILLA).exists():
            INFO(f"{Fname.VERSIONS_VANILLA} not found. updating vanilla versions")
            self.update_versions()

    def list_versions(self, show_snapshots: bool):
        with STEP("SUPPORTED VANILLA VERSIONS"):
            self.check_update_versions()

            # parsing file directly instead of json lib to keep release order
            versions = Cmd.fread(Fname.VERSIONS_VANILLA)
            for line in reversed(versions.splitlines()[1:-1]):
                v = line.split(":", maxsplit=1)[0].replace('"', "").strip()
                if not show_snapshots and self._filter_version(v):
                    continue
                print(v)

    def download_server(self, version: str) -> str:
        with STEP("GETTING VANILLA SERVER JAR"):
            folder = f"{Folder.SERVERS}/{LauncherType.VANILLA}"
            Cmd.cmd(f"mkdir -p {folder}")

            core_fname = f"{folder}/{version}.jar"
            if pathlib.Path(core_fname).exists():
                OK(f'existing server: "{core_fname}"')
                print()
                return core_fname

            self.check_update_versions()
            versions = Cmd.jload(Cmd.fread(Fname.VERSIONS_VANILLA))

            url = versions.get(version)
            if url is None:
                FAIL(f'version "{version}" not found. run list-versions command')
                raise MCNotFoundError()

            INFO(f'downloading {LauncherType.VANILLA} server "{core_fname}"')
            INFO(f"url: {url}")

            Cmd.wget(url + "xx", core_fname)
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
