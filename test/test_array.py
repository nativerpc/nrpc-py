import nrpc_py
import time
import sys
from nrpc_py import rpcclass
from dataclasses import field

@rpcclass({
    'name': 1,
    'value': 2,
    'newonserver': 3,
})
class ChildInfo:
    name: str = 0
    value: int = 0
    newonserver: int = 0

@rpcclass({
    'name': 1,
    'value': 2,
    'newonclient': 4,
})
class ChildInfo_Client:
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
    'summary': 1,
    'values': 2,
    'echos': 3
})
class ParentInfo_Client:
    summary: str = ''
    values: list[int] = field(default_factory=list)
    echos: list[ChildInfo_Client] = field(default_factory=list)


@rpcclass({
    'Hello': 1,
    'Hello2': 2,
})
class HelloService:
    def Hello(self, request: ParentInfo) -> ParentInfo:
        pass

    def Hello2(self, request: ParentInfo) -> list[ParentInfo]:
        pass


@rpcclass({
    'Hello': 1,
    'Hello2': 2,
})
class HelloService_Client:
    def Hello(self, request: ParentInfo_Client) -> ParentInfo_Client:
        pass

    def Hello2(self, request: ParentInfo_Client) -> list[ParentInfo_Client]:
        pass


class HelloServer:
    def __init__(self):
        self.counter = 0

    def Hello(self, request: ParentInfo) -> ParentInfo:
        print(f'CALL HelloServer.Hello, {self.counter}, {request}')
        self.counter += 1
        return ParentInfo(summary=f'test={self.counter}', values=[2, 3, 4], echos=[*request.echos])

    def Hello2(self, request: ParentInfo) -> list[ParentInfo]:
        print(f'CALL HelloServer.Hello2, {self.counter}, {request}')
        self.counter += 1
        return [ParentInfo(summary=f'test={self.counter}', values=[2, 3, 4], echos=[*request.echos])]


def start():
    cmd = nrpc_py.CommandLine(line=sys.argv, fields={
        'port': 9002,
        'format': 'json',
        'wait': 10,
    })

    sock1 = nrpc_py.RoutingSocket(nrpc_py.RoutingSocketOptions(
        type=nrpc_py.SocketType.BIND,
        protocol=nrpc_py.ProtocolType.TCP,
        format=nrpc_py.FormatType.JSON,
        caller='test_array_py_server',
        types=[
            ChildInfo,
            ParentInfo,
            [HelloService, HelloServer()],
        ]
    ))
    sock2 = nrpc_py.RoutingSocket(nrpc_py.RoutingSocketOptions(
        type=nrpc_py.SocketType.CONNECT,
        protocol=nrpc_py.ProtocolType.TCP,
        format=nrpc_py.FormatType.JSON,
        caller='test_array_py_client',
        types=[
            ChildInfo_Client,
            ParentInfo_Client,
            HelloService_Client,
        ],
        drop_postfix='_Client'
    ))

    sock1.bind('127.0.0.1', cmd['port'])
    print(f'START Server started, {cmd["port"]}')
    sock2.connect('127.0.0.1', cmd['port'], wait=True, sync=True)
    print(f'START Client started, {cmd["port"]}')

    start = time.time()
    while time.time() - start < cmd['wait']:
        req = ParentInfo_Client(summary='tester1', values=[1, 2, 3], echos=[ChildInfo_Client(name='tester1', value=555)])
        res = sock2.cast(HelloService_Client).Hello(req)
        print(f'SEND Hello, 1, {res}')

        time.sleep(1.0)

    sock2.close()
    sock1.close()


if __name__ == '__main__':
    start()
