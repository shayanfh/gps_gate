import frappe


def execute(filters=None):
    return get_columns(), get_data()


def get_columns():
    return [
        {
            "fieldname": "vehicle",
            "label": "Vehicle",
            "fieldtype": "HTML",
            "width": 180,
        },
        {
            "fieldname": "total",
            "label": "Total Due Services",
            "fieldtype": "HTML",
            "width": 140,
        },
        {
            "fieldname": "overdue",
            "label": "Overdue",
            "fieldtype": "HTML",
            "width": 100,
        },
        {
            "fieldname": "due_soon",
            "label": "Due Soon",
            "fieldtype": "HTML",
            "width": 100,
        },
        {
            "fieldname": "services",
            "label": "Services",
            "fieldtype": "Data",
            "width": 350,
        },
    ]


def get_data():
    schedules = frappe.get_all(
        "Vehicle Service Schedule",
        filters={"status": ["in", ["Overdue", "Due Soon"]]},
        fields=["vehicle", "service_type", "status"],
    )

    vehicle_map = {}
    for s in schedules:
        v = s.vehicle
        if v not in vehicle_map:
            vehicle_map[v] = {"overdue": 0, "due_soon": 0, "services": []}
        if s.status == "Overdue":
            vehicle_map[v]["overdue"] += 1
        else:
            vehicle_map[v]["due_soon"] += 1
        if s.service_type and s.service_type not in vehicle_map[v]["services"]:
            vehicle_map[v]["services"].append(s.service_type)

    # Sort: most overdue first, then due_soon
    sorted_vehicles = sorted(
        vehicle_map.items(),
        key=lambda x: (-(x[1]["overdue"]), -(x[1]["due_soon"])),
    )

    rows = []
    for vehicle, info in sorted_vehicles:
        base_url = f"/app/vehicle-service-schedule?vehicle={vehicle}"
        total = info["overdue"] + info["due_soon"]

        rows.append({
            "vehicle": (
                f'<a href="{base_url}" style="font-weight:600">{vehicle}</a>'
            ),
            "total": (
                f'<a href="{base_url}">{total}</a>'
            ),
            "overdue": (
                f'<span style="color:#e03;font-weight:600">'
                f'<a href="{base_url}&status=Overdue" style="color:#e03">{info["overdue"]}</a>'
                f'</span>'
                if info["overdue"]
                else '<span style="color:#888">0</span>'
            ),
            "due_soon": (
                f'<a href="{base_url}&status=Due%20Soon" style="color:#e96600;font-weight:600">'
                f'{info["due_soon"]}</a>'
                if info["due_soon"]
                else '<span style="color:#888">0</span>'
            ),
            "services": ", ".join(info["services"]),
        })

    return rows
