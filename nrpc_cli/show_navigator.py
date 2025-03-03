#
#   Contents:
#
#       ShowNavigator
#           __init__
#           create_sockets
#           read_sockets
#           main_loop
#           print_window
#
from colorama import Fore, Style
import time
import nrpc_py
from nrpc_cli.common_base import (
    LINE_UP,
    LINE_START,
    LINE_CLEAR,
    set_cursor_visibile,
    get_key_down,
    get_keyboard_char,
)
from nrpc_py.common_base import (  # noqa
    ctrl_handler,
)


class ShowNavigator:
    is_alive: bool
    is_ready: bool
    printed_lines: list[str]
    drill_down_level: int
    selected_index: list[int]
    selected_counts: list[int]
    show_help: bool
    last_selection: str
    last_selection_start: float
    client_sockets: list[nrpc_py.RoutingSocket]
    client_data: list[any]

    def __init__(self):
        self.is_alive = True
        self.is_ready = False
        self.printed_lines = []
        self.drill_down_level = 0
        self.selected_index = [0] * 3
        self.selected_counts = [0] * 3
        self.show_help = False
        self.last_selection = ''
        self.last_selection_start = 0
        self.client_sockets = [None] * 10
        self.client_data = []

    def create_sockets(self):
        start = 9000
        for index in range(len(self.client_sockets)):
            if not self.is_alive:
                break
            if self.client_sockets[index] and \
                self.client_sockets[index].client_socket.is_validated and \
                    self.client_sockets[index].client_socket.is_lost:
                # print(f'Client lost, #{index}')
                self.client_sockets[index].close()
                self.client_sockets[index] = None
                time.sleep(0.5)
            if self.client_sockets[index]:
                continue
            sock = nrpc_py.RoutingSocket(nrpc_py.RoutingSocketOptions(
                type=nrpc_py.SocketType.CONNECT,
                protocol=nrpc_py.ProtocolType.TCP,
                format=nrpc_py.FormatType.JSON,
                caller='show_navigator_py',
                types=[]
            ))
            sock.connect('127.0.0.1', start + index, wait=False, sync=False)
            self.client_sockets[index] = sock

    def read_sockets(self):
        found = 0
        node_index = 0
        client_data = []
        if not self.is_alive:
            self.client_data = []
            return
        self.create_sockets()

        for sock in self.client_sockets:
            if not self.is_alive:
                break
            if not sock:
                continue
            if not sock.client_socket.is_validated:
                continue
            if sock.client_socket.is_lost:
                continue
            app_info: nrpc_py.ApplicationInfo = sock.server_call(nrpc_py.RoutingMessage.GetAppInfo, {})
            schema_info: nrpc_py.SchemaInfo = sock.server_call(nrpc_py.RoutingMessage.GetSchema, {})

            found += 1

            schema_clients: list[nrpc_py.SchemaInfo.SchemaClientInfo] = schema_info['clients']
            schema_clients = [x for x in schema_clients if not x['is_lost']
                              and x['client_id'] != schema_info['active_client']]

            assert app_info['server_id'] == sock.port, f'Port mismatch: {app_info["server_id"]}, {sock.port}'
            assert schema_info['server_id'] == sock.port, f'Port mismatch: {schema_info["server_id"]}, {sock.port}'
            assert schema_info['client_id'] == 0
            assert sock.port == app_info['server_id']

            node_index += 1
            client_data.append({
                'server_id': app_info['server_id'],
                'client_id': 0,
                'app_info': app_info,
                'schema_info': schema_info,
                'main_port': sock.port,
            })
            for item in schema_clients:
                node_index += 1
                client_id = item['client_id']
                app_info2: nrpc_py.ApplicationInfo = sock.forward_call(client_id, nrpc_py.RoutingMessage.GetAppInfo, {})
                schema_info2: nrpc_py.SchemaInfo = sock.forward_call(client_id, nrpc_py.RoutingMessage.GetSchema, {})
                client_data.append({
                    'server_id': app_info['server_id'],
                    'client_id': item['client_id'],
                    'app_info': app_info2,
                    'schema_info': schema_info2,
                    'main_port': item['main_port'],
                })

        self.client_data = client_data

    def main_loop(self):
        time.sleep(2.0)
        self.read_sockets()

        while self.is_alive:
            if self.last_selection:
                self.last_selection_start = time.time()

            self.print_window()
            self.last_selection = ''

            just_update = False
            last_check = time.time()

            while self.is_alive and not just_update:
                if get_key_down():
                    break
                if self.last_selection_start and time.time() - self.last_selection_start > 0.5:
                    self.last_selection_start = 0
                    just_update = True
                    break

            if not self.is_alive or just_update:
                continue

            ch = get_keyboard_char()
            if ch == b'h':
                self.show_help = not self.show_help

            elif ch == b'r':
                self.last_selection = 'Read'
                self.drill_down_level = 0
                self.selected_index = [0] * 3
                self.selected_counts = [0] * 3
                self.read_sockets()

            elif ch == b'{space}' or ch == b'{enter}':
                if self.drill_down_level < 2:
                    self.drill_down_level += 1
                    self.selected_index[self.drill_down_level] = 0

            elif ch == b'{esc}':
                if self.drill_down_level > 0:
                    self.drill_down_level -= 1

            elif ch == b'{left}':
                self.selected_index[0] -= 1
                self.selected_index[0] = max(self.selected_index[0], 0)

            elif ch == b'{right}':
                self.selected_index[0] += 1
                self.selected_index[0] = min(self.selected_index[0], self.selected_counts[0] - 1)

            elif ch == b'{up}':
                self.selected_index[self.drill_down_level] -= 1
                self.selected_index[self.drill_down_level] = max(self.selected_index[self.drill_down_level], 0)

            elif ch == b'{down}':
                self.selected_index[self.drill_down_level] += 1
                self.selected_index[self.drill_down_level] = min(
                    self.selected_index[self.drill_down_level], self.selected_counts[self.drill_down_level] - 1)

            elif ch == b'{pgup}':
                # self.last_selection = 'Scroll'
                self.selected_index[self.drill_down_level] -= 10
                self.selected_index[self.drill_down_level] = max(self.selected_index[self.drill_down_level], 0)

            elif ch == b'{pgdn}':
                # self.last_selection = 'Scroll'
                self.selected_index[self.drill_down_level] += 10
                self.selected_index[self.drill_down_level] = min(
                    self.selected_index[self.drill_down_level], self.selected_counts[self.drill_down_level] - 1)

            elif ch == b'{home}':
                # self.last_selection = 'Scroll'
                self.selected_index[self.drill_down_level] = 0

            elif ch == b'{end}':
                # self.last_selection = 'Scroll'
                self.selected_index[self.drill_down_level] = self.selected_counts[self.drill_down_level] - 1

            elif ch == b'q' or ch == b'w':
                print(f'{LINE_START}{LINE_CLEAR}Selection: {Fore.YELLOW}Quit{Fore.RESET}')
                self.is_alive = False
                break

            else:
                pass

    def print_window(self):
        y = Fore.YELLOW
        g = Fore.GREEN
        b = Fore.BLUE
        m = Fore.MAGENTA
        r = Fore.RESET
        reset = Fore.RESET + Style.NORMAL
        rd = Fore.RED
        lines = []
        node_index = 0

        lines.append('[NETWORK TOPOLOGY]')
        lines.append('')
        lines.append(
            f'    {Style.DIM}{Fore.RESET}-------------- nodes --------------{Fore.RESET}{Style.NORMAL}'
        )
        for item in self.client_data:
            node_index += 1
            app_info: nrpc_py.ApplicationInfo = item['app_info']
            schema_info: nrpc_py.SchemaInfo = item['schema_info']
            app_clients: list[nrpc_py.ApplicationInfo.AppClientInfo] = app_info['clients']
            schema_clients: list[nrpc_py.SchemaInfo.SchemaClientInfo] = schema_info['clients']
            error_id = 0
            for item2 in schema_info['services']:
                if item2['service_errors']:
                    error_id = 1
                for item3 in schema_info['methods']:
                    if item3['service_name'] != item2['service_name']:
                        continue
                    if item3['method_errors']:
                        error_id = 2
            for item2 in schema_info['types']:
                if item2['type_errors']:
                    error_id = 3
                for item3 in schema_info['fields']:
                    if item3['type_name'] != item2['type_name']:
                        continue
                    if item3['field_errors']:
                        error_id = 4
            error_text = f'{rd}E{error_id}{r}' if error_id > 0 else 'none'
            arrow = f'{y}->{r}' if self.selected_index[0] == node_index - 1 else '  '
            if self.drill_down_level == 0 and arrow.strip():
                arrow = f'{g}->{r}'
            color = Fore.MAGENTA

            if item['client_id'] == 0:
                lines.append(
                    f' {arrow} '
                    f'{node_index}. {color}SERVER{reset} host={app_info["ip_address"]} '
                    f'port={y}{app_info["server_id"]}{r} '
                    f'id={y}{app_info["entry_file"]}{r} error={error_text}'
                )
            else:
                lines.append(
                    f' {arrow} '
                    f'{node_index}. {color}CLIENT{reset} host={app_info["ip_address"]} '
                    f'port={y}{app_info["server_id"]}{r} num={y}#{app_info["client_id"]}{r} '
                    f'id={y}{app_info['entry_file']}{r} error={error_text}'
                )
        self.selected_counts[0] = node_index

        if self.drill_down_level >= 1:
            data = self.client_data[self.selected_index[0]]
            app_info: nrpc_py.ApplicationInfo = data['app_info']
            schema_info: nrpc_py.SchemaInfo = data['schema_info']

            lines.append('')
            lines.append(
                f'    {Style.DIM}{Fore.RESET}-------------- types --------------{Fore.RESET}{Style.NORMAL}'
            )
            type_index = 0
            for item in schema_info['services']:
                type_index += 1
                arrow = f'{y}->{r}' if self.selected_index[1] == type_index - 1 else '  '
                if self.drill_down_level == 1 and arrow.strip():
                    arrow = f'{g}->{r}'
                error_id = 0
                if item['service_errors']:
                    error_id = 1
                for item3 in schema_info['methods']:
                    if item3['service_name'] != item['service_name']:
                        continue
                    if item3['method_errors']:
                        error_id = 2
                error_text = f'{rd}E{error_id}{r}' if error_id > 0 else 'none'
                color = Fore.GREEN if item["local"] else Style.DIM + Fore.GREEN

                lines.append(
                    f' {arrow} {type_index}. {color}SERVICE{reset} name={y}{item["service_name"]}{r} '
                    f'server={y}{item["has_server"]}{r} '
                    f'error={error_text}'
                )

            for item in schema_info['types']:
                if item['type_name'] == nrpc_py.DYNAMIC_OBJECT:
                    continue
                fields = []
                for item2 in schema_info['fields']:
                    if item2['type_name'] != item['type_name']:
                        continue
                    fields.append(item2)
                type_index += 1
                arrow = f'{y}->{r}' if self.selected_index[1] == type_index - 1 else '  '
                if self.drill_down_level == 1 and arrow.strip():
                    arrow = f'{g}->{r}'
                error_id = 0
                if item['type_errors']:
                    error_id = 1
                for item3 in schema_info['fields']:
                    if item3['type_name'] != item['type_name']:
                        continue
                    if item3['field_errors']:
                        error_id = 2
                error_text = f'{rd}E{error_id}{r}' if error_id > 0 else 'none'
                color = Fore.BLUE if item["local"] else Style.DIM + Fore.BLUE

                lines.append(
                    f' {arrow} {type_index}. {color}TYPE{reset} name={y}{item["type_name"]}{r} '
                    f'error={error_text}'
                )
            self.selected_counts[1] = type_index

        if self.drill_down_level >= 2:
            data = self.client_data[self.selected_index[0]]
            app_info: nrpc_py.ApplicationInfo = data['app_info']
            schema_info: nrpc_py.SchemaInfo = data['schema_info']
            service_info = None
            type_info = None
            if self.selected_index[1] < len(schema_info['services']):
                service_info = schema_info['services'][self.selected_index[1]]
            else:
                type_info = schema_info['types'][self.selected_index[1] - len(schema_info['services'])]

            if service_info:
                lines.append('')
                lines.append(
                    f'    {Style.DIM}{Fore.RESET}-------------- methods --------------{Fore.RESET}{Style.NORMAL}'
                )
                field_index = 0
                for item in schema_info['methods']:
                    if item['service_name'] != service_info['service_name']:
                        continue
                    field_index += 1
                    arrow = f'{g}->{r}' if self.selected_index[2] == field_index - 1 else '  '
                    error_id = 0
                    if item['method_errors']:
                        error_id = 1
                    error_text = f'{rd}E{error_id}{r}' if error_id > 0 else 'none'
                    color = Fore.GREEN if item["local"] else Style.DIM + Fore.GREEN

                    lines.append(
                        f' {arrow} {field_index}. {color}METHOD{reset} name={y}{item["method_name"]}{r} '
                        f'request={y}{item["request_type"]}{r} response={y}{item["response_type"]}{r} '
                        f'id={y}{item["id_value"]}{r} '
                        f'error={error_text}'
                    )
                    if item['method_errors']:
                        lines.append(f'              {rd}{item["method_errors"].strip()}{r}')
                self.selected_counts[2] = field_index
            else:
                lines.append('')
                lines.append(
                    f'    {Style.DIM}{Fore.RESET}-------------- fields --------------{Fore.RESET}{Style.NORMAL}'
                )
                field_index = 0
                for item in schema_info['fields']:
                    if item['type_name'] != type_info['type_name']:
                        continue
                    field_index += 1
                    arrow = f'{g}->{r}' if self.selected_index[2] == field_index - 1 else '  '

                    error_id = 0
                    if item['field_errors']:
                        error_id = 1
                    error_text = f'{rd}E{error_id}{r}' if error_id > 0 else 'none'
                    color = Fore.BLUE if item["local"] else Style.DIM + Fore.BLUE

                    lines.append(
                        f' {arrow} {field_index}. {color}FIELD{reset} name={y}{item["field_name"]}{r} type={y}{item["field_type"]}{r} '
                        f'id={y}{item["id_value"]}{r} '
                        f'error={error_text}'
                    )
                    if item['field_errors']:
                        lines.append(f'             {rd}{item["field_errors"].strip()}{r}')

                self.selected_counts[2] = field_index

        lines.append('')

        if self.show_help:
            lines.append('Help:')
            lines.append('    Space - enter, Enter - enter, Esc - exit')
            lines.append('    Up/Down - scroll, Left/Right - node switch')
            lines.append('    R - read, Q - exit')
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
        print(f'{LINE_CLEAR}Selection: {Fore.GREEN}{self.last_selection}{r}', end='', flush=True)
        set_cursor_visibile(True)
