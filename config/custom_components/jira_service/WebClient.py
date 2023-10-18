"""A Python module for interacting with JIRA's Web API."""
import logging

import aiohttp

_LOGGER = logging.getLogger(__name__)


class WebClient:
    """WebClient provides methods for interacting with JIRA's Web API.

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
        client = WebClient(base_url="https://your-instance.atlassian.net",
                          api_key="your-api-key",
                          username="your-username")

        connection_status = await client.verify_connection()
        if connection_status:
            print("Successfully connected to the JIRA API.")
        else:
            print("Failed to connect to the JIRA API.")

    """

    def __init__(self, base_url, api_key, username):
        """Initialize the WebClient with base URL, API key, and username."""
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
