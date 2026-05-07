# Copyright (c) 2026, Naqeeb Khan
# For license information, please see license.txt

import json
import frappe
from frappe.model.document import Document


class GPSGateVehicleStatus(Document):

    def before_save(self):
        if self.latitude and self.longitude:
            self.map_location = json.dumps({
                "type": "FeatureCollection",
                "features": [{
                    "type": "Feature",
                    "properties": {},
                    "geometry": {
                        "type": "Point",
                        "coordinates": [
                            float(self.longitude),
                            float(self.latitude)
                        ]
                    }
                }]
            })
