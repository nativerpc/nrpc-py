#
#   Contents:
#
#       TermExecutor
#           __init__
#           main_loop
#           connection_loop
#           flush_loop
#           flush_running
#           print_line
#           close
#
import os
import datetime
import shlex
import json
import glob
import subprocess
from colorama import Fore
import time
if os.name == 'nt':
    pass
else:
    import fcntl
import threading
import nrpc_py
from nrpc_cli.common_base import (
    LauncherCommand,
    LAUNCHER_PORT,
    OS_CONFIG_PYTHON,
    ProcessInfo,
    CommandInfo,
    clear_terminal,
    find_one,
    get_line_nonblock,
)


class TermExecutor:
    start_time: datetime.datetime
    is_alive: bool
    is_active: bool
    is_configured: bool
    client_index: int
    client_socket: nrpc_py.ClientSocket
    commands: list[CommandInfo]

    def __init__(self):
        self.start_time = datetime.datetime.now()
        self.is_alive = True
        self.is_active = False
        self.is_configured = False
        self.client_index = 0
        self.client_socket = None
        self.verbosity_level = 0
        self.console_thread = None
        self.commands = []

        self.console_thread = threading.Thread(target=self.flush_loop)
        self.console_thread.start()

    def main_loop(self):
        while self.is_alive:
            self.client_socket = nrpc_py.ClientSocket(
                ip_address='127.0.0.1',
                port=LAUNCHER_PORT,
                port_rev=10000 + LAUNCHER_PORT,
                entry_file='term_executor_py'
            )
            self.client_socket.add_metadata({
                'fixed_start_time': self.start_time.isoformat(),
            })
            self.client_socket.connect()
            self.is_active = True
            self.is_configured = False
            self.client_index = 0
            # print(f'Terminal connected #{self.client_socket.client_id}')

            self.connection_loop()

            self.is_active = False
            self.is_configured = False
            self.client_index = 0

            # Keep retrying on connection lost
            #
            if self.is_alive and self.client_socket.is_lost:
                print('Terminal lost')
                self.client_socket.close()
                self.client_socket = None
                time.sleep(1)
                continue

            break

        self.is_active = False
        self.is_configured = False
        self.client_index = 0
        if self.client_socket:
            self.client_socket.close()
            self.client_socket = None
        if self.console_thread:
            self.console_thread.join()
            self.console_thread = None

    def connection_loop(self):
        assert self.client_socket.is_validated

        while self.is_alive and not self.client_socket.is_lost:
            req = self.client_socket.recv_rev(1.0)
            if not req:
                continue

            method_name = req[0].decode()
            command_parameters = json.loads(req[1].decode())
            res = None

            if method_name == LauncherCommand.SetExecutables:
                if not self.is_configured:
                    self.is_configured = True
                client_index = 0
                for item in command_parameters['executables']:
                    client_index = item['client_index']
                    break
                if self.client_index != client_index:
                    self.client_index = client_index
                    if self.client_index > 0:
                        print(f'Terminal configured #{self.client_index}')
                assert command_parameters['version'] == 1
                prev_commands = list(self.commands)
                commands = []
                for item in command_parameters['executables']:
                    assert self.client_socket.client_id == item['client_id']
                    cmd_item = find_one(
                        prev_commands,
                        lambda x:
                            x.command_index == item['command_index'] and
                            x.command_type == item['command_type'] and
                            x.command_entry == item['command_entry']
                    )

                    if cmd_item:
                        prev_commands.remove(cmd_item)
                    else:
                        cmd_item = CommandInfo()

                    cmd_item.client_index = item['client_index']
                    cmd_item.client_id = item['client_id']
                    cmd_item.command_index = item['command_index']
                    cmd_item.command_type = item['command_type']
                    cmd_item.command_entry = item['command_entry']
                    cmd_item.command_parameters = item['command_parameters']
                    cmd_item.visible = item['visible']
                    commands.append(cmd_item)

                for item in prev_commands:
                    if cmd_item.command_process and cmd_item.command_process.handle:
                        try:
                            cmd_item.command_process.handle.kill()
                        except:  # noqa
                            pass
                        cmd_item.command_process.stopped = True

                self.commands = commands

                execs = []
                for item in self.commands:
                    execs.append({
                        'client_index': item.client_index,
                        'command_index': item.command_index,
                        'command_type': item.command_type,
                        'command_entry': item.command_entry,
                        'enabled': item.enabled,
                    })

                res = {
                    'executables': execs,
                }

            elif method_name == LauncherCommand.GetState:
                assert command_parameters['version'] == 1
                execs = []
                for item in self.commands:
                    execs.append({
                        'client_index': item.client_index,
                        'command_index': item.command_index,
                        'command_type': item.command_type,
                        'command_entry': item.command_entry,
                        'enabled': item.enabled,
                    })
                res = {
                    'executables': execs,
                }

            elif method_name == LauncherCommand.SetParameter:
                cmd_item = find_one(self.commands, lambda x: x.command_index == command_parameters['command_index'])
                cmd_item.command_parameters = command_parameters['command_parameters']
                res = {
                    'command_index': cmd_item.command_index,
                    'command_parameters': cmd_item.command_parameters,
                }

            elif method_name == LauncherCommand.ExecuteCommand:
                cmd_index = command_parameters['command_index']
                cmd_item = find_one(self.commands, lambda x: x.command_index == cmd_index)
                assert cmd_item
                command_entry = cmd_item.command_entry

                # Support basenames without a path
                #
                if command_entry and not os.path.exists(command_entry):
                    files = None
                    if not files and os.path.exists('src'):
                        files = glob.glob(f'src/**/{cmd_item.command_entry}', recursive=True)
                    if not files and os.path.exists('test'):
                        files = glob.glob(f'test/**/{cmd_item.command_entry}', recursive=True)
                    if files:
                        command_entry = files[0]

                if cmd_item.command_process:
                    if cmd_item.command_process.handle:
                        try:
                            cmd_item.command_process.handle.kill()
                        except:  # noqa
                            pass
                        cmd_item.command_process.stopped = True

                if cmd_item.command_type == 'stop':
                    count = 0
                    for item in self.commands:
                        if item.command_process:
                            if item.command_process.handle:
                                command_entry_short = os.path.basename(command_entry)
                                base_name = \
                                    command_entry_short[0: command_entry_short.index('.')].title() if command_entry else \
                                    item.command_type.title()
                                self.print_line(item, f'{base_name} stopped')
                                try:
                                    count += 1
                                    item.command_process.handle.kill()
                                except:  # noqa
                                    pass
                                item.command_process.stopped = True

                        item.enabled = False

                    cmd_item.command_process = ProcessInfo(
                        f'execute:{cmd_item.command_type}:{cmd_item.command_entry}'
                    )
                    cmd_item.enabled = True

                    if count:
                        self.print_line(cmd_item, f'Stopped, {count}')

                elif cmd_item.command_type == 'clear':
                    clear_terminal()
                    cmd_item.command_process = ProcessInfo(
                        f'execute:{cmd_item.command_type}:{cmd_item.command_entry}'
                    )

                elif cmd_item.command_type in ['python', 'run'] and \
                        command_entry.endswith('.py'):
                    cmd = f'{OS_CONFIG_PYTHON} -u {command_entry.replace("\\", "\\\\")} --is-terminal {cmd_item.command_parameters}'

                    proc = subprocess.Popen(
                        shlex.split(cmd),
                        stderr=subprocess.STDOUT,
                        stdin=subprocess.DEVNULL,
                        stdout=subprocess.PIPE,
                        shell=False,
                    )
                    cmd_item.command_process = ProcessInfo(
                        f'execute:{cmd_item.command_type}:{cmd_item.command_entry}',
                        proc
                    )

                    fd = proc.stdout.fileno()
                    os.set_blocking(fd, False)

                    # if os.name != 'nt':
                    #     fl = fcntl.fcntl(fd, fcntl.F_GETFL)
                    #     fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)

                    if self.verbosity_level >= 1:
                        self.print_line(cmd_item, 'Process started')

                else:
                    assert command_entry == ''
                    # res = os.system(f'{cmd_item.command_type} {cmd_item.command_parameters}')
                    cmd = f'{cmd_item.command_type} {cmd_item.command_parameters}'
                    if cmd_item.command_type == 'sleep':
                        cmd = f'powershell -c sleep {cmd_item.command_parameters}'
                    elif cmd_item.command_type == 'clear':
                        cmd = 'cls'

                    if '\\' in cmd:
                        cmd = cmd.replace('\\', '\\\\')

                    proc = subprocess.Popen(
                        shlex.split(cmd),
                        stderr=subprocess.STDOUT,
                        stdin=subprocess.DEVNULL,
                        stdout=subprocess.PIPE,
                        shell=True,
                    )
                    cmd_item.command_process = ProcessInfo(
                        f'execute:{cmd_item.command_type}:{cmd_item.command_entry}:{cmd_item.command_parameters}',
                        proc
                    )

                    fd = proc.stdout.fileno()
                    os.set_blocking(fd, False)

                    # if os.name != 'nt':
                    #     fl = fcntl.fcntl(fd, fcntl.F_GETFL)
                    #     fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)

                    if self.verbosity_level >= 1:
                        self.print_line(cmd_item, 'Process started')

                cmd_item.enabled = True
                res = {
                    'command_index': cmd_item.command_index,
                    'enabled': cmd_item.enabled,
                }

            elif method_name == LauncherCommand.StopCommand:
                cmd_item = None
                for item in self.commands:
                    if item.command_index != command_parameters['command_index'] and command_parameters['command_index'] != '*':
                        continue

                    if item.command_process:
                        if item.command_process.handle:
                            base_name = \
                                item.command_entry[0: item.command_entry.index('.')].title() if item.command_entry else \
                                item.command_type.title()
                            self.print_line(item, f'{base_name} stopped')
                            try:
                                # item.command_process.handle.terminate()
                                item.command_process.handle.kill()
                            except:  # noqa
                                pass
                            item.command_process.stopped = True

                    item.enabled = False
                    cmd_item = item

                res = {
                    'command_index': cmd_item.command_index,
                    'enabled': cmd_item.enabled,
                }

            elif method_name == LauncherCommand.GetConfig:
                res = {
                    'verbosity_level': self.verbosity_level
                }

            elif method_name == LauncherCommand.SetConfig:
                assert 'verbosity_level' in command_parameters
                self.verbosity_level = command_parameters['verbosity_level']
                res = {
                    'verbosity_level': self.verbosity_level
                }

            else:
                assert False, f'Unknown command: {method_name}'

            self.client_socket.send_rev([
                f'response:{method_name}',
                res
            ])

    def flush_loop(self):
        while self.is_alive:
            time.sleep(0.01)
            self.flush_running()

    def flush_running(self):
        for item in self.commands:
            if not item.command_process:
                continue

            # Dummy process cleanup
            #
            if not item.command_process.handle and item.enabled:
                time.sleep(0.2)
                item.enabled = False
                continue

            handle = item.command_process.handle if item.command_process else None
            if not handle:
                continue

            cur_res = handle.poll()
            if cur_res is not None:
                if item.command_process.handle == handle:
                    while True:
                        line = get_line_nonblock(handle.stdout)
                        if not line:
                            line = get_line_nonblock(handle.stdout)
                        if not line:
                            break
                        self.print_line(item, line)
                    if cur_res == 0:
                        if self.verbosity_level >= 1:
                            self.print_line(item, 'Completed')
                    elif item.command_process.stopped:
                        if self.verbosity_level >= 1:
                            self.print_line(item, 'Stopped')
                    else:
                        self.print_line(item, f'Failed, code={cur_res}')
                    item.command_process.handle = None
                    item.command_process.result = cur_res
                    item.enabled = False
            else:
                while True:
                    line = get_line_nonblock(handle.stdout)
                    if not line:
                        line = get_line_nonblock(handle.stdout)
                    if not line:
                        break
                    self.print_line(item, line)

    def print_line(self, command, line):
        command_index = command.command_index if command else 0
        if self.verbosity_level >= 1:
            print(f'{Fore.GREEN}[{command_index}]{Fore.RESET} {line}')
        else:
            print(line)

    def close(self):
        self.is_alive = False
