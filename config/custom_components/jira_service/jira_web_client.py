"""A Python module for interacting with JIRA's Web API."""
import logging

import aiohttp

_LOGGER = logging.getLogger(__name__)


class jira_web_client:
    """jira_web_client provides methods for interacting with JIRA's Web API.

    This class allows you to connect to JIRA's Web API, verify the connection, and perform API requests.

    Args:
        base_url (str): The base URL of the JIRA instance.
        api_key (str): Your JIRA API key.
        username (str): Your JIRA username.

    Methods:
        verify_connection: Verify the connection to the JIRA API.

    Attributes:
        base_url (str): The base URL of the JIRA instance.
        api_key (str): Your JIRA API key.
        username (str): Your JIRA username.

    Example:
        client = jira_web_client(base_url="https://your-instance.atlassian.net",
                          api_key="your-api-key",
                          username="your-username")

        connection_status = await client.verify_connection()
        if connection_status:
            print("Successfully connected to the JIRA API.")
        else:
            print("Failed to connect to the JIRA API.")

    """

    def __init__(self, base_url, api_key, username):
        """Initialize the jira_web_client with base URL, API key, and username."""
        self.base_url = base_url
        self.api_key = api_key
        self.username = username

    async def verify_connection(self):
        """Verify the connection to the JIRA API.

        This method makes a GET request to the JIRA API to verify the connection.
        It uses the provided base URL, API key, and username for authentication.

        Returns:
            bool: True if the connection is successful (status code 200), False otherwise.

        Example:
            connection_status = await verify_connection()
            if connection_status:
                print("Successfully connected to the JIRA API.")
            else:
                print("Failed to connect to the JIRA API.")
        """
        try:
            async with aiohttp.ClientSession() as session:
                # Construct the API URL
                url = f"{self.base_url}/rest/api/2/mypreferences/locale"

                # Set up Basic Authentication with the provided username and API token
                auth = aiohttp.BasicAuth(self.username, self.api_key)

                # Make a GET request to the API
                async with session.get(url, auth=auth) as response:
                    if response.status == 200:
                        # API request was successful (status code 200)
                        return True
                    else:
                        # Handle API request failure
                        _LOGGER.error(
                            "Failed to retrieve data from API. Status code: %s",
                            response.status,
                        )
                        return False
        except Exception as e:
            # Handle exceptions raised during the API request
            _LOGGER.error("Error while making API request: %s", str(e))
            return False

    async def get_user(self, account_id):
        """Retrieve user information based on the provided account ID.

        Args:
            account_id (str): The unique account ID of the user to retrieve.

        Returns:
            dict: A dictionary containing user information, including name and other details.

        Raises:
            Exception: If the API request fails, an exception is raised with an error message.

        This function makes an authenticated API request to retrieve user information from
        the JIRA server based on the provided account ID.

        Example:
            user_data = await get_user('account_id123')
            print(user_data)  # {'name': 'John Doe', 'email': 'john@example.com', ...}
        """
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.base_url}/rest/api/2/user?accountId={account_id}"

                auth = aiohttp.BasicAuth(self.username, self.api_key)

                async with session.get(url, auth=auth) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data
                    else:
                        _LOGGER.error(
                            "Failed to retrieve data from API. Status code: %s",
                            response.status,
                        )
                        raise Exception("Failed to retrieve User data")
        except Exception as e:
            _LOGGER.error("Error while making API request: %s", str(e))

    async def get_bulk_users(self, account_ids):
        """Retrieve user information for multiple account IDs in bulk.

        Args:
            account_ids (List[str]): A list of account IDs to retrieve user information for.

        Returns:
            dict: User information for the specified account IDs.

        Raises:
            Exception: If there was an error while making the API request.

        This function sends a bulk request to retrieve user information for the specified
        account IDs using the Jira REST API. It returns a dictionary containing user data.

        Example:
            account_ids = ["123adskf-23234", "848399dkkd"]
        user_data = await get_bulk_users(account_ids)
        """
        try:
            account_ids_request = ""
            for account_id in account_ids:
                account_ids_request += f"&accountId={account_id}"

            async with aiohttp.ClientSession() as session:
                url = f"{self.base_url}/rest/api/2/user/bulk?{account_ids_request}"

                auth = aiohttp.BasicAuth(self.username, self.api_key)

                async with session.get(url, auth=auth) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data
                    else:
                        _LOGGER.error(
                            "Failed to retrieve Bulk User data from API. Status code: %s",
                            response.status,
                        )
                        raise Exception("Failed to retrieve Bulk User data")
        except Exception as e:
            _LOGGER.error("Error while making Bulk User API request: %s", str(e))

    async def get_tickets_by_account_id(self, account_id, days_to_look_back):
        """Retrieve Jira tickets assigned to a user based on their account ID and a specified time frame.

        Args:
            account_id (str): The account ID of the user for whom to retrieve Jira tickets.
            days_to_look_back (int): The number of days to look back for updated tickets.

        Returns:
            list: A list of Jira ticket objects that match the criteria, each containing an additional 'original_account_id' property
                indicating the user the ticket was retrieved for. An empty list is returned if no matching tickets are found.

        Raises:
            Exception: If an error occurs during the API request.

        Note:
            The 'original_account_id' property is added to each ticket to keep track of the user for whom the ticket was retrieved.
        """
        try:
            async with aiohttp.ClientSession() as session:
                url = (
                    self.base_url
                    + f"/rest/api/2/search?jql=assignee was {account_id} AND updated >= -{days_to_look_back}d&ORDER BY updated DESC"
                )
                auth = aiohttp.BasicAuth(self.username, self.api_key)
                async with session.get(url, auth=auth) as response:
                    if response.status == 200:
                        data = await response.json()
                        # Lets keep track of what the original account_id this is for so we can use this later
                        for issue in data.get("issues", []):
                            issue["original_account_id"] = account_id
                        return data.get("issues", [])
                    else:
                        _LOGGER.error(
                            "Failed to retrieve data from API. Status code: %s",
                            response.status,
                        )
        except Exception as e:
            _LOGGER.error("Error while making API request: %s", str(e))

    async def get_tickets_by_current_user(self, days_to_look_back):
        """Retrieve Jira tickets assigned to the current user within a specified time frame.

        Args:
            days_to_look_back (int): The number of days to look back for updated tickets.

        Returns:
            dict: A dictionary containing Jira ticket data. Returns None if the API request fails.

        Raises:
            Exception: If an error occurs during the API request.

        Note:
            The function fetches Jira tickets assigned to the current user based on the 'currentuser()' JQL query.
        """
        try:
            async with aiohttp.ClientSession() as session:
                url = (
                    self.base_url
                    + f"/rest/api/2/search?jql=assignee was currentuser() AND updated >= -{days_to_look_back}d&ORDER BY updated DESC"
                )
                auth = aiohttp.BasicAuth(self.username, self.api_key)
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

    async def get_ticket_details(self, ticket_key):
        """Fetch detailed information for a specific Jira ticket.

        Args:
            ticket_key (str): The unique identifier (key) of the Jira ticket.

        Returns:
            dict: A dictionary containing detailed information about the Jira ticket.
                Returns None if the API request fails.

        Raises:
            Exception: If an error occurs during the API request.

        Note:
            This function makes a GET request to the Jira API to retrieve detailed information about a specific Jira ticket.
        """
        try:
            async with aiohttp.ClientSession() as session:
                url = self.base_url + "/rest/api/2/issue/" + ticket_key
                auth = aiohttp.BasicAuth(self.username, self.api_key)
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
