# pylint: disable=C0413,W1508,E0401
"""Notifications system email trigger channel module"""
__all__ = ("EmailState", "EmailTrigger")
__author__ = "Sriram Velamur<sriram@likewyss.com>"

import sys
sys.dont_write_bytecode = True
import smtplib
from os import getenv

from .scaffolds import Trigger, State

SMTP_URL = getenv("SMTP_URL")
if SMTP_URL is None:
    print("SMTP url not found in environment")
    exit(1)
try:
    SMTP_PORT = int(getenv("SMTP_PORT"))
except TypeError:
    print("SMTP port not found in environment")
    exit(1)

SMTP_USER = getenv("SMTP_USER")
if SMTP_USER is None:
    print("SMTP user not found in environment")
    exit(1)
SMTP_PASSWORD = getenv("SMTP_PASSWORD")
if SMTP_PASSWORD is None:
    print("SMTP password not found in environment")
    exit(1)


class EmailState(State):
    """Email trigger channel state model class"""
    keys = {"from", "to", "subject", "body"}

    @classmethod
    def validate(cls, trigger_data):
        """Helper to validate an email payload data"""
        for key in cls.keys:
            if not trigger_data.get(key):
                return True, "Missing data for {}".format(key), 400

        return False, None, None


def get_email_contents(trigger_data):
    """Helper to construct email contents from trigger data"""
    return """\
    From: {from}
    To: {to}
    Subject: {subject}

    {body}
    """.format(**trigger_data)



class EmailTrigger(Trigger):

    """Custom trigger class for email notifications"""

    async def trigger(self, trigger_data):

        error, message, status_code = EmailState.validate(trigger_data)
        if error:
            return status_code, message

        try:
            server = smtplib.SMTP(SMTP_URL, SMTP_PORT)
            server.ehlo()
            server.starttls()
            server.ehlo()
            contents = get_email_contents(trigger_data)
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_USER, trigger_data.get("to"), contents)
            server.close()
        except BaseException:
            return 500, "Server error. Unable to connect to email server"

        return 200, "Email channel triggered successfully"
