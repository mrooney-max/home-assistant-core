"""Support for JIRA Integration custom component."""
import logging

import aiohttp

_LOGGER = logging.getLogger(__name__)

DOMAIN = "jira_service"

ATTR_NAME = "name"
DEFAULT_NAME = "World"


async def async_setup(hass, config):
    """Set up is called when Home Assistant is loading our component."""

    async def handle_jira(call):
        """Handle the service call."""
        call.data.get(ATTR_NAME, DEFAULT_NAME)

        # Make the API request with Basic Authentication
        username = config[DOMAIN].get("username")
        api_token = config[DOMAIN].get("api_token")
        baseurl = config[DOMAIN].get("jira_base_url")
        data = await get_data_from_api(username, api_token, baseurl)
        message = ""
        for issue in data["issues"]:
            message += issue["key"] + " - " + issue["fields"]["summary"] + "\n"
        message = message.rstrip()

        if data:
            # Process the API response data here
            # Example: set a state or perform other actions based on the data
            _LOGGER.info("Received data from API: %s", data)
            _LOGGER.info("Identified Jiras: \n%s", message)
            # hass.states.set("jira_service.jira", json.dumps(data))
            hass.states.async_set("jira_service.jira", "on", {"Summary": message})

        else:
            # Handle API request failure
            _LOGGER.error("Failed to retrieve data from API")

    hass.services.async_register(DOMAIN, "jira", handle_jira)

    # Return boolean to indicate that initialization was successful.
    return True


async def get_data_from_api(username, api_token, baseurl):
    """Make a GET request to the API with Basic Authentication."""

    try:
        async with aiohttp.ClientSession() as session:
            url = (
                baseurl
                + "search?jql=assignee was currentuser() AND updated >= -1d&ORDER BY updated DESC"
            )
            auth = aiohttp.BasicAuth(username, api_token)
            async with session.get(url, auth=auth) as response:
                if response.status == 200:
                    data = await response.json()
                    return data
                else:
                    _LOGGER.error(
                        "Failed to retrieve data from API. Status code: %s",
                        response.status,
                    )
                    return None
    except Exception as e:
        _LOGGER.error("Error while making API request: %s", str(e))
        return None
