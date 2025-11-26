"""Slack utilities for handling file operations and channel interactions.

This module provides classes for interacting with Slack channels through the Slack SDK,
including functionality for polling channels for files, downloading files, uploading files,
and managing file deletions.

Classes:
    SlackBase: Base class for Slack authentication and initialization.
    SlackPoller: Polls Slack channels for file presence.
    SlackHandler: Handles file operations including download, upload, and deletion.
"""

from dotenv import load_dotenv
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from src.custom_logger import get_custom_logger
import logging
import requests
import os

class SlackBase:
    """Base class for Slack authentication and token management.

    Handles initialization with Slack API tokens and validates authentication
    for both bot and user tokens.

    Attributes:
        channel_id (str): The Slack channel ID for operations.
        bot_token (str): The Slack bot token for API authentication.
        user_token (str, optional): The Slack user token for user-specific operations.
        bot_user_id (str): The user ID of the authenticated bot.
        user_id (str, optional): The user ID of the authenticated user.
        logger: Custom logger instance for this module.
    """

    def __init__(self, env_file: str = ".env") -> None:
        """Initialize SlackBase with channel and authentication tokens.

        Args:
            channel_id (str): The Slack channel ID for operations.
            bot_token (str): The Slack bot token for API authentication.
            user_token (str, optional): The Slack user token for user-specific operations.
                Defaults to None.

        Raises:
            SlackApiError: If bot token authentication fails.
        """
        load_dotenv(env_file)
        self.logger = get_custom_logger(__name__)
        self.channel_id = os.getenv("CHANNEL_ID")
        self.bot_token = os.getenv("BOT_TOKEN")
        self._test_bot_auth()
        try:
            self.user_token = os.getenv("USER_TOKEN")
            self._test_user_auth()
        except:
            self.logger.info("No USER_TOKEN found in .env file, proceeding without a USER_TOKEN")

    def _test_bot_auth(self):
        """Test bot token authentication with Slack API.

        Validates the bot token by calling auth.test endpoint and stores
        the bot user ID for reference.

        Raises:
            SlackApiError: If authentication fails.
        """
        try:
            self.logger.info("Testing Slack BOT token")
            client = WebClient(self.bot_token)
            auth_test = client.auth_test()
            self.bot_user_id = auth_test["user_id"]
            self.logger.info(f"BOT Authentication successful.")
        except SlackApiError as e:
            self.logger.exception(e)
            raise
        
    def _test_user_auth(self):
        """Test user token authentication with Slack API.

        Validates the user token by calling auth.test endpoint and stores
        the user ID for reference.

        Raises:
            SlackApiError: If authentication fails.
        """
        try:
            self.logger.info("Testing Slack USER token")
            client = WebClient(self.bot_token)
            auth_test = client.auth_test()
            self.user_id = auth_test["user_id"]
            self.logger.info(f"USER Authentication successful.")
        except SlackApiError as e:
            self.logger.exception(e)
            raise

class SlackPoller(SlackBase):
    """Polls a Slack channel for file presence.

    Monitors a Slack channel to check for file uploads and enforces
    a constraint that only one file can exist in the channel at a time.
    """

    def _poll_for_one_file(self) -> bool:
        """Check if exactly one file exists in the Slack channel.

        Polls the Slack channel's files and validates that there is exactly
        one file present.

        Returns:
            bool: True if exactly one file exists, False if no files exist.

        Raises:
            ValueError: If more than one file exists in the channel.
            SlackApiError: If the Slack API call fails.
        """
        client = WebClient(self.bot_token)
        try:
            response = client.files_list(channel=self.channel_id)
            if len(response["files"]) == 1:
                self.logger.info("Poll successful. Found one file in Slack channel.")
                return True
            elif len(response["files"])==0 or response["files"] is None:
                self.logger.info("Poll successful. No files in Slack channel")
                return False
            else:
                error_message = "During polling, found more than one file in the channel. There can only be max one file in the channel. Manually delete the unnecesaary files in the channel."
                logging.error(error_message)
                raise ValueError(error_message)
        except SlackApiError as e:
            self.logger.exception(e)
        
    def poll(self) -> bool:
        """Poll the Slack channel for file presence.

        Public method that checks if exactly one file exists in the channel.

        Returns:
            bool: True if exactly one file exists, False if no files exist.

        Raises:
            ValueError: If more than one file exists in the channel.
            SlackApiError: If the Slack API call fails.
        """
        result = self._poll_for_one_file()
        return result
    
