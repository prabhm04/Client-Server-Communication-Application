# CP372 Socket Programming — Shared TCP Protocol (v1.0)

**Course:** CP372, Fall 2026  
**Deadline:** October 26, 2026  
**Implementation:** Python standard library, TCP sockets only  
**Owners:** Server developer (`Server.py`) and client developer (`Client.py`)  
**Status:** Proposed integration contract — both partners should approve before implementation.

## 1. Purpose and assignment alignment

Build one TCP server supporting multiple concurrent CLI clients, with sequential names (`Client01`, `Client02`, ...), a **maximum of 3 active clients**, message echo plus `ACK`, `status`, `exit`, `list`, file downloads, and an in-memory connection history with accepted/finished timestamps.

**Required submission:** `Server.py`, `Client.py`, `Report.pdf`; both students' names on source files and report. A GTA demo is mandatory and must be booked separately.

This document defines design choices where the assignment leaves details open. **The JSON wire format, port, directories, and error codes below are our team's choices, not professor-mandated requirements.** Document them in the report.

## 2. How this extends the supplied examples

| Uploaded example | What it demonstrates | What we need to add |
|---|---|---|
| `echo-server.py` / `echo-client.py` | `socket.AF_INET`, `socket.SOCK_STREAM`, `bind`, `listen`, `accept`, `connect`, `sendall`, `recv`; loopback port 65432 | Multiple simultaneous clients, names, commands, framing, files, session cache |
| `TCPServer.py` / `TCPclient.py` | CLI input and `.encode()` / `.decode()`; localhost port 12345 | Persistent sessions, threads, client limit, responses beyond uppercase, transfers |

**Important:** The examples use `recv(1024)` for simple messages. TCP is a byte stream: a single `recv` may return part of a message or several messages together. Do **not** treat `recv(1024)` as one complete command, especially for file transfers.

## 3. Fixed configuration

| Setting | Agreed value |
|---|---|
| Transport | TCP (`socket.AF_INET`, `socket.SOCK_STREAM`) |
| Server bind host | `127.0.0.1` for same-machine demo |
| Client target host | `127.0.0.1` (configurable for different computers) |
| Port | `65432` |
| Maximum active clients | `3` |
| Text encoding | UTF-8 |
| Control message framing | One JSON object followed by a newline byte (`\n`) |
| File content framing | File metadata JSON line, then **exactly `size` raw bytes** |
| File repository | `server_files/` beside `Server.py` |
| Client download directory | `downloads/` beside `Client.py` |
| Filename policy | Basenames only; no `/`, `\\`, `..`, or absolute paths |
| Client identifiers | `Client01`, `Client02`, ...; never reuse an assigned number in one server session |
| Timestamp format | UTC ISO 8601 string, e.g. `2026-10-23T20:30:00Z` |

Use `pathlib.Path(__file__).resolve().parent` to locate directories regardless of working directory. Repository is read-only from the client's perspective. The server may send any regular file inside `server_files/`; use a small `.txt` and a binary file to test.

## 4. Wire protocol rules (both partners MUST implement)

1. Every **control frame** is one compact UTF-8 JSON object terminated by `\n` (newline). Each frame has a `type` string. The examples below are logical JSON frames; the newline is not displayed.
2. `sendall(json.dumps(obj).encode('utf-8') + b'\n')` sends a control frame. Do not use `send` and assume all bytes were sent.
3. Keep a **persistent per-connection receive buffer**. To read a control frame, accumulate bytes until `\n`, parse only those bytes as JSON, and retain bytes after the newline for subsequent reads.
4. **During download**, after parsing the `file_start` frame, read **exactly** the declared `size` bytes into the destination file. Preserve any bytes already buffered after the metadata newline. Only after consuming exactly `size` bytes may the client parse the next JSON control frame.
5. For simplicity, each client has **one outstanding request at a time**. Client sends a request, waits for its complete response, then prompts for another command. No concurrent sends on the same socket from multiple threads.
6. Files are transferred as raw bytes, not JSON strings, and not decoded as UTF-8. `size` is the number of **bytes**, not characters.
7. All successful command responses and errors are JSON control frames, except the raw file bytes following `file_start`.
8. Do not impose `recv(1024)` as a maximum frame or file size; it is merely a chunk size. Set a reasonable maximum control-line size (e.g. 64 KiB) and reject malformed/oversized control frames.

**Implementation warning:** A `socket.makefile('rb')` buffered reader can simplify `readline()` and `read(size)` *if the same reader is used consistently*. Do not mix `makefile()` reads with direct `socket.recv()` on that socket: buffering can consume bytes unexpectedly. Alternatively implement a single buffered socket reader shared by all reads.

## 5. Connection handshake and naming

1. Server accepts TCP connection.
2. Under a lock, server checks current active count. If already 3, send `server_full`, close socket, **do not allocate a name or add a cache record**.
3. Otherwise, reserve an active slot, increment the lifetime-in-session client counter, assign name, and record accepted timestamp in the cache (finished timestamp initially `null`).
4. Server sends `welcome` with assigned name.
5. Client sends `identify` with the **same name** as required by the assignment.
6. Server validates and replies `identified`. Only then display the interactive CLI prompt.
7. If identification is wrong, send `error` and disconnect, updating the cache and freeing the slot.

