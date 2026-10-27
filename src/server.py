import socket
import json
import threading
from datetime import datetime, timezone
from pathlib import Path
import os

HOST = "127.0.0.1"
PORT = 65432
MAX_CLIENTS = 3
SERVER_FILES_DIR = Path(__file__).resolve().parent.parent / "server_files"
next_client_number = 1
active_clients = {}
client_history = []
client_lock = threading.Lock()

def get_timestamp():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

def send_json(client_socket, data):
    message = json.dumps(data) + "\n"
    client_socket.sendall(message.encode("utf-8"))

def recieve_json(reader):
    line = reader.readline(65537)

    if not line:
        return None
    if len(line) > 65536 or not line.endswith(b"\n"):
        raise ValueError("Invalid JSON frame")

    data = json.loads(line.decode("utf-8"))

    if not isinstance(data,dict):
        raise ValueError("JSON message must be object")

    return data

def register_client(client_socket):
    global next_client_number
    with client_lock:
        if len(active_clients) >= MAX_CLIENTS:
            return None
        
        client_name = f"Client{next_client_number:02d}"
        next_client_number += 1
        active_clients[client_name] = client_socket

        client_record = {
            "client_name": client_name,
            "accepted_at": get_timestamp(),
            "finished_at": None
        }

        client_history.append(client_record)
        active_count = len(active_clients)

    print(f"Connected to {client_name}")
    print(f"Active clients: {active_count}/{MAX_CLIENTS}")

    return client_name

def send_file(client_socket, filename):
    if (
        not isinstance(filename, str)
        or not filename
        or Path(filename).name != filename
        or filename in (".", "..")
    ):
        send_json(client_socket, {
            "type": "error",
            "code": "INVALID_FILENAME",
            "message": "Invalid filename"
        })
        return

    file_path = SERVER_FILES_DIR / filename

    if not file_path.resolve().is_relative_to(SERVER_FILES_DIR.resolve()):
        send_json(client_socket, {
            "type": "error",
            "code": "INVALID_FILENAME",
            "message": "Invalid filename"
        })
        return

    if not file_path.is_file():
        send_json(client_socket, {
            "type": "error",
            "code": "FILE_NOT_FOUND",
            "message": "Requested file does not exist"
        })
        return

    with open(file_path, "rb") as file:

        file_size = os.fstat(file.fileno()).st_size
        send_json(client_socket, {
            "type": "download_ready",
            "filename": filename,
            "size": file_size
        })

        while True:
            chunk = file.read(4096)

            if not chunk:
                break
            client_socket.sendall(chunk)

def get_server_files():
    files = []

    for file_path in SERVER_FILES_DIR.iterdir():
        if file_path.is_file():
            files.append(file_path.name)
    files.sort()

    return files

def get_server_status():
    with client_lock:
        clients=[]
        for record in client_history:
            client_name = record["client_name"]
            if client_name in active_clients:
                connection_status = "connected"
            else:
                connection_status = "disconnected"
            clients.append({
                "client_name": client_name,
                "accepted_at": record["accepted_at"],
                "finished_at": record["finished_at"],
                "status": connection_status
            })
        active_count = len(active_clients)

    return {
        "type": "status",
        "active_count": active_count,
        "max_clients": MAX_CLIENTS,
        "clients": clients
    }

def handle_client(client_socket, client_name):
    reader = client_socket.makefile("rb")

    try:
        send_json(client_socket, {
            "type": "welcome",
            "client_name": client_name
        })

        response = recieve_json(reader)
        if response is None:
            print(f"ERROR, {client_name} disconnected during handshake")
            return
        # validate id
        if (
            response.get("type") != "identify"
            or response.get("client_name") != client_name
        ):
            send_json(client_socket, {
                "type": "error",
                "code": "INVALID_CLIENT_NAME",
                "message": "Client indentification failed"
            })
            print(f"ERROR, invalid indentification from {client_name}")
            return
        #confirm id
        send_json(client_socket, {
            "type": "identified",
            "client_name": client_name
        })

        print(f"Identified {client_name}")

        while True:
            message = recieve_json(reader)

            if message is None:
                print(f"{client_name} closed the connection")
                break

            if message.get("type") == "message":
                text = message.get("text")

                if not isinstance(text, str):
                    send_json(client_socket, {
                        "type": "error",
                        "code": "INVALID_MESSAGE",
                        "message": "Message text must be a string"
                    })
                    continue

                ack_text = text + " ACK"
                #acknowldgement to client
                send_json(client_socket, {
                    "type": "ack",
                    "text": ack_text
                })

                print(f"Message from {client_name}: {text}")
                print(f"ACK sent to {client_name}: {ack_text}")

            elif message.get("type") == "status":
                status_data = get_server_status()
                send_json(client_socket, status_data)
                print(f"Status sent to {client_name}")
                print(json.dumps(status_data, indent=4))

            elif message.get("type") == "list":
                files = get_server_files()

                send_json(client_socket, {
                    "type": "list",
                    "files": files
                })

                print(f"File list sent to {client_name}")

            elif message.get("type") == "download":
                filename = message.get("filename")

                send_file(client_socket, filename)

                print(f"Download requested by {client_name}: {filename}")

            elif message.get("type") == "exit":
                send_json(client_socket, {
                    "type": "exit_ack",
                    "message": "Disconnected"
                })
                print(f"{client_name} requested exit")
                break
            else:
                send_json(client_socket, {
                    "type": "error",
                    "code": "UNKNOWN_COMMAND",
                    "message": "Unknown message type"
                })

    except (OSError, ValueError, UnicodeError) as error:
        print(f"ERROR, {client_name}: {error}")

    finally:
        with client_lock:
            for record in client_history:
                if record["client_name"] == client_name:
                    record["finished_at"] = get_timestamp()
                    break
            # remove client from connections
            active_clients.pop(client_name, None)

        reader.close()
        client_socket.close()
        print(f"Disconnected {client_name}")

def start_server():

    server_socket = socket.socket(
        socket.AF_INET,
        socket.SOCK_STREAM
    )

    server_socket.setsockopt(
        socket.SOL_SOCKET,
        socket.SO_REUSEADDR,
        1
    )

    server_socket.bind((HOST, PORT))
    server_socket.listen(MAX_CLIENTS)

    print(f"Server running on {HOST}:{PORT}")
    print(f"Maximum clients: {MAX_CLIENTS}")
    print("Waiting for connections...")

    try:
        while True:
            client_socket, client_adress = server_socket.accept()

            print(f"\nNew connection from {client_adress}")
            #assign cleint name
            client_name = register_client(client_socket)
            # Rejection
            if client_name is None:
                try:
                    send_json(client_socket, {
                        "type": "server_full",
                        "message": "Max number of clients reached"
                    })
                except OSError as error:
                    print(f"Could not send server_full response: {error}")
                finally:
                    client_socket.close()

                print("Connection rejected: Server is full")
                continue

            #create a thread for client
            client_thread = threading.Thread(
                target=handle_client,
                args=(client_socket, client_name),
                daemon=True
            )
            client_thread.start()

    except KeyboardInterrupt:

        print("\nServer shutting down...")

    finally:

        server_socket.close()

if __name__ == "__main__":
    start_server()