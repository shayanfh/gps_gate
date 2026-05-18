frappe.listview_settings["Vehicle"] = {
	get_indicator: function (doc) {
		if (doc.custom_vehicle_type) {
			return [__("Active"), "green", "custom_vehicle_type,is,set"];
		}
		return [__("Incomplete"), "orange", "custom_vehicle_type,is,not set"];
	},

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

		listview.page.add_action_item(__("Set Vehicle Type"), function () {
			let selected = listview.get_checked_items(true);
			if (!selected.length) {
				frappe.show_alert({
					message: __("Please select at least one vehicle."),
					indicator: "orange",
				}, 5);
				return;
			}
			frappe.prompt(
				{
					label: __("Vehicle Type"),
					fieldname: "vehicle_type",
					fieldtype: "Link",
					options: "Vehicle Type",
					reqd: 1,
				},
				function (values) {
					frappe.call({
						method: "gps_gate.apis.sync_vehicles.bulk_set_vehicle_type",
						args: {
							vehicles: selected,
							vehicle_type: values.vehicle_type,
						},
						callback: function (r) {
							if (r.message) {
								frappe.show_alert({
									message: __("{0} vehicle(s) updated.", [r.message.updated]),
									indicator: "green",
								}, 5);
								listview.refresh();
							}
						},
					});
				},
				__("Set Vehicle Type"),
				__("Update")
			);
		});
	},
};
