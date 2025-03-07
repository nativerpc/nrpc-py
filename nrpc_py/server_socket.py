#
#   Contents:
#
#       ServerSocket
#           __init__
#           bind
#           get_client_change
#           recv_norm
#           send_norm
#           send_rev
#           recv_rev
#           _add_client
#           _track_client
#           _recv_norm_step
#           _recv_rev_step
#           _get_buffer
#           _forward_call
#           get_client_ids
#           get_client_full
#           get_client_info
#           add_metadata
#           update
#           wait
#           close
#
import datetime
import json
import base64
import threading
import zmq
import time
import socket as _socket
from .common_base import ClientInfo, ServerMessage, find, SocketMetadataInfo


class ServerSocket:
    server_id: int
    ip_address: str
    port: int
    port_rev: int
    entry_file: str
    next_index: int
    server_signature: bytes
    server_signature_rev: bytes
    clients: list[ClientInfo]
    metadata: SocketMetadataInfo
    zmq_context: zmq.Context
    zmq_server: zmq.Socket
    zmq_server_rev: zmq.Socket
    zmq_monitor: zmq.Socket
    zmq_monitor_thread: threading.Thread
    request_lock: threading.Lock
    is_alive: bool
    norm_messages_: list[bytes]
    rev_messages_: list[bytes]

    def __init__(self, ip_address, port, port_rev, entry_file):
        self.server_id = 0
        self.ip_address = ip_address
        self.port = port
        self.port_rev = port_rev
        self.entry_file = entry_file
        self.next_index = 0
        self.server_signature = b'server:0'
        self.server_signature_rev = b'rev:server:0'
        self.clients = []
        self.metadata = SocketMetadataInfo(
            server_id=0,
            lang='python',
            ip_address=ip_address,
            main_port=port,
            main_port_rev=port_rev,
            host=_socket.gethostname(),
            entry_file=self.entry_file,
            start_time=datetime.datetime.now().isoformat(),
            server_signature=base64.b64encode(self.server_signature).decode('ascii'),
            server_signature_rev=base64.b64encode(self.server_signature_rev).decode('ascii'),
        )

        self.request_lock = threading.Lock()
        self.is_alive = True
        self.norm_messages_ = []
        self.rev_messages_ = []

        self.zmq_context = None
        self.zmq_server = None
        self.zmq_server_rev = None
        self.zmq_monitor = None
        self.zmq_monitor_thread = None

        self.zmq_context = zmq.Context.instance()

        zmq_server = self.zmq_context.socket(zmq.ROUTER)
        zmq_server.set(zmq.IDENTITY, self.server_signature)

        zmq_server_rev = self.zmq_context.socket(zmq.ROUTER)
        zmq_server_rev.set(zmq.IDENTITY, self.server_signature_rev)

        self.zmq_server = zmq_server
        self.zmq_server_rev = zmq_server_rev

        # self.zmq_monitor = zmq_server.get_monitor_socket(zmq.Event.ALL)
        # self.zmq_monitor_thread = threading.Thread(target=self._track_client)
        # self.zmq_monitor_thread.start()

    def bind(self):
        self.zmq_server.bind(f'tcp://{self.ip_address}:{self.port}')
        self.zmq_server_rev.bind(f'tcp://{self.ip_address}:{self.port_rev}')

    def get_client_change(self, timeout_seconds, expected_clients):
        """New clients are first added to self.clients, later they show up in self.get_client_ids()."""
        start = time.time()
        while True:
            client_ids = self.get_client_ids()
            if set(client_ids) != set(expected_clients):
                return True
            if timeout_seconds == 0:
                break
            time.sleep(0.05)
            if time.time() - start > timeout_seconds:
                break
        return False

    def recv_norm(self):
        while self.is_alive:
            req = self._recv_norm_step()
            if req is None:
                continue

            if req[1] == ServerMessage.AddClient:
                self._add_client(req)

            elif req[1] == ServerMessage.ForwardCall:
                self._forward_call(req)

            else:
                client = find(self.clients, lambda x: x.client_signature == req[0])
                if not client:
                    # print(f'Unknown client: {req[0]}')
                    continue
                assert len(req) == 3
                return client.client_id, req[1:3]
        return 0, None

    def send_norm(self, client_id, response):
        client = find(self.clients, lambda x: x.client_id == client_id)
        assert client
        assert len(response) == 2
        resp = [
            client.client_signature,
            self._get_buffer(response[0]),
            self._get_buffer(response[1]),
        ]
        self.zmq_server.send_multipart(resp)

    def send_rev(self, client_id, request):
        assert len(request) == 2
        client = find(self.clients, lambda x: x.client_id == client_id)
        assert client, f'Unknown client: {client_id}'

        if client.is_lost:
            # print(f'Old client: {client_id}')
            return

        req = [
            client.client_signature_rev,
            self._get_buffer(request[0]),
            self._get_buffer(request[1]),
        ]

        peer_state = zmq.backend.cython._zmq._zmq_socket_get_peer_state(self.zmq_server, client.client_signature) + 1
        peer_state_rev = zmq.backend.cython._zmq._zmq_socket_get_peer_state(
            self.zmq_server_rev, client.client_signature_rev) + 1
        if peer_state == 0 or peer_state_rev == 0:
            client.is_lost = True
            # print(f'Lost client: {client_id}')
            return
        self.zmq_server_rev.send_multipart(req)

    def recv_rev(self, client_id):
        client = find(self.clients, lambda x: x.client_id == client_id)
        assert client, f'Unknown client: {client_id}'
        if client.is_lost:
            # print(f'Old client: {client_id}')
            return None
        
        resp = None
        while self.is_alive and not client.is_lost:
            resp = self._recv_rev_step(client)
            if resp is None:
                continue
            break
        
        return resp[2] if resp else None

    def _add_client(self, req):
        self.next_index += 1
        req2 = json.loads(req[2].decode())
        client = ClientInfo(
            client_id=self.next_index,
            client_signature=req[0],
            client_signature_rev=b'rev:' + req[0],
            client_metadata=req2,
            connect_time=datetime.datetime.now(),
            is_validated=False,
            is_lost=False,
        )
        self.clients.append(client)

        resp = {
            'client_id': client.client_id,
            'client_signature': base64.b64encode(client.client_signature).decode('ascii'),
            'client_signature_rev': base64.b64encode(client.client_signature_rev).decode('ascii'),
            'client_metadata': client.client_metadata,
            'server_metadata': self.metadata,
        }

        # print(f'client added: {Fore.MAGENTA}server{Fore.RESET} <-> {Fore.MAGENTA}client:{client.client_id}{Fore.RESET}')

        self.zmq_server.send_multipart([
            client.client_signature,
            ServerMessage.ClientAdded,
            json.dumps(resp).encode()
        ])

        time.sleep(0.1)

        # Validate reverse direction
        with self.request_lock:
            self.zmq_server_rev.send_multipart([
                client.client_signature_rev,
                ServerMessage.ValidateClient,
                json.dumps(resp).encode()
            ])

            resp2 = self.zmq_server_rev.recv_multipart()
            assert resp2[0] == client.client_signature_rev, \
                f'Add_Client signature mismatch: {resp2[0]}, {client.client_signature_rev}'
            assert resp2[1] == ServerMessage.ClientValidated, \
                f'Add_Client command mismatch: {resp2[1]}, {ServerMessage.ClientValidated}'
            resp3 = json.loads(resp2[2].decode())
            assert resp3['client_id'] == client.client_id
            assert base64.b64decode(resp3['client_signature']) == client.client_signature
            # print(f'client validated: {Fore.MAGENTA}server{Fore.RESET} <-> {Fore.MAGENTA}client:{client.client_id}{Fore.RESET}')
            client.is_validated = True

    def _track_client(self):
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

            # event_id, value = struct.unpack("=hi", parts[0])
            # print(
            #     'MONITOR',
            #     zmq.Event(event_id),
            #     zmq.Event(value),
            #     parts[1],
            # )

    def _recv_norm_step(self):
        ready = False
        ready_timeout = False

        while self.is_alive:
            self.zmq_server.setsockopt(zmq.RCVTIMEO, 100)
            msg = None
            try:
                msg = self.zmq_server.recv()
            except zmq.error.Again:
                ready_timeout = True
            finally:
                if not self.is_alive:
                    break
                self.zmq_server.setsockopt(zmq.RCVTIMEO, -1)

            if not self.is_alive:
                break
            if ready_timeout:
                break

            assert msg
            self.norm_messages_.append(msg)
            if not self.zmq_server.getsockopt(zmq.RCVMORE):
                ready = True
                break

        if not ready:
            return None

        messages = [*self.norm_messages_]
        while self.norm_messages_:
            self.norm_messages_.pop()
        assert len(messages) == 3
        return messages
    
    def _recv_rev_step(self, client):
        ready = False
        ready_timeout = False

        while self.is_alive and not client.is_lost:
            self.zmq_server_rev.setsockopt(zmq.RCVTIMEO, 100)
            msg = None
            try:
                msg = self.zmq_server_rev.recv()
            except zmq.error.Again:
                ready_timeout = True
            finally:
                if not (self.is_alive and not client.is_lost):
                    break
                self.zmq_server_rev.setsockopt(zmq.RCVTIMEO, -1)

            if not (self.is_alive and not client.is_lost):
                break
            if ready_timeout:
                peer_state = zmq.backend.cython._zmq._zmq_socket_get_peer_state(self.zmq_server, client.client_signature) + 1
                peer_state_rev = zmq.backend.cython._zmq._zmq_socket_get_peer_state(self.zmq_server_rev, client.client_signature_rev) + 1
                if peer_state == 0 or peer_state_rev == 0:
                    client.is_lost = True
                    # print(f'Lost client: {client_id}')
                    break
                break

            assert msg
            self.rev_messages_.append(msg)
            if not self.zmq_server_rev.getsockopt(zmq.RCVMORE):
                ready = True
                break

        if not ready:
            return None

        messages = [*self.rev_messages_]
        while self.rev_messages_:
            self.rev_messages_.pop()
        assert len(messages) == 3
        assert messages[0] == client.client_signature_rev, \
            f'Recv_wait_rev signature mismatch: {messages[0]}, {client.client_signature_rev}'
        return messages

    def _get_buffer(self, value):
        if isinstance(value, str):
            return value.encode()
        elif isinstance(value, list):
            return json.dumps(value).encode()
        elif isinstance(value, dict):
            return json.dumps(value).encode()
        else:
            return value

    def _forward_call(self, req):
        req2 = json.loads(req[2].decode())
        assert 'client_id' in req2
        client_id = req2['client_id']
        method_name = req2['method_name']
        method_params = req2['method_params']
        client1 = find(self.clients, lambda x: x.client_signature == req[0])
        client2 = find(self.clients, lambda x: x.client_id == client_id)
        assert client2

        res = None
        with self.request_lock:
            self.send_rev(client_id, [method_name, method_params])
            res = self.recv_rev(client_id)
        if res:
            res = json.loads(res.decode())

        # print(f'call forwarded: {Fore.MAGENTA}client:{client1.client_id}{Fore.RESET} <-> {Fore.MAGENTA}server{Fore.RESET} <-> {Fore.MAGENTA}client:{client2.client_id}{Fore.RESET}')

        self.zmq_server.send_multipart([
            client1.client_signature,
            f'fwd_response:{method_name}'.encode(),
            json.dumps(res).encode()
        ])

    def get_client_ids(self):
        result = []
        for client in self.clients:
            if client.is_lost:
                continue
            if client.client_signature_rev is None:
                continue
            if not client.is_validated:
                continue
            peer_state = zmq.backend.cython._zmq._zmq_socket_get_peer_state(
                self.zmq_server, client.client_signature) + 1
            peer_state_rev = zmq.backend.cython._zmq._zmq_socket_get_peer_state(
                self.zmq_server_rev, client.client_signature_rev) + 1
            if peer_state == 0 or peer_state_rev == 0:
                client.is_lost = True
                # print(f'Lost client: {client_id}')
                continue
            result.append(client.client_id)
        return result

    def get_client_full(self) -> list[ClientInfo]:
        return self.clients

    def get_client_info(self, client_id):
        client = find(self.clients, lambda x: x.client_id == client_id)
        return client

    def add_metadata(self, obj: dict[str, any]):
        for key, value in obj.items():
            self.metadata[key] = value

    def update(self):
        for client in self.clients:
            if client.is_lost:
                continue
            peer_state = zmq.backend.cython._zmq._zmq_socket_get_peer_state(
                self.zmq_server, client.client_signature) + 1
            peer_state_rev = zmq.backend.cython._zmq._zmq_socket_get_peer_state(
                self.zmq_server_rev, client.client_signature_rev) + 1
            if peer_state == 0 or peer_state_rev == 0:
                client.is_lost = True
                # print(f'Lost client: {client_id}')

    def wait(self):
        while self.zmq_server.poll(0):
            if self.zmq_server.closed:
                break
            time.sleep(0.1)

    def close(self):
        sockets = [self.zmq_monitor, self.zmq_server, self.zmq_server_rev]
        zmq_monitor_thread = self.zmq_monitor_thread

        self.is_alive = False
        self.zmq_server = None
        self.zmq_server_rev = None
        self.zmq_monitor = None
        self.zmq_monitor_thread = None

        if zmq_monitor_thread:
            zmq_monitor_thread.join()
            zmq_monitor_thread = None

        for item in sockets:
            if item:
                try:
                    item.close()
                except:  # noqa
                    pass

        self.zmq_context = None