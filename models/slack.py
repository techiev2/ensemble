# pylint: disable=C0413,W1508,E0401,R0903
"""Notification system Slack specific models module"""
__all__ = ("SlackTrigger", "SlackState")
__author__ = "Sriram Velamur<sriram@likewyss.com>"

import sys
sys.dont_write_bytecode = True

from datetime import datetime

from .scaffolds import Trigger, State, post_to_http_service


class SlackTrigger(Trigger):

    """Custom trigger class for Slack notifications"""

    async def trigger(self, trigger_data):
        self.set_state_object_class(SlackState)
        error, text, status_code = await self.get_payload(trigger_data)
        if error:
            return status_code, text

        error, response, status_code = \
            post_to_http_service(self.url, {"text": text})
        if error:
            return status_code, response

        if response.status == 200:
            return 200, "Slack channel triggered successfully"

        # Final fallback.
        return 500, "Error while triggering Slack channel trigger"


class SlackState(State):

    """[WIP] Custom state model for Slack"""

    async def get_assign_data(self):
        """Helper to get assigment specific notification payload"""
        return "Triggering assign at {}".format(datetime.utcnow())
