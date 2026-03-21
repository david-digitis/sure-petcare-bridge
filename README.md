# Sure Petcare MQTT Bridge for Gladys Assistant

[![Build](https://github.com/david-digitis/sure-petcare-bridge/actions/workflows/docker.yml/badge.svg)](https://github.com/david-digitis/sure-petcare-bridge/actions/workflows/docker.yml)

A lightweight Docker bridge that connects **Sure Petcare** devices (cat flaps, pet doors) to **[Gladys Assistant](https://gladysassistant.com)** via MQTT.

Polls the Sure Petcare cloud API using [surepy](https://github.com/benleb/surepy) (the same library Home Assistant used) and publishes pet/device state to Gladys MQTT topics.

## Features

- Pet location tracking (inside/outside) as a binary presence sensor
- Flap battery level as a percentage sensor
- Auto-discovery of all pets and flaps on your Sure Petcare account
- Smart logging: only logs state changes, not every poll
- ~50 MB RAM footprint
- Multi-arch Docker image (amd64 + arm64)

## Quick Start

### Prerequisites

- **Gladys Assistant** with the **MQTT integration** configured
- A **Mosquitto** MQTT broker connected to Gladys
- A **Sure Petcare** account (the one you use in the smartphone app)
- A **Cat Flap Connect** or **Pet Door Connect** with its **Hub** connected to WiFi

### Run with Docker

```bash
docker run -d \
  --name sure-petcare-bridge \
  --network host \
  --restart unless-stopped \
  -e SUREPETCARE_EMAIL=your@email.com \
  -e SUREPETCARE_PASSWORD=your_password \
  -e MQTT_HOST=localhost \
  -e MQTT_PORT=1883 \
  -e POLL_INTERVAL=60 \
  ghcr.io/david-digitis/sure-petcare-bridge:latest
```

### Check the logs

```bash
docker logs sure-petcare-bridge
```

You should see:
```
12:15:21 [sure-bridge] MQTT connected (localhost:1883)
12:15:21 [sure-bridge] Sure Petcare Bridge v1.1 started
12:15:21 [sure-bridge] Account: your@email.com | poll: 60s
12:15:23 [sure-bridge] Discovered: 1 pet(s), 1 flap(s), 1 hub(s)
12:15:23 [sure-bridge]   Pet: Arwen (id=12345)
12:15:23 [sure-bridge]   Flap: CatDoor (id=67890)
12:15:23 [sure-bridge] [PET] Arwen: inside
12:15:23 [sure-bridge] [FLAP] CatDoor: battery=51% lock=Unlocked
```

> The `404` warning on `/api/report/household/` is normal — it's an optional Sure Petcare API endpoint that surepy attempts to call. It doesn't affect anything.

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `SUREPETCARE_EMAIL` | Yes | — | Your Sure Petcare account email |
| `SUREPETCARE_PASSWORD` | Yes | — | Your Sure Petcare account password |
| `MQTT_HOST` | No | `localhost` | MQTT broker hostname |
| `MQTT_PORT` | No | `1883` | MQTT broker port |
| `POLL_INTERVAL` | No | `60` | Polling interval in seconds |
| `LOG_LEVEL` | No | `INFO` | Log level (DEBUG, INFO, WARNING, ERROR) |

## Configure Gladys Devices

### Device 1 — Your pet

Go to **Integrations -> MQTT -> Devices -> New +**

| Field | Value |
|-------|-------|
| Name | Your pet's name (e.g. `Arwen`) |
| External ID | `mqtt:maison:pet-arwen` |
| Room | Pick one |

**Add a feature:**

| Field | Value |
|-------|-------|
| Name | `Presence` |
| External ID | `mqtt:maison:pet-arwen:presence` |
| Category | Presence sensor |
| Type | Binary |
| Read only (sensor) | **Yes** |
| Min | 0 |
| Max | 1 |

> **Naming convention**: the external ID must match what the bridge publishes. Format: `mqtt:maison:pet-{name-in-lowercase}`. If your cat is named "Whiskers", it becomes `mqtt:maison:pet-whiskers`.

### Device 2 — The flap

| Field | Value |
|-------|-------|
| Name | Your flap name (e.g. `Cat Flap`) |
| External ID | `mqtt:maison:chatiere-catdoor` |
| Room | Where the flap is installed |

**Add a feature:**

| Field | Value |
|-------|-------|
| Name | `Battery` |
| External ID | `mqtt:maison:chatiere-catdoor:battery` |
| Category | Battery |
| Type | Integer |
| Read only (sensor) | **Yes** |
| Min | 0 |
| Max | 100 |
| Unit | % |

> **Tip**: check the bridge logs on first startup to find the correct slugs. The bridge displays the name of each detected pet and flap.

## How It Works

```
Sure Petcare Cloud <--HTTPS--> sure-petcare-bridge (Python) <--MQTT--> Mosquitto <--> Gladys
```

1. Your pet goes through the flap
2. The flap detects the microchip (or RFID tag) and sends the info to the Sure Petcare Hub
3. The Hub transmits to the Sure Petcare cloud
4. The bridge polls the cloud API via **surepy**
5. The bridge publishes the new state to MQTT
6. Gladys receives the message and updates the dashboard

### Why cloud polling?

Sure Petcare doesn't expose a local API. Everything goes through their cloud. This is the same limitation Home Assistant had. If Sure Petcare servers go down, no data (but the smartphone app will be down too).

Polling at 60 seconds is a good trade-off: fast enough to know where your pet is, not aggressive enough to get rate-limited.

## Compatible Devices

The bridge auto-detects all devices on your Sure Petcare account:
- **Cat Flap Connect** (microchip cat flap)
- **Pet Door Connect** (pet door)
- **Hub** (WiFi gateway)
- Feeder Connect / Felaqua (detected but not yet exposed — easy to add)

Multiple pets? The bridge creates one MQTT topic per pet. Just create one Gladys device per pet.

## Limitations

- **Cloud only**: no local control, depends on Sure Petcare servers
- **Latency**: 0 to 60 seconds depending on poll timing (configurable via `POLL_INTERVAL`)
- **Read only**: lock/unlock control from Gladys is not implemented yet (technically possible with surepy)
- **No last-passage timestamp**: Gladys doesn't have a native "timestamp" feature type. However, the presence feature records when the value last changed — effectively your "last passage"

## Build Locally

If you prefer to build the image yourself:

```bash
git clone https://github.com/david-digitis/sure-petcare-bridge.git
cd sure-petcare-bridge
docker build -t sure-petcare-bridge .
docker run -d --name sure-petcare-bridge --network host --restart unless-stopped \
  -e SUREPETCARE_EMAIL=your@email.com \
  -e SUREPETCARE_PASSWORD=your_password \
  -e MQTT_HOST=localhost \
  sure-petcare-bridge:latest
```

## License

MIT
