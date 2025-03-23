#!/usr/bin/env python
#
#  GoogleFindMyTools - A set of tools to interact with the Google Find My API
#  Copyright © 2024 Leon Böttger. All rights reserved.
#  Copyright © 2025 Elan Ruusamäe. All rights reserved.
#
from os import environ
from datetime import datetime
from dataclasses import dataclass
from functools import cached_property

import requests

from NovaApi.ExecuteAction.LocateTracker.decrypted_location import WrappedLocation
from NovaApi.ExecuteAction.LocateTracker.location_request import get_location_data_for_device
from ProtoDecoders import Common_pb2, DeviceUpdate_pb2
from ProtoDecoders.Common_pb2 import Status


@dataclass
class Location:
    time: datetime
    status: str
    is_own_report: bool
    accuracy: float
    name: str

    latitude: float
    longitude: float
    altitude: float

    device_id: str

    @classmethod
    def from_wrapped_location(cls, loc: WrappedLocation, canonic_device_id: str):
        if loc.status == Common_pb2.Status.SEMANTIC:
            latitude = longitude = altitude = None
        else:
            proto_loc = DeviceUpdate_pb2.Location()
            proto_loc.ParseFromString(loc.decrypted_location)

            latitude = proto_loc.latitude / 1e7
            longitude = proto_loc.longitude / 1e7
            altitude = proto_loc.altitude

        return cls(
            name=loc.name,
            time=datetime.fromtimestamp(loc.time),
            status=Status.Name(loc.status),
            is_own_report=loc.is_own_report,
            accuracy=loc.accuracy,

            latitude=latitude,
            longitude=longitude,
            altitude=altitude,

            device_id=canonic_device_id,
        )


class Store:
    CREATE_SCHEMA = """
    CREATE TABLE IF NOT EXISTS locations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        time TIMESTAMP NOT NULL,
        device_id TEXT NOT NULL,
        name TEXT NOT NULL,
        status TEXT NOT NULL,
        is_own_report INTEGER NOT NULL,
        accuracy REAL NOT NULL,
        latitude REAL NOT NULL,
        longitude REAL NOT NULL,
        altitude REAL NOT NULL,
        UNIQUE(time, device_id)
    )
    """

    def __init__(self, path):
        self.path = path

    def add(self, location: Location):
        is_own_report = 1 if location.is_own_report else 0
        time = location.time.isoformat() if isinstance(location.time, datetime) else location.time

        row_id = self.insert(
            '''
            INSERT OR IGNORE INTO locations
            (time, status, is_own_report, accuracy, name, latitude, longitude, altitude, device_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''',
            time,
            location.status,
            is_own_report,
            location.accuracy,
            location.name,
            location.latitude,
            location.longitude,
            location.altitude,
            location.device_id
        )

        return row_id

    def insert(self, sql: str, *args):
        cursor = self.con.cursor()
        cursor.execute(sql, args)
        row_id = cursor.lastrowid
        self.commit()

        return row_id

    def commit(self):
        self.connection.commit()

    def close(self):
        self.connection.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    @cached_property
    def connection(self):
        import sqlite3

        return sqlite3.connect(self.path)

    @cached_property
    def con(self):
        connection = self.connection
        connection.cursor().execute(self.CREATE_SCHEMA)
        connection.commit()

        return connection


class TraccarApiError(Exception):
    """Exception raised for errors in the Traccar API response."""

    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message
        super().__init__(f"Traccar API Error: {status_code} - {message}")


class TraccarResponseError(Exception):
    """Exception raised for invalid response from Traccar API."""

    def __init__(self, message: str):
        self.message = message
        super().__init__(f"Traccar Response Error: {message}")


class Traccar:
    def __init__(self, host: str, token: str):
        self.host = host
        self.token = token

    def add(self, location: Location):
        self.request({
            'timestamp': int(location.time.timestamp()),
            'deviceid': location.device_id,
            'lat': location.latitude,
            'lon': location.longitude,
            'altitude': location.altitude,
            'accuracy': location.accuracy,
        })

    def request(self, params: dict):
        # OsmAnd protocol port
        # https://www.traccar.org/osmand/
        endpoint = f"http://{self.host}:5055"
        headers = {
            'Authorization': f'Bearer {self.token}'
        }

        response = requests.get(
            endpoint,
            params=params,
            headers=headers,
            timeout=10,
        )

        if response.status_code != 200:
            raise TraccarApiError(response.status_code, f"Failed to update location: {response.text}")

        # Check for empty response (Content-Length: 0)
        content_length = response.headers.get('Content-Length', None)
        if content_length is None or int(content_length) != 0:
            raise TraccarResponseError("Unexpected response from server")


def main(args: list[str]):
    if not len(args):
        return
    canonic_device_id = args[0]
    locations = get_location_data_for_device(canonic_device_id, "")

    with Store("locations.sqlite3") as store:
        for wrapped in locations:
            location = Location.from_wrapped_location(wrapped, canonic_device_id)
            store.add(location)


if __name__ == '__main__':
    import sys

    main(sys.argv[1:])
