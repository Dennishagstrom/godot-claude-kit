#!/usr/bin/env python3
"""UDP lag proxy for testing netcode (stdlib only).

Sits between game clients and the host and relays ENet's UDP datagrams,
adding latency, jitter and packet loss per direction:

    client  --(up: client -> host)-->  proxy  -->  host
    client  <--(down: host -> client)-- proxy  <--  host

Clients connect to the proxy's --listen port instead of the host. Every
client address gets its own upstream socket, so several clients can share
one proxy.

Example: 100 ms round trip with +-20 ms jitter and 1 % loss each way, host
on 7777, clients join 127.0.0.1:7778:

    python3 -I tools/lag_proxy.py --listen 7778 --target 127.0.0.1:7777 \
        --rtt 100 --jitter 20 --loss 1

Delay options (milliseconds):
    --rtt N         sets both one-way delays to N / 2 (default 0)
    --up N/--down N one-way delay per direction (override --rtt)
    --jitter N      uniform random +-N added to every packet's delay
    --loss P        percent of packets dropped (each direction)
    --up-loss/--down-loss  per direction loss (override --loss)
    --no-reorder    never deliver a packet before an earlier one of the
                    same direction (jitter without reordering)

The proxy prints a stats line every --stats seconds (0 = off) and on exit
(Ctrl+C or SIGTERM). --duration S stops it after S seconds. Both ports are
shifted by {{GAME_ENV}}_PORT_OFFSET when set (the test runner's port block).
"""

import argparse
import heapq
import itertools
import os
import random
import selectors
import signal
import socket
import sys
import time

MAX_DATAGRAM = 65535
IDLE_CLIENT_TIMEOUT = 60.0


class Direction:
    """Delay/loss model and counters for one direction."""

    def __init__(self, name, delay_ms, jitter_ms, loss_pct, reorder, rng):
        self.name = name
        self.delay = max(delay_ms, 0.0) / 1000.0
        self.jitter = max(jitter_ms, 0.0) / 1000.0
        self.loss = min(max(loss_pct, 0.0), 100.0) / 100.0
        self.reorder = reorder
        self.rng = rng
        self.last_due = 0.0
        self.received = 0
        self.dropped = 0
        self.sent = 0
        self.bytes = 0
        self.delay_sum = 0.0

    def schedule(self, now):
        """Returns the delivery time for a packet arriving now, or None if dropped."""
        self.received += 1
        if self.loss > 0.0 and self.rng.random() < self.loss:
            self.dropped += 1
            return None
        delay = self.delay
        if self.jitter > 0.0:
            delay += self.rng.uniform(-self.jitter, self.jitter)
        due = now + max(delay, 0.0)
        if not self.reorder and due < self.last_due:
            due = self.last_due
        self.last_due = max(self.last_due, due)
        self.delay_sum += due - now
        return due

    def summary(self):
        mean = (self.delay_sum / max(self.received - self.dropped, 1)) * 1000.0
        return "%s: recv=%d sent=%d dropped=%d (%.2f%%) mean_delay=%.1fms" % (
            self.name, self.received, self.sent, self.dropped,
            100.0 * self.dropped / max(self.received, 1), mean)


PORT_OFFSET_ENV = "{{GAME_ENV}}_PORT_OFFSET"


def port_offset():
    """The test runner's port block offset (tools/test_runner.py), 0 if unset."""
    try:
        return max(0, int(os.environ.get(PORT_OFFSET_ENV, "0") or 0))
    except ValueError:
        return 0


