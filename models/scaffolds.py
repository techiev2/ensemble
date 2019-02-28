# pylint: disable=C0413,W1508,E0401
"""Scaffolds module for notifier"""
__all__ = ("Trigger", "State")
__author__ = "Sriram Velamur<sriram@likewyss.com>"

import sys
sys.dont_write_bytecode = True

from types import FunctionType, MethodType
from urllib.request import Request, urlopen
from json import dumps

TYPE_MAP = {
    "str": str,
    "int": int,
    "float": float,
    # "function": type(lambda x: x)
    "function": (FunctionType, MethodType)
}


class Trigger:
    """Base class to define a trigger for notifying actions"""

    def __init__(self, trigger_init_data):
        self.data = trigger_init_data
        self.name = self.data.get("name")
        self.url = self.data.get("url")
        self.state_data = self.data.get("state", {})
        self.state_name = self.state_data.get("name")
        self.state_object_name = "{}State".format(self.state_name)

    def set_state_object_class(self, state_object_class=None):
        """Helper to set the trigger's state object to identify the
        data provider information downstream"""
        if not state_object_class:
            state_object_class = globals().get(self.state_object_name)
            if state_object_class is None:
                state_object_class = State
        self.data["structure"].update({
            "state": state_object_class
        })
        self.state_object = state_object_class(self.state_data)
        self.state_object.providers = self.data.get("providers")

    async def get_payload(self, trigger_data):
        """Helper to get the notification trigger payload based on the
        incoming trigger data.
        If a state value is provided for transition and a corresponding
        next state is available (not the final/StopIteration not raised),
        data is obtained from it.
        If the state class for the current trigger specifies a state data
        provider method defined as get_<state>_data in it, the data is
        obtained from it. Else, a base string of Triggering <state> is
        returned.

        If a stop iteration is raised by the state object, the end of
        life for this item has been reached and a corresponding invalid
        transition message is returned.

        If a text data is provided by the payload, it is returned as is
        finally.
        """
        if trigger_data.get("state"):
            try:
                next(self.state_object)
                next_state_name = self.state_object.current[0]
                next_state_provider = getattr(
                    self.state_object,
                    "get_{}_data".format(next_state_name),
                    None
                )
                if isinstance(next_state_provider, TYPE_MAP.get("function")):
                    try:
                        state_value = await next_state_provider()
                        return False, state_value, None
                    except BaseException:
                        return True, "Error fetching provider data", 500
                if not next_state_provider:
                    return False, "Triggering {}".format(next_state_name), None
            except StopIteration:
                return True, "Invalid transition. State end", 400
        else:
            return False, trigger_data.get("text"), None

    async def trigger(self, trigger_data):
        """Default trigger method. Custom trigger classes can override
        this method to provide their own functional flows."""
        return (
            200, "DEFAULT:: Triggering {} with {}".format(
                self.name, trigger_data
            )
        )


class State:

    """State object to manage state transitions"""

    # TODO: Add a way to allow for custom models to define their
    # additional payload information based on the trigger.
    # Ex: Slack - icon_emoji, channel

    def __init__(self, state_map):
        self.providers = {}
        if not isinstance(state_map, dict) or not state_map:
            raise SystemError(
                "State map must be a valid dict of transitions"
            )
        if state_map.get("transitions"):
            state_map = state_map.get("transitions")
        if not isinstance(state_map, dict) or not state_map:
            raise SystemError(
                "State map must be a valid dict of transitions"
            )
        self.states_map = state_map
        self.states = [(key, value) for key, value in state_map.items()]
        self.current = self.states[0]
        self._id = id(self)

    def __next__(self):
        curr_index = self.states.index(self.current)
        try:
            self.current = self.states[curr_index + 1]
            return self
        except IndexError:
            raise StopIteration("Final state for current state model")

    def __iter__(self):
        return self


def post_to_http_service(url, data):
    """Generic helper to post data to a HTTP service"""
    try:
        _data = dumps(data).encode("utf-8")
    except (TypeError, ValueError):
        return True, "Invalid payload data", 400

    try:
        response = urlopen(Request(url=url, method="POST", data=_data))
        return False, response, response.status
    except BaseException:
        return True, "Server error", 500
