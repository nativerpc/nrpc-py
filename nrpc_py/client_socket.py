#
#   Contents:
#
#       ClientSocket
#           __init__
#           connect
#           send_norm
#           recv_norm
#           recv_rev
#           send_rev
#           _validate_client
#           _track_client
#           _get_buffer
#           add_metadata
#           is_validated
#           wait
#           close
#
import datetime
import json
import base64
import threading
import zmq
import zmq.utils.monitor
import time
import socket as _socket
import struct
from .common_base import ServerMessage, SocketMetadataInfo


class ClientSocket:
    client_id: int
    ip_address: str
    port: int
    port_rev: int
    entry_file: str
    server_signature: bytes
    server_signature_rev: bytes
    client_signature: bytes
    client_signature_rev: bytes
    is_alive: bool
    is_connected: bool
    is_validated_: bool
    is_lost: bool
    last_error: any
    metadata: SocketMetadataInfo
    server_metadata: SocketMetadataInfo
    zmq_client: zmq.Socket
    zmq_client_rev: zmq.Socket
    zmq_monitor: zmq.Socket
    zmq_monitor_thread: threading.ThreadError
    request_lock: threading.Lock

    def __init__(self, ip_address, port, port_rev, entry_file):
        self.client_id = 0
        self.ip_address = ip_address
        self.port = port
        self.port_rev = port_rev
        self.entry_file = entry_file
        self.server_signature = b'server:0'
        self.server_signature_rev = b'rev:server:0'
        self.client_signature = None
        self.client_signature_rev = None
        self.is_alive = True
        self.is_connected = False
        self.is_validated_ = False
        self.is_lost = False
        self.metadata = SocketMetadataInfo(
            client_id=None,
            lang='python',
            ip_address=ip_address,
            main_port=port,
            main_port_rev=port_rev,
            host=_socket.gethostname(),
            entry_file=self.entry_file,
            start_time=datetime.datetime.now().isoformat(),
            client_signature=None,
            client_signature_rev=None,
        )
        self.server_metadata = None
        self.zmq_context = None
        self.zmq_client = None
        self.zmq_client_rev = None
        self.zmq_monitor = None
        self.zmq_monitor_thread = None
        self.request_lock = threading.Lock()

    def connect(self):
        assert not self.is_validated_

        self.zmq_context = zmq.Context.instance()

        zmq_client = self.zmq_context.socket(zmq.ROUTER)
        zmq_client.connect(f'tcp://{self.ip_address}:{self.port}')

        self.zmq_client = zmq_client
        self.zmq_client_rev = None
        self.zmq_monitor = zmq_client.get_monitor_socket(zmq.Event.HANDSHAKE_SUCCEEDED | zmq.Event.DISCONNECTED)
        self.zmq_monitor_thread = threading.Thread(target=self._track_client)
        self.zmq_monitor_thread.start()

        while not self.is_connected:
            time.sleep(0.1)

        resp = None
        with self.request_lock:
            self.zmq_client.send_multipart([
                self.server_signature,
                ServerMessage.AddClient,
                json.dumps(self.metadata).encode()
            ])
            resp = self.zmq_client.recv_multipart()

        assert resp[1] == ServerMessage.ClientAdded
        resp = json.loads(resp[2].decode())

        self.client_id = resp['client_id']
        self.client_signature = base64.b64decode(resp['client_signature'])
        self.client_signature_rev = base64.b64decode(resp['client_signature_rev'])
        self.metadata['client_id'] = self.client_id
        self.metadata['client_signature'] = base64.b64encode(self.client_signature).decode('ascii')
        self.metadata['client_signature_rev'] = base64.b64encode(self.client_signature_rev).decode('ascii')

        # assert self.terminal_id == resp['terminal_id']
        assert self.zmq_client_rev is None

        zmq_client_rev = self.zmq_context.socket(zmq.ROUTER)
        zmq_client_rev.set(zmq.IDENTITY, self.client_signature_rev)
        zmq_client_rev.connect(f'tcp://{self.ip_address}:{self.port_rev}')

        self.zmq_client_rev = zmq_client_rev

        while True:
            req = self.zmq_client_rev.recv_multipart()
            assert len(req) == 3
            if req[1] == ServerMessage.ValidateClient:
                self._validate_client(req)
                break
            else:
                print('Early message on client side!')
                method_name = req[1].decode()
                self.zmq_client_rev.send_multipart([
                    self.server_signature_rev,
                    f'message_dropped:{method_name}'.encode(),
                    json.dumps({'error': 'Early message dropped'}).encode()
                ])

        assert self.is_validated_

    def send_norm(self, request):
        assert self.zmq_client_rev is not None
        req = [
            self.server_signature,
            self._get_buffer(request[0]),
            self._get_buffer(request[1]),
        ]
        assert len(req) == 3
        self.zmq_client.send_multipart(req)

    def recv_norm(self):
        rep = self.zmq_client.recv_multipart()
        assert len(rep) == 3
        assert rep[2] != b'null', 'Invalid null response'
        # TODO: getting empty buffer when client is lost
        assert rep[2][0] == b'{'[0] or rep[2][0] == b'['[0], f'Invalid json: {rep[2]}'
        return rep[2]

    def recv_rev(self, timeout=0):
        if not self.is_validated_:
            time.sleep(0.1)
            if not self.is_validated_:
                return None

        started = time.time()
        req = None
        while self.is_alive:
            parts = []
            try:
                parts.append(self.zmq_client_rev.recv(zmq.DONTWAIT, copy=True, track=False))
            except zmq.error.Again:
                pass
            if not parts or not parts[0]:
                time.sleep(0.05)
                if timeout > 0 and time.time() - started > timeout:
                    return None
                continue

            while self.zmq_client_rev.getsockopt(zmq.RCVMORE):
                part = self.zmq_client_rev.recv(0, copy=True, track=False)
                parts.append(part)

            req = parts

            assert len(req) == 3
            if req[1] == ServerMessage.ValidateClient:
                assert False, f'Second validation! {self.client_id}'
                self._validate_client(req)
            else:
                break

        return req[1:3] if req else None

    def send_rev(self, response):
        assert self.zmq_client_rev is not None
        assert len(response) == 2
        resp = [
            self.server_signature_rev,
            self._get_buffer(response[0]),
            self._get_buffer(response[1])
        ]
        self.zmq_client_rev.send_multipart(resp)

    def _validate_client(self, req):
        assert req[0] == self.server_signature_rev
        req2 = json.loads(req[2].decode())
        assert self.client_id == req2['client_id']
        assert self.client_signature == base64.b64decode(req2['client_signature'])
        assert self.client_signature_rev == base64.b64decode(req2['client_signature_rev'])
        self.server_metadata = req2['server_metadata']
        self.zmq_client_rev.send_multipart([
            self.server_signature_rev,
            ServerMessage.ClientValidated,
            json.dumps(self.metadata).encode()
        ])
        self.is_validated_ = True

    def _track_client(self):
        time.sleep(0.1)
        while self.is_alive:
            parts = []
            try:
                part = self.zmq_monitor.recv(zmq.DONTWAIT, copy=True, track=False)
                parts.append(part)
            except zmq.error.Again:
                pass
            if not parts or not parts[0]:
                time.sleep(0.1)
                continue
            while self.zmq_monitor.getsockopt(zmq.RCVMORE):
                part = self.zmq_monitor.recv(0, copy=True, track=False)
                parts.append(part)
            event_id, value = struct.unpack("=hi", parts[0])
            if event_id == zmq.Event.CONNECTED:
                pass
            elif event_id == zmq.Event.HANDSHAKE_SUCCEEDED:
                self.is_connected = True
            elif event_id == zmq.Event.DISCONNECTED:
                self.is_lost = True

            # print(
            #     'MONITOR',
            #     zmq.Event(event_id),
            #     zmq.Event(value),
            #     parts[1]
            # )

    def _get_buffer(self, value):
        if isinstance(value, str):
            return value.encode()
        elif isinstance(value, list):
            return json.dumps(value).encode()
        elif isinstance(value, dict):
            return json.dumps(value).encode()
        else:
            return value

    def add_metadata(self, obj: dict[str, any]):
        for key, value in obj.items():
            self.metadata[key] = value

    @property
    def is_validated(self):
        return self.is_validated_

    def wait(self):
        while self.is_alive and self.zmq_client.poll(0):
            if self.zmq_client.closed:
                break
            time.sleep(0.1)

    def close(self):
        zmq_client = self.zmq_client
        sockets = [self.zmq_monitor, self.zmq_client, self.zmq_client_rev]
        zmq_monitor_thread = self.zmq_monitor_thread

        self.is_alive = False
        self.zmq_client = None
        self.zmq_client_rev = None
        self.zmq_monitor = None
        self.zmq_monitor_thread = None

        if zmq_monitor_thread:
            zmq_monitor_thread.join()
            zmq_monitor_thread = None

        if zmq_client:
            zmq_client.disable_monitor()

        for item in sockets:
            if item:
                try:
                    item.close()
                except:
                    pass
