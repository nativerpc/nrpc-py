from nrpc_py.common_base import rpcclass
import nrpc_py


@rpcclass({
    'client_id': 1,
    'is_validated': 2,
    'is_lost': 3,
    'socket_name': 4,
})
class ExampleClass:
    client_id: int = 0
    is_validated: bool = False
    is_lost: bool = False
    socket_name: str = '-'


@rpcclass({
    'One': 1,
    'Two': 2,
})
class ExampleService:
    def One(self, request: ExampleClass) -> ExampleClass:
        pass

    def Two(self, request: dict) -> dict:
        pass


class ExampleServer:
    def One(self, request: ExampleClass) -> ExampleClass:
        print('CALL One called', request)
        return request

    def Two(self, request: dict) -> dict:
        print('CALL Two called', request)
        return request


class TestApplication:
    def start(self):
        port = 8910
        sock1 = nrpc_py.RoutingSocket(
            type=nrpc_py.SocketType.BIND,
            protocol=nrpc_py.ProtocolType.TCP,
            format=nrpc_py.FormatType.JSON,
            name='test_routing_server_py',
            types=[
                ExampleClass,
                [ExampleService, ExampleServer()]
            ],
        )
        sock2 = nrpc_py.RoutingSocket(
            type=nrpc_py.SocketType.CONNECT,
            protocol=nrpc_py.ProtocolType.TCP,
            format=nrpc_py.FormatType.JSON,
            name='test_routing_client_py',
            types=[
                ExampleClass,
                ExampleService
            ],
        )
        print(f'BIND {port}')
        sock1.bind('127.0.0.1', port)
        print(f'CONNECT {port}')
        sock2.connect('127.0.0.1', port)
        print('CALL')
        client: ExampleService = sock2.cast(ExampleService)
        resp = client.One(ExampleClass(client_id=123, is_validated=True))
        print('RESP', resp)
        resp = client.Two({'x': 123, 'y': True})
        print('RESP', resp)
        print('META1', sock1._get_app_info({}))
        print('META2', sock1._get_schema({}))
        print('META3', sock2._get_app_info({}))
        print('META4', sock2._get_schema({}))
        sock2.close()
        sock1.close()
        print('ALL OK')


if __name__ == '__main__':
    nrpc_py.init()
    app = TestApplication()
    app.start()
