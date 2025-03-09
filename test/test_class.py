from nrpc_py.common_base import (
    rpcclass, g_all_types, g_all_services,
    assign_values,
    construct_item,
    construct_json,
    get_class_string,
    CommandLine
)
import nrpc_py


@rpcclass({
    'client_id': 1,
    'is_validated': 2,
    'is_lost': 3,
    'socket_name': 4,
})
class SimpleData:
    client_id: int = 0
    is_validated: bool = False
    is_lost: bool = False
    socket_name: str = '-'


@rpcclass({
    'One': 1,
    'Two': 2,
})
class SimpleService:
    def One(self, request: SimpleData) -> SimpleData:
        pass

    def Two(self, request: dict) -> dict:
        pass


class TestApplication:
    def start(self):
        cmd = CommandLine({
            'port': 1000,
            'host': '-',
            'rate': 1.0,
        })
        print('CMD', cmd.as_string())
        assert isinstance(cmd['port'], int)
        assert isinstance(cmd['rate'], float)
        test = SimpleData(client_id=100, is_validated=True, socket_name='abc.py')
        temp = {}
        other = SimpleData()
        x = [test, other]
        y = []
        y2 = []
        z1 = {'a': 1, 'b': 2}
        z2 = {}
        z3 = {}
        assign_values('SimpleData', test, temp, 1)
        assign_values('SimpleData', other, temp, 0)
        assign_values('SimpleData[]', x, y, 1)
        assign_values('SimpleData[]', y2, y, 0)
        assign_values('dict', z1, z2, 1)
        assign_values('dict', z3, z2, 0)
        assert x == y2
        assert z1 == z3
        print('TEST', test)
        print('JSON', other)
        print('JSON', construct_json(test))
        print('LIST', x)
        print('LIST', y)
        print('DICT', z1)
        print('DICT', z3)
        print('TYPE', g_all_types['SimpleData'])
        print('SERVICE', g_all_services['SimpleService'])
        print('STR', get_class_string('SimpleData[]', x))
        print('CTOR', construct_item('SimpleData[]', [{'client_id': 123, 'is_validated': True}]))


if __name__ == '__main__':
    nrpc_py.init()
    app = TestApplication()
    app.start()