class SlackHandler(SlackBase):
    """Handles file operations in a Slack channel.

    Provides methods for downloading, uploading, deleting files, and sending
    messages to a Slack channel.

    Attributes:
        file_name (str, optional): Name of the file retrieved from the channel.
        url_private (str, optional): Private URL of the file for authenticated access.
        file_id (str, optional): ID of the file in Slack.
        new_file (dict, optional): Response from file upload operation.
        file_url (str, optional): Permalink URL of the uploaded file.
        new_message (dict, optional): Response from message post operation.
    """

    # _get_file_info() can just retrieve the list of all files in the channel then filter the metadata later
    # use this to create methods: _get_file_by_date, _get_file_by_user
    # _get_file_info will pass the returned list of files to the filtering functions
    # the data retrieved from these methods will be used to download a file or files

    def _get_file_info(self) -> None:
        """Retrieve file information from the Slack channel.

        Gets the name, private URL, and file ID of the file in the channel.
        Assumes only 0 or 1 files can exist in the channel.

        Raises:
            ValueError: If more than one file exists in the channel.
            SlackApiError: If the Slack API call fails.
        """
        client = WebClient(self.bot_token)
        try:
            response = client.files_list(channel=self.channel_id)
            if len(response["files"])==1:
                self.file_name = response["files"][0]["name"] # this gives us name with extension
                self.url_private = response["files"][0]["url_private"]
                self.file_id = response["files"][0]["id"]
                self.logger.info("Retrieved file info from file in Slack")
            elif len(response["files"])==0 or response["files"] is None:
                self.file_name = None
                self.url_private = None
                self.file_id = None
                self.logger.info("File retrieval successful. No files in Slack channel")
            elif len(response["files"])>1:
                error_message = "There can only be max one file in the channel"
                logging.error(error_message)
                raise ValueError(error_message)
        except SlackApiError as e:
            self.logger.exception(e)
        
    def download_files(self, output_dir: str) -> None:
        """Download a file from the Slack channel to the local filesystem.

        Retrieves file information from the channel and downloads it to the
        specified output directory using the private URL with bot authentication.

        Args:
            output_dir (str): Directory path where the file will be saved.

        Raises:
            RequestException: If the file download fails.
            SlackApiError: If the Slack API call fails.
        """
        self._get_file_info()
        if self.file_id is not None:
            output_path = f"{output_dir}/{self.file_name}"
            try:
                headers = {'Authorization': f'Bearer {self.bot_token}'}
                download_response = requests.get(self.url_private, headers=headers, stream=True)
                with open(f"{output_path}", 'wb') as f:
                    for chunk in download_response.iter_content(chunk_size=8192):
                        f.write(chunk)
                self.logger.info(f"File download successful. File saved to: {output_path}")
            except requests.exceptions.RequestException as e:
                self.logger.exception(e)
        else:
            self.logger.info("No files to download")
        
    # we may not need to use share_file in addition to upload file
        
    def _upload_file(self, file_path: str, image_title: str, initial_comment: str = None) -> None:
        """Upload a file to the Slack channel.

        Uploads a file to the channel and stores the response for later use.
        The uploaded file will be visible to all channel members.

        Args:
            file_path (str): Path to the file to be uploaded.
            image_title (str): Title/name for the file in Slack.
            initial_comment (str, optional): Comment to post with the file.
                Defaults to None.

        Raises:
            SlackApiError: If the Slack API call fails.
        """
        client = WebClient(self.bot_token)
        try:
            self.new_file = client.files_upload_v2(
            channel=self.channel_id,
            title=image_title,
            file=file_path,
            initial_comment=initial_comment)
            self.logger.info(f"File '{image_title}' uploaded successfully to Slack")
        except SlackApiError as e:
            self.logger.exception(e)
    
    def _share_file(self) -> None:
        """Post a message with the uploaded file URL to the channel.

        Shares the uploaded file with the channel by posting a message containing
        the file permalink. Note: files_upload_v2 already makes files visible in
        the channel, so this is optional.

        Raises:
            SlackApiError: If the Slack API call fails.
        """
        client = WebClient(self.bot_token)
        try:
            self.file_url = self.new_file.get("file").get("permalink")
            self.new_message = client.chat_postMessage(
            channel=self.channel_id,
            text=f"Here is the file url: {self.file_url}")
            self.logger.info(f"File shared successfully with URL: {self.file_url}")
        except SlackApiError as e:
            self.logger.exception(e)
    
    def publish_file(self, file_path: str, image_title: str, initial_comment: str) -> None:
        """Upload and publish a file to the Slack channel.

        Uploads a file to the channel with a title and optional comment.
        The file becomes immediately visible to all channel members.

        Args:
            file_path (str): Path to the file to be uploaded.
            image_title (str): Title/name for the file in Slack.
            initial_comment (str): Comment to post with the file.

        Raises:
            SlackApiError: If the Slack API call fails.
        """
        self._upload_file(file_path, image_title, initial_comment)
        #self._share_file()
        #return self.file_url
    
    # SAME INFO NEEDED AS DOWNLOAD FILE - need to know what file to delete
    # _get_file_info() can just retrieve the list of all files in the channel then filter the metadata later
    # use this to create methods: _get_file_by_date, _get_file_by_user
    # _get_file_info will pass the returned list of files to the filtering functions
    # the data retrieved from these methods will be used to DELETE a file or files
    
    def delete_files(self) -> None:
        """Delete the file from the Slack channel.

        Removes the file from the channel. Requires a user token because bots
        cannot delete files they don't own. This is typically called after
        downloading a file to prepare the channel for the next file.

        Requires:
            user_token: Must be set during initialization.

        Raises:
            SlackApiError: If the Slack API call fails.
        """
        self._get_file_info()
        if self.file_id is not None:
            client = WebClient(self.user_token)
            try:
                client.files_delete(file=self.file_id)
                self.logger.info(f"File '{self.file_id}' has been deleted from Slack")
            except SlackApiError as e:
                self.logger.exception(e)
        else:
            self.logger.info("No files to delete")
    
    def send_message(self, message: str) -> None:
        """Send a text message to the Slack channel.

        Posts a message to the channel as the bot.

        Args:
            message (str): The text message to send.

        Raises:
            SlackApiError: If the Slack API call fails.
        """
        client = WebClient(self.bot_token)
        try:
            client.chat_postMessage(
                channel=self.channel_id,
                text=message
            )
            self.logger.info("Message sent successfully to Slack channel")
        except SlackApiError as e:
            self.logger.exception(e)