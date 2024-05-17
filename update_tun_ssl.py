import base64
import ssl
import subprocess
import argparse
import sys
import socket
from http.server import HTTPServer, SimpleHTTPRequestHandler
from socketserver import ThreadingMixIn

# Global variable to store the current IP address
current_ip = None

class AuthHandler(SimpleHTTPRequestHandler):
    def _set_remote_address(self, new_ip):
        global current_ip
        if new_ip == "myip":
            # Read IP from client connection
            client_ip = self.client_address[0]
            new_ip = client_ip

        if new_ip != current_ip:
            try:
                subprocess.run(['ip', 'link', 'set', args.tunnel_name, 'type', args.tunnel_type, 'remote', new_ip], check=True)
                current_ip = new_ip
                self.send_response(200)
                self.send_header('Content-type', 'text/plain')
                self.end_headers()
                self.wfile.write(bytes(f"updated: {new_ip}", 'utf-8'))
            except subprocess.CalledProcessError as e:
                print(f"Error: {e}")
                self.send_response(500)
                self.end_headers()
        else:
            print("IP address unchanged.")
            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(bytes(f"nochg: {new_ip}", 'utf-8'))

    def do_POST(self):
        if self.path == '/update_endpoint_ip':
            # Check for Basic authentication in POST request
            auth_header = self.headers.get('Authorization')
            if auth_header is None or auth_header != 'Basic ' + args.auth_credentials_base64:
                self.send_response(401)
                self.send_header('WWW-Authenticate', 'Basic realm="Test"')
                self.send_header('Content-type', 'text/html')
                self.end_headers()
                self.wfile.write(bytes('Authentication required', 'utf-8'))
                return

            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length).decode('utf-8')
            self._set_remote_address(post_data)
        else:
            self.send_response(404)
            self.end_headers()
            print("404 Not Found")

    def do_AUTHHEAD(self):
        self.send_response(401)
        self.send_header('WWW-Authenticate', 'Basic realm="Test"')
        self.send_header('Content-type', 'text/html')
        self.end_headers()

    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(bytes('Please use post request to update the tunnel endpoint', 'utf-8'))
        pass

class HTTPServerV6(ThreadingMixIn, HTTPServer):
  address_family = socket.AF_INET6

def run(server_class=HTTPServerV6, handler_class=AuthHandler, args=None):
    server_address = ('::', args.port)
    httpd = server_class(server_address, handler_class)
    print(f"Starting server on port {args.port}...")
    httpd.socket = ssl.wrap_socket(httpd.socket, keyfile=args.key_file, certfile=args.cert_file, server_side=True)
    httpd.timeout = 10
    httpd.serve_forever()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='HTTP server for updating tunnel endpoint')
    parser.add_argument('-t', '--tunnel_name', help='Name of the tunnel', required=True)
    parser.add_argument('-T', '--tunnel_type', help='Type of the tunnel (e.g., vxlan, gre)', required=True)
    parser.add_argument('-a', '--auth_credentials', help='Authentication credentials (default: admin:password)', default="admin:password")
    parser.add_argument('-c', '--cert_file', help='Path to SSL certificate file (default: /root/ssl.pem)', default="/root/ssl.pem")
    parser.add_argument('-k', '--key_file', help='Path to SSL key file (default: /root/ssl.key)', default="/root/ssl.key")
    parser.add_argument('-p', '--port', type=int, default=16581, help='Port to run the server on (default: 16581)')
    args = parser.parse_args()
    args.auth_credentials_base64 = base64.b64encode(f"{args.auth_credentials}".encode()).decode()
    
    run(args=args)

    