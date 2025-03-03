#
#   Contents:
#
#       start
#
import sys
import os
import colorama
from nrpc_cli.show_navigator import ShowNavigator
from nrpc_cli.common_base import (
    set_line_wrap,
    init_term,
    set_normal_term,
    clear_terminal,
)
import traceback


def start():
    colorama.init()

    if '-wrap' in sys.argv or '--wrap' in sys.argv:
        colorama.init()
        res = set_line_wrap(None, toggle=True)
        if res:
            print('Lines wrapped')
        else:
            print('Lines full')

    else:
        colorama.init()
        init_term(line_wrap=False)
        clear_terminal()

        try:
            nav = ShowNavigator()
            nav.create_sockets()
            nav.main_loop()
        except KeyboardInterrupt:
            set_normal_term()
            print('Keyboard exit')
            os._exit(0)
        except:  # noqa
            set_normal_term()
            traceback.print_exc(file=sys.stderr)
            os._exit(0)

        os._exit(0)


if __name__ == '__main__':
    start()
