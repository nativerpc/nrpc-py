#
#   Contents:
#
#       LauncherCommand
#       LINE_XXX
#       OS_CONFIG_XXX
#       g_stdin_xxx
#       g_cursor_xxx
#       ProcessInfo
#       CommandInfo
#       set_line_wrap
#       init_term
#       set_normal_term
#       clear_terminal
#       ConsoleCursorInfo
#       set_cursor_visibile
#       get_key_down
#       get_keyboard_char
#       find_one
#       find_all
#       get_param_dict
#       get_dict_text
#       is_number
#       get_line_nonblock
#
import os
import sys
import json
from dataclasses import dataclass
import select
import atexit
import subprocess
import ctypes
if os.name == 'nt':
    import msvcrt
else:
    import termios
from nrpc_py import ctrl_handler  # noqa

LAUNCHER_PORT = 8900


class LauncherCommand:
    SetExecutables = 'TermLauncher.SetExecutables'
    GetState = 'TermLauncher.GetState'
    SetConfig = 'TermLauncher.SetConfig'
    GetConfig = 'TermLauncher.GetConfig'
    SetParameter = 'TermLauncher.SetParameter'
    ExecuteCommand = 'TermLauncher.ExecuteCommand'
    StopCommand = 'TermLauncher.StopCommand'


LINE_UP = '\033[1A'
LINE_START = '\r'
LINE_START2 = '\x1b[1G'
LINE_CLEAR = '\x1b[2K'
OS_CONFIG_PYTHON = 'python'
OS_CONFIG_TERMINAL = ''
if os.name == 'nt':
    OS_CONFIG_TERMINAL = os.path.expanduser(
        '~/AppData/Local/Packages/Microsoft.WindowsTerminal_8wekyb3d8bbwe/LocalState/settings.json')
# OS_CONFIG_LAUNCHER = os.path.expanduser('~/.config/nrpc_launcher/config.json')

g_stdin_fileno = 0
g_stdin_settings = None
g_cursor_info = None


@dataclass
class ProcessInfo:
    name: str
    handle: subprocess.Popen = None
    result: int | None = None
    stopped: bool = False


@dataclass
class CommandInfo:
    client_index: int = 0
    client_id: int = 0
    command_index: int = 0
    command_type: str = ''
    command_entry: str = ''
    command_parameters: str = ''
    visible: bool = False
    enabled: bool = False
    command_process: ProcessInfo | None = None


def set_line_wrap(line_wrap, toggle=False):
    if os.name == 'nt':
        assert os.path.exists(OS_CONFIG_TERMINAL)
        wt_config = {}
        changed = False
        with open(OS_CONFIG_TERMINAL, 'rt') as file:
            wt_config = json.load(file)
        if toggle:
            line_wrap = wt_config['profiles']['defaults'].get('padding', '') != ''
        if line_wrap:
            if 'padding' in wt_config['profiles']['defaults']:
                changed = True
                del wt_config['profiles']['defaults']['padding']
        else:
            if wt_config['profiles']['defaults'].get('padding', '') != '0, 0, -10000, 0':
                changed = True
                wt_config['profiles']['defaults']['padding'] = '0, 0, -10000, 0'
        if changed:
            with open(OS_CONFIG_TERMINAL, 'wt') as file:
                json.dump(wt_config, file, indent=4)
        return line_wrap
    else:
        if line_wrap:
            os.system('setterm -linewrap on')
        else:
            os.system('setterm -linewrap off')
        return line_wrap


def init_term(line_wrap):
    global g_stdin_fileno, g_stdin_settings

    if os.name == 'nt':
        pass
    else:
        if line_wrap:
            os.system('setterm -linewrap on')
        else:
            os.system('setterm -linewrap off')

        if not g_stdin_settings:
            g_stdin_fileno = sys.stdin.fileno()
            g_stdin_settings = termios.tcgetattr(g_stdin_fileno)

        settings = termios.tcgetattr(g_stdin_fileno)
        settings[3] = (settings[3] & ~termios.ICANON & ~termios.ECHO)
        termios.tcsetattr(g_stdin_fileno, termios.TCSAFLUSH, settings)

    atexit.register(set_normal_term)


def set_normal_term():
    global g_stdin_fileno, g_stdin_settings
    # set_line_wrap(True)

    if os.name == 'nt':
        pass
    else:
        os.system('setterm -linewrap on')
        if g_stdin_settings:
            termios.tcsetattr(g_stdin_fileno, termios.TCSAFLUSH, g_stdin_settings)


