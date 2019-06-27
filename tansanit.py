#!/usr/bin/env python3

import sys
import time
import threading

from cmd import Cmd
from pyfiglet import Figlet
from bismuthclient.bismuthutil import BismuthUtil
from bismuthclient.bismuthclient import BismuthClient


class Tansanit(Cmd):

    __version__ = "0.1"

    def __init__(self):
        super().__init__()

        self.client = BismuthClient()
        self.client.new_wallet()
        self.client.get_server()
        self.client.load_wallet()

    def do_version(self, args):
        """ Show Tansanit version """
        self._prnt(f"Tansanit Version {self.__version__}")

    def do_info(self, args):
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
            self._prnt(f"{address} is not a valid address")
            return

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
        self._prnt("Quitting...")
        raise SystemExit

    def _prnt(self, obj):
        print(f"{obj}\n")


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
