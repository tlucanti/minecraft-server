import time

while True:
    print("hello", flush=True)
    time.sleep(1)


import subprocess, select, sys

p = subprocess.Popen(
    ["python3", "-u", "./main.py", "run", "--name", "test"],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    close_fds=True,
)

pipes = [p.stdout, p.stderr]
while pipes:
    reads, _, _ = select.select(pipes, [], [])
    for r in reads:
        line = r.readline()
        if line:
            # you could distinguish stdout vs stderr here if you wish
            sys.stdout.write(line)
        else:
            # EOF on this pipe
            pipes.remove(r)
# At this point both pipes have hit EOF
p.wait()
