import os
import json
import psycopg2
from http.server import BaseHTTPRequestHandler, HTTPServer

class NostrRelay(BaseHTTPRequestHandler):
    def _send_response(self, message):
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(message).encode())

    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        payload = json.loads(self.rfile.read(content_length))
        print(payload)
        # Connect to the PostgreSQL database
        conn = psycopg2.connect(
            host=os.environ.get("DB_HOST"),
            port=os.environ.get("DB_PORT"),
            user=os.environ.get("DB_USER"),
            password=os.environ.get("DB_PASS"),
            dbname=os.environ.get("DB_NAME")
        )
        cur = conn.cursor()
        # Insert payload into the database
        cur.execute("INSERT INTO messages (payload) VALUES (%s)", (json.dumps(payload),))
        conn.commit()
        # Return success message
        self._send_response({"status": "success"})

def run(server_class=HTTPServer, handler_class=NostrRelay, port=7447):
    server_address = ('', port)
    httpd = server_class(server_address, handler_class)
    print(f"Starting nostr relay on port {port}...")
    httpd.serve_forever()

if __name__ == "__main__":
    run()
