import socket
import json
from pathlib import Path

def json_server_helper(client_reader):
    line = client_reader.readline()

    if not line:
        return None

    return json.loads(line.decode("utf-8"))

def run_client():
    host = '127.0.0.1'
    port = 65432

    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client_reader = None
    #Trying to connect to server
    try:
        client_socket.connect((host,port))
        client_reader = client_socket.makefile("rb")
        try :

            client_data = json_server_helper(client_reader)

            if client_data is None:
                print("Server closed the connection")
                return

            if client_data.get("type") == "server_full":
                print("Connection rejected:", client_data.get("message"))
                return

            if client_data.get("type") != "welcome":
                print("Unexpected server response:", client_data)
                return
            client_name = client_data.get("client_name")
           
            print(f"Client is connected, identity is: {client_name}" )
            intialaization_payload = {
                "client_name": client_name,
                "type": "identify"
            }
            json_convert = json.dumps(intialaization_payload) + "\n"
            client_socket.sendall(json_convert.encode('utf-8'))
            
            server_data = json_server_helper(client_reader)
            print(f"Server reply: {server_data}\n")

            if (
                server_data is None
                or server_data.get("type") != "identified"
                or server_data.get("client_name") != client_name
            ):
                print("Identification failed:", server_data)
                return

            print("Identification successful")
            while True:
                message = input(f"[{client_name}] Type a message (Type exit to quit): ") 
                message_type = "message"
                if message.lower() == "exit":
                    payload = {"type": "exit"}

                    json_convert = json.dumps(payload) + "\n"
                    client_socket.sendall(json_convert.encode("utf-8"))
                    server_data = json_server_helper(client_reader)

                    if server_data and server_data.get("type") == "exit_ack":
                        print("Server reply:", server_data.get("message"))
                    else:
                        print("Unexpected exit response:", server_data)
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
                    filename = input("Enter the filename to download: ").strip()

                    if not filename:
                        print("Filename cannot be empty")
                        continue

                    payload = {
                        "type": "download",
                        "filename": filename
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

                server_data = json_server_helper(client_reader)
                if server_data is None:
                    print("Server disconnected unexpectedly")
                    break

                



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
                    if server_data.get("type") == "error":
                        print("Download failed:", server_data.get("message"))
                    elif server_data.get("type") == "download_ready":
                        filename = server_data.get("filename")
                        file_size = server_data.get("size")

                        downloads_folder = Path(__file__).resolve().parent.parent / "downloads"
                        downloads_folder.mkdir(exist_ok=True)
                        file_path = downloads_folder / filename

                        remaining = file_size

                        with open(file_path, "wb") as file:
                            while remaining > 0:
                                chunk = client_reader.read(min(4096, remaining))
                                if not chunk:
                                    raise ConnectionError("Connection lost during downlaod")

                                file.write(chunk)
                                remaining -=len(chunk)
                        print(f"Downloaded {filename} successfully")
                        print(f"Saved to: {file_path}")
                    else:
                        print("Unexpected download repsonse:", server_data)
        except json.JSONDecodeError:
           print("Server did not send valid JSON initialization data")
        except (ConnectionError, OSError) as error:
            print("Connection error:", error)
    except ConnectionRefusedError:
        print("Could not connect to server")
    finally:
        if client_reader is not None:
            client_reader.close()
        client_socket.close()
        print("Client connection to server is closed")

if __name__ == '__main__':
    run_client()
