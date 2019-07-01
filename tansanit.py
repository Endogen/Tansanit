#!/usr/bin/env python3

import os
import sys
import time
import logging
import threading

from cmd import Cmd
from pyfiglet import Figlet
from PyInquirer import prompt
from datetime import datetime
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

        # Log arguments
        logging.debug(self.args)

        # Create folders if needed
        path = os.path.dirname(self.args.wallet)
        path and os.makedirs(path, exist_ok=True)

        # Create and load wallet
        self.client = BismuthClient()
        self.client.new_wallet(self.args.wallet)
        self.client.load_wallet(self.args.wallet)

        # Connect to server
        if self.args.server:
            # Connect to specified server
            self.client.set_server(self.args.server)
        else:
            # Automatically choose best server
            self.client.get_server()

    def _parse_args(self):
        desc = "Tansanit - command line wallet for Bismuth (BIS)"
        parser = ArgumentParser(description=desc)

        # Wallet
        parser.add_argument(
            "-w",
            dest="wallet",
            help="set wallet file location",
            required=False,
            default="wallet.der")

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

    def precmd(self, line):
        print()
        return line

    def postcmd(self, stop, line):
        print()
        return stop

    def do_version(self, args):
        """ Show Tansanit version """

        print(f"Tansanit Version {self.__version__}")

    def do_wallet(self, args):
        """ Show wallet info """

        result = self.client.wallet()

        print(f"Address:   {result['address']}\n"
              f"Location:  {os.path.abspath(result['file'])}\n"
              f"Encrypted: {result['encrypted']}")

    def do_servers(self, args):
        """ Show server list """

        result = self.client.info()

        for s in result["full_servers_list"]:
            ip, port, load, height = s['ip'], s['port'], s['load'], s['height']
            print(f"IP: {ip:<16} Port: {port:<5} Load: {load:<3} Height: {height}")

    def do_connect(self, args):
        """ Select server to connect with """

        result = self.client.info()
        s_list = list()

        for s in result["full_servers_list"]:
            ip, port, load, height = s['ip'], s['port'], s['load'], s['height']
            s_list.append(f"IP: {ip:<16} Port: {port:<5} Load: {load:<3} Height: {height}")

        question = [
            {
                'type': 'list',
                'name': 'servers',
                'message': f"Select a server to connect with",
                'choices': s_list
            }
        ]

        result = prompt(question)

        if result:
            server = list(filter(None, result["servers"].split(" ")))
            selected = f"{server[1].strip()}:{server[3].strip()}"
            result = self.client.set_server(selected)
            if selected == result:
                print("DONE!")
            else:
                print(result)
        else:
            print("No selection")

    def do_status(self, args):
        """ Show server status """

        result = self.client.info()

        print(f"Server:    {result['server']}\n"
              f"Connected: {result['connected']}")

    def do_send(self, args):
        """ Send coins to address """

        arg_list = args.split(" ")
        address = arg_list[0]
        amount = arg_list[1]

        # Check if wallet address is valid
        if not BismuthUtil.valid_address(address):
            msg = f"'{address}' is not a valid address"
            logging.error(msg)
            print(f"\n{msg}\n")
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

        if result:
            if result[question[0]["name"]] == "Yes":
                reply = self.client.send(address, float(amount))

                if reply:
                    print(f"\nDONE! TRXID: {reply}\n")
                else:
                    print("Transaction couldn't be send")
        else:
            print("No selection")

    def do_balance(self, args):
        """ Show wallet balance """

        print(f"{self.client.balance(for_display=True)} BIS")

    def do_transactions(self, args):
        """ Show latest transactions """

        result = self.client.latest_transactions()

        if not result:
            print("No transactions yet")
            return

        address = self.client.wallet()["address"]

        msg = str()
        for trx in result:
            if trx['address'] == address:
                trx['address'] = f"{trx['address']} >> loaded"
            else:
                trx['recipient'] = f"{trx['recipient']} >> loaded"

            dt = trx['timestamp']
            dt = datetime.utcfromtimestamp(dt).strftime('%Y-%m-%d %H:%M:%S')
            trx['timestamp'] = f"{dt} UTC"

            msg += f"Amount:    {trx['amount']}\n" \
                   f"Block:     {trx['block_height']}\n" \
                   f"From:      {trx['address']}\n" \
                   f"To:        {trx['recipient']}\n" \
                   f"Timestamp: {trx['timestamp']}\n" \
                   f"Trx ID:    {trx['signature'][:56]}\n" \
                   f"Fee:       {trx['fee']}\n" \
                   f"Operation: {trx['operation']}\n\n"

        print(msg[:-2])

    def do_refresh(self, args):
        """ Refresh server list """

        self.client.refresh_server_list()
        self.do_servers(args)

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


class Spinner:
    busy = False
    delay = 0.1

    @staticmethod
    def spinning_cursor():
        while 1:
            for cursor in '|/-\\':
                yield cursor

    def __init__(self, delay=None):
        self.spinner_generator = self.spinning_cursor()
        if delay and float(delay):
            self.delay = delay

    def spinner_task(self):
        while self.busy:
            sys.stdout.write(f"{next(self.spinner_generator)} Loading...")
            sys.stdout.flush()
            time.sleep(self.delay)
            sys.stdout.write('\b'*12)
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
