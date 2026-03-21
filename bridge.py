#!/usr/bin/env python3
"""
Sure Petcare MQTT Bridge for Gladys Assistant v1.1

Polls Sure Petcare cloud API via surepy and publishes pet/device state
to Gladys via MQTT topics.

Features published:
  - Pet location (inside/outside) -> presence-sensor binary
  - Flap battery level -> battery integer (%)

Topics published (state -> Gladys):
  gladys/master/device/{ext_id}/feature/{feat_ext_id}/state

Environment variables:
  SUREPETCARE_EMAIL       (required)
  SUREPETCARE_PASSWORD    (required)
  MQTT_HOST               (default: localhost)
  MQTT_PORT               (default: 1883)
  POLL_INTERVAL           (default: 60, seconds)
  LOG_LEVEL               (default: INFO)
"""

import os
import sys
import signal
import asyncio
import logging

import paho.mqtt.client as paho
from surepy import Surepy
from surepy.enums import EntityType

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

EMAIL = os.environ.get('SUREPETCARE_EMAIL', '')
PASSWORD = os.environ.get('SUREPETCARE_PASSWORD', '')
MQTT_HOST = os.environ.get('MQTT_HOST', 'localhost')
MQTT_PORT = int(os.environ.get('MQTT_PORT', '1883'))
POLL_INTERVAL = int(os.environ.get('POLL_INTERVAL', '60'))
LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')

if not EMAIL or not PASSWORD:
    sys.exit('[FATAL] SUREPETCARE_EMAIL and SUREPETCARE_PASSWORD required')

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
    format='%(asctime)s [%(name)s] %(message)s',
    datefmt='%H:%M:%S',
)
log = logging.getLogger('sure-bridge')

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def slugify(name: str) -> str:
    """Name -> slug compatible with Gladys external_id (mqtt:xxx:yyy)."""
    s = name.lower().replace(' ', '-').replace("'", '').replace('"', '')
    for old, new in {
        '\xe9': 'e', '\xe8': 'e', '\xea': 'e',
        '\xe0': 'a', '\xf9': 'u', '\xe7': 'c',
    }.items():
        s = s.replace(old, new)
    return s


def publish(client, device_ext: str, feature_suffix: str, value):
    """Publish a value to the Gladys MQTT topic."""
    feat_ext = f'{device_ext}:{feature_suffix}'
    topic = f'gladys/master/device/{device_ext}/feature/{feat_ext}/state'
    client.publish(topic, str(value))

# ---------------------------------------------------------------------------
# State cache (only log changes)
# ---------------------------------------------------------------------------

_prev_state: dict[str, dict] = {}


def state_changed(key: str, **kwargs) -> bool:
    """Return True if state changed since last poll."""
    prev = _prev_state.get(key)
    if prev != kwargs:
        _prev_state[key] = kwargs
        return True
    return False

# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

async def run():
    """Main bridge loop."""

    # --- MQTT ---
    try:
        mqtt = paho.Client(paho.CallbackAPIVersion.VERSION2, client_id='sure-petcare-bridge')
    except (AttributeError, TypeError):
        # Fallback paho-mqtt v1
        mqtt = paho.Client(client_id='sure-petcare-bridge')

    mqtt.on_connect = lambda *_: log.info(f'MQTT connected ({MQTT_HOST}:{MQTT_PORT})')
    mqtt.on_disconnect = lambda *_: log.warning('MQTT disconnected, auto-reconnecting...')
    mqtt.reconnect_delay_set(min_delay=1, max_delay=30)

    try:
        mqtt.connect(MQTT_HOST, MQTT_PORT)
    except Exception as e:
        sys.exit(f'[FATAL] MQTT connection failed: {e}')

    mqtt.loop_start()

    # --- Sure Petcare ---
    surepy = Surepy(email=EMAIL, password=PASSWORD)

    log.info('Sure Petcare Bridge v1.1 started')
    log.info(f'Account: {EMAIL} | poll: {POLL_INTERVAL}s')

    first_run = True

    try:
        while True:
            try:
                entities = await surepy.get_entities()

                # First poll: discovery log
                if first_run:
                    pets = [e for e in entities.values() if e.type == EntityType.PET]
                    flaps = [e for e in entities.values()
                             if e.type in (EntityType.CAT_FLAP, EntityType.PET_FLAP)]
                    hubs = [e for e in entities.values() if e.type == EntityType.HUB]
                    log.info(
                        f'Discovered: {len(pets)} pet(s), '
                        f'{len(flaps)} flap(s), {len(hubs)} hub(s)'
                    )
                    for p in pets:
                        log.info(f'  Pet: {p.name} (id={p.id})')
                    for f in flaps:
                        log.info(f'  Flap: {f.name} (id={f.id}, serial={getattr(f, "serial", "?")})')
                    first_run = False

                # --- Pets ---
                for entity in entities.values():
                    if entity.type != EntityType.PET:
                        continue

                    slug = slugify(entity.name)
                    ext_id = f'mqtt:maison:pet-{slug}'
                    at_home = 1 if entity.at_home else 0

                    publish(mqtt, ext_id, 'presence', at_home)

                    if state_changed(f'pet-{entity.id}', at_home=at_home):
                        loc = 'inside' if at_home else 'outside'
                        since = ''
                        try:
                            if entity.location and entity.location.since:
                                since = f' since {entity.location.since.strftime("%H:%M")}'
                        except Exception:
                            pass
                        log.info(f'[PET] {entity.name}: {loc}{since}')

                # --- Flaps / Pet Doors ---
                for entity in entities.values():
                    if entity.type not in (EntityType.CAT_FLAP, EntityType.PET_FLAP):
                        continue

                    slug = slugify(entity.name)
                    ext_id = f'mqtt:maison:chatiere-{slug}'

                    battery = getattr(entity, 'battery_level', None)
                    if battery is not None:
                        publish(mqtt, ext_id, 'battery', battery)

                    lock_state = getattr(entity, 'state', None)
                    lock_label = str(lock_state) if lock_state is not None else '?'

                    if state_changed(f'flap-{entity.id}', battery=battery, lock=lock_label):
                        log.info(f'[FLAP] {entity.name}: battery={battery}% lock={lock_label}')

            except Exception as e:
                log.error(f'Poll error: {e}', exc_info=(LOG_LEVEL.upper() == 'DEBUG'))

            await asyncio.sleep(POLL_INTERVAL)

    finally:
        mqtt.loop_stop()
        mqtt.disconnect()
        log.info('Bridge stopped')


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

def main():
    # SIGTERM (Docker stop) -> clean shutdown
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))

    try:
        asyncio.run(run())
    except (KeyboardInterrupt, SystemExit):
        log.info('Shutdown.')


if __name__ == '__main__':
    main()
