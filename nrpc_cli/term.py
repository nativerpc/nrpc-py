#
#   Contents:
#
#       start
#
import sys
import os
import colorama
import traceback
from colorama import Fore
from nrpc_cli.common_base import (
    LINE_START,
    LINE_CLEAR,
    set_line_wrap,
    init_term,
    set_normal_term,
    clear_terminal,
)
from . import term_executor
from . import term_launcher


def start():
    if '-wrap' in sys.argv or '--wrap' in sys.argv:
        colorama.init()
        res = set_line_wrap(None, toggle=True)
        if res:
            print('Lines wrapped')
        else:
            print('Lines full')

    elif '-ui' in sys.argv or '--ui' in sys.argv:
        colorama.init()
        init_term(line_wrap=False)
        clear_terminal()

        command_args = [x for x in sys.argv[1:] if not x.startswith('-')]

        try:
            app = term_launcher.TermLauncher(command_args)
            app.print_commands()
            app.main_loop()
        except KeyboardInterrupt:
            set_normal_term()
            print(f'{LINE_START}{LINE_CLEAR}Selection: {Fore.YELLOW}Quit{Fore.RESET}')
            print('Keyboard exit')
            os._exit(0)
        except:  # noqa
            set_normal_term()
            traceback.print_exc(file=sys.stderr)
            os._exit(0)

        os._exit(0)

    else:
        colorama.init()
        app = term_executor.TermExecutor()
        try:
            app.main_loop()
        except KeyboardInterrupt:
            print('Keyboard exit')
            os._exit(0)
        except:  # noqa
            traceback.print_exc(file=sys.stderr)
            os._exit(0)


if __name__ == '__main__':
    start()

__all__ = [
    start
]
