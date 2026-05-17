# Copyright (c) 2026, Naqeeb Khan
# For license information, please see license.txt

"""
GPS Gate API Client Module
Centralized module for all GPS Gate REST API interactions.
"""

import frappe
import requests
from frappe import _
import time

class GPSGateAPIError(Exception):
    """Custom exception for GPS Gate API errors"""
    def __init__(self, message, status_code=None, response_text=None):
        self.message = message
        self.status_code = status_code
        self.response_text = response_text
        super().__init__(self.message)


class GPSGateClient:
    """
    Client for interacting with GPS Gate REST API.
    
    Usage:
        client = GPSGateClient()
        users = client.get_users()
        new_user = client.create_user(payload)
    """
    
    # def __init__(self):
    #     """Initialize the GPS Gate API client with settings from DocType."""
    #     self.settings = frappe.get_single("GPS Gate Settings")
    #     self._validate_settings()
        
    #     self.base_url = (self.settings.base_url or "").rstrip("/")
    #     self.app_id = self.settings.app_id
    #     self.token = self.settings.token
    #     self.headers = {
    #         "Authorization": self.token,
    #         "Content-Type": "application/json"
    #     }
    def __init__(self):
        """Initialize GPS Gate API client using logged-in user's default company."""

        # Get logged in user
        user = frappe.session.user

        # Get user's default company
        company = frappe.defaults.get_user_default("Company")

        if not company:
            raise GPSGateAPIError(
                _("No default company is set for user {0}").format(user)
            )

        # Fetch company document
        self.settings = frappe.get_doc("Company", company)

        self._validate_settings()

        self.base_url = (self.settings.custom_base_url or "").rstrip("/")
        self.app_id = self.settings.custom_app_id
        self.token = self.settings.custom_token

        self.headers = {
            "Authorization": self.token,
            "Content-Type": "application/json"
        }
        
    def _validate_settings(self):
        """Validate that GPS Gate settings are properly configured."""
        if not self.settings.custom_enable:
            raise GPSGateAPIError(_("GPS Gate integration is disabled. Please enable it in GPS Gate Settings inside Company doctype."))
        
        if not self.settings.custom_base_url:
            raise GPSGateAPIError(_("GPS Gate Base URL is not configured."))
        
        if not self.settings.custom_app_id:
            raise GPSGateAPIError(_("GPS Gate App ID is not configured."))
        
        if not self.settings.custom_token:
            raise GPSGateAPIError(_("GPS Gate Token is not configured."))
    
    def _build_url(self, endpoint):
        """Build the full API URL."""
        return f"{self.base_url}/comGpsGate/api/v.1/applications/{self.app_id}/{endpoint}"
    
    def _make_request(self, method, endpoint, payload=None, timeout=30, return_headers=False):
        """
        Make an HTTP request to the GPS Gate API.
        
        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint (e.g., 'users', 'users/123')
            payload: Request body for POST/PUT requests
            timeout: Request timeout in seconds
            return_headers: If True, return tuple of (data, headers)
            
        Returns:
            Response data as dict/list or None for DELETE
            If return_headers is True, returns tuple (data, headers)
            
        Raises:
            GPSGateAPIError: If the API request fails
        """
        url = self._build_url(endpoint)
        
        try:
            if method.upper() == "GET":
                response = requests.get(url, headers=self.headers, timeout=timeout)
            elif method.upper() == "POST":
                response = requests.post(url, json=payload, headers=self.headers, timeout=timeout)
            elif method.upper() == "PUT":
                response = requests.put(url, json=payload, headers=self.headers, timeout=timeout)
            elif method.upper() == "DELETE":
                response = requests.delete(url, headers=self.headers, timeout=timeout)
            else:
                raise GPSGateAPIError(f"Unsupported HTTP method: {method}")
            
            # Check for HTTP errors
            if response.status_code >= 400:
                error_message = self._parse_error_response(response)
                self._log_api_error(method, url, payload, response)
                raise GPSGateAPIError(
                    message=error_message,
                    status_code=response.status_code,
                    response_text=response.text
                )
            
            # Return response data
            if method.upper() == "DELETE":
                return None
            
            data = None
            if response.text:
                data = response.json()
            
            if return_headers:
                return data, response.headers
            return data
            
        except requests.exceptions.Timeout:
            error_msg = _("GPS Gate API request timed out")
            self._log_api_error(method, url, payload, error_msg=error_msg)
            raise GPSGateAPIError(error_msg)
            
        except requests.exceptions.ConnectionError:
            error_msg = _("Failed to connect to GPS Gate API. Please check the Base URL and network connectivity.")
            self._log_api_error(method, url, payload, error_msg=error_msg)
            raise GPSGateAPIError(error_msg)
            
        except requests.exceptions.RequestException as e:
            error_msg = _("GPS Gate API request failed: {0}").format(str(e))
            self._log_api_error(method, url, payload, error_msg=error_msg)
            raise GPSGateAPIError(error_msg)
    
    def _parse_error_response(self, response):
        """Parse error response from GPS Gate API."""
        try:
            error_data = response.json()
            if isinstance(error_data, dict):
                # Common error response formats
                message = error_data.get("message") or error_data.get("Message") or error_data.get("error")
                if message:
                    return _("GPS Gate API Error ({0}): {1}").format(response.status_code, message)
        except Exception:
            pass
        
        # Fallback to raw response
        return _("GPS Gate API Error ({0}): {1}").format(response.status_code, response.text[:500])
    
    def _log_api_error(self, method, url, payload=None, response=None, error_msg=None):
        """Log API errors to ERPNext Error Log."""
        error_details = f"""
            GPS Gate API Error
            ==================
            Method: {method}
            URL: {url}
            Payload: {frappe.as_json(payload) if payload else 'None'}
            """
        if response:
            error_details += f"""
            Status Code: {response.status_code}
            Response: {response.text[:2000]}
            """
        if error_msg:
            error_details += f"""
            Error: {error_msg}
            """
        frappe.log_error(
            title="GPS Gate API Error",
            message=error_details
        )
    
    # ========== USER API METHODS ==========
    import time
    def get_users(self, page_size=1000):
        all_users = []
        from_index = 0
        batch_num = 1
        
        while True:
            try:
                print(f"Fetching batch {batch_num}, from_index={from_index}, total so far={len(all_users)}")
                
                endpoint = f"users?take={page_size}&FromIndex={from_index}"
                data = self._make_request("GET", endpoint)
                
                # None check
                if data is None:
                    print("API returned None, stopping.")
                    break
                    
                # Empty list check    
                if len(data) == 0:
                    print("Empty response, all users fetched.")
                    break
                
                all_users.extend(data)
                print(f"Batch {batch_num} fetched: {len(data)} users")
                
                # Last page check
                if len(data) < page_size:
                    print("Last batch received, pagination complete.")
                    break
                
                # Last user ID
                last_user = data[-1]
                last_user_id = last_user.get("id")
                
                if not last_user_id:
                    print("No ID found in last user, stopping.")
                    break
                
                # Infinite loop protection
                if last_user_id == from_index:
                    print("from_index same as before, stopping to avoid infinite loop.")
                    break
                
                from_index = last_user_id
                batch_num += 1
                
                # Server pe load kam karne k liye small delay
                time.sleep(0.5)
                
            except Exception as e:
                print(f"Error in batch {batch_num}: {str(e)}")
                break
        
        print(f"Total users fetched: {len(all_users)}")
        return all_users

    # def get_users(self, page_size=1000):
    #     """
    #     Get all users from GPS Gate with pagination support.
    #     By default, the API returns max 1000 records per request.
    #     This method fetches all pages automatically.
        
    #     Args:
    #         page_size: Number of records per page (max 1000)
            
    #     Returns:
    #         list: List of all user dictionaries from all pages
    #     """
    #     import json
        
    #     all_users = []
    #     page = 1
        
    #     while True:
    #         endpoint = f"users?PageSize={page_size}&Page={page}"
    #         data, headers = self._make_request("GET", endpoint, return_headers=True)
            
    #         if data:
    #             all_users.extend(data)
            
    #         # Check x-pagination header for next page info
    #         pagination_header = headers.get('x-pagination') or headers.get('X-Pagination')
            
    #         if not pagination_header:
    #             break
            
    #         try:
    #             pagination_info = json.loads(pagination_header)
    #             has_next = pagination_info.get('HasNextPage', False) or pagination_info.get('hasNextPage', False)
                
    #             if not has_next:
    #                 break
                    
    #             page += 1
    #         except (json.JSONDecodeError, TypeError):
    #             # If we can't parse pagination info, stop
    #             break
        
    #     return all_users
    
    def get_user(self, user_id):
        """
        Get a specific user by ID.
        
        Args:
            user_id: GPS Gate user ID
            
        Returns:
            dict: User data
        """
        return self._make_request("GET", f"users/{user_id}")
    
    def create_user(self, payload):
        """
        Create a new user in GPS Gate.
        
        Args:
            payload: User data dictionary containing:
                - username (required): Unique username
                - password (required): User password
                - name (required): First name
                - userTypeId (required): User type ID
                - surname: Last name
                - email: Email address
                - phoneNumber: Phone number
                - driverID: Driver ID
                - description: Description
                - devices: List of device objects
                
        Returns:
            dict: Created user data including the assigned ID
        """
        return self._make_request("POST", "users", payload)
    
    def update_user(self, user_id, payload):
        """
        Update an existing user in GPS Gate.
        
        Args:
            user_id: GPS Gate user ID
            payload: User data dictionary (same fields as create_user)
            
        Returns:
            dict: Updated user data
        """
        return self._make_request("PUT", f"users/{user_id}", payload)
    
    def delete_user(self, gps_gate_id):
        """
        Delete a user from GPS Gate.
        
        Args:
            user_id: GPS Gate user ID
            
        Returns:
            None
        """
        return self._make_request("DELETE", f"users/{gps_gate_id}")
    
    # ========== USER TYPE API METHODS ==========
    
    def get_user_types(self):
        """
        Get all user types from GPS Gate.
        
        Returns:
            list: List of user type dictionaries
        """
        return self._make_request("GET", "usertypes")
    
    # ========== EVENT RULES API METHODS ==========
    
    def get_event_rules(self):
        """
        Get all event rules from GPS Gate.
        
        Returns:
            list: List of event rule dictionaries containing:
                - id: Event rule ID
                - name: Event rule name
                - description: Description
                - enabled: Whether the rule is enabled
        """
        return self._make_request("GET", "eventrules")
    
    def get_event_rule(self, event_rule_id):
        """
        Get a specific event rule by ID.
        
        Args:
            event_rule_id: GPS Gate event rule ID
            
        Returns:
            dict: Event rule data
        """
        return self._make_request("GET", f"eventrules/{event_rule_id}")
    
    # ========== EVENTS API METHODS ==========
    
    def get_events(self, date, user_id=None, event_rule_id=None):
        """
        Get events from GPS Gate for a specific date.
        
        Args:
            date: Date in YYYY-MM-DD format (e.g., '2025-11-20')
            user_id: Optional - Filter by GPS Gate user ID
            event_rule_id: Optional - Filter by event rule ID
            
        Returns:
            list: List of event dictionaries containing:
                - id: Event ID
                - eventRuleId: Related event rule ID
                - eventRuleName: Event rule name
                - userId: User ID
                - time: Event timestamp
                - position: Location data (latitude, longitude, altitude)
                - speed: Speed at time of event
                - heading: Direction/heading
                - message: Event message
        """
        # Build query parameters - API accepts single date parameter in YYYY-MM-DD format
        params = []
        params.append(f"date={date}")
        
        if user_id:
            params.append(f"UserId={user_id}")
        
        if event_rule_id:
            params.append(f"RuleId={event_rule_id}")
        
        query_string = "&".join(params)
        endpoint = f"events?{query_string}"
        
        return self._make_request("GET", endpoint)
    
    def get_event(self, event_id):
        """
        Get a specific event by ID.
        
        Args:
            event_id: GPS Gate event ID
            
        Returns:
            dict: Event data
        """
        return self._make_request("GET", f"events/{event_id}")
    
    # ========== GROUPS API METHODS ==========
    
    def get_groups(self):
        """
        Get all groups from GPS Gate.
        
        Returns:
            list: List of group dictionaries containing:
                - id: Group ID
                - name: Group name
                - description: Description
                - parentId: Parent group ID (if hierarchical)
        """
        return self._make_request("GET", "groups")
    
    def get_group(self, group_id):
        """
        Get a specific group by ID.
        
        Args:
            group_id: GPS Gate group ID
            
        Returns:
            dict: Group data
        """
        return self._make_request("GET", f"groups/{group_id}")
    
    def create_group(self, payload):
        """
        Create a new group in GPS Gate.
        
        Args:
            payload: Group data dictionary containing:
                - name (required): Group name
                - description: Group description
                - parentId: Parent group ID (optional, for hierarchical groups)
                
        Returns:
            dict: Created group data including the assigned ID
        """
        return self._make_request("POST", "groups", payload)
    
    def update_group(self, group_id, payload):
        """
        Update an existing group in GPS Gate.
        
        Args:
            group_id: GPS Gate group ID
            payload: Group data dictionary (same fields as create_group)
            
        Returns:
            dict: Updated group data
        """
        return self._make_request("PUT", f"groups/{group_id}", payload)
    
    def delete_group(self, group_id):
        """
        Delete a group from GPS Gate.
        
        Args:
            group_id: GPS Gate group ID
            
        Returns:
            None
        """
        return self._make_request("DELETE", f"groups/{group_id}")
    
    # ========== GROUP MEMBERS API METHODS ==========
    
    def get_group_users(self, group_id):
        """
        Get all users/assets within a group.
        
        Args:
            group_id: GPS Gate group ID
            
        Returns:
            list: List of user dictionaries in the group
        """
        return self._make_request("GET", f"groups/{group_id}/users")
    
    def add_user_to_group(self, group_id, user_id):
        """
        Add a user/asset to a group.
        
        Args:
            group_id: GPS Gate group ID
            user_id: GPS Gate user ID to add
            
        Returns:
            dict: Response data
        """
        return self._make_request("POST", f"groups/{group_id}/users", {"userId": user_id})
    
    def remove_user_from_group(self, group_id, user_id):
        """
        Remove a user/asset from a group.

        Args:
            group_id: GPS Gate group ID
            user_id: GPS Gate user ID to remove

        Returns:
            None
        """
        return self._make_request("DELETE", f"groups/{group_id}/users/{user_id}")

    # ========== VEHICLE STATUS & TRACKING API METHODS ==========

    def get_users_status(self, from_index=0, page_size=1000, group_id=None,
                         updates_from=None, kind=None, name=None):
        """
        Get the current status of all vehicles/users in the application.

        Endpoint: GET /applications/{applicationid}/usersstatus

        Args:
            from_index: Paging start index (default 0)
            page_size: Number of records per page (default 1000)
            group_id: Filter by GPS Gate group/tag ID
            updates_from: Only users active after this timestamp (RFC3339, e.g. '2026-05-07T08:00:00Z')
            kind: Filter by user kind, e.g. 'Asset' for vehicles
            name: Case-insensitive name filter

        Returns:
            list: List of UserStatusModel dicts, each containing:
                - id: User ID
                - name: Vehicle/user name
                - position: {latitude, longitude, altitude, speed, heading, valid, timestamp}
                - variables: {speed, ignition, odometer, fuelLevel, satellites, ...}
        """
        params = [f"FromIndex={from_index}", f"PageSize={page_size}"]

        if group_id is not None:
            params.append(f"GroupId={group_id}")
        if updates_from:
            params.append(f"UpdatesFrom={updates_from}")
        if kind:
            params.append(f"Kind={kind}")
        if name:
            params.append(f"Name={name}")

        query_string = "&".join(params)
        return self._make_request("GET", f"usersstatus?{query_string}")

    def get_user_status(self, user_id):
        """
        Get the current status of a single vehicle/user.

        Endpoint: GET /applications/{applicationid}/users/{userid}/status

        Args:
            user_id: GPS Gate user ID

        Returns:
            dict: UserStatusModel containing:
                - id: User ID
                - name: Vehicle/user name
                - position: {latitude, longitude, altitude, speed, heading, valid, timestamp}
                - variables: {speed, ignition, fuelLevel, odometer, ...}
        """
        return self._make_request("GET", f"users/{user_id}/status")

    def get_user_tracks(self, user_id, date, from_time=None, until_time=None, filtered=None):
        """
        Get GPS track points for a specific vehicle/user for a given date.

        Endpoint: GET /applications/{applicationid}/users/{userid}/tracks

        Args:
            user_id: GPS Gate user ID
            date: Local date string (e.g. '2026-05-07')
            from_time: Start time string (e.g. '00:00:00'). Default: 00:00:00
            until_time: End time string (e.g. '23:59:59'). Default: 23:59:59
            filtered: Boolean — use filtered track reader (default True on server)

        Returns:
            list: List of TrackModel dicts, each containing:
                - timestamp: Track point datetime (UTC)
                - latitude, longitude, altitude: Position
                - speed: Speed at this point
                - heading: Direction/heading
                - valid: Whether the GPS fix is valid
                - variables: {ignition, fuelLevel, ...}
        """
        params = [f"Date={date}"]

        if from_time:
            params.append(f"From={from_time}")
        if until_time:
            params.append(f"Until={until_time}")
        if filtered is not None:
            params.append(f"Filtered={'true' if filtered else 'false'}")

        query_string = "&".join(params)
        return self._make_request("GET", f"users/{user_id}/tracks?{query_string}")

    def get_user_trip_infos(self, user_id, date):
        """
        Get trip summary information for a specific vehicle/user for a given date.

        Endpoint: GET /applications/{applicationid}/users/{userid}/tripinfos

        Args:
            user_id: GPS Gate user ID
            date: Local date string (e.g. '2026-05-07')

        Returns:
            list: List of TripInfoModel dicts, each containing:
                - id: Trip ID
                - startTime, endTime: Trip start/end timestamps (UTC)
                - distance: Total distance in km (or meters — check your server config)
                - duration: Total trip duration in seconds
                - maxSpeed: Maximum speed during the trip
                - averageSpeed: Average speed during the trip
                - startPosition: {latitude, longitude}
                - endPosition: {latitude, longitude}
        """
        return self._make_request("GET", f"users/{user_id}/tripinfos?Date={date}")

    def get_user_accumulators(self, user_id):
        """
        Get accumulator values for a specific user/vehicle.

        Endpoint: GET /applications/{applicationid}/users/{userid}/accumulators

        Args:
            user_id: GPS Gate user ID

        Returns:
            list: List of accumulator dicts, each typically containing:
                - name: Accumulator name (e.g. 'odometer', 'engineHours')
                - value: Current accumulator value
                - unit: Unit of measurement
        """
        return self._make_request("GET", f"users/{user_id}/accumulators")

    def get_user_custom_fields(self, user_id):
        """
        Get custom field values for a specific user/vehicle.

        Endpoint: GET /applications/{applicationid}/users/{userid}/customfields

        Args:
            user_id: GPS Gate user ID (int)

        Returns:
            list: List of custom field dicts, each typically containing:
                - fieldId / name: Field identifier
                - value: Field value
        """
        return self._make_request("GET", f"users/{user_id}/customfields")


def get_gps_gate_client():
    """
    Factory function to create a GPS Gate client.
    
    Returns:
        GPSGateClient: Configured API client
        
    Raises:
        frappe.ValidationError: If settings are invalid
    """
    try:
        return GPSGateClient()
    except GPSGateAPIError as e:
        frappe.throw(str(e.message))
