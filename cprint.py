import sys
from contextlib import contextmanager
from typing import NoReturn

from MCException import *


def cprint(color, *args, **kwargs):
    color_table = {
        "red": "\033[0;31m",
        "green": "\033[0;32m",
        "yellow": "\033[0;33m",
        "blue": "\033[0;34m",
        "purple": "\033[0;35m",
        "cyan": "\033[0;36m",
        "white": "\033[0;37m",
        "bred": "\033[1;31m",
        "bgreen": "\033[1;32m",
        "byellow": "\033[1;33m",
        "bblue": "\033[1;34m",
        "bpurple": "\033[1;35m",
        "bcyan": "\033[1;36m",
        "bwhite": "\033[1;37m",
        "reset": "\033[0m",
    }
    print(color_table[color], end="", file=sys.stderr)
    print(*args, **kwargs, file=sys.stderr)
    print(color_table["reset"], end="", flush=True, file=sys.stderr)


@contextmanager
def STEP(*args, **kwargs):
    cprint("yellow")
    cprint("yellow", *args, **kwargs)
    try:
        yield
    finally:
        pass


def INFO(*args, **kwargs):
    cprint("bblue", "[INFO]:", *args, **kwargs)


def OK(*args, **kwargs):
    cprint("bgreen", "[ OK ]:", *args, **kwargs)


def WARN(*args, **kwargs):
    cprint("byellow", "[WARN]:", *args, **kwargs)


def FAIL(*args, **kwargs):
    cprint("bred", "[FAIL]:", *args, **kwargs)


def ABORT(*args, **kwargs) -> NoReturn:
    cprint("bred", "[INTERNAL_ERROR]:", *args, **kwargs)
    raise MCInternalError()
