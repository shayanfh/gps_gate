# Copyright (c) 2026, Naqeeb Khan
# For license information, please see license.txt

import json
import frappe
from frappe.model.document import Document


class GPSGateTripInfo(Document):

    def before_save(self):
        has_start = self.start_latitude and self.start_longitude
        has_end = self.end_latitude and self.end_longitude

        if has_start and has_end:
            slat = float(self.start_latitude)
            slng = float(self.start_longitude)
            elat = float(self.end_latitude)
            elng = float(self.end_longitude)

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
                        "properties": {},
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
