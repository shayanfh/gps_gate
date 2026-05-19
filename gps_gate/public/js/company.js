frappe.ui.form.on("Company", {
	refresh(frm) {
		if (frm.is_new()) {
			return;
		}

		frm.add_custom_button(__("Test GPS Gate Token"), function () {
			if (!frm.doc.custom_enable) {
				frappe.msgprint({
					title: __("GPS Gate Disabled"),
					message: __("Please enable GPS Gate integration first."),
					indicator: "orange"
				});
				return;
			}

			if (!frm.doc.custom_base_url || !frm.doc.custom_app_id || !frm.doc.custom_token) {
				frappe.msgprint({
					title: __("Missing GPS Gate Settings"),
					message: __("Please fill Base URL, App ID, and Token before testing."),
					indicator: "orange"
				});
				return;
			}

			frappe.call({
				method: "gps_gate.apis.company.test_gps_gate_token",
				args: {
					company: frm.doc.name
				},
				freeze: true,
				freeze_message: __("Testing GPS Gate token..."),
				callback: function (r) {
					const result = r.message;

					if (!result) {
						frappe.msgprint({
							title: __("No Response"),
							message: __("No response received from server."),
							indicator: "red"
						});
						return;
					}

					if (result.ok) {
						frappe.msgprint({
							title: __("GPS Gate Token Valid"),
							message: `
								<b>${frappe.utils.escape_html(result.message)}</b><br>
								Status Code: ${result.status_code}
							`,
							indicator: "green"
						});
						return;
					}

					let message = `<b>${frappe.utils.escape_html(result.message)}</b><br>`;

					if (result.status_code) {
						message += `Status Code: ${result.status_code}<br>`;
					}

					if (result.response) {
						message += `
							<br>
							<pre style="white-space: pre-wrap;">${frappe.utils.escape_html(result.response)}</pre>
						`;
					}

					frappe.msgprint({
						title: __("GPS Gate Token Test Failed"),
						message: message,
						indicator: "red"
					});
				},
				error: function () {
					frappe.msgprint({
						title: __("Error"),
						message: __("Failed to test GPS Gate token. Check Error Log."),
						indicator: "red"
					});
				}
			});
		}, __("GPS Gate"));
	}
});