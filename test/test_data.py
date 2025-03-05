import json
from typing import TypedDict
import nrpc_py


class AppInfo(TypedDict):
    class AppClientInfo(TypedDict):
        client_id: int
        is_validated: bool
        is_lost: bool
        entry_file: str

    clients: list[AppClientInfo]
    entry_file: str


class TestApplication:
    def start(self):
        list: AppInfo = AppInfo(
            clients=[]
        )
        print('LIST', list['clients'])
        list['clients'].append(AppInfo.AppClientInfo(client_id=12, is_validated=False))
        print('LIST', json.dumps(list))


if __name__ == '__main__':
    nrpc_py.init()
    app = TestApplication()
    app.start()
