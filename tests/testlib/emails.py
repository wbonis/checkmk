import email
import logging
import re
import time
from email.policy import default
from getpass import getuser
from pathlib import Path

from tests.testlib.repo import repo_path
from tests.testlib.utils import run

logger = logging.getLogger(__name__)


class EmailManager:
    def __init__(self) -> None:
        self.maildir_folder = Path.home() / "Maildir" / "new"
        scripts_folder = repo_path() / "tests" / "scripts"
        self.setup_postfix_script = scripts_folder / "setup_postfix.sh"
        self.teardown_postfix_script = scripts_folder / "teardown_postfix.sh"
        self._username = getuser()
        self.html_file_path = repo_path() / "email_content.html"

    def __enter__(self):
        self.setup_postfix()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.teardown_postfix()
        self.delete_html_file()

    def setup_postfix(self) -> None:
        """Install and configure Postfix to send emails to a local Maildir."""
        logger.info("Setting up postfix...")

        run([str(self.setup_postfix_script), self._username], sudo=True)
        logger.info("Postfix is set up")

    def teardown_postfix(self) -> None:
        """Uninstall Postfix and delete all related files."""
        logger.info("Deleting postfix and related files...")
        run([str(self.teardown_postfix_script), self._username], sudo=True)
        logger.info("Postfix is deleted")

    def find_email_by_subject(self, email_subject: str) -> Path | None:
        """Check all emails in the Maildir folder and return the file path of the email
        with the specified subject. Delete checked emails.
        """
        for file_name in self.maildir_folder.iterdir():
            file_path = self.maildir_folder / file_name
            with open(file_path, "r") as file:
                msg = email.message_from_file(file, policy=default)
                logger.info("Email received, subject: '%s'", msg.get("Subject"))
                if msg.get("Subject") == email_subject:
                    return file_path
                file_path.unlink()
        return None

    def wait_for_email(self, email_subject: str, interval: int = 3, timeout: int = 20) -> Path:
        """Wait for an email with the specified subject to be received in the Maildir folder.
        Return the file path of the email if it is received, otherwise raise TimeoutError.
        """
        logger.info("Waiting for the email with subject: '%s'", email_subject)
        start_time = time.time()
        while time.time() - start_time < timeout:
            if self.maildir_folder.exists():
                file_path = self.find_email_by_subject(email_subject)
                if file_path:
                    return file_path
            time.sleep(interval)
        raise TimeoutError(
            f"Email with subject '{email_subject}' was not received after {timeout} seconds"
        )

    def check_email_content(
        self,
        file_path: Path,
        expected_fields: dict[str, str],
        expected_text_content: dict[str, str],
    ) -> None:
        """Check that the email has expected fields and text content."""
        with open(file_path, "r") as file:
            msg = email.message_from_file(file, policy=default)
            logger.info("Check that email fields have expected values")
            for field, expected_value in expected_fields.items():
                assert msg.get(field) == expected_value, f"Field '{field}' has unexpected value"

            logger.info("Check that email text content has expected value")
            for part in msg.walk():
                if part.get_content_type() == "text/plain":
                    payload = part.get_payload(decode=True)
                    if isinstance(payload, bytes):
                        text = payload.decode()
                    else:
                        raise ValueError("Unexpected payload type: %s" % type(payload))
                    text_dict = self.convert_text_into_dict(text)
                    for key, expected_value in expected_text_content.items():
                        actual_value = text_dict[key]
                        assert expected_value == actual_value, f"Field '{key}' has unexpected value"

    def copy_html_content_into_file(self, file_path: Path) -> Path:
        """Copy the html content of the email into a file and return the file path."""
        with open(file_path, "r") as file:
            msg = email.message_from_file(file, policy=default)
            for part in msg.walk():
                if part.get_content_type() == "text/html":
                    payload = part.get_payload(decode=True)
                    if isinstance(payload, bytes):
                        html_content = payload.decode()
                    else:
                        raise ValueError("Unexpected payload type")
                    with open(self.html_file_path, "w") as html_file:
                        html_file.write(html_content)
                    break
        return self.html_file_path.absolute()

    def delete_html_file(self) -> None:
        """Delete the html file if exists."""
        if self.html_file_path.exists():
            logger.info("Delete the html file with email content")
            self.html_file_path.unlink()

    @staticmethod
    def convert_text_into_dict(text: str) -> dict[str, str]:
        """Convert text content of the email into a dictionary."""
        lines = text.split("\n")
        dict_result = {}
        for line in lines:
            if ": " in line:
                key, value = line.split(": ", 1)
                dict_result[key.strip()] = value.strip()
        return dict_result
