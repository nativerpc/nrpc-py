import nrpc_py
import time
from nrpc_py import rpcclass
from dataclasses import field
import nrpc_py


@rpcclass({
    'name': 1,
    'value': 2,
    'newonclient': 4,
})
class ChildInfo:
    name: str = 0
    value: int = 0
    newonclient: int = 0


@rpcclass({
    'summary': 1,
    'values': 2,
    'echos': 3
})
class ParentInfo:
    summary: str = ''
    values: list[int] = field(default_factory=list)
    echos: list[ChildInfo] = field(default_factory=list)


@rpcclass({
    'Hello': 1,
    'Hello2': 2,
})
class HelloService:
    def Hello(self, request: ParentInfo) -> ParentInfo:
        pass

    def Hello2(self, request: ParentInfo) -> list[ParentInfo]:
        pass


class ClientApplication:
    def start(self):
        cmd = nrpc_py.CommandLine({
            'port': 9002,
            'format': 'json',
            'wait': 10,
            'from_server': False,
        })

        assert cmd['from_server']

        print(f'START Client started, {cmd["port"]}')

        sock = nrpc_py.RoutingSocket(nrpc_py.RoutingSocketOptions(
            type=nrpc_py.SocketType.CONNECT,
            protocol=nrpc_py.ProtocolType.TCP,
            format=nrpc_py.FormatType.JSON,
            caller='test_array_py',
            types=[
                ChildInfo,
                ParentInfo,
                HelloService,
            ]
        ))

        sock.connect('127.0.0.1', cmd['port'], wait=True, sync=True)

        start = time.time()
        while time.time() - start < cmd['wait']:
            req = ParentInfo(summary='tester1', values=[1, 2, 3], echos=[
                ChildInfo(name='tester1', value=555)])
            res = sock.cast(HelloService).Hello(req)
            print(f'SEND Hello, 1, {res}')

            time.sleep(1.0)

        sock.close()


if __name__ == '__main__':
    nrpc_py.init()
    app = ClientApplication()
    app.start()
