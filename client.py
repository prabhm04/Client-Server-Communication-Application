import socket
import json
import threading
from datetime import datetime, timezone
from pathlib import Path
import os


def run_client():
    host = '127.0.0.1'
    port = 65432

    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    #Trying to connect to server
    try:
        client_socket.connect((host,port))

        client_name = client_socket.recv(1024).decode('utf-8')
    
        print(f"Client is connected, identity is: {client_name}" )

        while True:
            message = input(f"[{client_name}] Type a message: ") 

            if message.lower() == "quit":
                break

            if not message.strip():
                continue

            data_payload = {
                "client" : client_name,
                "type" : type

                "text" : message
            }

            json_convert = json.dumps(data_payload) + "\n"
            client_socket.sendall(json_convert.encode('utf-8'))

            server_data = client_socket.recv(1024)
            print(f"Server reply: {server_data.decode('utf-8')}\n")
    except ConnectionRefusedError:
        print("Could not connect to server")
    finally:
        client_socket.close()
        print("Client connection to server is closed")

if __name__ == '__main__':
    run_client()
    