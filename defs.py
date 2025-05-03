class LauncherType:
    VANILLA = "vanilla"
    FORGE = "forge"


class Fname:
    VERSIONS_VANILLA = f"versions.{LauncherType.VANILLA}.json"
    VERSIONS_FORGE = f"versions.{LauncherType.FORGE}.json"


class Folder:
    SERVERS = "cores"
    WORLDS = "worlds"
    DATA = "data"


class Java:
    THREADS = 1
    HEAP = "256M"
    MAX_HEAP = "1G"


class Action:
    HELP = "help"
    DEPENDENCIES = "deps"
    CREATE = "create"
    DELETE = "delete"
    RUN = "run"
    STOP = "stop"
    CMD = "cmd"
    BACKUP = "backup"
    RESTORE = "restore"
    LIST = "list"
    LIST_RUNNING = "ps"
    LIST_VERSIONS = "list-versions"
    UPDATE_VERSIONS = "update-versions"
