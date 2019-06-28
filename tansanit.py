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


# TODO: Support encrypted wallets
# TODO: Add possibility to convert wallets: der <--> json
class Tansanit(Cmd):

    __version__ = "0.2"

    WALLET_DER = "wallet.der"
    WALLET_ENC = "wallet.json"
    LOG_FILE = os.path.join("log", "tansanit.log")

    def __init__(self):
        super().__init__()

        # Parse command line arguments
        self.args = self._parse_args()

        # Set up logging
        self._logging(self.args.log)

        # Log arguments
        logging.debug(self.args)

        # Create and load wallet
        self.client = BismuthClient()
        self.client.new_wallet()
        self.client.load_wallet()

        # Connect to server
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

        # Encrypted
        parser.add_argument(
            "-e",
            dest="encrypted",
            action="store_true",
            help="use encrypted wallet",
            default=False,
            required=False)

        return parser.parse_args()

    def _logging(self, level):
        logger = logging.getLogger()
        logger.setLevel(level)
        logger.handlers = []

        if level in [10, 20, 30, 40, 50]:
            # Create 'log' directory if not present
            log_path = os.path.dirname(self.LOG_FILE)
            os.makedirs(log_path, exist_ok=True)

            # Log to file
            file_log = TimedRotatingFileHandler(
                self.LOG_FILE,
                when="H",
                encoding="utf-8")

            s = "[%(asctime)s %(levelname)s %(filename)s:%(lineno)s %(funcName)s()] %(message)s"
            file_log.setFormatter(logging.Formatter(s))
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

        # Check if wallet address is valid
        if not BismuthUtil.valid_address(address):
            msg = f"'{address}' is not a valid address"
            logging.error(msg)
            self._prnt(msg)
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

        result = prompt(question)
        if result and result[question[0]["name"]] == "Yes":
            self._prnt(self.client.send(address, float(amount)))

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

        result = prompt(question)
        if result and result[question[0]["name"]] == "Yes":
            raise SystemExit

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
            sys.stdout.write(f"{next(self.spinner_generator)} Loading...")
            sys.stdout.flush()
            time.sleep(self.delay)
            sys.stdout.write('\b\b\b\b\b\b\b\b\b\b\b\b')
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
