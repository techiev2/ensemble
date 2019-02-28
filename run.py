# pylint: disable=C0413,W1508,E0401
"""Notification service main runner. Exposes register, and notify
procedures over Tornadoweb server.

(A) register - Allows consumers to register a notification intent handler
    1. Register payload consists of the following data.
        (a) A target that consists of a payload structure for minimal
            consistency checks
        (b) Endpoint for the notification target to push over HTTP
        (c) Allowed signals for notification

(B) notify   - Allows consumers to initiate a notification with specified
               payloads/targets.
"""
__all__ = ("run_server",)
__author__ = "Sriram Velamur<sriram@likewyss.com>"

import sys
sys.dont_write_bytecode = True

from api import APIApplication, RegisterController, NotifyController


def run_server():
    """Main runner for API"""
    APIApplication([
        (r"^/register/?$", RegisterController),
        (r"^/notify/?$", NotifyController)
    ]).run(port=None)


if __name__ == "__main__":
    run_server()
