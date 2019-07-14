#!/usr/bin/env python3

import time
import qrcode
import threading
import logging
import sys
import os
import json

from cmd import Cmd
from pyfiglet import Figlet
from PyInquirer import prompt
from client import Client
from argparse import ArgumentParser
from bismuthclient.bismuthutil import BismuthUtil
from logging.handlers import TimedRotatingFileHandler
from datetime import datetime


# TODO: Remove 'self.log.error(e)' from tansanit.py since it's in client already
class Tansanit(Cmd):

    __version__ = "0.2"

    LOG_FILE = os.path.join("log", "tansanit.log")

    SELECTED = "  <-- SELECTED"
    NO_LABEL = "<no label>"

    LEGACY_WALLET = "wallet.der"

    ARGS_RECEIVE = ["tty"]
    ARGS_BALANCE = ["all"]

    def __init__(self):
        super().__init__()

        # Parse command line arguments
        self.args = self._parse_args()

        # Set up logging
        self._logging(self.args.log)

        # Log arguments
        logging.debug(self.args)

        # Create folders if needed
        wallet_path = os.path.dirname(self.args.wallet)
        wallet_path and os.makedirs(wallet_path, exist_ok=True)

        # Get password if wallet is encrypted
        password = self._get_password(self.args.wallet)

        try:
            with Spinner():
                self._init_wallet(password)
        except Exception as e:
            logging.error(e)
            print(f"\n{e}\n")
            raise SystemExit

    def _parse_args(self):
        desc = "Tansanit - command line wallet for Bismuth (BIS)"
        parser = ArgumentParser(description=desc)

        # Wallet
        parser.add_argument(
            "-w",
            dest="wallet",
            help="set wallet file location",
            required=False,
            default="wallet.json")

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
            help="debug, info, warning, error, critical",
            default=60,
            required=False)

        # Clear
        parser.add_argument(
            "--no-clear",
            dest="clear",
            action="store_false",
            help="don't clear after each command",
            required=False,
            default=True)

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

    def _get_password(self, wallet_file):
        with open(wallet_file, 'r') as file:
            data = json.load(file)

        if data["encrypted"]:
            enter_pass = [
                {
                    "type": "password",
                    "name": "password",
                    "message": "Password:"
                }
            ]

            res_pass = prompt(enter_pass)

            sys.stdout.write("\033[F")  # back to previous line
            sys.stdout.write("\033[K")  # clear line

            if res_pass:
                return res_pass["password"] if res_pass["password"] else None
            else:
                print("No password provided\n")
                raise SystemExit
        else:
            return None

    def _init_wallet(self, password=None):
        # Create and load wallet
        self.client = Client(self.args.wallet, password=password)

        # Connect to server
        if self.args.server:
            # Connect to specified server
            self.client.set_server(self.args.server)
        else:
            # Automatically choose best server
            self.client.get_server()

    def preloop(self):
        if self.args.clear:
            os.system("clear")

    def precmd(self, line):
        if self.args.clear:
            os.system("clear")
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

        print(f"Address:   {self.client.address}\n"
              f"Location:  {os.path.abspath(result['file'])}\n"
              f"Encrypted: {result['encrypted']}")

    def do_servers(self, args):
        """ Show server list """

        result = self.client.info()

        for s in result["full_servers_list"]:
            ip, port, load, height = s["ip"], s["port"], s["load"], s["height"]
            print(f"IP: {ip:<16} Port: {port:<5} Load: {load:<3} Height: {height}")

    def do_connect(self, args):
        """ Select server to connect with """

        result = self.client.info()
        s_list = list()

        for s in result["full_servers_list"]:
            ip, port, load, height = s["ip"], s["port"], s["load"], s["height"]
            s_list.append(f"IP: {ip:<16} Port: {port:<5} Load: {load:<3} Height: {height}")

        question = [
            {
                "type": "list",
                "name": "servers",
                "message": f"Select a server to connect with",
                "choices": s_list
            }
        ]

        result = prompt(question)

        if result:
            server = list(filter(None, result["servers"].split(" ")))
            selected = f"{server[1].strip()}:{server[3].strip()}"
            result = self.client.set_server(selected)
            if selected == result:
                print("DONE! Connected")
            else:
                print(result)

    def do_status(self, args):
        """ Show server status """

        result = self.client.info()

        print(f"Server:    {result['server']}\n"
              f"Connected: {result['connected']}")

    def do_send(self, args):
        """ Send coins to address """

        if args:
            arg_list = list(filter(None, args.split(" ")))
            if args and len(arg_list) == 2:
                address = arg_list[0]
                amount = arg_list[1]
                operation = ""
                data = ""
            else:
                print("Provide following syntax\n"
                      "send <address> <amount>")
                return
        else:
            question = [
                {
                    "type": "input",
                    "name": "address",
                    "message": "To:",
                },
                {
                    "type": "input",
                    "name": "amount",
                    "message": "Amount:",
                },
                {
                    "type": "input",
                    "name": "operation",
                    "message": "Operation:",
                },
                {
                    "type": "input",
                    "name": "data",
                    "message": "Data:",
                }
            ]

            res_send = prompt(question)

            if res_send:
                address = res_send["address"] if res_send["address"] else ""
                amount = res_send["amount"] if res_send["amount"] else ""
                operation = res_send["operation"] if res_send["operation"] else ""
                data = res_send["data"] if res_send["data"] else ""
            else:
                return

        if not BismuthUtil.valid_address(address):
            msg = f"'{address}' is not a valid address!"
            logging.error(msg)
            print(msg)
            return

        try:
            float(amount)
        except ValueError:
            msg = "'Amount' has to be numeric!"
            logging.error(msg)
            print(msg)
            return

        if self.client.reject_empty_msg(address) and not data:
            msg = "This address needs a 'Data' entry!"
            logging.error(msg)
            print(msg)
            return

        question = [
            {
                "type": "list",
                "name": "send",
                "message": f"Send {amount} BIS?",
                "choices": [
                    "Yes",
                    "No"
                ]
            }
        ]

        result = prompt(question)

        if result:
            if result[question[0]["name"]] == "Yes":
                try:
                    reply = self.client.send(
                        address,
                        float(amount),
                        operation=operation,
                        data=data)

                    if reply:
                        print(f"\nDONE! TRXID: {reply}\n")
                    else:
                        print("Transaction couldn't be send")
                except Exception as e:
                    logging.error(e)
                    print(str(e))

    def do_receive(self, args):
        """ Show QR-Code to receive BIS """

        qr = qrcode.QRCode()
        qr.add_data(self.client.address)

        if args and args.lower() == "tty":
            qr.print_tty()
        else:
            qr.print_ascii(invert=True)

    def complete_receive(self, text, line, begidx, endidx):
        return [i for i in self.ARGS_RECEIVE if i.startswith(text)]

    def do_balance(self, args):
        """ Show wallet balance """

        if args and args.lower() == "all":
            with Spinner():
                balance = self.client.global_balance(for_display=True)
        else:
            with Spinner():
                balance = self.client.balance(for_display=True)

        print("N/A" if balance == "N/A" else f"{balance} BIS")

    def complete_balance(self, text, line, begidx, endidx):
        return [i for i in self.ARGS_BALANCE if i.startswith(text)]

    def do_transactions(self, args):
        """ Show latest transactions """

        num = 5
        if args:
            if args.strip().isnumeric():
                num = args.strip()
            else:
                print("Provide following argument\n"
                      "transactions <number of last transactions>")
                return

        reverse = False
        if args and len(list(filter(None, args.split(" ")))) > 0:
            if args.lower() == "reverse":
                reverse = True

        try:
            with Spinner():
                result = self.client.latest_transactions(num=num)
            if not result:
                print("No transactions yet")
                return
        except Exception as e:
            logging.error(e)
            print(str(e))
            return

        msg = str()
        for trx in result:
            trx_amount = trx["amount"]
            trx_height = trx["block_height"]
            trx_address = trx["address"]
            trx_recipient = trx["recipient"]
            trx_timestamp = trx["timestamp"]
            trx_signature = trx["signature"]
            trx_operation = trx["operation"]
            trx_fee = trx["fee"]

            if trx_address == self.client.address:
                trx_address = f"{trx_address}{self.SELECTED}"
            else:
                trx_recipient = f"{trx_recipient}{self.SELECTED}"

            dt = datetime.utcfromtimestamp(trx_timestamp).strftime("%Y-%m-%d %H:%M:%S")
            trx_timestamp = f"{dt} UTC"

            trx_msg = f"Amount:    {trx_amount}\n" \
                      f"Block:     {trx_height}\n" \
                      f"From:      {trx_address}\n" \
                      f"To:        {trx_recipient}\n" \
                      f"Timestamp: {trx_timestamp}\n" \
                      f"Trx ID:    {trx_signature[:56]}\n" \
                      f"Fee:       {trx_fee}\n" \
                      f"Operation: {trx_operation}\n\n"

            if reverse:
                msg = msg + trx_msg
            else:
                msg = trx_msg + msg

        print(msg[:-2])

    def do_refresh(self, args):
        """ Refresh server list """

        self.client.refresh_servers()
        self.do_servers(args)

    def do_addresses(self, args):
        """ List wallet addresses """

        for address in self.client.addresses():
            addr = address["address"]

            label = address["label"]
            label = f"{label}" if label else self.NO_LABEL

            msg = f"{addr} {label}"
            if addr == self.client.address:
                msg += self.SELECTED

            print(msg)

    # TODO: Do i really have to set salt on every new address?
    def do_new(self, args):
        """ Create new address """

        question = [
            {
                "type": "input",
                "name": "label",
                "message": "Label:",
            }
        ]

        res_label = prompt(question)

        if res_label:
            label = res_label["label"] if res_label["label"] else ""
        else:
            return

        question = [
            {
                "type": "password",
                "name": "password1",
                "message": "Password 1/2:"
            },
            {
                "type": "password",
                "name": "password2",
                "message": "Password 2/2:"
            }
        ]

        res_pass = prompt(question)

        if res_pass:
            password1 = res_pass["password1"] if res_pass["password1"] else ""
            password2 = res_pass["password2"] if res_pass["password2"] else ""

            if password1 != password2:
                print("Passwords don't match!")
                return
        else:
            return

        question = [
            {
                "type": "input",
                "name": "salt",
                "message": "Salt:",
            }
        ]

        res_salt = prompt(question)

        if res_salt:
            salt = res_salt["salt"] if res_salt["salt"] else ""
        else:
            return

        with Spinner():
            try:
                self.client.new_address(label, password1, salt)
            except Exception as e:
                logging.error(e)
                print(str(e))

    def do_select(self, args):
        """ Change currently active address """

        if args:
            if BismuthUtil.valid_address(args):
                self.client.set_address(args)
                print("DONE! Address selected")
            else:
                print("Address not valid!")
            return

        if len(self.client.addresses()) < 1:
            print("At least two addresses are needed")
            return

        result = self._select_address()

        if result:
            try:
                addresses = list(filter(None, result["addresses"].split(" ")))
                self.client.set_address(addresses[0].strip())
                print("DONE! Address selected")
            except Exception as e:
                logging.error(e)
                print(str(e))

    def do_import(self, args):
        """ Import legacy .der wallet """

        if not os.path.isfile(self.LEGACY_WALLET):
            print(f"No '{self.LEGACY_WALLET}' file found!")
            return

        question = [
            {
                "type": "input",
                "name": "label",
                "message": "Label:",
            }
        ]

        res_label = prompt(question)

        if res_label:
            label = res_label["label"] if res_label["label"] else ""
        else:
            return

        question = [
            {
                "type": "password",
                "name": "password",
                "message": "Password:"
            }
        ]

        res_pass = prompt(question)

        if res_pass:
            password = res_pass["password"] if res_pass["password"] else ""
        else:
            return

        try:
            with Spinner():
                self.client.import_der(label=label, password=password)
            print("DONE! Successfully imported")
        except Exception as e:
            logging.error(e)
            print(str(e))

    def do_label(self, args):
        """ Change label of selected address """

        question = [
            {
                "type": "input",
                "name": "label",
                "message": "New label:",
            }
        ]

        res_label = prompt(question)

        if res_label:
            if not res_label["label"]:
                print("No label provided")
                return

            label = res_label["label"]
        else:
            return

        self.client.set_label(self.client.address, label)
        print("DONE! Label changed")

    def do_msg_encrypt(self, args):
        """ Encrypts given message for recipient """

        question = [
            {
                "type": "input",
                "name": "recipient",
                "message": "Recipient:",
            },
            {
                "type": "input",
                "name": "message",
                "message": "Message:",
            }
        ]

        res_data = prompt(question)

        if res_data:
            recipient = res_data["recipient"] if res_data["recipient"] else ""
            message = res_data["message"] if res_data["message"] else ""
        else:
            return

        try:
            with Spinner():
                encrypted = self.client.encrypt_message(message, recipient)
            print(f"\n{encrypted}")
        except Exception as e:
            logging.error(e)
            print(str(e))
            return

    def do_msg_decrypt(self, args):
        """ Decrypts given message """

        question = [
            {
                "type": "input",
                "name": "message",
                "message": "Message:",
            }
        ]

        res_msg = prompt(question)

        if res_msg:
            message = res_msg["message"] if res_msg["message"] else ""
        else:
            return

        try:
            with Spinner():
                decrypt = self.client.decrypt_message(message)
            print(f"\n{decrypt}")
        except Exception as e:
            logging.error(e)
            print(f"\n{e}")

    def do_encrypt(self, args):
        """ Encrypt the wallet """

        if self.client.wallet()["encrypted"]:
            print("Wallet already encrypted")
            return

        question = [
            {
                "type": "password",
                "name": "password",
                "message": "Password:"
            }
        ]

        res_pass = prompt(question)

        if res_pass:
            password = res_pass["password"] if res_pass["password"] else ""
        else:
            return

        try:
            with Spinner():
                self.client.encrypt_wallet(password=password)
            print("DONE! Wallet encrypted")
        except Exception as e:
            logging.error(e)
            print(str(e))

    def do_decrypt(self, args):
        """ Decrypt the wallet """

        if not self.client.wallet()["encrypted"]:
            print("Wallet already decrypted")
            return

        question = [
            {
                "type": "password",
                "name": "password",
                "message": "Password:"
            }
        ]

        res_pass = prompt(question)

        if res_pass:
            password = res_pass["password"] if res_pass["password"] else ""
        else:
            return

        # TODO: Not yet possible to decrypt and save it
        try:
            with Spinner():
                self.client.decrypt_wallet(password=password)
            print("DONE! Wallet decrypted")
        except Exception as e:
            logging.error(e)
            print(str(e))

    def do_shell(self, command):
        """ Execute shell commands """

        os.system(command)
        print("DONE! Command executed")

    def do_quit(self, args):
        """ Quit Tansanit """

        question = [
            {
                "type": "list",
                "name": "quit",
                "message": "Do you really want to quit?",
                "choices": [
                    "Yes",
                    "No"
                ]
            }
        ]

        result = prompt(question)

        if result and result[question[0]["name"]] == "Yes":
            raise SystemExit

    def _select_address(self, name="addresses", message="Select an address"):
        addresses = self.client.addresses()

        address_list = list()
        for address_data in addresses:
            address = address_data["address"]

            label = address_data["label"]
            label = f"{label}" if label else self.NO_LABEL

            msg = f"{address} {label}"
            if address == self.client.address:
                msg += self.SELECTED

            address_list.append(msg)

        question = [
            {
                "type": "list",
                "name": name,
                "message": message,
                "choices": address_list
            }
        ]

        return prompt(question)


class Spinner:
    busy = False
    delay = 0.1

    @staticmethod
    def spinning_cursor():
        while 1:
            for cursor in "|/-\\":
                yield cursor

    def __init__(self, delay=None):
        self.spinner_generator = self.spinning_cursor()
        if delay and float(delay):
            self.delay = delay

    def spinner_task(self):
        while self.busy:
            sys.stdout.write(f"{next(self.spinner_generator)} Working")
            sys.stdout.flush()
            time.sleep(self.delay)
            sys.stdout.flush()
            sys.stdout.write("\b"*9)

    def __enter__(self):
        self.busy = True
        threading.Thread(target=self.spinner_task).start()

    def __exit__(self, exception, value, tb):
        self.busy = False
        time.sleep(self.delay)
        sys.stdout.write("\b"*9)
        sys.stdout.write("\033[K")
        if exception is not None:
            return False


if __name__ == "__main__":
    f = Figlet(font="slant")

    t = Tansanit()
    t.prompt = "> "
    t.cmdloop(f.renderText("Tansanit"))
