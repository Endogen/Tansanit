#!/usr/bin/env python3

import os
import sys
import time
import logging
import threading

from cmd import Cmd
from pyfiglet import Figlet
from PyInquirer import prompt
from argparse import ArgumentParser
from bismuthclient.bismuthutil import BismuthUtil
from bismuthclient.bismuthclient import BismuthClient
from logging.handlers import TimedRotatingFileHandler


class Tansanit(Cmd):

    __version__ = "0.2"

    LOG_FILE = os.path.join("log", "tansanit.log")

    def __init__(self):
        super().__init__()

        # Parse command line arguments
        self.args = self._parse_args()

        # Set up logging
        self._logging(self.args.log)

        self.client = BismuthClient()
        self.client.new_wallet()
        self.client.load_wallet()

        if self.args.server:
            # Connect to specified server
            self.client.set_server(self.args.server)
        else:
            # Automatically choose best server
            self.client.get_server()

    def _parse_args(self):
        desc = "Command line wallet for Bismuth (BIS)"
        parser = ArgumentParser(description=desc)

        # Server
        parser.add_argument(
            "-s",
            dest="server",
            help="connect to server (host:port)",
            required=False,
            default=None)

        # Logging
        parser.add_argument(
            "-l",
            dest="log",
            type=int,
            choices=[10, 20, 30, 40, 50],
            help="Debug, Info, Warning, Error, Critical",
            default=60,
            required=False)

        return parser.parse_args()

    def _logging(self, level):
        logger = logging.getLogger()
        logger.setLevel(level)

        if level <= 50:
            # Create 'log' directory if not present
            log_path = os.path.dirname(self.LOG_FILE)
            os.makedirs(log_path, exist_ok=True)

            # Log to file
            file_log = TimedRotatingFileHandler(
                self.LOG_FILE,
                when="H",
                encoding="utf-8")

            log_format = '%(asctime)s - %(levelname)s - %(message)s'
            file_log.setFormatter(logging.Formatter(log_format))
            file_log.setLevel(level)

            logger.addHandler(file_log)

    def do_version(self, args):
        """ Show Tansanit version """
        self._prnt(f"Tansanit Version {self.__version__}")

    def do_wallet(self, args):
        """ Show wallet info """
        self._prnt(self.client.wallet())

    def do_servers(self, args):
        """ Show server list """
        self._prnt(self.client.servers_list)

    def do_status(self, args):
        """ Show server status """
        self._prnt(self.client.info())

    def do_send(self, args):
        """ Send coins to address """
        arg_list = args.split(" ")
        address = arg_list[0]
        amount = arg_list[1]

        if not BismuthUtil.valid_address(address):
            self._prnt(f"'{address}' is not a valid address")
            return

        question = [
            {
                'type': 'list',
                'name': 'send',
                'message': f"Send {amount} BIS?",
                'choices': [
                    'Yes',
                    'No'
                ]
            }
        ]

        print()
        if prompt(question)["send"] == "Yes":
            print()
            self._prnt(self.client.send(address, float(amount)))
        else:
            print()

    def do_balance(self, args):
        """ Show wallet balance """
        self._prnt(f"{self.client.balance(for_display=True)} BIS")

    def do_transactions(self, args):
        """ Show latest transactions """
        self._prnt(self.client.latest_transactions())

    def do_refresh(self, args):
        """ Refresh server list """
        self.client.refresh_server_list()
        self._prnt(self.client.servers_list)

    def do_quit(self, args):
        """ Quit Tansanit """

        question = [
            {
                'type': 'list',
                'name': 'quit',
                'message': 'Do you really want to quit?',
                'choices': [
                    'Yes',
                    'No'
                ]
            }
        ]

        print()
        if prompt(question)["quit"] == "Yes":
            print()
            raise SystemExit
        else:
            print()

    def _prnt(self, obj):
        print(f"\n{obj}\n")


class Spinner:
    busy = False
    delay = 0.1

    @staticmethod
    def spinning_cursor():
        while 1:
            for cursor in '|/-\\': yield cursor

    def __init__(self, delay=None):
        self.spinner_generator = self.spinning_cursor()
        if delay and float(delay):
            self.delay = delay

    def spinner_task(self):
        while self.busy:
            sys.stdout.write(next(self.spinner_generator))
            sys.stdout.flush()
            time.sleep(self.delay)
            sys.stdout.write('\b')
            sys.stdout.flush()

    def __enter__(self):
        self.busy = True
        threading.Thread(target=self.spinner_task).start()

    def __exit__(self, exception, value, tb):
        self.busy = False
        time.sleep(self.delay)
        if exception is not None:
            return False


if __name__ == '__main__':
    f = Figlet(font='slant')

    with Spinner():
        t = Tansanit()

    t.prompt = "> "
    t.cmdloop(f.renderText('Tansanit'))