def clear_terminal():
    if os.name == 'nt':
        os.system('cls')
    else:
        os.system('clear')


class ConsoleCursorInfo(ctypes.Structure):
    _fields_ = [
        ("dwSize", ctypes.c_uint),
        ("bVisible", ctypes.c_bool)
    ]


def set_cursor_visibile(value):
    global g_cursor_info
    if os.name == 'nt':
        stdout_num = ctypes.windll.kernel32.GetStdHandle(-11)
        # stdout_fileno = sys.stdout.fileno()
        if not g_cursor_info:
            g_cursor_info = ConsoleCursorInfo()
            ctypes.windll.kernel32.GetConsoleCursorInfo(stdout_num, ctypes.byref(g_cursor_info))
        g_cursor_info.bVisible = value
        ctypes.windll.kernel32.SetConsoleCursorInfo(stdout_num, ctypes.byref(g_cursor_info))


def get_key_down():
    if os.name == 'nt':
        return msvcrt.kbhit()
    else:
        dr, dw, de = select.select([sys.stdin], [], [], 0)
        return bool(dr)


def get_keyboard_char():
    global g_stdin_fileno
    if os.name == 'nt':
        res = msvcrt.getch()
        while get_key_down():
            res += msvcrt.getch()
        if res == b'\r' or res == b'\n':
            res = b'{enter}'
        elif res == b'\t':
            res = b'{tab}'
        elif res == b' ':
            res = b'{space}'
        elif res == b'\xe0K':
            res = b'{left}'
        elif res == b'\xe0M':
            res = b'{right}'
        elif res == b'\xe0H':
            res = b'{up}'
        elif res == b'\xe0P':
            res = b'{down}'
        elif res == b'\xe0I':
            res = b'{pgup}'
        elif res == b'\xe0Q':
            res = b'{pgdn}'
        elif res == b'\xe0G':
            res = b'{home}'
        elif res == b'\xe0O':
            res = b'{end}'
        elif res == b'\x1b':
            res = b'{esc}'
        if len(res) == 1 and res[0] >= ord('A') and res[0] <= ord('Z'):
            res = chr(res[0] - ord('A') + ord('a')).encode()
        return res
    else:
        res = os.read(g_stdin_fileno, 1)
        while get_key_down():
            res += os.read(g_stdin_fileno, 1)
        if res == b'\r' or res == b'\n':
            res = b'{enter}'
        elif res == b'\t':
            res = b'{tab}'
        elif res == b' ':
            res = b'{space}'
        elif res == b'\x1b[D':
            res = b'{left}'
        elif res == b'\x1b[C':
            res = b'{right}'
        elif res == b'\x1b[A':
            res = b'{up}'
        elif res == b'\x1b[B':
            res = b'{down}'
        elif res == b'\x1b[5~':
            res = b'{pgup}'
        elif res == b'\x1b[6~':
            res = b'{pgdn}'
        elif res == b'\x1b[H':
            res = b'{home}'
        elif res == b'\x1b[F':
            res = b'{end}'
        elif res == b'\x1b':
            res = b'{esc}'
        if len(res) == 1 and res[0] >= ord('A') and res[0] <= ord('Z'):
            res = chr(res[0] - ord('A') + ord('a')).encode()
        return res


def find_one(iterable, function):
    for item in iterable:
        if function(item):
            return item
    return None


def find_all(iterable, function):
    result = []
    for item in iterable:
        if function(item):
            result.append(item)
    return result


def get_param_dict(text):
    result = {}
    parts = [x for x in text.split(' ') if x]
    index = -1
    for item in parts:
        index += 1
        if '=' in item:
            parts2 = item.split('=')
            result[parts2[0]] = parts2[1]
        else:
            result[f'numbered:{index}'] = item
    return result


def get_dict_text(json):
    result = ''
    for key, value in json.items():
        if key.startswith('numbered:'):
            result += f'{value} '
        else:
            result += f'{key}={value} '
    return result.rstrip()


def is_number(text):
    try:
        int(text)
        return True
    except Exception:
        pass
    return False


def get_line_nonblock(output):
    try:
        return output.readline().decode().rstrip('\r\n')
    except:
        return None

    # if os.name == 'nt':
    #     rlist, _, _ = select.select([output], [], [], 0)
    #     if rlist:
    #         return output.read(1024).decode().rstrip('\r\n')
    #     return None
    # else:
    #     rlist, _, _ = select.select([output], [], [], 0)
    #     if rlist:
    #         return output.readline().decode().rstrip('\r\n')
    #     return None
