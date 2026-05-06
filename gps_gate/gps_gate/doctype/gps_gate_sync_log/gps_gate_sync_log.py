# Copyright (c) 2026, Naqeeb Khan
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class GPSGateSyncLog(Document):
    def before_save(self):
        # Calculate progress percent
        if self.total_batches and self.completed_batches:
            self.progress_percent = round((self.completed_batches / self.total_batches) * 100, 1)
        else:
            self.progress_percent = 0
