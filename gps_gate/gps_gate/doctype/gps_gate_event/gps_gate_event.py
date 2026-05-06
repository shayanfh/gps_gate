# Copyright (c) 2026, Naqeeb Khan
# For license information, please see license.txt
import json
import math
import frappe
from frappe.model.document import Document  # ✅ Correct import


def calculate_distance_km(lat1, lon1, lat2, lon2):
    """Haversine formula - distance in kilometers"""
    R = 6371  # Earth radius in km

    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))

    return round(R * c, 3)


class GPSGateEvent(Document):

    def before_save(self):
        has_start = self.start_latitude and self.start_longitude
        has_end = self.end_latitude and self.end_longitude

        if has_start and has_end:
            slat = float(self.start_latitude)
            slng = float(self.start_longitude)
            elat = float(self.end_latitude)
            elng = float(self.end_longitude)

            distance_km = calculate_distance_km(slat, slng, elat, elng)

            self.map_location = json.dumps({
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "properties": {"point_type": "start"},
                        "geometry": {
                            "type": "Point",
                            "coordinates": [slng, slat]
                        }
                    },
                    {
                        "type": "Feature",
                        "properties": {"point_type": "end"},
                        "geometry": {
                            "type": "Point",
                            "coordinates": [elng, elat]
                        }
                    },
                    {
                        "type": "Feature",
                        "properties": {"distance_km": distance_km},
                        "geometry": {
                            "type": "LineString",
                            "coordinates": [
                                [slng, slat],
                                [elng, elat]
                            ]
                        }
                    }
                ]
            })

            if hasattr(self, 'distance_km'):
                self.distance_km = distance_km

        elif has_start:
            slat = float(self.start_latitude)
            slng = float(self.start_longitude)

            self.map_location = json.dumps({
                "type": "FeatureCollection",
                "features": [{
                    "type": "Feature",
                    "properties": {"point_type": "start"},
                    "geometry": {
                        "type": "Point",
                        "coordinates": [slng, slat]
                    }
                }]
            })

