import frappe
import requests
from frappe import _
import logging 

log = frappe.logger("company_log", allow_site=True, file_count=5)
log.setLevel(logging.DEBUG)

@frappe.whitelist()
def test_gps_gate_token(company: str):
	"""
	Test GPS Gate token from Company custom fields.
	"""

	if not company:
		frappe.throw(_("Company is required."))

	if not frappe.has_permission("Company", "read", company):
		frappe.throw(_("You do not have permission to read this Company."))

	company_doc = frappe.get_doc("Company", company)

	if not company_doc.get("custom_enable"):
		frappe.throw(_("GPS Gate integration is disabled for this Company."))

	base_url = (company_doc.get("custom_base_url") or "").strip().rstrip("/")
	app_id = (company_doc.get("custom_app_id") or "").strip()

	token = (company_doc.get_password("custom_token") or "").strip()
	log.debug(f"token is : {token}")

	if not base_url:
		frappe.throw(_("GPS Gate Base URL is missing."))

	if not app_id:
		frappe.throw(_("GPS Gate App ID is missing."))

	if not token:
		frappe.throw(_("GPS Gate Token is missing."))

	url = f"{base_url}/comGpsGate/api/v.1/applications/{app_id}/users?take=1&FromIndex=0"

	headers = {
		"Authorization": token,
		"Content-Type": "application/json",
	}

	try:
		response = requests.get(url, headers=headers, timeout=15)

		if response.status_code == 200:
			return {
				"ok": True,
				"status_code": response.status_code,
				"message": "GPS Gate token is valid.",
			}

		if response.status_code == 401:
			return {
				"ok": False,
				"status_code": response.status_code,
				"message": "Unauthorized. Token is invalid or expired.",
				"response": response.text[:500],
			}

		if response.status_code == 403:
			return {
				"ok": False,
				"status_code": response.status_code,
				"message": "Forbidden. Token works, but does not have enough permission.",
				"response": response.text[:500],
			}

		if response.status_code == 404:
			return {
				"ok": False,
				"status_code": response.status_code,
				"message": "Not found. Base URL or App ID may be wrong.",
				"response": response.text[:500],
			}

		return {
			"ok": False,
			"status_code": response.status_code,
			"message": "GPS Gate token test failed.",
			"response": response.text[:500],
		}

	except requests.exceptions.Timeout:
		return {
			"ok": False,
			"status_code": None,
			"message": "Request timed out. GPS Gate server did not respond.",
		}

	except requests.exceptions.ConnectionError:
		return {
			"ok": False,
			"status_code": None,
			"message": "Connection error. Check Base URL or server network.",
		}

	except Exception:
		frappe.log_error(
			title="GPS Gate Token Test Error",
			message=frappe.get_traceback(),
		)

		return {
			"ok": False,
			"status_code": None,
			"message": "Unexpected error. Check Error Log.",
		}