class LagProxy:
    def __init__(self, args):
        # The game adds the same offset to every port it hosts or joins on
        # (PortOffset), so the proxy follows it.
        offset = port_offset()
        self.listen_addr = (args.bind, args.listen + offset)
        host, _, port = args.target.rpartition(":")
        self.target = (host or "127.0.0.1", int(port) + offset)
        rng = random.Random(args.seed)
        up = args.up if args.up is not None else args.rtt / 2.0
        down = args.down if args.down is not None else args.rtt / 2.0
        up_loss = args.up_loss if args.up_loss is not None else args.loss
        down_loss = args.down_loss if args.down_loss is not None else args.loss
        self.up = Direction("up", up, args.jitter, up_loss, not args.no_reorder, rng)
        self.down = Direction("down", down, args.jitter, down_loss, not args.no_reorder, rng)
        self.selector = selectors.DefaultSelector()
        self.listener = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.listener.bind(self.listen_addr)
        self.listener.setblocking(False)
        self.selector.register(self.listener, selectors.EVENT_READ, None)
        # client address -> [upstream socket, last activity]
        self.clients = {}
        # heap of (due, counter, socket, payload, address, direction)
        self.queue = []
        self.counter = itertools.count()
        self.running = True
        self.stats_interval = args.stats
        self.duration = args.duration
        self.quiet = args.quiet

    def log(self, text):
        if not self.quiet:
            print("[lag_proxy] " + text, flush=True)

    def _upstream_for(self, client_addr, now):
        entry = self.clients.get(client_addr)
        if entry is None:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.bind(("0.0.0.0", 0))
            sock.setblocking(False)
            self.selector.register(sock, selectors.EVENT_READ, client_addr)
            entry = [sock, now]
            self.clients[client_addr] = entry
            self.log("new client %s:%d via upstream port %d" % (client_addr[0], client_addr[1], sock.getsockname()[1]))
        entry[1] = now
        return entry[0]

    def _enqueue(self, direction, sock, payload, address, now):
        due = direction.schedule(now)
        if due is None:
            return
        heapq.heappush(self.queue, (due, next(self.counter), sock, payload, address, direction))

    def _flush(self, now):
        while self.queue and self.queue[0][0] <= now:
            _, _, sock, payload, address, direction = heapq.heappop(self.queue)
            try:
                sock.sendto(payload, address)
                direction.sent += 1
                direction.bytes += len(payload)
            except OSError:
                pass

    def _expire_clients(self, now):
        for addr in [a for a, e in self.clients.items() if now - e[1] > IDLE_CLIENT_TIMEOUT]:
            sock = self.clients.pop(addr)[0]
            self.selector.unregister(sock)
            sock.close()
            self.log("client %s:%d timed out" % addr)

    def stop(self, *_):
        self.running = False

    def stats_line(self):
        return "%s | %s | clients=%d queued=%d" % (self.up.summary(), self.down.summary(), len(self.clients), len(self.queue))

    def run(self):
        start = time.monotonic()
        next_stats = start + self.stats_interval if self.stats_interval > 0 else float("inf")
        next_expire = start + 5.0
        self.log("listening on %s:%d -> %s:%d (up %.0fms, down %.0fms, jitter +-%.0fms, loss up %.1f%% down %.1f%%)" % (
            self.listen_addr[0], self.listen_addr[1], self.target[0], self.target[1],
            self.up.delay * 1000, self.down.delay * 1000, self.up.jitter * 1000,
            self.up.loss * 100, self.down.loss * 100))
        while self.running:
            now = time.monotonic()
            if self.duration > 0 and now - start >= self.duration:
                break
            timeout = 0.05
            if self.queue:
                timeout = min(timeout, max(self.queue[0][0] - now, 0.0))
            for key, _ in self.selector.select(timeout):
                sock = key.fileobj
                try:
                    payload, addr = sock.recvfrom(MAX_DATAGRAM)
                except (BlockingIOError, ConnectionResetError, OSError):
                    continue
                now = time.monotonic()
                if sock is self.listener:
                    upstream = self._upstream_for(addr, now)
                    self._enqueue(self.up, upstream, payload, self.target, now)
                else:
                    client_addr = key.data
                    if client_addr in self.clients:
                        self.clients[client_addr][1] = now
                    self._enqueue(self.down, self.listener, payload, client_addr, now)
            now = time.monotonic()
            self._flush(now)
            if now >= next_stats:
                next_stats = now + self.stats_interval
                self.log(self.stats_line())
            if now >= next_expire:
                next_expire = now + 5.0
                self._expire_clients(now)
        self.log("stopped: " + self.stats_line())


def parse_args(argv):
    parser = argparse.ArgumentParser(description="UDP lag proxy (latency, jitter, loss per direction).")
    parser.add_argument("--listen", type=int, default=7778, help="port clients connect to (default 7778)")
    parser.add_argument("--bind", default="0.0.0.0", help="address to listen on (default 0.0.0.0)")
    parser.add_argument("--target", default="127.0.0.1:7777", help="host address:port (default 127.0.0.1:7777)")
    parser.add_argument("--rtt", type=float, default=0.0, help="round trip ms; each direction gets half")
    parser.add_argument("--up", type=float, default=None, help="client->host one-way delay ms")
    parser.add_argument("--down", type=float, default=None, help="host->client one-way delay ms")
    parser.add_argument("--jitter", type=float, default=0.0, help="+- ms random per packet")
    parser.add_argument("--loss", type=float, default=0.0, help="percent loss per direction")
    parser.add_argument("--up-loss", type=float, default=None, help="client->host loss percent")
    parser.add_argument("--down-loss", type=float, default=None, help="host->client loss percent")
    parser.add_argument("--no-reorder", action="store_true", help="keep packet order despite jitter")
    parser.add_argument("--seed", type=int, default=None, help="random seed (repeatable runs)")
    parser.add_argument("--stats", type=float, default=0.0, help="print stats every N seconds")
    parser.add_argument("--duration", type=float, default=0.0, help="stop after N seconds (0 = run forever)")
    parser.add_argument("--quiet", action="store_true", help="no log output")
    return parser.parse_args(argv)


def main(argv):
    proxy = LagProxy(parse_args(argv))
    signal.signal(signal.SIGINT, proxy.stop)
    signal.signal(signal.SIGTERM, proxy.stop)
    proxy.run()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
