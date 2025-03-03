#
#   Contents:
#
#       TermLauncher
#           __init__
#           load_commands
#           main_loop
#           socket_reader
#           update_clients
#           print_commands
#
import json
from colorama import Fore, Style
import time
import nrpc_py
import threading
import datetime
from nrpc_cli.common_base import (
    LAUNCHER_PORT,
    LauncherCommand,
    CommandInfo,
    LINE_UP,
    LINE_START,
    LINE_CLEAR,
    set_cursor_visibile,
    get_key_down,
    get_keyboard_char,
    find_one,
    find_all,
    get_param_dict,
    get_dict_text,
    is_number,
)


class TermLauncher:
    is_alive: bool
    is_ready: bool
    all_commands: list[CommandInfo]
    visible_commands: list[CommandInfo]
    ordered_client_ids: list
    printed_lines: list[str]
    selected_index: int
    last_selection: str
    last_selection_start: float
    show_help: bool
    verbosity_level: int
    update_count: list
    clients_dirty: bool
    states_dirty: bool
    custom_lines: list
    server_socket: nrpc_py.ServerSocket
    processor: threading.Thread

    def __init__(self, command_args):
        self.is_alive = True
        self.is_ready = False
        self.all_commands = []
        self.visible_commands = []
        self.ordered_client_ids = []
        self.printed_lines = []
        self.selected_index = 0
        self.last_selection = ''
        self.last_selection_start = 0
        self.show_help = False
        self.verbosity_level = 0
        self.update_count = [0] * 5
        self.clients_dirty = True
        self.states_dirty = False
        self.custom_lines = []

        self.server_socket = nrpc_py.ServerSocket(
            ip_address='127.0.0.1',
            port=LAUNCHER_PORT,
            port_rev=10000 + LAUNCHER_PORT,
            entry_file='term_launcher_py'
        )
        self.server_socket.add_metadata({
            'fixed_start_time': datetime.datetime.now().isoformat(),
        })

        self.server_socket.bind()
        self.processor = threading.Thread(target=self.socket_reader)
        self.processor.start()

        self.load_commands(command_args)

    def load_commands(self, command_args):
        commands = []
        client_index = 0
        command_index = 1

        command = CommandInfo()
        command.client_index = 0
        command.client_id = 0
        command.command_index = command_index
        command.command_type = 'clear'
        command.command_entry = ''
        command.command_parameters = ''
        command.visible = True
        commands.append(command)
        command_index += 1

        command = CommandInfo()
        command.client_index = 0
        command.client_id = 0
        command.command_index = command_index
        command.command_type = 'stop'
        command.command_entry = ''
        command.command_parameters = ''
        command.visible = True
        commands.append(command)
        command_index += 1

        client_index = 0
        for client_commands in command_args:
            client_index += 1
            command_index = 1
            command = CommandInfo()
            command.client_index = client_index
            command.client_id = 0
            command.command_index = command_index
            command.command_type = 'clear'
            command.command_entry = ''
            command.command_parameters = ''
            command.visible = False
            commands.append(command)
            command_index += 1

            command = CommandInfo()
            command.client_index = client_index
            command.client_id = 0
            command.command_index = command_index
            command.command_type = 'stop'
            command.command_entry = ''
            command.command_parameters = ''
            command.visible = False
            commands.append(command)
            command_index += 1

            for client_command in client_commands.split(':'):
                parts = client_command.split()
                has_entry = parts[0] in ['run', 'build', 'python']
                params_start = 2 if has_entry else 1

                command = CommandInfo()
                command.command_id = len(commands) + 1
                command.client_index = client_index
                command.client_id = 0
                command.command_index = command_index
                command.command_type = parts[0]
                command.command_entry = parts[1] if has_entry and 1 < len(parts) else ''
                command.command_parameters = \
                    ' '.join(parts[params_start:]) if params_start < len(parts) else ''
                command.visible = True
                commands.append(command)
                command_index += 1

        self.all_commands = commands
        self.visible_commands = [x for x in commands if x.visible]

    def main_loop(self):
        while self.is_alive:
            if self.clients_dirty or self.server_socket.get_client_change(0, self.ordered_client_ids):
                client_ids = self.server_socket.get_client_ids()
                self.clients_dirty = False
                self.states_dirty = True
                self.update_clients(client_ids)
                self.update_count[0] += 1
                assert set(client_ids) == set(self.ordered_client_ids)

            if self.states_dirty:
                self.states_dirty = False
                self.update_count[1] += 1
                has_stop = False
                has_clear = False

                for client_id in self.ordered_client_ids:
                    client_index = self.ordered_client_ids.index(client_id) + 1
                    assert client_index > 0

                    resp = None
                    with self.server_socket.request_lock:
                        self.server_socket.send_rev(
                            client_id,
                            [
                                LauncherCommand.GetState,
                                {'version': 1}
                            ]
                        )
                        resp = self.server_socket.recv_rev(client_id)
                        resp = json.loads(resp.decode())

                    for item in resp['executables']:
                        cmd_item = find_one(self.all_commands, lambda x: x.client_index ==
                                            client_index and x.command_index == item['command_index'])
                        cmd_item.enabled = item['enabled']
                        if cmd_item.command_type == 'stop':
                            has_stop |= cmd_item.enabled
                        elif cmd_item.command_type == 'clear':
                            has_clear |= cmd_item.enabled
                        assert cmd_item.command_type == item['command_type']
                        assert cmd_item.command_entry == item['command_entry']

                if not has_stop:
                    common_cmd = find_one(self.all_commands, lambda x: x.client_index == 0 and x.command_type == 'stop')
                    common_cmd.enabled = False
                if not has_clear:
                    common_cmd = find_one(self.all_commands, lambda x: x.client_index ==
                                          0 and x.command_type == 'clear')
                    common_cmd.enabled = False

            if self.last_selection:
                self.last_selection_start = time.time()

            self.print_commands()

            self.last_selection = ''

            # Sleep and detect changes
            # Look for following changes:
            #   - accepted new clients
            #   - timeout on input display
            #   - dirty enabled state
            #
            just_update = False
            last_check = time.time()
            while self.is_alive and not just_update:
                if get_key_down():
                    break

                latest_ids = self.server_socket.get_client_ids()
                if get_key_down():
                    break

                if self.server_socket.get_client_change(0.1, self.ordered_client_ids):
                    self.clients_dirty = True
                    self.update_count[2] += 1
                    just_update = True
                    break

                if self.last_selection_start and time.time() - self.last_selection_start > 0.5:
                    self.last_selection_start = 0
                    self.update_count[3] += 1
                    just_update = True
                    break

                if time.time() - last_check > 0.3:
                    last_check = time.time()
                    assert set(latest_ids) == set(self.ordered_client_ids)
                    checked = 0

                    for client_id in latest_ids:
                        client_index = self.ordered_client_ids.index(client_id) + 1
                        assert client_index > 0

                        resp = None
                        with self.server_socket.request_lock:
                            self.server_socket.send_rev(
                                client_id,
                                [
                                    LauncherCommand.GetState,
                                    {'version': 1}
                                ]
                            )
                            resp = self.server_socket.recv_rev(client_id)
                            if not resp:
                                assert self.server_socket.get_client_change(0.1, self.ordered_client_ids)
                                just_update = True
                                break
                            resp = json.loads(resp.decode())

                        for item in resp['executables']:
                            cmd_item = find_one(self.all_commands, lambda x: x.client_index ==
                                                client_index and x.command_index == item['command_index'])
                            assert cmd_item.command_type == item['command_type']
                            assert cmd_item.command_entry == item['command_entry']
                            checked += 1
                            if cmd_item.enabled != item['enabled']:
                                self.update_count[4] += 1
                                just_update = True
                                self.states_dirty = True
                                break

                        if just_update:
                            break

                    if just_update:
                        break

            if not self.is_alive or just_update:
                continue

            ch = get_keyboard_char()

            if ch == b'{space}' or ch == b'{enter}':
                current_command = self.visible_commands[self.selected_index]
                current_client_id = current_command.client_id

                if current_client_id == 0:
                    command_type = current_command.command_type
                    self.last_selection = command_type.title()
                    current_command.enabled = True

                    for item in [x for x in self.all_commands if x.command_type == command_type]:
                        if item.client_index == 0 or item.client_id == 0:
                            continue
                        client_id = item.client_id
                        req = {'command_index': item.command_index}
                        self.server_socket.send_rev(client_id, [LauncherCommand.ExecuteCommand, req])
                        resp = self.server_socket.recv_rev(client_id)
                        resp = json.loads(resp.decode())
                        item.enabled = resp['enabled']

                elif current_command.enabled:
                    self.last_selection = 'Stop'
                    req = {'command_index': current_command.command_index}
                    self.server_socket.send_rev(current_client_id, [LauncherCommand.StopCommand, req])
                    resp = self.server_socket.recv_rev(current_client_id)
                    resp = json.loads(resp.decode())
                    current_command.enabled = resp['enabled']

                else:
                    self.last_selection = 'Run'
                    req = {'command_index': current_command.command_index}
                    self.server_socket.send_rev(current_client_id, [LauncherCommand.ExecuteCommand, req])
                    resp = self.server_socket.recv_rev(current_client_id)
                    resp = json.loads(resp.decode())
                    current_command.enabled = resp['enabled']

            elif ch == b'c':
                self.last_selection = 'Clear'
                common_cmd = find_one(self.all_commands, lambda x: x.client_index == 0 and x.command_type == 'clear')
                common_cmd.enabled = True

                for item in [x for x in self.all_commands if x.command_type == 'clear']:
                    if item.client_index == 0 or item.client_id == 0:
                        continue
                    client_id = item.client_id
                    req = {'command_index': item.command_index}
                    self.server_socket.send_rev(client_id, [LauncherCommand.ExecuteCommand, req])
                    resp = self.server_socket.recv_rev(client_id)
                    resp = json.loads(resp.decode())
                    item.enabled = resp['enabled']

            elif ch == b'r':
                self.last_selection = 'Reload'
                # print(f'{LINE_START}Selection: {Fore.YELLOW}Reload{Fore.RESET}')
                self.load_commands(True)
                self.printed_lines.append('')

            elif ch == b'h':
                self.show_help = not self.show_help
                self.last_selection = 'Help'

            elif ch == b'v':
                self.verbosity_level = (self.verbosity_level + 1) % 2
                for client_id in self.ordered_client_ids:
                    self.server_socket.send_rev(
                        client_id,
                        [
                            LauncherCommand.SetConfig,
                            {'verbosity_level': self.verbosity_level}
                        ]
                    )
                    self.server_socket.recv_rev(client_id)

                self.last_selection = f'Level {self.verbosity_level}'

            elif ch == b'{left}' or ch == b'{right}':
                left = ch == b'{left}'
                self.last_selection = 'Inc' if not left else 'Dec'
                current_command = self.visible_commands[self.selected_index]
                current_client_id = current_command.client_id
                params = get_param_dict(current_command.command_parameters)
                command_keys = list(params.keys())
                last_key = command_keys[len(command_keys) - 1] if command_keys else ''
                req = None

                if current_command.enabled:
                    pass

                elif current_client_id == 0:
                    pass

                elif not self.ordered_client_ids:
                    pass

                elif last_key == '':
                    pass

                elif last_key and \
                        isinstance(params[last_key], str) and \
                        is_number(params[last_key]):
                    value = int(params[last_key])
                    value += -1 if left else 1
                    value = str(value)
                    params[last_key] = value
                    req = {
                        'command_index': current_command.command_index,
                        'command_parameters': get_dict_text(params)
                    }
                    self.server_socket.send_rev(current_client_id, [LauncherCommand.SetParameter, req])
                    resp = self.server_socket.recv_rev(current_client_id)
                    resp = json.loads(resp.decode())
                    current_command.command_parameters = resp['command_parameters']

                else:
                    assert False, f'Unknown last key: {last_key}'

            elif ch == b'{up}':
                # self.last_selection = 'Scroll'
                self.selected_index -= 1
                self.selected_index = max(self.selected_index, 0)

            elif ch == b'{down}':
                # self.last_selection = 'Scroll'
                self.selected_index += 1
                self.selected_index = min(self.selected_index, len(self.visible_commands) - 1)

            elif ch == b'{pgup}':
                # self.last_selection = 'Scroll'
                self.selected_index -= 10
                self.selected_index = max(self.selected_index, 0)

            elif ch == b'{pgdn}':
                # self.last_selection = 'Scroll'
                self.selected_index += 10
                self.selected_index = min(self.selected_index, len(self.visible_commands) - 1)

            elif ch == b'{home}':
                # self.last_selection = 'Scroll'
                self.selected_index = 0

            elif ch == b'{end}':
                # self.last_selection = 'Scroll'
                self.selected_index = len(self.visible_commands) - 1

            elif ch == b'q' or ch == b'w':
                print(f'{LINE_START}Selection: {Fore.YELLOW}Quit{Fore.RESET}')
                self.is_alive = False
                break

            # elif ch == b'e':
            #     self.last_selection = 'Edit'
            #     os.system(f'code {self.demo_config}')

            elif ch == b's' or ch == b'k' or ch == b'x' or ch == b'{esc}':
                self.last_selection = 'Stop'
                common_cmd = find_one(self.all_commands, lambda x: x.client_index == 0 and x.command_type == 'stop')
                common_cmd.enabled = True

                for item in [x for x in self.all_commands if x.command_type == 'stop']:
                    if item.client_index == 0 or item.client_id == 0:
                        continue
                    client_id = item.client_id
                    req = {'command_index': item.command_index}
                    self.server_socket.send_rev(client_id, [LauncherCommand.ExecuteCommand, req])
                    resp = self.server_socket.recv_rev(client_id)
                    resp = json.loads(resp.decode())
                    item.enabled = resp['enabled']

    def socket_reader(self):
        self.is_ready = True
        while self.is_alive:
            client_id, req = self.server_socket.recv_norm()
            if not self.is_alive:
                break
            if not req:
                time.sleep(0.1)
                continue
            method_name = req[0].decode()
            command_parameters = json.loads(req[1].decode())
            self.server_socket.send_norm(
                client_id,
                [
                    f'response:{method_name}',
                    {'unknown': True}
                ]
            )
            assert False, f'Unknown server call: {method_name}'

    def update_clients(self, client_ids):
        # Ensure new ids are added to the sorted list
        #
        for client_id in client_ids:
            assert self.server_socket.get_client_info(client_id).client_metadata['start_time']
            assert self.server_socket.get_client_info(client_id).client_metadata['fixed_start_time']
        sorted_list = list(client_ids)
        sorted_list.sort(
            key=lambda x: self.server_socket.get_client_info(x).client_metadata['fixed_start_time']
        )
        self.ordered_client_ids = sorted_list

        # Assign client ids
        #
        for item in self.all_commands:
            if item.client_index == 0:
                continue
            client_id = self.ordered_client_ids[item.client_index -
                                                1] if item.client_index - 1 < len(self.ordered_client_ids) else 0
            item.client_id = client_id

        for client_id in self.ordered_client_ids:
            if client_id == 0:
                continue
            executables = []
            client_index = self.ordered_client_ids.index(client_id) + 1
            assert client_index > 0

            for item in self.all_commands:
                if not client_index:
                    continue
                if item.client_index != client_index:
                    continue
                executables.append({
                    'client_index': item.client_index,
                    'client_id': item.client_id,
                    'command_index': item.command_index,
                    'command_type': item.command_type,
                    'command_entry': item.command_entry,
                    'command_parameters': item.command_parameters,
                    'visible': item.visible,
                })

            resp = None
            with self.server_socket.request_lock:
                self.server_socket.send_rev(
                    client_id,
                    [
                        LauncherCommand.SetExecutables,
                        {'version': 1, 'executables': executables}
                    ]
                )
                resp = self.server_socket.recv_rev(client_id)
                resp = json.loads(resp.decode())

            for item in resp['executables']:
                cmd_info = find_all(
                    self.all_commands,
                    lambda x:
                        x.client_index == client_index and
                        x.client_id == client_id and
                        x.command_index == item['command_index']
                )
                assert len(cmd_info) == 1
                cmd_info[0].enabled = item['enabled']

        for client_id in self.ordered_client_ids:
            if client_id == 0:
                continue
            with self.server_socket.request_lock:
                self.server_socket.send_rev(
                    client_id,
                    [
                        LauncherCommand.SetConfig,
                        {'verbosity_level': self.verbosity_level}
                    ]
                )
                self.server_socket.recv_rev(client_id)

    def print_commands(self):
        lines = []
        lines.extend(self.custom_lines)
        lines.extend(['[TERMINAL UI]', ''])
        # lines = []
        cmd_index = -1
        prefix = ''
        last_client_index = -1
        for command in self.visible_commands:
            cmd_index += 1
            arrow = '  '
            if self.selected_index == cmd_index:
                arrow = f'{Fore.YELLOW}->{Fore.RESET}'
            colr = Fore.RESET
            colr2 = Style.DIM+Fore.YELLOW
            if command.enabled:
                colr = Fore.BLUE
                colr2 = Fore.YELLOW
            elif command.client_index > 0 and command.client_id == 0:
                colr = f'{Style.DIM}{colr}'

            cmd_num = ''
            command_type = command.command_type
            command_entry = command.command_entry
            command_final = f'{command_type} {command_entry}'.strip()
            if self.verbosity_level >= 1:
                cmd_num = f'{Fore.GREEN}[{command.command_index}]{Fore.RESET} '
            else:
                cmd_num = ''

            if last_client_index != command.client_index:
                last_client_index = command.client_index
                if command.client_index == 0:
                    lines.append(
                        f'    {Style.DIM}{Fore.RESET}-------------- all --------------{Fore.RESET}{Style.NORMAL}')
                    # pass
                else:
                    lines.append('')
                    lines.append(
                        f'    {Style.DIM}{Fore.RESET}--------------- {command.client_index} ---------------{Fore.RESET}{Style.NORMAL}')

            lines.append(
                f'{prefix} {arrow} {cmd_num}{colr}{command_final}{Fore.RESET}{Style.NORMAL} '
                f'{colr2}{command.command_parameters}{Fore.RESET}'
                f'{Style.NORMAL}'
            )

        lines.append('')

        # Uncomment to track update counts
        #   lines.append(f'Update tracker: {self.update_count}, {self.server_socket.get_client_ids()}, {self.ordered_client_ids}')
        #   lines.append('')
        
        if self.show_help:
            lines.append('Help:')
            lines.append('    C - clear, S - stop, V - verbose, H - help')
            lines.append('    Up/Down - scroll, Space - run, Enter - run')
            lines.append('    Left/Right - adjust, Esc - stop, Q - exit')
            lines.append('')

        set_cursor_visibile(False)
        index = len(self.printed_lines)
        for item in self.printed_lines:
            index -= 1
            if index >= len(lines):
                print(LINE_CLEAR + LINE_UP, end='')
            else:
                print(LINE_UP, end='')
        print(LINE_START, flush=True, end='')
        self.printed_lines = lines
        for item in lines:
            print(f'{LINE_CLEAR}{item}')
        print(f'{LINE_CLEAR}Selection: {Fore.GREEN}{self.last_selection}{Fore.RESET}', end='', flush=True)
        set_cursor_visibile(True)
