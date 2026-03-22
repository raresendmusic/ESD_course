# Hiking Assistant Receiver

Raspberry Pi-side Bluetooth receiver for the Hiking Assistant system.

This repository is responsible for connecting to the watch over **Classic Bluetooth RFCOMM**, synchronizing completed hiking sessions, and storing them in the server-side database.

This repository is intended to run on the **Raspberry Pi** together with the `web-ui` repository. The receiver handles watch communication and data ingestion, while the web UI provides storage-backed browsing and visualization of synchronized sessions.

## Responsibilities

This service:

- connects to the watch over Classic Bluetooth
- performs the protocol handshake with the watch
- sends wall-clock time to the watch after connection
- requests finished sessions from the watch
- receives sessions one by one
- acknowledges each stored session explicitly
- stores synchronized sessions in the backend database
- tolerates connection loss, watch reboot, and temporary timeouts during synchronization

## Repository structure

```text
.
├── README.md
├── bt.py
├── db.py
├── hike.py
├── receiver.py
└── requirements.txt
```

### File overview

* `receiver.py` — main process entry point
* `bt.py` — Bluetooth transport and synchronization protocol handling
* `db.py` — database access layer
* `hike.py` — hiking session model and related helpers
* `requirements.txt` — Python dependencies

## Runtime role in the full system

The full system is split across repositories:

* `watch` — records sessions on the LilyGo T-Watch 2020 V3
* `receiver` — receives and stores synchronized sessions on the Raspberry Pi
* `web-ui` — serves the browser-based dashboard and API

A typical Raspberry Pi layout looks like this:

```text
/home/user/hiking-app/
├── receiver/
├── web-ui/
└── .venv/
```

The receiver and the web UI are expected to be cloned locally onto the same Raspberry Pi.

## Requirements

* Python 3
* `python3-virtualenv`
* `python3-pip`
* `python3-bluez`
* `bluez`

Install the required system packages on Debian-based systems such as Raspberry Pi OS:

```bash
sudo apt update
sudo apt install python3-virtualenv python3-pip python3-bluez bluez
```

## Setup

### 1. Create and activate a virtual environment

From the parent directory that contains both `receiver` and `web-ui`:

```bash
virtualenv --system-site-packages -p python3 .venv
source .venv/bin/activate
```

### 2. Install Python dependencies

From the `receiver` repository:

```bash
python3 -m pip install -r requirements.txt
```

### 3. Verify Bluetooth Python support

```bash
python3 -c "import bluetooth; print(bluetooth.__file__)"
```

If this import fails, check that `python3-bluez` is installed and that the virtual environment was created with `--system-site-packages`.

## Environment and configuration

The receiver uses watch connection constants defined in `bt.py`, including:

* `WATCH_BT_MAC`
* `WATCH_BT_PORT`
* `BT_PROTOCOL_VERSION`

If the watch Bluetooth address changes, update `WATCH_BT_MAC` accordingly.

If this repository also includes a local `.env.example`, copy it to `.env` and adjust values for your setup. If not, configuration is currently handled directly in source files.

## Run the receiver

From the `receiver` directory:

```bash
source ../.venv/bin/activate
python3 receiver.py
```

Typical logs include messages such as:

* `Starting Bluetooth receiver.`
* `Waiting for connection...`
* `Hub -> Watch: HELLO|2`
* `Hub -> Watch: TIME_SYNC|...`
* `Synchronizing with watch...`
* `Watch -> Hub: SESSION|...`
* `Watch reported sync completion.`

These logs are the main way to debug Bluetooth connectivity and synchronization behavior.

## Synchronization protocol overview

The receiver currently uses a simple line-based Classic Bluetooth protocol.

### Outgoing messages from hub to watch

#### `HELLO|<protocol_version>`

Sent immediately after connecting.

#### `TIME_SYNC|<unix_epoch>`

Sent immediately after connecting so the watch can restore a trusted wall clock after boot.

#### `SYNC_PULL`

Requests the next finished session from the watch.

#### `SESSION_ACK|<session_id>`

Sent after a received session has been successfully processed and stored.

### Incoming messages from watch

#### `HELLO_ACK|<protocol_version>`

Acknowledges the protocol version.

#### `TIME_SYNC_ACK|<unix_epoch>`

Acknowledges successful time synchronization.

#### `TIME_SYNC_NACK|invalid_epoch`

Indicates that the watch rejected the provided epoch.

#### `SESSION|<json>`

Contains one completed hiking session.

#### `SYNC_DONE`

Indicates that the watch has no more finished sessions to transfer in the current sync cycle.

## Session flow

A normal sync cycle looks like this:

1. The receiver connects to the watch.
2. The receiver sends `HELLO|...`.
3. The receiver sends `TIME_SYNC|...`.
4. The receiver sends `SYNC_PULL`.
5. The watch sends either:
   * `SESSION|<json>` for the next finished session, or
   * `SYNC_DONE` if there is nothing to transfer.
6. The receiver stores each received session.
7. The receiver replies with `SESSION_ACK|<session_id>`.
8. The watch sends the next session or finishes with `SYNC_DONE`.

This design ensures that sessions are transferred one at a time and only removed from the watch after explicit acknowledgment.

## Reboot and timeout handling

The receiver is designed to tolerate temporary failures.

Examples include:

* the watch rebooting during synchronization
* Bluetooth receive timeouts
* connection loss during transfer

In those cases, the receiver closes the current socket, resets connection state, and returns to waiting for the next connection attempt.

## Project structure and responsibilities

### `receiver.py`

The main long-running loop.

Responsibilities:

* start the receiver process
* wait for a Bluetooth connection
* trigger synchronization
* pass received sessions to the database layer

### `bt.py`

Bluetooth protocol and transport logic.

Responsibilities:

* connect to the watch
* send handshake and time-sync messages
* parse incoming protocol lines
* detect sync completion
* recover from Bluetooth timeouts and disconnects
* acknowledge stored sessions

### `db.py`

Persistence layer for synchronized sessions.

Responsibilities:

* insert received sessions into the database
* isolate database access from Bluetooth logic

### `hike.py`

Session data model.

Responsibilities:

* represent a synchronized hiking session
* provide conversion and helper logic if needed by the receiver and database code

## Development notes

* This repository handles **Bluetooth ingestion only**.
* The web server and dashboard now belong in the separate `web-ui` repository.
* The overall system is designed for offline Raspberry Pi deployment.
* The receiver should be run on the same Raspberry Pi that hosts the web UI and database.
* During development, it is often easiest to run the receiver manually and inspect logs directly in the terminal.
