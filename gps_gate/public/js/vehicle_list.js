frappe.listview_settings["Vehicle"] = {
	add_fields: ["custom_vehicle_type"],

	get_indicator: function (doc) {
		if (doc.custom_vehicle_type) {
			return [doc.custom_vehicle_type, "green", "custom_vehicle_type,=," + doc.custom_vehicle_type];
		}

		return [__("No Vehicle Type"), "orange", "custom_vehicle_type,is,not set"];
	},


	onload: function (listview) {
		let _syncDialog = null;

		function _closeSyncDialog() {
			frappe.realtime.off("vehicle_sync_progress", _onProgress);
			if (_syncDialog) {
				_syncDialog.hide();
				_syncDialog = null;
			}
		}

		function _onProgress(data) {
			if (!_syncDialog) return;

			const pct = data.total ? Math.round((data.current / data.total) * 100) : 0;
			const bar = _syncDialog.$wrapper.find(".sync-bar");
			const lbl = _syncDialog.$wrapper.find(".sync-label");

			if (["done", "cancelled", "error"].includes(data.status)) {
				_closeSyncDialog();
				listview.refresh();

				const indicators = { done: "green", cancelled: "orange", error: "red" };
				const messages = {
					done: __("Sync complete — {0} created, {1} updated, {2} errors.", [
						data.created, data.updated, data.errors,
					]),
					cancelled: __("Sync cancelled — {0} of {1} vehicles processed.", [
						data.current, data.total,
					]),
					error: __("Sync failed. Check Error Log for details."),
				};
				frappe.show_alert({ message: messages[data.status], indicator: indicators[data.status] }, 8);
				return;
			}

			bar.css("width", pct + "%").text(pct + "%");
			lbl.text(__("Syncing {0}  ({1} / {2})", [data.label || "", data.current, data.total]));
		}

		listview.page.add_inner_button(__("Sync GPS Gate Vehicles"), function () {
			if (_syncDialog) {
				frappe.show_alert({ message: __("Sync is already in progress."), indicator: "orange" }, 4);
				return;
			}

			_syncDialog = new frappe.ui.Dialog({
				title: __("Syncing GPS Gate Vehicles"),
				fields: [{ fieldtype: "HTML", fieldname: "progress_area" }],
				primary_action_label: __("Cancel Sync"),
				primary_action: function () {
					frappe.call({
						method: "gps_gate.apis.sync_vehicles.cancel_vehicle_sync",
						callback: function () {
							_syncDialog && _syncDialog.get_primary_btn()
								.prop("disabled", true)
								.text(__("Cancelling…"));
						},
					});
				},
			});

			_syncDialog.fields_dict.progress_area.$wrapper.html(`
				<div style="padding: 10px 0 6px;">
					<div class="progress" style="height: 22px; border-radius: 4px; overflow: hidden; margin-bottom: 10px;">
						<div class="sync-bar progress-bar progress-bar-striped active"
							 style="width: 2%; min-width: 2em; transition: width 0.4s ease;
							        line-height: 22px; text-align: center; font-size: 12px;">
							0%
						</div>
					</div>
					<p class="sync-label text-muted small" style="margin: 0;">${__("Connecting to GPS Gate…")}</p>
				</div>
			`);

			_syncDialog.onhide = _closeSyncDialog;
			_syncDialog.show();

			frappe.realtime.on("vehicle_sync_progress", _onProgress);

			frappe.call({
				method: "gps_gate.apis.sync_vehicles.sync_vehicles_from_gps_gate",
				callback: function (r) {
					if (!r.message || r.message.status !== "queued") {
						_closeSyncDialog();
						frappe.show_alert({ message: __("Failed to start sync."), indicator: "red" }, 5);
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
