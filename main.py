#!/bin/python3

from __future__ import annotations

import argparse

import Manager
from Enviroment import Enviroment
from cprint import *
from defs import *


def add_name_argument(subparser):
    subparser.add_argument("--name", required=True)


def add_launcher_argument(subparser):
    subparser.add_argument("--launcher", choices=["vanilla", "forge"], required=True)


def add_deps_option(subparsers):
    deps = subparsers.add_parser(Action.DEPENDENCIES, help="install dependencies")
    deps.set_defaults(action=Action.DEPENDENCIES)


def add_create_option(subparsers):
    create = subparsers.add_parser(Action.CREATE, help="create new server")
    create.add_argument("--version", required=True)
    add_name_argument(create)
    add_launcher_argument(create)
    create.set_defaults(action=Action.CREATE)


def add_delete_option(subparsers):
    delete = subparsers.add_parser(Action.DELETE, help="delete server")
    delete.add_argument(
        "--force",
        action="store_true",
        help="ignore errors, delete even running server",
    )
    add_name_argument(delete)
    delete.set_defaults(action=Action.DELETE)


def add_run_option(subparsers):
    run = subparsers.add_parser(Action.RUN, help="run server")
    run.add_argument(
        "--log-to-stdout",
        action="store_true",
        help=(
            "print server log to console stdout instead of log file "
            "(helpful while debugging)"
        ),
    )
    add_name_argument(run)
    run.set_defaults(action=Action.RUN)


def add_stop_option(subparsers):
    stop = subparsers.add_parser(
        Action.STOP, help="gracefully stop running server saving world data"
    )
    stop.add_argument(
        "--kill",
        action="store_true",
        help=(
            "kill server process without saving world. "
            "WARNING: can corrupt world data, use only after "
            "graceful stop did not work",
        ),
    )
    add_name_argument(stop)
    stop.set_defaults(action=Action.STOP)


def add_backup_option(subparsers):
    backup = subparsers.add_parser(
        Action.BACKUP, help="backup existing server to repository"
    )
    add_name_argument(backup)
    backup.set_defaults(action=Action.BACKUP)


def add_restore_option(subparsers):
    pass


def add_list_option(subparsers):
    list_servers = subparsers.add_parser(Action.LIST, help="list created servers")
    list_servers.set_defaults(action=Action.LIST)


def add_list_running_option(subparsers):
    pass


def add_list_versions_option(subparsers):
    list_versions = subparsers.add_parser(
        Action.LIST_VERSIONS, help="list avaliable minecraft versions"
    )
    list_versions.add_argument(
        "--show-snapshots", action="store_true", help="also show snapshot versions"
    )
    add_launcher_argument(list_versions)
    list_versions.set_defaults(action=Action.LIST_VERSIONS)


def add_update_versions_option(subparsers):
    update_versions = subparsers.add_parser(
        Action.UPDATE_VERSIONS, help="update list of avaliable minecraft versions"
    )
    add_launcher_argument(update_versions)
    update_versions.set_defaults(action=Action.UPDATE_VERSIONS)


def main():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(required=True)

    add_deps_option(subparsers)
    add_create_option(subparsers)
    add_delete_option(subparsers)
    add_run_option(subparsers)
    add_stop_option(subparsers)
    add_backup_option(subparsers)
    add_restore_option(subparsers)
    add_list_option(subparsers)
    add_list_running_option(subparsers)
    add_list_versions_option(subparsers)
    add_update_versions_option(subparsers)

    args = parser.parse_args()

    match args.action:
        case Action.CREATE:
            Manager.create_server()

        case Action.DELETE:
            Manager.delete_server(args.name, args.force)

        case Action.RUN:
            server = Manager.find_server(args.name)
            try:
                server.run(log_to_stdout=args.log_to_stdout)
            except Exception:
                server.stop(kill=True)
                raise

        case Action.BACKUP:
            server = Manager.find_server(args.name)
            server.save()

        case Action.RESTORE:
            server = Manager.find_server(args.name)
            server.restore()

        case Action.STOP:
            server = Manager.find_server(args.name)
            server.stop(args.force)

        case Action.LIST:
            Manager.list_servers()

        case Action.LIST_RUNNING:
            Manager.list_running_servers()

        case Action.UPDATE_VERSIONS:
            env = Enviroment(args.launcher)
            env.update_versions()

        case Action.LIST_VERSIONS:
            env = Enviroment(args.launcher)
            env.list_versions(args.show_snapshots)

        case Action.DEPENDENCIES:
            env = Enviroment(args.launcher)
            env.download_dependencies()

        case _:
            ABORT(f"invalid action: {args.action}")


if __name__ == "__main__":
    main()
