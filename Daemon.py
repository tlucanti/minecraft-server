import os
import sys
import subprocess
import pathlib


def daemon(
    args,
    stdout: str,
    stderr: str | None = None,
    stdin="/dev/null",
    cwd: str | None = None,
    pidfile="pid",
):
    if os.fork() > 0:
        return

    try:
        os.setsid()
        os.umask(0)

        if os.fork() > 0:
            os._exit(0)

        sys.stdout.flush()
        sys.stderr.flush()

        with open(stdout, "w") as so:
            os.dup2(so.fileno(), sys.stdout.fileno())

            if stderr:
                # redirect to stderr file
                with open(stderr, "w") as se:
                    os.dup2(se.fileno(), sys.stderr.fileno())
            else:
                # combine stderr to stdout
                os.dup2(so.fileno(), sys.stderr.fileno())

        with open(stdin, "r") as si:
            os.dup2(si.fileno(), sys.stdin.fileno())

        pidfile_resolved = pathlib.Path(pidfile).absolute()
        if cwd:
            os.chdir(cwd)

        proc = subprocess.Popen(args, close_fds=True)

        with open(pidfile_resolved, "w") as pf:
            pf.write(str(proc.pid))

        proc.wait()

    except Exception:
        pass
    finally:
        os._exit(0)
