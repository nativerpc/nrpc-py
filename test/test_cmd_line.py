from nrpc_py.common_base import (
    CommandLine
)
import nrpc_py


class TestApplication:
    def start(self):
        cmd = CommandLine({
            'port': 1000,
            'condition': False,
        })
        print(f'CMD port={cmd["port"]} condition={cmd["condition"]}')


if __name__ == '__main__':
    nrpc_py.init()
    app = TestApplication()
    app.start()
