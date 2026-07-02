import http.server
import os
import pathlib
import socketserver
import threading
import time
import urllib.parse

ROOT = pathlib.Path(__file__).resolve().parent
PORT = 8001

class LiveReloadHandler(http.server.SimpleHTTPRequestHandler):
    def translate_path(self, path):
        path = urllib.parse.urlparse(path).path
        if path == '/' or path == '':
            return str(ROOT / 'index.html')
        path = path.lstrip('/')
        return str(ROOT / path)

    def end_headers(self):
        self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
        super().end_headers()

    def do_GET(self):
        if urllib.parse.urlparse(self.path).path == '/livereload':
            self.send_response(200)
            self.send_header('Content-Type', 'text/event-stream')
            self.send_header('Cache-Control', 'no-cache')
            self.send_header('Connection', 'keep-alive')
            self.end_headers()

            self.server.add_client(self.wfile)
            try:
                while True:
                    time.sleep(1)
            except (ConnectionResetError, BrokenPipeError):
                pass
            finally:
                self.server.remove_client(self.wfile)
            return

        super().do_GET()

    def do_HEAD(self):
        if urllib.parse.urlparse(self.path).path == '/livereload':
            self.send_response(200)
            self.send_header('Content-Type', 'text/event-stream')
            self.send_header('Cache-Control', 'no-cache')
            self.send_header('Connection', 'keep-alive')
            self.end_headers()
            return

        super().do_HEAD()

class LiveReloadServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, server_address, RequestHandlerClass):
        super().__init__(server_address, RequestHandlerClass)
        self.clients = []

    def add_client(self, client):
        self.clients.append(client)

    def remove_client(self, client):
        if client in self.clients:
            self.clients.remove(client)

    def broadcast(self, message):
        payload = f'data: {message}\n\n'.encode('utf-8')
        for client in list(self.clients):
            try:
                client.write(payload)
                client.flush()
            except Exception:
                self.remove_client(client)


def watch_files(server, interval=0.75):
    mtimes = {}
    while True:
        changed = False
        for root, dirs, files in os.walk(ROOT):
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            for filename in files:
                if filename.startswith('.'):
                    continue
                path = pathlib.Path(root) / filename
                try:
                    mtime = path.stat().st_mtime
                except OSError:
                    continue
                old = mtimes.get(path)
                if old is None:
                    mtimes[path] = mtime
                    continue
                if mtime != old:
                    mtimes[path] = mtime
                    changed = True
        if changed:
            print('Change detected, reloading browsers...')
            server.broadcast('reload')
        time.sleep(interval)


def main():
    os.chdir(ROOT)
    server = LiveReloadServer(('0.0.0.0', PORT), LiveReloadHandler)
    watcher = threading.Thread(target=watch_files, args=(server,), daemon=True)
    watcher.start()
    print(f'Serving {ROOT} at http://127.0.0.1:{PORT}/')
    server.serve_forever()


if __name__ == '__main__':
    main()
