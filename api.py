# pylint: disable=C0413,W1508,E0401,W0223,W0703,W0611
"""Notifier REST API server class module"""
__all__ = ("APIApplication", "APIController")
__author__ = "Sriram Velamur<sriram@likewyss.com>"

import sys
sys.dont_write_bytecode = True

from os import getenv
import pickle
from json import loads, dumps
from ast import literal_eval

from tornado.web import Application, RequestHandler
from tornado.ioloop import IOLoop

from models.scaffolds import Trigger, TYPE_MAP

# TODO: Find a way to inject the custom State/Trigger classes dynamically.
# In the absence of the custom State/Trigger classes in the module
# global namespace, the trigger handle flow falls back to the base State
# and its trigger.
from models.slack import SlackState, SlackTrigger
from models.email import EmailState, EmailTrigger


class APIApplication(Application):
    """API application class for notification service"""

    def add_trigger(self, trigger_data):
        """Helper to add a trigger to an application"""
        if not isinstance(trigger_data, dict):
            return (400, "Invalid trigger data. dict data expected")
        trigger_name = trigger_data.get("name")
        existing_trigger = self.triggers.get(trigger_name)
        if existing_trigger is not None:
            return (
                400,
                "Service registered with that name. Please try another"
            )
        self.triggers.update({trigger_name: trigger_data})
        self.pickle_trigger_data()
        for key, value in self.triggers.items():
            trigger_class_name = "{}Trigger".format(trigger_data.get("service"))
            trigger_class = globals().get(trigger_class_name)
            if trigger_class is None:
                trigger_class = Trigger
            self.trigger_objects[key] = trigger_class(value)
        return (None, None)

    def pickle_trigger_data(self):
        """Helper to pickle trigger information to a local file to
        retain trigger data on app reload"""
        with open(self.trigger_data_file, "wb") as _file:
            pickle.dump(self.triggers, _file)

    def load_trigger_data(self):
        """Helper to load pickled trigger information on app load"""
        try:
            with open(self.trigger_data_file, "rb") as _file:
                self.triggers = pickle.load(_file)
        except (IOError, EOFError, FileNotFoundError):
            print("No pickled data found. Using an empty trigger data")
            self.triggers = {}
        except BaseException as error:
            print("Error loading trigger data from local file - {}".format(
                error
            ))
            self.triggers = {}

        for key, value in self.triggers.items():
            service = value.get("service")
            trigger_class_name = "{}Trigger".format(service)
            trigger_class = globals().get(trigger_class_name)
            if trigger_class is None:
                trigger_class = Trigger
            self.trigger_objects[key] = trigger_class(value)

    headers = {
        "Content-Type": "application/json",
        "Server": "Notification orchestrator v0.0.1"
    }
    triggers = {}
    trigger_objects = {}

    def __init__(self, *args, **kwargs):
        env_trues = ("True", "true")
        kwargs.update({
            "debug": True
        })
        super(APIApplication, self).__init__(*args, **kwargs)
        self.trigger_data_file = "triggers.pkl"
        self.load_trigger_data()
        self.loop = IOLoop.instance()

    def run(self, port):
        """API application runner method"""
        port = port if isinstance(port, int) else 9999
        self.listen(port)
        print("Listening in http://localhost:{}".format(port))
        self.loop.start()


class APIController(RequestHandler):
    """Base API controller class"""

    def get(self, *args, **kwargs):
        pass

    def post(self, *args, **kwargs):
        pass

    def __init__(self, *args, **kwargs):
        super(APIController, self).__init__(*args, **kwargs)
        self.data = {}

    def prepare(self):
        body = self.request.body.decode("utf-8")
        try:
            self.data = loads(body)
        except (TypeError, ValueError):
            splits = body.split("&")
            for splat in splits:
                _splat = splat.split("=")
                if len(_splat) != 2:
                    continue
                self.data[_splat[0]] = _splat[1]

        for key, value in self.data.items():
            try:
                self.data[key] = literal_eval(value)
            except (TypeError, ValueError, SyntaxError):
                pass

    def respond(self, status_code, response):
        """HTTP responder convenience helper"""
        self.set_status(status_code)
        if status_code > 399 or status_code < 200:
            key = "message"
        else:
            key = "data"
        response = dumps({key: response})
        self.set_status(status_code)
        self.write(response)
        self.finish()

    def set_default_headers(self):
        for key, value in self.application.headers.items():
            self.set_header(key, value)


class RegisterController(APIController):
    """Notification trigger/intent registration end point controller"""

    def post(self, *args, **kwargs):

        key_structure_map = {
            "url": str,
            "service": str,
            "structure": dict
        }
        for key, key_type in key_structure_map.items():
            data_value = self.data.get(key)
            if not isinstance(data_value, key_type):
                return self.respond(
                    400,
                    "Invalid type for {}. Expected {}, got {}".format(
                        key, key_type, type(data_value)
                    )
                )

        payload_structure = self.data.get("structure")
        for key, value in payload_structure.items():
            _type = TYPE_MAP.get(value)
            if _type is None:
                return self.respond(
                    400,
                    "Type {} not allowed in paylod".format(value)
                )
            payload_structure[key] = _type

        self.data["structure"] = payload_structure

        status_code, response = self.application.add_trigger(self.data)
        if status_code and response:
            return self.respond(status_code, response)

        return self.respond(201, "Registered new trigger {}".format(
            self.data.get("name")
        ))


class NotifyController(APIController):

    """Notification trigger end point controller"""

    async def post(self, *args, **kwargs):
        trigger_name = self.data.get("name")
        trigger_data = self.data.get("payload")
        trigger = self.application.triggers.get(trigger_name)
        if trigger is None:
            return self.respond(
                404,
                "No triggers registered for {}".format(trigger_name)
            )
        if not trigger_data:
            return self.respond(400, "Invalid payload")

        # Validate payload based on registered trigger payload structure
        # trigger_payload = trigger.get("structure")
        # invalids = 0
        # payload_data_size = len(list(trigger_payload.keys()))
        # for key, value in trigger_payload.items():
        #     data_value = trigger_data.get(key)
        #     if not isinstance(data_value, value):
        #         invalids += 1

        # if invalids == payload_data_size:
        #     return self.respond(
        #         400,
        #         "Invalid type for {}. Expected {}, got {}".format(
        #             key, value, type(data_value)
        #         )
        #     )

        # Initialize a trigger method on the trigger object, if any.
        trigger_object = self.application.trigger_objects.get(trigger_name)
        try:
            status_code, response = await trigger_object.trigger(trigger_data)
        except AttributeError as error:
            status_code = 500
            response = "Trigger for {} does not show a custom trigger".format(
                trigger_name
            )
        except BaseException as error:
            print(error)
            status_code = 500
            response = "Server error"

        return self.respond(status_code, response)
