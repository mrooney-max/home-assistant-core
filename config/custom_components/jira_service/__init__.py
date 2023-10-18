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
        data = await get_jira_tickets(username, api_token, baseurl)
        message = ""
        for issue in data["issues"]:
            message += issue["key"] + " - Status: " + issue["fields"]["status"]["name"] + " - " + issue["fields"]["summary"] + "\n"
            ticket_details = await get_jira_ticket_details(username, api_token, baseurl, issue["key"])
            message += format_ticket_details(ticket_details)

        message = message.rstrip() + "\n"

        if data:
            # Process the API response data here
            # Example: set a state or perform other actions based on the data
            # _LOGGER.info("Received data from API: %s", data)
            _LOGGER.info("Identified Jiras: \n%s\n\n", message)

            # hass.states.set("jira_service.jira", json.dumps(data))
            hass.states.async_set("jira_service.jira", "on", {"Summary": message})

        else:
            # Handle API request failure
            _LOGGER.error("Failed to retrieve data from API")

    hass.services.async_register(DOMAIN, "jira", handle_jira)

    # Return boolean to indicate that initialization was successful.
    return True

def format_ticket_details(ticket_details):
    """Format the Jira JSON into readable text."""
    latest_status_change_date = ticket_details["fields"]["statuscategorychangedate"]
    latest_comment = ticket_details["fields"]["comment"]["comments"][-1]
    latest_comment_text = latest_comment["body"]
    latest_comment_author = latest_comment["author"]["displayName"]
    latest_comment_date = latest_comment["updated"]
    formatted_ticket_details = f"Status last changed: {latest_status_change_date}\n" \
        f"Latest comment by {latest_comment_author} on {latest_comment_date}\n" \
        f"Text: {latest_comment_text[:80].strip()}\n\n"
    return formatted_ticket_details

async def get_jira_tickets(username, api_token, baseurl):
    """Make a GET request to the API with Basic Authentication."""

    try:
        async with aiohttp.ClientSession() as session:
            url = (
                baseurl
                + "search?jql=assignee was currentuser() AND updated >= -2d&ORDER BY updated DESC"
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

async def get_jira_ticket_details(username, api_token, baseurl, ticket_key):
    """Make a GET request to the API with Basic Authentication."""

    try:
        async with aiohttp.ClientSession() as session:
            url = baseurl + "issue/" + ticket_key
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
