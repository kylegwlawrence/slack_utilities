"""Slack utilities for handling file operations and channel interactions.

This module provides functions for interacting with Slack channels through the Slack SDK,
including functionality for polling channels for files, downloading files, uploading files,
managing file deletions, and sending messages.

All functions support optional parameters for channel_id and tokens, falling back to
environment variables loaded from .env file.

Public Functions:
    Authentication:
        test_bot_auth() - Test bot token authentication
        test_user_auth() - Test user token authentication

    File Operations:
        poll_channel() - Check if exactly one file exists in channel
        get_file_info() - Retrieve file metadata from channel
        download_file() - Download file from channel to local filesystem
        upload_file() - Upload file to channel
        delete_file() - Delete file from channel

    Messaging:
        send_message() - Send text message to channel
"""

from dotenv import load_dotenv
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from src.custom_logger import get_custom_logger
import requests
import os

__all__ = [
    'test_bot_auth',
    'test_user_auth',
    'poll_channel',
    'get_file_info',
    'download_file',
    'upload_file',
    'delete_file',
    'send_message',
    'get_config',
]

# ============================================================================
# CONFIGURATION
# ============================================================================

_config_cache = None


def _load_config(env_file: str = ".env") -> dict:
    """Load and cache configuration from environment variables.

    Args:
        env_file (str): Path to .env file, defaults to ".env"

    Returns:
        dict: Configuration dictionary with keys: channel_id, bot_token, user_token
    """
    global _config_cache
    if _config_cache is None:
        load_dotenv(env_file)
        _config_cache = {
            'channel_id': os.getenv("CHANNEL_ID"),
            'bot_token': os.getenv("BOT_TOKEN"),
            'user_token': os.getenv("USER_TOKEN")
        }
    return _config_cache


def get_config(env_file: str = ".env", force_reload: bool = False) -> dict:
    """Get Slack configuration from environment.

    Args:
        env_file (str): Path to .env file, defaults to ".env"
        force_reload (bool): Force reload from file (useful for testing), defaults to False

    Returns:
        dict: Configuration dictionary with keys: channel_id, bot_token, user_token

    Examples:
        >>> config = get_config()
        >>> print(config['channel_id'])
    """
    global _config_cache
    if force_reload:
        _config_cache = None
    return _load_config(env_file)


# ============================================================================
# HELPER FUNCTIONS (Private)
# ============================================================================

_logger = None


def _get_logger():
    """Get or create module logger.

    Returns:
        logging.Logger: Configured logger instance
    """
    global _logger
    if _logger is None:
        _logger = get_custom_logger(__name__)
    return _logger


def _create_bot_client(bot_token: str = None) -> WebClient:
    """Create authenticated bot WebClient.

    Args:
        bot_token (str): Bot token, defaults to BOT_TOKEN from environment

    Returns:
        WebClient: Authenticated WebClient instance

    Raises:
        ValueError: If bot_token not provided and not in environment
    """
    if bot_token is None:
        config = get_config()
        bot_token = config['bot_token']
    if bot_token is None:
        raise ValueError("bot_token not provided and BOT_TOKEN not in environment")
    return WebClient(bot_token)


def _create_user_client(user_token: str = None) -> WebClient:
    """Create authenticated user WebClient.

    Args:
        user_token (str): User token, defaults to USER_TOKEN from environment

    Returns:
        WebClient: Authenticated WebClient instance

    Raises:
        ValueError: If user_token not provided and not in environment
    """
    if user_token is None:
        config = get_config()
        user_token = config['user_token']
    if user_token is None:
        raise ValueError("user_token not provided and USER_TOKEN not in environment")
    return WebClient(user_token)


# ============================================================================
# AUTHENTICATION
# ============================================================================


def test_bot_auth(bot_token: str = None) -> dict:
    """Test bot token authentication with Slack API.

    Validates the bot token by calling auth.test endpoint.

    Args:
        bot_token (str): Bot token, defaults to BOT_TOKEN from environment

    Returns:
        dict: Authentication response with keys: ok, url, team, user, team_id, user_id

    Raises:
        SlackApiError: If authentication fails
        ValueError: If bot_token not provided and not in environment

    Examples:
        >>> result = test_bot_auth()
        >>> print(result['user_id'])
    """
    logger = _get_logger()
    try:
        logger.info("Testing Slack BOT token")
        client = _create_bot_client(bot_token)
        auth_test = client.auth_test()
        logger.info("BOT Authentication successful")
        return auth_test
    except SlackApiError as e:
        logger.exception(f"Slack API error during bot authentication")
        raise
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        raise


