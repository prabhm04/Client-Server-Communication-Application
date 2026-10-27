import socket
import json
import threading
from datetime import datetime, timezone
from pathlib import Path
import os

def json_server_helper(client_socket):
    buffer = b""

    while True:

        chunk = client_socket.recv(1024)

        if not chunk:
            return None

        buffer += chunk

        if b"\n" in buffer:

            line_bytes, left = buffer.split(b"\n" ,1)

            raw_line = line_bytes.decode('utf-8')
            return json.loads(raw_line)
def run_client():
    host = '127.0.0.1'
    port = 65432

    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    #Trying to connect to server
    try:
        client_socket.connect((host,port))
        client_reader = client_socket.makefile('r', encoding= 'utf-8')
        try :

            client_identity = client_reader.readline()

            client_data = json.loads(client_identity)

            client_name = client_data.get("client_name")
            client_type = client_data.get("type")
           
            print(f"Client is connected, identity is: {client_name}" )
            message = input(f"[{client_name}] Type identify to verify: ")
            intialaization_payload = {
                "client_name": client_name,
                "type" : message
            }
            json_convert = json.dumps(intialaization_payload) + "\n"
            client_socket.sendall(json_convert.encode('utf-8'))
            
            server_data = client_socket.recv(1024)
            print(f"Server reply: {server_data.decode('utf-8')}\n")
            while True:
                message = input(f"[{client_name}] Type a message (Type exit to quit): ") 
                message_type = "message"
                if message.lower() == "exit":
                    break
                if message.lower() == "status":
                    message_type = "status"
                    payload = {
                        "type" : message_type
                    }
                    json_convert = json.dumps(payload) + "\n"
                    client_socket.sendall(json_convert.encode('utf-8'))
                    
                elif message.lower() == "list":
                    message_type = "list"
                    payload = {
                        "type" : message_type
                    }
                    json_convert = json.dumps(payload) + "\n"
                    client_socket.sendall(json_convert.encode('utf-8'))
                elif message.lower() =="download":
                    message_type = "download"
                    payload = {
                        "type" : message_type
                    }
                    json_convert = json.dumps(payload) + "\n"
                    client_socket.sendall(json_convert.encode('utf-8'))
                if not message.strip():
                    continue
               
                data_payload = {
                    
                    "type" : message_type,
                    "text" : message
                }

                if message_type == "message":

                    json_convert = json.dumps(data_payload) + "\n"
                    client_socket.sendall(json_convert.encode('utf-8'))

                server_data = json_server_helper(client_socket)

                



                if message.lower() == "status":
                    
                    cache_type = server_data.get("type")
                    cache_active_count = server_data.get("active_count",0)
                    cache_max_clients = server_data.get("max_clients",0)
                    cache_clients = server_data.get("clients")
                    print(f"Server reply: \n")
                    print(f"Type: {cache_type}\n")
                    print(f"Active Count: {cache_active_count}\n")
                    print(f"Max clients: {cache_max_clients}\n")
                    print(f"Client list: {cache_clients}\n")
                elif message_type == "message":
                    server_message = server_data.get("text")
                    print(f"Server reply: {server_message}\n")
                elif message.lower() == "list":
                    server_message = server_data.get("files")
                    print(f"Server reply: Files in {server_message}\n")
                elif message.lower() == "download":
                    server_message = server_data.get("filename")
                    print(f"Server reply: downloaded {server_message}\n")
        except json.JSONDecodeError:
           print("Server did not send valid JSON initization data")
    except ConnectionRefusedError:
        print("Could not connect to server")
    finally:
        client_socket.close()
        print("Client connection to server is closed")

if __name__ == '__main__':
    run_client()