Server → Client:

```json
{"type":"welcome","client_name":"Client01"}
```

Client → Server:

```json
{"type":"identify","client_name":"Client01"}
```

Server → Client:

```json
{"type":"identified","client_name":"Client01"}
```

Server → rejected fourth connection:

```json
{"type":"server_full","message":"Maximum of 3 active clients reached"}
```

**Example:** Client01, Client02, Client03 connect. A fourth attempt is rejected without taking a name. Client02 exits; next accepted connection is **Client04**, while Client02 remains in the history.

## 6. Commands and exact responses

The CLI user types a command; the client converts it to the corresponding JSON request. Commands are **case-sensitive** (`status`, `list`, `exit`). Any other nonempty input is an echo message **unless it matches an available filename**, in which case the client should request a download. To avoid ambiguity, **recommended CLI:** use `get <filename>` for downloads; the assignment's “send the name of any file” is satisfied by the client transmitting the filename in the `download` request. Optionally also support bare filenames for the demo.

### 6.1 Echo message

Client → Server:

```json
{"type":"message","content":"Hello server"}
```

Server → Client:

```json
{"type":"message_ack","content":"Hello server ACK"}
```

Append a space and `ACK` to the **unchanged original string**. For example, `Hi!` → `Hi! ACK`. Do not uppercase the content (unlike one sample project).

### 6.2 Status / session cache

Client → Server:

```json
{"type":"status"}
```

Server → Client (example):

```json
{"type":"status_result","clients":[{"client_name":"Client01","accepted_at":"2026-10-23T20:30:00Z","finished_at":null},{"client_name":"Client02","accepted_at":"2026-10-23T20:31:00Z","finished_at":"2026-10-23T20:35:00Z"}]}
```

The **server prints the cache to its own terminal** and also returns it to the client so the client can display it. This satisfies the assignment's server-print wording while making the CLI useful. History includes disconnected clients until the server process ends. Read/cache-copy under a lock to avoid concurrent mutation.

### 6.3 Exit

Client → Server:

```json
{"type":"exit"}
```

Server → Client:

```json
{"type":"goodbye","message":"Disconnected"}
```

Server then closes the client socket, records `finished_at`, and releases its active slot. Client prints the response and closes its socket. Unexpected socket closure also triggers cleanup in a `finally` block; **cleanup must happen once**.

### 6.4 List files

Client → Server:

```json
{"type":"list"}
```

Server → Client:

```json
{"type":"list_result","files":["example.txt","sample.bin"]}
```

Return only regular files in the configured repository, sorted by filename. An empty repository returns `"files":[]`.

### 6.5 Download file

CLI input: `get example.txt`

Client → Server:

```json
{"type":"download","filename":"example.txt"}
```

Server → Client **control frame**:

```json
{"type":"file_start","filename":"example.txt","size":12}
```

Server → Client **binary payload**: exactly 12 raw bytes from the file, immediately after the metadata frame's newline. No newline or terminator is added after the payload. For a zero-byte file, `size` is `0` and there is no payload.

Server should use `sendall()` in a loop over file chunks (e.g. 4096 or 8192 bytes), keeping file size consistent with metadata. Client writes bytes in binary mode (`wb`) until it receives exactly `size` bytes. Client should save to `downloads/` using the basename. On premature EOF, delete the incomplete download and report failure.

**Not found:**

```json
{"type":"error","code":"FILE_NOT_FOUND","message":"File not found: missing.txt"}
```

**Invalid path:**

```json
{"type":"error","code":"INVALID_FILENAME","message":"Only simple filenames are allowed"}
```

**Design decision:** The server sends **no separate completion frame** after file bytes. Receipt of exactly `size` bytes is completion; this avoids confusion between binary bytes and JSON. Subsequent commands may then resume.

### 6.6 Other errors

```json
{"type":"error","code":"BAD_REQUEST","message":"Unknown or malformed request"}
```

Other reasonable codes: `NOT_IDENTIFIED`, `INVALID_CLIENT_NAME`, `FILE_READ_ERROR`, `INTERNAL_ERROR`. Client displays the error without crashing. A socket-level failure may require terminating the connection rather than sending an error.

## 7. Server implementation contract (`Server.py` owner)

- Create one listening socket, `listen()`, then repeatedly `accept()`.
- Spawn a `threading.Thread(..., daemon=True)` for **each accepted active client**. Keep the main accept loop responsive.
- Use `threading.Lock` around **both** the active-slot count and client-name/cache changes. Check-and-reserve must be atomic to avoid accepting a fourth client during a race.
- Track `next_client_number`, `active_count` or active-client set, and session cache in memory.
- Update `finished_at` and release the active slot in a `finally` block for exit, errors, or abrupt disconnects.
- Never hold the shared lock while blocking on `recv`, `sendall`, or file reads.
- Implement the handshake and exact request/response names in Sections 5–6.
- Keep file access within `server_files/`; reject traversal and avoid following symlinks outside the repository.
- Print connection, disconnection, cache, and file activity for demonstration.
- Catch expected socket/file exceptions so one broken client does not terminate the server.