def test_user_auth(user_token: str = None) -> dict:
    """Test user token authentication with Slack API.

    Validates the user token by calling auth.test endpoint.

    Args:
        user_token (str): User token, defaults to USER_TOKEN from environment

    Returns:
        dict: Authentication response with keys: ok, url, team, user, team_id, user_id

    Raises:
        SlackApiError: If authentication fails
        ValueError: If user_token not provided and not in environment

    Examples:
        >>> result = test_user_auth()
        >>> print(result['user_id'])
    """
    logger = _get_logger()
    try:
        logger.info("Testing Slack USER token")
        client = _create_user_client(user_token)
        auth_test = client.auth_test()
        logger.info("USER Authentication successful")
        return auth_test
    except SlackApiError as e:
        logger.exception(f"Slack API error during user authentication")
        raise
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        raise


# ============================================================================
# FILE OPERATIONS
# ============================================================================


def poll_channel(channel_id: str = None, bot_token: str = None) -> bool:
    """Check if exactly one file exists in the Slack channel.

    Polls the Slack channel's files and validates that there is exactly one file
    present. This enforces the constraint that only one file can exist in the
    channel at a time.

    Args:
        channel_id (str): Slack channel ID, defaults to CHANNEL_ID from environment
        bot_token (str): Bot token, defaults to BOT_TOKEN from environment

    Returns:
        bool: True if exactly one file exists, False if no files exist

    Raises:
        ValueError: If more than one file exists in the channel
        SlackApiError: If the Slack API call fails

    Examples:
        >>> if poll_channel():
        ...     print("File ready for processing")
    """
    logger = _get_logger()
    config = get_config()

    channel_id = channel_id or config['channel_id']
    bot_token = bot_token or config['bot_token']

    if channel_id is None:
        raise ValueError("channel_id not provided and CHANNEL_ID not in environment")

    try:
        client = _create_bot_client(bot_token)
        response = client.files_list(channel=channel_id)
        file_count = len(response["files"])

        if file_count == 1:
            logger.info("Poll successful. Found one file in Slack channel.")
            return True
        elif file_count == 0:
            logger.info("Poll successful. No files in Slack channel")
            return False
        else:
            error_message = (
                f"During polling, found {file_count} files in the channel. "
                "There can only be max one file in the channel. "
                "Manually delete the unnecessary files in the channel."
            )
            logger.error(error_message)
            raise ValueError(error_message)
    except SlackApiError as e:
        logger.exception(f"Slack API error during polling")
        raise


def get_file_info(channel_id: str = None, bot_token: str = None) -> dict | None:
    """Retrieve file information from the Slack channel.

    Gets metadata for the file in the channel. Assumes 0 or 1 files exist.

    Args:
        channel_id (str): Slack channel ID, defaults to CHANNEL_ID from environment
        bot_token (str): Bot token, defaults to BOT_TOKEN from environment

    Returns:
        dict: File info with keys: file_name, url_private, file_id
        None: If no files in channel

    Raises:
        ValueError: If more than one file exists in the channel
        SlackApiError: If the Slack API call fails

    Examples:
        >>> file_info = get_file_info()
        >>> if file_info:
        ...     print(f"File: {file_info['file_name']}")
    """
    logger = _get_logger()
    config = get_config()

    channel_id = channel_id or config['channel_id']
    bot_token = bot_token or config['bot_token']

    if channel_id is None:
        raise ValueError("channel_id not provided and CHANNEL_ID not in environment")

    try:
        client = _create_bot_client(bot_token)
        response = client.files_list(channel=channel_id)
        file_count = len(response["files"])

        if file_count == 1:
            file_data = response["files"][0]
            file_info = {
                'file_name': file_data["name"],
                'url_private': file_data["url_private"],
                'file_id': file_data["id"]
            }
            logger.info("Retrieved file info from file in Slack")
            return file_info
        elif file_count == 0:
            logger.info("File retrieval successful. No files in Slack channel")
            return None
        else:
            error_message = (
                f"There are {file_count} files in the channel. "
                "There can only be max one file in the channel."
            )
            logger.error(error_message)
            raise ValueError(error_message)
    except SlackApiError as e:
        logger.exception(f"Slack API error retrieving file info")
        raise


def download_file(
    output_dir: str,
    channel_id: str = None,
    bot_token: str = None
) -> str | None:
    """Download file from Slack channel to local filesystem.

    Retrieves file information from the channel and downloads it to the specified
    output directory using the private URL with bot authentication.

    Args:
        output_dir (str): Directory path where the file will be saved
        channel_id (str): Slack channel ID, defaults to CHANNEL_ID from environment
        bot_token (str): Bot token, defaults to BOT_TOKEN from environment

    Returns:
        str: Full path to downloaded file
        None: If no files in channel

    Raises:
        requests.exceptions.RequestException: If file download fails
        SlackApiError: If Slack API call fails
        ValueError: If more than one file exists

    Examples:
        >>> output_path = download_file("./downloads")
        >>> if output_path:
        ...     print(f"Downloaded to: {output_path}")
    """
    logger = _get_logger()
    config = get_config()

    bot_token = bot_token or config['bot_token']

    file_info = get_file_info(channel_id, bot_token)

    if file_info is None:
        logger.info("No files to download")
        return None

    output_path = f"{output_dir}/{file_info['file_name']}"

    try:
        headers = {'Authorization': f'Bearer {bot_token}'}
        download_response = requests.get(
            file_info['url_private'],
            headers=headers,
            stream=True
        )
        download_response.raise_for_status()

        with open(output_path, 'wb') as f:
            for chunk in download_response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)

        logger.info(f"File download successful. File saved to: {output_path}")
        return output_path
    except requests.exceptions.RequestException as e:
        logger.exception(f"Request error during file download")
        raise
    except IOError as e:
        logger.exception(f"IO error writing file to {output_path}")
        raise


