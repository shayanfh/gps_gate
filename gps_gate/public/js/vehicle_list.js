frappe.listview_settings["Vehicle"] = {
	onload: function (listview) {
		listview.page.add_inner_button(__("Sync GPS Gate Vehicles"), function () {
			frappe.call({
				method: "gps_gate.apis.sync_vehicles.sync_vehicles_from_gps_gate",
				freeze: true,
				freeze_message: __("Syncing vehicles from GPS Gate..."),
				callback: function (r) {
					if (!r.message) return;
					let res = r.message;
					let msg =
						`<b>${__("Sync Complete")}</b><br>` +
						`${__("Created")}: ${res.created}<br>` +
						`${__("Updated")}: ${res.updated}<br>` +
						`${__("Total with devices")}: ${res.total_with_devices}`;

					if (res.errors && res.errors.length) {
						msg += `<br><span class="text-danger">${__("Errors")}: ${res.errors.length} (${res.errors.join(", ")})</span>`;
					}

					frappe.msgprint({ title: __("GPS Gate Sync"), message: msg, indicator: res.errors.length ? "orange" : "green" });
					listview.refresh();
				},
			});
		});
	},
};
