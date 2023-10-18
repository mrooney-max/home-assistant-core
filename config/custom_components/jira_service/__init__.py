"""Support for JIRA Integration custom component."""
import logging

import aiohttp

from homeassistant.const import CONF_API_KEY, CONF_HOST, CONF_USERNAME, Platform
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import discovery

from .const import DATA_CLIENT, DATA_HASS_CONFIG, DOMAIN, JIRA_DATA
from .WebClient import WebClient

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.NOTIFY, Platform.SENSOR]

ATTR_NAME = "name"
DEFAULT_NAME = "World"


async def async_setup(hass, config):
    """Set up is called when Home Assistant is loading our component."""

    async def handle_jira(call):
        """Handle the service call."""
        call.data.get(ATTR_NAME, DEFAULT_NAME)

        username = config[DOMAIN].get("username")
        api_token = config[DOMAIN].get("api_token")
        baseurl = config[DOMAIN].get("jira_base_url")
        account_ids = config[DOMAIN].get("jira_account_ids")
        comment_length = config[DOMAIN].get("comment_length", 80)

        webClient = WebClient(
            api_key=api_token,
            base_url=baseurl,
            username=username,
        )

        process_current_user_only = account_ids is None or len(account_ids) == 0

        data = await get_jira_tickets(username, api_token, baseurl, account_ids)
        if process_current_user_only:
            sorted_issues = data["issues"]
        else:
            sorted_issues = sorted_issues = sorted(
                data["issues"], key=lambda x: x["original_account_id"]
            )

        message = ""
        current_account_id = ""
        for issue in sorted_issues:
            if (
                not process_current_user_only
                and current_account_id != issue["original_account_id"]
            ):
                if current_account_id != "":
                    message += "\n"
                current_account_id = issue["original_account_id"]
                user_data = await webClient.get_user(current_account_id)
                message += f"*{user_data['displayName']}'s tickets:*\n"

            message += (
                f"*<{baseurl}/browse/{issue['key']}|{issue['key']}>*"
                + f" - Status: *{issue['fields']['status']['name']}* - {issue['fields']['summary']}\n"
            )
            ticket_details = await get_jira_ticket_details(
                username, api_token, baseurl, issue["key"]
            )

            message += format_ticket_details(
                ticket_details,
                comment_length,
                process_current_user_only,
                username,
                current_account_id,
            )

        message = sanitize_message(message)
        message = message.rstrip() + "\n"

        if data:
            _LOGGER.info("Identified Jiras: \n%s\n\n", message)

            hass.states.async_set("jira_service.jira", "on", {"Summary": message})

        else:
            _LOGGER.error("Failed to retrieve data from API")

    hass.services.async_register(DOMAIN, "jira", handle_jira)
    hass.data[DATA_HASS_CONFIG] = config

    # Return boolean to indicate that initialization was successful.
    return True


def sanitize_message(message):
    """Sanitize the message so that it can be pasted to Slack without any problems."""
    message = message.replace("{", "[")
    message = message.replace("}", "]")
    return message


async def async_setup_entry(hass, entry):
    """Set up a config entry for Jira Service."""
    webClient = WebClient(
        api_key=entry.data[CONF_API_KEY],
        base_url=entry.data[CONF_HOST],
        username=entry.data[CONF_USERNAME],
    )

    try:
        await webClient.verify_connection()
    except Exception as ex:
        raise ConfigEntryNotReady("Error while setting up integration") from ex
    data = {
        DATA_CLIENT: webClient,
    }
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = entry.data | {JIRA_DATA: data}

    hass.async_create_task(
        discovery.async_load_platform(
            hass,
            Platform.NOTIFY,
            DOMAIN,
            hass.data[DOMAIN][entry.entry_id],
            hass.data[DATA_HASS_CONFIG],
        )
    )

    await hass.config_entries.async_forward_entry_setups(
        entry, [platform for platform in PLATFORMS if platform != Platform.NOTIFY]
    )

    return True


