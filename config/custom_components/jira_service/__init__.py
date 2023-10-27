"""Support for JIRA Integration custom component."""
import logging
import re

from homeassistant.const import CONF_API_KEY, CONF_HOST, CONF_USERNAME, Platform
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import discovery

from .const import DATA_CLIENT, DATA_HASS_CONFIG, DOMAIN, JIRA_DATA
from .jira_web_client import jira_web_client

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.NOTIFY, Platform.SENSOR]

ATTR_NAME = "name"
DEFAULT_NAME = "World"


async def async_setup(hass, config):
    """Set up is called when Home Assistant is loading our component."""

    async def handle_jira(call):
        """Handle the service call."""
        call.data.get(ATTR_NAME, DEFAULT_NAME)

        entry = hass.config_entries.async_entries(DOMAIN)[0]
        username = entry.data.get(CONF_USERNAME)
        api_token = entry.data.get(CONF_API_KEY)
        base_url = entry.data.get(CONF_HOST)
        account_ids = config[DOMAIN].get("jira_account_ids")
        comment_length = config[DOMAIN].get("comment_length", 80)

        web_client = jira_web_client(
            api_key=api_token,
            base_url=base_url,
            username=username,
        )

        process_current_user_only = account_ids is None or len(account_ids) == 0

        data = await get_jira_tickets(account_ids, web_client)
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
                    message += "--------------------------------------------\n\n"
                current_account_id = issue["original_account_id"]
                user_data = await web_client.get_user(current_account_id)
                message += f"*{user_data['displayName']}'s tickets:*\n"

            message += (
                f"*<{base_url}/browse/{issue['key']}|{issue['key']}>*"
                + f" - Status: *{issue['fields']['status']['name']}* - {issue['fields']['summary']}\n"
            )
            ticket_details = await web_client.get_ticket_details(issue["key"])

            message += format_ticket_details(
                ticket_details,
                comment_length,
                process_current_user_only,
                username,
                current_account_id,
            )

        message = await convert_comment_account_ids_to_user_names(message, web_client)

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


async def async_setup_entry(hass, entry):
    """Set up a config entry for Jira Service."""
    web_client = jira_web_client(
        api_key=entry.data[CONF_API_KEY],
        base_url=entry.data[CONF_HOST],
        username=entry.data[CONF_USERNAME],
    )

    try:
        await web_client.verify_connection()
    except Exception as ex:
        raise ConfigEntryNotReady("Error while setting up integration") from ex
    data = {
        DATA_CLIENT: web_client,
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
        author = comment["author"]
        created_timestamp = comment["created"]

        author_email = author.get("emailAddress")

        if author_email is not None and author_email == username:
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


async def get_jira_tickets(account_ids, web_client):
    """Make a GET request to the API with Basic Authentication."""

    days_to_look_back = 1

    if account_ids is not None and account_ids.strip() != "":
        account_id_list = [account_id.strip() for account_id in account_ids.split(",")]
        result = {"issues": []}

        for account_id in account_id_list:
            data = await web_client.get_tickets_by_account_id(
                account_id, days_to_look_back
            )
            result["issues"].extend(data)
        return result
    else:
        data = await web_client.get_tickets_by_current_user(days_to_look_back)
        return data


async def convert_comment_account_ids_to_user_names(message, web_client):
    """In the message replace [~accountid:2434432:asdf324-234sdf-4bb6-234asd-234243asfd] with the user's display name."""
    pattern = r"\[~accountid:([^\]]+)\]"

    matching_account_ids = re.findall(pattern, message)

    bulk_user_data = await web_client.get_bulk_users(matching_account_ids)

    for user_data in bulk_user_data["values"]:
        message = message.replace(
            f"[~accountid:{user_data['accountId']}]", user_data["displayName"]
        )

    return message


def sanitize_message(message):
    """Sanitize the message so that it can be pasted to Slack without any problems."""
    message = message.replace("{", "[")
    message = message.replace("}", "]")
    return message
