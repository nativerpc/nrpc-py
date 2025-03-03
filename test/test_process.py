import subprocess
import shlex
import os
import time
from nrpc_cli.common_base import (
    get_line_nonblock,
)


def start():
    delay = 5
    cmd = f'echo Sleeping for {delay} seconds... && powershell -c sleep {delay} && echo Sleep ready'
    print(cmd)

    proc = subprocess.Popen(
        shlex.split(cmd),
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        shell=True,
    )
    fd = proc.stdout.fileno()
    os.set_blocking(fd, False)

    while proc.poll() is None:
        time.sleep(0.5)
        while True:
            line = get_line_nonblock(proc.stdout)
            if not line:
                line = get_line_nonblock(proc.stdout)
            if not line:
                break
            print('LINE', line)
        print('WAIT')

    print('EXITED', proc.poll())


if __name__ == '__main__':
    start()
