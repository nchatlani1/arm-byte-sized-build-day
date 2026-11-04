"""Bounded account data over USB during development or encrypted BLE for wall power."""
import asyncio
import json
import queue
import threading
import time

SERVICE = '9d410001-35d6-4eab-9f97-cd074073ab40'
WRITE = '9d410002-35d6-4eab-9f97-cd074073ab40'
NOTIFY = '9d410003-35d6-4eab-9f97-cd074073ab40'


class Transport:
    def __init__(self):
        self.lock = threading.RLock()
        self.serial = None
        self.ble = None
        self.label = 'Disconnected'
        self.message = 'Connect a device over USB, or hold MENU for Bluetooth pairing.'
        self.identifier = 0
        self.displayed = None
        self.capabilities = None # None preserves older protocol-2 firmware compatibility.
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self.loop.run_forever, daemon=True)
        self.thread.start()
        self.acks = queue.Queue()
        self.partial = bytearray()
        self.on_disconnect = lambda: None

    def ports(self):
        from serial.tools import list_ports
        return [{'id': p.device, 'name': p.description} for p in list_ports.comports() if p.vid is not None]

    def scan(self):
        async def discover():
            from bleak import BleakScanner
            devices = await BleakScanner.discover(timeout=6, return_adv=True, service_uuids=[SERVICE])
            return [{'id': address, 'name': device.name or advertisement.local_name or 'CrowPanel'}
                    for address, (device, advertisement) in devices.items()
                    if SERVICE in [s.lower() for s in advertisement.service_uuids]]
        return asyncio.run_coroutine_threadsafe(discover(), self.loop).result(timeout=15)

    def _notify(self, _, data):
        self.partial.extend(data)
        if len(self.partial) > 4096:
            self.partial.clear()
            return
        while b'\n' in self.partial:
            line, _, tail = self.partial.partition(b'\n')
            self.partial[:] = tail
            self.acks.put(bytes(line))

    def connect(self, kind, address, automatic=False):
        with self.lock:
            self.disconnect()
            self.partial.clear()
            while not self.acks.empty():
                try:
                    self.acks.get_nowait()
                except queue.Empty:
                    break
            if kind == 'usb':
                if address not in {p['id'] for p in self.ports()}:
                    raise ValueError('Choose an available USB device.')
                import serial
                port = serial.Serial()
                port.port, port.baudrate, port.timeout, port.write_timeout = address, 115200, .2, 3
                port.dtr = port.rts = False
                if hasattr(port, 'exclusive'):
                    port.exclusive = True
                port.open()
                self.serial = port
            elif kind == 'ble':
                async def connect_ble():
                    from bleak import BleakClient, BleakScanner
                    # A BLEDevice avoids Bleak's implicit, unbounded address discovery.
                    target = await BleakScanner.find_device_by_address(address,timeout=4 if automatic else 6,service_uuids=[SERVICE])
                    if target is None:
                        raise RuntimeError('Saved display is not nearby.')
                    def lost(client):
                        if self.ble is client:
                            self.label = 'Disconnected'
                            self.message = 'Display disconnected. Waiting to retry.'
                            self.on_disconnect()
                    client = BleakClient(target,disconnected_callback=lost)
                    self.ble = client
                    try:
                        await asyncio.wait_for(client.connect(),timeout=8 if automatic else 35)
                        await asyncio.wait_for(client.start_notify(NOTIFY,self._notify),timeout=5)
                    except BaseException:
                        try:
                            await asyncio.wait_for(client.disconnect(),timeout=3)
                        except Exception:
                            pass
                        raise
                future = asyncio.run_coroutine_threadsafe(connect_ble(), self.loop)
                try:
                    future.result(timeout=22 if automatic else 52)
                except Exception:
                    future.cancel()
                    self.disconnect()
                    raise RuntimeError('Display unavailable. Automatic retries back off to five minutes. For first pairing, hold MENU and enter the screen code in the OS prompt.') from None
            else:
                raise ValueError('Choose USB or Bluetooth.')
            try:
                hello = self.command({'op': 'hello'}, timeout=5 if automatic else 12)
                if hello.get('protocol') != 2 or hello.get('mode') != 'data':
                    raise RuntimeError('Incompatible firmware')
                capabilities = hello.get('capabilities')
                if capabilities is not None:
                    if (not isinstance(capabilities, list) or
                            any(item not in ('calendar', 'spotify') for item in capabilities)):
                        raise RuntimeError('Invalid firmware capabilities')
                    self.capabilities = frozenset(capabilities)
            except Exception:
                self.disconnect()
                raise RuntimeError('The board did not answer the companion protocol. Enable extensions.calendar or extensions.spotify in advanced/display/device.json, build/upload from VS Code, and close other serial monitors.') from None
            self.label = 'USB connected' if kind == 'usb' else 'Bluetooth connected'
            self.message = 'Connected. Enabled account data updates every 30 seconds. Layout and enabled screens come from your firmware.'

    def disconnect(self):
        with self.lock:
            if self.serial:
                self.serial.close()
                self.serial = None
            if self.ble:
                client, self.ble = self.ble, None
                try:
                    asyncio.run_coroutine_threadsafe(client.disconnect(), self.loop).result(timeout=5)
                except Exception:
                    pass
            self.label = 'Disconnected'
            self.capabilities = None
            self.on_disconnect()

    def command(self, command, timeout=5):
        payload = (json.dumps(command, separators=(',', ':')) + '\n').encode()
        if len(payload) > 383:
            raise ValueError('Protocol command too long.')
        if self.serial:
            self.serial.write(payload)
        elif self.ble and self.ble.is_connected:
            async def write():
                characteristic = self.ble.services.get_characteristic(WRITE)
                # Twenty bytes works with the minimum BLE MTU on both platforms.
                for offset in range(0, len(payload), 20):
                    await self.ble.write_gatt_char(characteristic, payload[offset:offset+20], response=True)
            asyncio.run_coroutine_threadsafe(write(), self.loop).result(timeout=15)
        else:
            raise RuntimeError('Connect a device first.')
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.serial:
                line = self.serial.readline()
            else:
                try:
                    line = self.acks.get(timeout=.2)
                except queue.Empty:
                    continue
            if line.startswith(b'CP_DISPLAY_READY:'):
                self.displayed = line.decode(errors='replace').strip().split(':', 1)[1].strip()
            if not line.startswith(b'CP_ACK '):
                continue
            try:
                ack = json.loads(line[7:])
            except ValueError:
                continue
            if ack.get('op') == command['op'] and ack.get('id', 0) == command.get('id', 0):
                if not ack.get('ok'):
                    raise RuntimeError('Device rejected the account update; reconnect and retry.')
                if command['op'] == 'chunk' and ack.get('offset') != command['offset']:
                    continue
                return ack
        raise RuntimeError('Device acknowledgement timed out. Check power, connection, and firmware.')

    def close(self):
        self.disconnect()
        self.loop.call_soon_threadsafe(self.loop.stop)
        self.thread.join(timeout=3)
        if not self.thread.is_alive():
            self.loop.close()

    def send_data(self, packet):
        with self.lock:
            if packet.get('op') not in ('calendar', 'spotify'):
                raise ValueError('The companion only delivers calendar and music account data.')
            self.identifier = (self.identifier+1) & 0x7fffffff
            self.command(dict(packet,id=self.identifier),timeout=15)
            self.message = 'Account data received by device. Firmware controls the screen and refresh timing.'
