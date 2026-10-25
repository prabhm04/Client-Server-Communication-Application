import socket
import json
import threading
from datetime import datetime, timezone

HOST = "127.0.0.1"
PORT = 65432
MAX_CLIENTS = 3
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

            print(f"Message from {client_name}: {message}")

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