def format_ticket_details(
    ticket_details, comment_length, process_current_user_only, username, account_id
):
    """Format the Jira JSON into readable text."""
    latest_status_change_date = ticket_details["fields"]["statuscategorychangedate"]
    if process_current_user_only:
        latest_comment = get_latest_comment_from_current_user(ticket_details, username)
    else:
        latest_comment = get_latest_comment_from_current_account_id(
            ticket_details, account_id
        )
        latest_comment = ticket_details["fields"]["comment"]["comments"][-1]
    if latest_comment is None:
        return "N/A\n"
    latest_comment_text = latest_comment["body"]
    latest_comment_author = latest_comment["author"]["displayName"]
    latest_comment_date = latest_comment["updated"]
    formatted_ticket_details = (
        f"Status last changed: {format_date(latest_status_change_date)}\n"
        f"Latest comment by {latest_comment_author} on {format_date(latest_comment_date)}\n"
        f"Text: {latest_comment_text[:comment_length].strip()}\n\n"
    )
    return formatted_ticket_details


def get_latest_comment_from_current_user(ticket_details, username):
    """Get the latest comment for the current user. We don't care about comments from other users."""
    latest_comment = None
    latest_timestamp = None

    for comment in ticket_details["fields"]["comment"]["comments"]:
        author_email = comment["author"]["emailAddress"]
        created_timestamp = comment["created"]

        if author_email == username:
            if latest_timestamp is None or created_timestamp > latest_timestamp:
                latest_comment = comment
                latest_timestamp = created_timestamp

    return latest_comment


def get_latest_comment_from_current_account_id(ticket_details, account_id):
    """Get the latest comment for the current user. We don't care about comments from other users."""
    latest_comment = None
    latest_timestamp = None

    for comment in ticket_details["fields"]["comment"]["comments"]:
        author_account_id = comment["author"]["accountId"]
        created_timestamp = comment["created"]

        if author_account_id == account_id:
            if latest_timestamp is None or created_timestamp > latest_timestamp:
                latest_comment = comment
                latest_timestamp = created_timestamp

    return latest_comment


def format_date(date):
    """Format the datetime into MM/DD/YYYY HH:MM format."""
    hour = int(date[11:13])
    ampm = "AM"
    if hour >= 12:
        ampm = "PM"
    if hour > 12:
        hour -= 12
    elif hour < 1:
        hour = 12
    minute = date[14:16]

    formatted_date = f"{date[5:7]}/{date[8:10]}/{date[0:4]} {hour}:{minute} {ampm}"
    return formatted_date


async def get_jira_tickets(username, api_token, baseurl, account_ids):
    """Make a GET request to the API with Basic Authentication."""

    daysToLookBack = 2

    if account_ids is not None and account_ids.strip() != "":
        account_id_list = [account_id.strip() for account_id in account_ids.split(",")]
        result = {"issues": []}

        for account_id in account_id_list:
            try:
                async with aiohttp.ClientSession() as session:
                    url = (
                        baseurl
                        + f"/rest/api/2/search?jql=assignee was {account_id} AND updated >= -{daysToLookBack}d&ORDER BY updated DESC"
                    )
                    auth = aiohttp.BasicAuth(username, api_token)
                    async with session.get(url, auth=auth) as response:
                        if response.status == 200:
                            data = await response.json()
                            # Let us keep track of what the original account_id this is for so we can use this later
                            for issue in data.get("issues", []):
                                issue["original_account_id"] = account_id
                            result["issues"].extend(data.get("issues", []))
                        else:
                            _LOGGER.error(
                                "Failed to retrieve data from API. Status code: %s",
                                response.status,
                            )
            except Exception as e:
                _LOGGER.error("Error while making API request: %s", str(e))

        return result
    else:
        try:
            async with aiohttp.ClientSession() as session:
                url = (
                    baseurl
                    + f"/rest/api/2/search?jql=assignee was currentuser() AND updated >= -{daysToLookBack}d&ORDER BY updated DESC"
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
            url = baseurl + "/rest/api/2/issue/" + ticket_key
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


async def verify_connection(username, api_token, baseurl):
    """Make a GET request to the API with Basic Authentication."""

    try:
        async with aiohttp.ClientSession() as session:
            url = baseurl + "/rest/api/2/mypreferences/locale"
            auth = aiohttp.BasicAuth(username, api_token)
            async with session.get(url, auth=auth) as response:
                if response.status == 200:
                    return True
                else:
                    _LOGGER.error(
                        "Failed to retrieve data from API. Status code: %s",
                        response.status,
                    )
                    return False
    except Exception as e:
        _LOGGER.error("Error while making API request: %s", str(e))
        return False