def upload_file(
    file_path: str,
    title: str = None,
    initial_comment: str = None,
    channel_id: str = None,
    bot_token: str = None
) -> str:
    """Upload file to Slack channel.

    Uploads a file to the channel with optional title and comment.
    The file becomes immediately visible to all channel members.

    Args:
        file_path (str): Path to the file to upload
        title (str): Title/name for the file in Slack, defaults to filename
        initial_comment (str): Optional comment to post with the file
        channel_id (str): Slack channel ID, defaults to CHANNEL_ID from environment
        bot_token (str): Bot token, defaults to BOT_TOKEN from environment

    Returns:
        str: Permalink URL of the uploaded file

    Raises:
        SlackApiError: If Slack API call fails
        FileNotFoundError: If file_path doesn't exist

    Examples:
        >>> file_url = upload_file("report.pdf", title="Weekly Report")
        >>> print(f"Uploaded to: {file_url}")
    """
    logger = _get_logger()
    config = get_config()

    channel_id = channel_id or config['channel_id']
    bot_token = bot_token or config['bot_token']

    if channel_id is None:
        raise ValueError("channel_id not provided and CHANNEL_ID not in environment")

    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    if title is None:
        title = os.path.basename(file_path)

    try:
        client = _create_bot_client(bot_token)
        response = client.files_upload_v2(
            channel=channel_id,
            title=title,
            file=file_path,
            initial_comment=initial_comment
        )
        file_url = response.get("file", {}).get("permalink_public")
        logger.info(f"File '{title}' uploaded successfully to Slack")
        return file_url
    except SlackApiError as e:
        logger.exception(f"Slack API error during file upload")
        raise


def delete_file(
    channel_id: str = None,
    user_token: str = None
) -> bool:
    """Delete file from Slack channel.

    Removes the file from the channel. Requires a user token because bots cannot
    delete files they don't own. This is typically called after downloading a file
    to prepare the channel for the next file.

    Args:
        channel_id (str): Slack channel ID, defaults to CHANNEL_ID from environment
        user_token (str): User token, defaults to USER_TOKEN from environment

    Returns:
        bool: True if file was deleted, False if no files to delete

    Raises:
        SlackApiError: If Slack API call fails
        ValueError: If user_token not provided and not in environment

    Examples:
        >>> if delete_file():
        ...     print("File deleted successfully")
    """
    logger = _get_logger()
    config = get_config()

    channel_id = channel_id or config['channel_id']

    if channel_id is None:
        raise ValueError("channel_id not provided and CHANNEL_ID not in environment")

    file_info = get_file_info(channel_id)

    if file_info is None:
        logger.info("No files to delete")
        return False

    try:
        client = _create_user_client(user_token)
        client.files_delete(file=file_info['file_id'])
        logger.info(f"File '{file_info['file_id']}' has been deleted from Slack")
        return True
    except SlackApiError as e:
        logger.exception(f"Slack API error during file deletion")
        raise
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        raise


# ============================================================================
# MESSAGING
# ============================================================================


def send_message(
    message: str,
    channel_id: str = None,
    bot_token: str = None
) -> dict:
    """Send text message to Slack channel.

    Posts a message to the channel as the bot.

    Args:
        message (str): The text message to send
        channel_id (str): Slack channel ID, defaults to CHANNEL_ID from environment
        bot_token (str): Bot token, defaults to BOT_TOKEN from environment

    Returns:
        dict: Message response with keys: ok, channel, ts, message

    Raises:
        SlackApiError: If Slack API call fails

    Examples:
        >>> response = send_message("Processing complete")
        >>> print(f"Message sent at {response['ts']}")
    """
    logger = _get_logger()
    config = get_config()

    channel_id = channel_id or config['channel_id']
    bot_token = bot_token or config['bot_token']

    if channel_id is None:
        raise ValueError("channel_id not provided and CHANNEL_ID not in environment")

    try:
        client = _create_bot_client(bot_token)
        response = client.chat_postMessage(
            channel=channel_id,
            text=message
        )
        logger.info("Message sent successfully to Slack channel")
        return response
    except SlackApiError as e:
        logger.exception(f"Slack API error sending message")
        raise