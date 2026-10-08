"""Loopback-only concurrent test server, with explicit simulated latency."""
import argparse
import time
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--delay', type=float, default=0.2)
    parser.add_argument('--port', type=int, default=8000)
    args = parser.parse_args()
    if args.delay < 0:
        parser.error('--delay must be non-negative')

    class Handler(SimpleHTTPRequestHandler):
        def do_GET(self):
            time.sleep(args.delay)
            super().do_GET()

        def log_message(self, fmt, *values):
            pass

    handler = partial(Handler, directory=str(Path(__file__).resolve().parent / 'www'))
    with ThreadingHTTPServer(('127.0.0.1', args.port), handler) as server:
        print(f'HTTP server: http://127.0.0.1:{args.port}; delay={args.delay}s', flush=True)
        print('Stop: Ctrl+C', flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == '__main__':
    main()
