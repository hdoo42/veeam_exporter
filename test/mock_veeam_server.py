#!/usr/bin/env python3
"""
Mock Veeam REST API Server for testing token refresh logic
"""

from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import time
import urllib.parse

# Store tokens and their creation time
tokens = {}
TOKEN_LIFETIME = 60  # 60 seconds for testing

class MockVeeamHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Custom logging with timestamp
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {format % args}")

    def do_POST(self):
        if self.path in ['/oauth2/token', '/api/oauth2/token']:
            self.handle_token_request()
        else:
            self.send_error(404)

    def do_GET(self):
        auth_header = self.headers.get('Authorization', '')
        
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
        
        print(f"\n=== Token Request ===")
        print(f"Grant type: {grant_type}")
        
        if grant_type == 'password':
            username = params.get('username', [''])[0]
            password = params.get('password', [''])[0]
            print(f"Username: {username}")
            
            if username and password:
                access_token = f"access_{int(time.time())}"
                refresh_token = f"refresh_{int(time.time())}"
                tokens[access_token] = time.time()
                
                response = {
                    "access_token": access_token,
                    "refresh_token": refresh_token,
                    "expires_in": TOKEN_LIFETIME,
                    "token_type": "Bearer"
                }
                print(f"New access token: {access_token}")
                self.send_json_response(response)
            else:
                self.send_error(401, "Invalid credentials")
                
        elif grant_type == 'refresh_token':
            refresh_token = params.get('refresh_token', [''])[0]
            print(f"Refresh token: {refresh_token}")
            
            # Always accept refresh token in mock
            access_token = f"access_refreshed_{int(time.time())}"
            new_refresh_token = f"refresh_{int(time.time())}"
            tokens[access_token] = time.time()
            
            response = {
                "access_token": access_token,
                "refresh_token": new_refresh_token,
                "expires_in": TOKEN_LIFETIME,
                "token_type": "Bearer"
            }
            print(f"Refreshed access token: {access_token}")
            self.send_json_response(response)
        else:
            self.send_error(400, "Unsupported grant type")

    def handle_server_time(self, auth_header):
        print(f"\n--- Server Time Request ---")
        print(f"Auth header: {auth_header[:50]}..." if len(auth_header) > 50 else f"Auth header: {auth_header}")
        
        if not self.is_valid_token(auth_header):
            print("RESULT: 401 Unauthorized")
            self.send_error(401, "Unauthorized")
            return
        
        response = {"serverTime": time.strftime("%Y-%m-%dT%H:%M:%S")}
        print("RESULT: 200 OK")
        self.send_json_response(response)

    def handle_backups(self, auth_header):
        print(f"\n--- Backups Request ---")
        print(f"Auth header: {auth_header[:50]}..." if len(auth_header) > 50 else f"Auth header: {auth_header}")
        
        if not self.is_valid_token(auth_header):
            print("RESULT: 401 Unauthorized")
            self.send_error(401, "Unauthorized")
            return
        
        response = {
            "data": [
                {"name": "backup1", "platformName": "VmWare"},
                {"name": "backup2", "platformName": "HyperV"}
            ]
        }
        print("RESULT: 200 OK")
        self.send_json_response(response)

    def is_valid_token(self, auth_header):
        if not auth_header.startswith('Bearer '):
            return False
        
        token = auth_header[7:].strip()
        if token not in tokens:
            return False
        
        # Check if token is expired
        created_at = tokens[token]
        if time.time() - created_at > TOKEN_LIFETIME:
            print(f"Token expired! Created: {created_at}, Now: {time.time()}")
            return False
        
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
    server = HTTPServer(('localhost', 9999), MockVeeamHandler)
    print(f"Mock Veeam Server starting on http://localhost:9999")
    print(f"Token lifetime: {TOKEN_LIFETIME} seconds")
    print(f"Test commands:")
    print(f"  1. Get token: curl -X POST http://localhost:9999/oauth2/token -d 'grant_type=password&username=test&password=test'")
    print(f"  2. Call API: curl -H 'Authorization: Bearer <token>' http://localhost:9999/api/v1/backups")
    print(f"\nPress Ctrl+C to stop\n")
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        server.shutdown()


if __name__ == '__main__':
    main()
