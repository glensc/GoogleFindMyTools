#!/usr/bin/env python
#
#  GoogleFindMyTools - A set of tools to interact with the Google Find My API
#  Copyright © 2024 Leon Böttger. All rights reserved.
#  Copyright © 2025 Elan Ruusamäe. All rights reserved.
#

from datetime import datetime
from dataclasses import dataclass
from NovaApi.ExecuteAction.LocateTracker.decrypted_location import WrappedLocation
from NovaApi.ExecuteAction.LocateTracker.location_request import get_location_data_for_device
from ProtoDecoders import Common_pb2, DeviceUpdate_pb2
from ProtoDecoders.Common_pb2 import Status


@dataclass
class Location:
    time: datetime
    status: int
    is_own_report: bool
    accuracy: int
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


def main(args: list[str]):
    if not len(args):
        return
    canonic_device_id = args[0]
    locations = get_location_data_for_device(canonic_device_id, "")

    for wrapped in locations:
        location = Location.from_wrapped_location(wrapped, canonic_device_id)
        print(location)


if __name__ == '__main__':
    import sys

    main(sys.argv[1:])
