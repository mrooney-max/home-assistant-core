"""Support for JIRA Integration custom component."""
import logging

import requests

_LOGGER = logging.getLogger(__name__)

DOMAIN = "hello_service"

ATTR_NAME = "name"
DEFAULT_NAME = "World"


def setup(hass, config):
    """Set up is called when Home Assistant is loading our component."""

    def handle_hello(call):
        """Handle the service call."""
        call.data.get(ATTR_NAME, DEFAULT_NAME)

        # Make the API request with Basic Authentication
        username = config[DOMAIN].get("username")
        api_token = config[DOMAIN].get("api_token")
        baseurl = config[DOMAIN].get("jira_base_url")
        data = get_data_from_api(username, api_token, baseurl)
        message = ""
        for issue in data["issues"]:
            message += issue["key"] +" - " + issue["fields"]["summary"] + "\n"
        message = message.rstrip()
        if data:
            # Process the API response data here
            # Example: set a state or perform other actions based on the data
            _LOGGER.info("Received data from API: %s", data)
            _LOGGER.info("Identified Jiras: \n%s", message)
            # hass.states.set("hello_service.hello", json.dumps(data))
            # await hass.states.async_set(
            #     "hello_service.hello", "on", {"my_attribute": json.dumps(data)}
            # )

        else:
            # Handle API request failure
            _LOGGER.error("Failed to retrieve data from API")

    hass.services.register(DOMAIN, "hello", handle_hello)

    # Return boolean to indicate that initialization was successful.
    return True


def get_data_from_api(username, api_token, baseurl):
    """Make a GET request to the API with Basic Authentication."""

    try:
        response = requests.get(
            baseurl
            + "search?jql=assignee was currentuser() AND updated >= -1d&ORDER BY updated DESC",
            auth=(username, api_token),
        )

        if response.status_code == 200:
            # API request was successful, process the response
            data = response.json()  # Assuming the response is in JSON format
            return data
        else:
            _LOGGER.error(
                "Failed to retrieve data from API. Status code: %s",
                response.status_code,
            )
            return None

    except Exception as e:
        _LOGGER.error("Error while making API request: %s", str(e))
        return None
