#!/usr/bin/env python3
"""
Mock Veeam REST API Server for testing token refresh logic (with file logging)
"""

from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import time
import urllib.parse
import sys

# Setup logging to file
LOG_FILE = '/tmp/mock_veeam_server.log'

def log(msg):
    with open(LOG_FILE, 'a') as f:
        f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")
    print(msg)

# Store tokens and their creation time
tokens = {}
TOKEN_LIFETIME = 60  # 60 seconds for testing

class MockVeeamHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        log(format % args)

    def do_POST(self):
        log(f"POST {self.path}")
        if self.path in ['/oauth2/token', '/api/oauth2/token']:
            self.handle_token_request()
        else:
            self.send_error(404)

    def do_GET(self):
        auth_header = self.headers.get('Authorization', '')
        log(f"GET {self.path}, Auth: {auth_header[:30]}...")
        
        if self.path in ['/api/v1/serverTime', '/v1/serverTime']:
            self.handle_server_time(auth_header)
        elif self.path in ['/api/v1/backups', '/v1/backups']:
            self.handle_backups(auth_header)
        else:
            self.send_error(404)

    def handle_token_request(self):
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length).decode('utf-8')
        params = urllib.parse.parse_qs(post_data)
        
        grant_type = params.get('grant_type', [''])[0]
        
        log(f"=== Token Request ===")
        log(f"Grant type: {grant_type}")
        
        if grant_type == 'password':
            username = params.get('username', [''])[0]
            log(f"Username: {username}")
            
            access_token = f"access_{int(time.time())}"
            refresh_token = f"refresh_{int(time.time())}"
            tokens[access_token] = time.time()
            
            response = {
                "access_token": access_token,
                "refresh_token": refresh_token,
                "expires_in": TOKEN_LIFETIME,
                "token_type": "Bearer"
            }
            log(f"NEW TOKEN CREATED: {access_token}")
            self.send_json_response(response)
                
        elif grant_type == 'refresh_token':
            refresh_token = params.get('refresh_token', [''])[0]
            log(f"Refresh token received: {refresh_token[:20]}...")
            
            access_token = f"access_refreshed_{int(time.time())}"
            new_refresh_token = f"refresh_{int(time.time())}"
            tokens[access_token] = time.time()
            
            response = {
                "access_token": access_token,
                "refresh_token": new_refresh_token,
                "expires_in": TOKEN_LIFETIME,
                "token_type": "Bearer"
            }
            log(f"TOKEN REFRESHED: {access_token}")
            self.send_json_response(response)
        else:
            self.send_error(400, "Unsupported grant type")

    def handle_server_time(self, auth_header):
        if not self.is_valid_token(auth_header):
            log("RESULT: 401 Unauthorized")
            self.send_error(401, "Unauthorized")
            return
        
        response = {"serverTime": time.strftime("%Y-%m-%dT%H:%M:%S")}
        log("RESULT: 200 OK (serverTime)")
        self.send_json_response(response)

    def handle_backups(self, auth_header):
        if not self.is_valid_token(auth_header):
            log("RESULT: 401 Unauthorized")
            self.send_error(401, "Unauthorized")
            return
        
        response = {
            "data": [
                {"name": "backup1", "platformName": "VmWare"},
                {"name": "backup2", "platformName": "HyperV"}
            ]
        }
        log("RESULT: 200 OK (backups)")
        self.send_json_response(response)

    def is_valid_token(self, auth_header):
        if not auth_header.startswith('Bearer '):
            return False
        
        token = auth_header[7:].strip()
        if token not in tokens:
            log(f"Unknown token: {token[:20]}...")
            return False
        
        created_at = tokens[token]
        elapsed = time.time() - created_at
        if elapsed > TOKEN_LIFETIME:
            log(f"Token EXPIRED! Elapsed: {elapsed:.1f}s")
            return False
        
        log(f"Token valid. Elapsed: {elapsed:.1f}s")
        return True

    def send_json_response(self, data):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def send_error(self, code, message=None):
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        error_data = {"error": message or "Error", "code": code}
        self.wfile.write(json.dumps(error_data).encode())


def main():
    # Clear log file
    with open(LOG_FILE, 'w') as f:
        f.write(f"Mock Server Started at {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    server = HTTPServer(('localhost', 9999), MockVeeamHandler)
    log(f"Mock Veeam Server on http://localhost:9999")
    log(f"Token lifetime: {TOKEN_LIFETIME} seconds")
    log(f"Log file: {LOG_FILE}")
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log("Shutting down...")
        server.shutdown()


if __name__ == '__main__':
    main()
