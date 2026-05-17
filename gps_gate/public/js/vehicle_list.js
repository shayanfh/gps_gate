frappe.listview_settings["Vehicle"] = {
	onload: function (listview) {
		listview.page.add_inner_button(__("Sync GPS Gate Vehicles"), function () {
			frappe.call({
				method: "gps_gate.apis.sync_vehicles.sync_vehicles_from_gps_gate",
				callback: function (r) {
					if (r.message && r.message.status === "queued") {
						frappe.show_alert({
							message: __("Vehicle sync started in background. Check Error Log if issues occur."),
							indicator: "blue",
						}, 8);
					}
				},
			});
		});
	},
};