## 8. Client implementation contract (`Client.py` owner)

- Connect to configured host/port; handle `ConnectionRefusedError` gracefully.
- Read `welcome` or `server_full`; if welcomed, send `identify` and wait for `identified`.
- Prompt repeatedly until `exit`, disconnect, or unrecoverable error.
- Convert CLI text into JSON requests using Section 6 and display responses clearly.
- For `get <filename>`, read `file_start`, then exactly `size` bytes to `downloads/<filename>`; show a useful success/error message.
- Preserve binary file contents; do not call `.decode()` on file bytes.
- Keep one request outstanding; do not prompt for another command during a transfer.
- Handle unexpected EOF and clean up sockets/download temp files.

## 9. Integration checkpoints and ownership

| Checkpoint | Server owner | Client owner | Joint acceptance |
|---|---|---|---|
| A — handshake | Listener, naming, `welcome`, `identified` | Connect, identify, prompt | `Client01` connects and is named correctly |
| B — echo/exit | `message_ack`, `goodbye`, cleanup | Send/display commands | `Hello` → `Hello ACK`; exit releases slot |
| C — concurrency | Threads, max 3, cache | Run multiple client processes | 3 simultaneous; fourth rejected; next accepted = `Client04` |
| D — status | Cache and `status_result` | Display status | Connected and finished timestamps visible |
| E — files | List, validate, stream | List, download | List, valid download, missing-file error |
| F — delivery | Server tests and server report notes | Client tests, screenshots, report assembly | All rubric cases pass; demo rehearsed |

**Workflow:** Agree on this protocol → commit `PROTOCOL.md` to `main` → each partner works in their own branch (`feature/server`, `feature/client`) → merge and test after checkpoint B, not only at the end. Any protocol change must be agreed to by both partners and committed before either implementation changes.

## 10. Demonstration / acceptance test plan

| Test ID | Procedure | Expected result | Rubric points |
|---|---|---|---:|
| T01 | Start server, then one client | TCP connection succeeds | 20 |
| T02 | Connect clients sequentially | Names Client01, Client02, Client03 | 10 |
| T03 | Leave 3 clients connected; message from each | All receive responses independently | 20 |
| T04 | Attempt fourth simultaneous connection | `server_full`, no active fourth client | 10 |
| T05 | Send `Hello world` | `Hello world ACK` | 20 |
| T06 | Client02 sends `exit`; connect again | Slot freed; new client is Client04 | 10 |
| T07 | Send `status` after connect/disconnect | Cache shows names, accepted/finished timestamps | 10 |
| T08 | Send `list` | Correct repository filenames | 10 |
| T09 | Download text and binary file | Correct bytes; missing filename gives error | 10 |
| T10 | Capture results and document design/challenges/improvements | Complete `Report.pdf` with screenshots | 30 |

**Total rubric:** 150 points (120 implementation + 30 report). The rubric says **no partial credit per item**. Capture screenshots during T01–T09. Also test zero-byte files, abrupt client termination, repeated `status`, and a download followed by another command.

## 11. Demo commands and environment

Run in **four separate terminals**, from the project directory:

```bash
python3 Server.py
```

```bash
python3 Client.py
```

Run `python3 Client.py` again in two additional terminals. To demonstrate a fourth connection, open one more terminal; it should be rejected. Then `exit` from an active client and reconnect.

Recommended CLI demo sequence: `Hello` → `status` → `list` → `get example.txt` → `get missing.txt` → `exit`.

For same-machine testing, `127.0.0.1` works on macOS, Windows, and Linux. For separate machines, change server bind address and client destination to the server's LAN IP, and account for firewalls. Keep the same port and protocol.

## 12. Decisions to confirm together (before coding)

- [ ] Approve **JSON-lines control frames + raw length-delimited file bytes**.
- [ ] Approve port `65432` and `MAX_CLIENTS = 3`.
- [ ] Approve server-generated name followed by client `identify` message.
- [ ] Approve `get <filename>` CLI syntax (and optionally support bare filename input).
- [ ] Approve server printing **and** returning `status`.
- [ ] Approve `server_files/` and `downloads/` folders.
- [ ] Decide who books the **mandatory GTA demo** and confirm booking.
- [ ] Decide who submits the three files before **October 26**.

## 13. Submission reminders

- Submit **exactly the required named deliverables**: `Server.py`, `Client.py`, `Report.pdf` to Assignment 1 Dropbox (additional working files are not required).
- Include both student names in both Python files and the report; comment/document source code.
- Report sections: brief description and design decisions; difficulties and solutions; screenshots for **all rubric items**; possible improvements.
- **Mandatory demo:** reserve a GTA timeslot using the shared Excel sheet. No demo means no grade.

**Source material:** CP372 *Socket Programming_Fall 2026.pdf* assignment handout; uploaded `echo-server.py`, `echo-client.py`, `TCPServer.py`, `TCPclient.py` classroom examples.
