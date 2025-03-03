import sys
from nrpc_py.common_base import (
    rpcclass, all_types, all_services,
    assign_values,
    construct_item,
    get_class_string,
    CommandLine
)


@rpcclass({
    'client_id': 1,
    'is_validated': 2,
    'is_lost': 3,
    'entry_file': 4,
})
class SimpleData:
    client_id: int = 0
    is_validated: bool = False
    is_lost: bool = False
    entry_file: str = '-'


@rpcclass({
    'One': 1,
    'Two': 2,
})
class SimpleService:
    def One(self, request: SimpleData) -> SimpleData:
        pass

    def Two(self, request: dict) -> dict:
        pass


def start():
    cmd = CommandLine(line=sys.argv, fields={
        'port': 1000,
        'host': '-',
        'rate': 1.0,
    })
    print('CMD', cmd.as_string())
    assert isinstance(cmd['port'], int)
    assert isinstance(cmd['rate'], float)
    test = SimpleData(client_id=100, is_validated=True, entry_file='abc.py')
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
    print('LIST', x)
    print('LIST', y)
    print('DICT', z1)
    print('DICT', z3)
    print('TYPE', all_types['SimpleData'])
    print('SERVICE', all_services['SimpleService'])
    print('STR', get_class_string('SimpleData[]', x))
    print('CTOR', construct_item('SimpleData[]', [{'client_id': 123, 'is_validated': True}]))


if __name__ == '__main__':
    start()
