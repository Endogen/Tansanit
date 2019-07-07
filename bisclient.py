import time
import json
import base64
import logging
import sys
import os

from time import time
from datetime import timedelta
from bismuthclient import lwbench
from bismuthclient import bismuthapi
from bismuthclient import bismuthcrypto
from bismuthclient import rpcconnections
from bismultiwallet import BisMultiWallet
from bismuthclient.bismuthformat import TxFormatter, AmountFormatter
from os import path


"""
A all in one Bismuth Native client that connects to local or distant wallet servers
"""


class BisClient:

    __version__ = '0.0.44'

    __slots__ = ('initial_servers', 'servers', 'log', 'address',
                 '_current_server', 'wallet_file', '_wallet', '_connection', '_cache',
                 'verbose', 'full_servers', 'time_drift', '_alias_cache', '_alias_cache_file')

    # Hardcoded list of addresses that need a message (like exchanges)
    REJECT_EMPTY_MSG = ['f6c0363ca1c5aa28cc584252e65a63998493ff0a5ec1bb16beda9bac',
                        '49ca873779b36c4a503562ebf5697fca331685d79fd3deef64a46888',
                        'edf2d63cdf0b6275ead22c9e6d66aa8ea31dc0ccb367fad2e7c08a25']

    def __init__(self, wallet_file='wallet.json', servers=None, log=None, verbose=False):
        self.verbose = verbose
        self.servers = servers if servers else []
        self.initial_servers = self.servers
        self.log = log if log else logging
        self.wallet_file = None
        self._wallet = None
        self.address = None
        self.full_servers = None
        self._current_server = None
        self._connection = None
        self._cache = {}
        self._alias_cache = {}
        self._alias_cache_file = None
        self.time_drift = 0  # Difference between local time and server time

        self.load_multi_wallet(wallet_file)

    # --- alias functions

    def set_alias_cache_file(self, filename: str):
        """Define an optional file for persistent storage of alias data"""
        self._alias_cache_file = filename
        # Try to load
        if path.isfile(filename):
            with open(filename) as f:
                self._alias_cache = json.load(f)

    def get_aliases(self, addresses: list) -> dict:
        """Get alias from a list of addresses. returns a dict {address:alias (or '')}"""
        # Filter out the ones from valid cache
        now = time()
        addresses = set(addresses)  # dedup
        cached = {address: self._alias_cache[address][0] for address in addresses if address in self._alias_cache and self._alias_cache[address][1] > now}
        print("cached", cached)
        # Ask for the rest.
        unknown = [address for address in addresses if address not in cached]
        aliases = self.command("aliasesget", [unknown])
        # Returns a list of aliases (or addresses if no alias)
        # print("aliases", aliases)
        new = dict(zip(unknown, aliases))
        for address, alias in new.items():
            # cache empty ones for 1 hour, existing ones for a day.
            if address == alias:
                self._alias_cache[address] = [alias, now + 3600]
            else:
                self._alias_cache[address] = [alias, now + 3600 * 24]
        # save cache if alias_cache_file is defined
        if self._alias_cache_file:
            with open(self._alias_cache_file, 'w') as fp:
                json.dump(self._alias_cache, fp)
        # return merge
        return {**cached, **new}

    def has_alias(self, address):
        """Does this address have an alias? - not the most efficient, prefer get_aliases_of for batch ops."""
        return self.get_aliases([address]) != ''

    def alias_exists(self, alias):
        """Does this alias exists?"""
        # if we have in cache, it does.
        for address, info in self._alias_cache:
            if info[0] == alias:
                return True
        # if not, ask the chain (do not cache there)
        return self.command("aliascheck", [alias])

    # --- cache functions

    def _get_cached(self, key, timeout_sec=30):
        if key in self._cache:
            data = self._cache[key]
            if data[0] + timeout_sec >= time():
                return data[1]
        return None

    def _set_cache(self, key, value):
        self._cache[key] = (time(), value)

    def clear_cache(self):
        self._cache = {}

    # --- server functions

    @property
    def current_server(self):
        return self._current_server

    def set_server(self, ipport):
        """
        Tries to connect and use the given server
        :param ipport:
        :return:
        """
        if not lwbench.connectible(ipport):
            self._current_server = None
            self._connection = None
            return False
        self._current_server = ipport

        if self.verbose:
            print("connect server", ipport)
        self._connection = rpcconnections.Connection(ipport, verbose=self.verbose)
        return ipport

    def get_server(self):
        """
        Tries to find the best available server given the config and sets self._current_server for later use.

        Returns the first connectible server.
        """
        # Use the API or bench to get the best one.
        if not len(self.initial_servers):
            self.full_servers = bismuthapi.get_wallet_servers_legacy(self.initial_servers, self.log, minver='0.1.5', as_dict=True)
            self.servers = ["{}:{}".format(server['ip'], server['port']) for server in self.full_servers]
        else:
            self.servers = self.initial_servers
            self.full_servers = [
                {
                    "ip": server.split(':')[0],
                    "port": server.split(':')[1],
                    'load':'N/A',
                    'height': 'N/A'
                }
                for server in self.servers
            ]

        # Now try to connect
        if self.verbose:
            print("self.servers_list", self.servers)
        for server in self.servers:
            if self.verbose:
                print("test server", server)
            if lwbench.connectible(server):
                self._current_server = server
                # TODO: if self._loop, use async version
                if self.verbose:
                    print("connect server", server)
                self._connection = rpcconnections.Connection(server, verbose=self.verbose)
                return server
        self._current_server = None
        self._connection = None
        # TODO: raise
        return None

    def refresh_servers(self):
        """
        Gets info from api, add to previous config list.
        :return:
        """
        backup = list(self.full_servers)
        self.full_servers = bismuthapi.get_wallet_servers_legacy(
            self.initial_servers,
            self.log,
            minver='0.1.5', as_dict=True)

        for server in backup:
            is_there = False
            for present in self.full_servers:
                if server['ip'] == present['ip'] and server['port'] == present['port']:
                    is_there=True
            if not is_there:
                self.full_servers.append(server)

        self.servers = ["{}:{}".format(server['ip'], server['port']) for server in self.full_servers]

    # --- wallet functions

    def latest_transactions(self, num=10, offset=0, for_display=False):
        """
        Returns the list of the latest num transactions for the current address.

        Each transaction is a dict with the following keys:
        `["block_height", "timestamp", "address", "recipient", "amount", "signature",
        "public_key", "block_hash", "fee", "reward", "operation", "openfield"]`
        """
        if not self.address or not self._wallet:
            return []
        try:
            key = "tx{}-{}".format(num, offset)
            cached = self._get_cached(key)
            if cached:
                return cached
            if offset == 0:
                transactions = self.command("addlistlim", [self.address, num])
            else:
                transactions = self.command("addlistlimfrom", [self.address, num, offset])
        except Exception as e:
            self.log.error(e)
            transactions = []

        json_data = [TxFormatter(tx).to_json(for_display=for_display) for tx in transactions]
        self._set_cache(key, json_data)
        return json_data

    def balance(self, for_display=False):
        """
        Returns the current balance for the current address.
        """
        if not self.address or not self._wallet:
            return 'N/A'
        try:
            balance = self._get_cached('balance')
            if not balance:
                balance = self.command("balanceget", [self.address])[0]
                self._set_cache('balance', balance)
                balance = self._get_cached('balance')
        except Exception as e:
            self.log.error(e)
            return 'N/A'
        if for_display:
            balance = AmountFormatter(balance).to_string(leading=0)
        if balance == '0E-8':
            balance = 0.000
        return balance

    def global_balance(self, for_display=False):
        """
        Returns the current global balance for all addresses of current multiwallet.
        """
        if not type(self._wallet) == BisMultiWallet:
            raise RuntimeWarning("Not a Multiwallet")
        if not self.address or not self._wallet:
            return 'N/A'
        try:
            address_list = [add['address'] for add in self._wallet._addresses]
            # print('al', address_list)
            balance = self.command("globalbalanceget", [address_list])
            # print('balance', balance)
            balance = balance[0]
        except:
            # TODO: Handle retry, at least error message.
            balance = 'N/A'
        if for_display:
            balance = AmountFormatter(balance).to_string(leading=0)
        if balance == '0E-8':
            balance = 0.000
        return balance

    def reject_empty_msg(self, address: str) -> bool:
        """Hardcoded list."""
        return address in self.REJECT_EMPTY_MSG

    def send(self, recipient: str, amount: float, operation: str = '', data: str = '', error_reply: list = []):
        """
        Sends the given transaction
        """
        try:
            timestamp = time()
            if self.time_drift > 0:
                # we are more advanced than server, fix and add 0.1 sec safety
                timestamp -= (self.time_drift + 0.1)
                # This is to avoid "rejected transaction because in the future
            public_key_hashed = base64.b64encode(self._wallet.public_key.encode('utf-8'))
            signature_enc = bismuthcrypto.sign_with_key(timestamp, self.address, recipient, amount, operation, data, self._wallet.key)
            txid = signature_enc[:56]
            tx_submit = ('%.2f' % timestamp, self.address, recipient, '%.8f' % float(amount),
                          str(signature_enc), str(public_key_hashed.decode("utf-8")), operation, data)
            reply = self.command('mpinsert', [tx_submit])
            if self.verbose:
                print("Server replied '{}'".format(reply))
            if reply[-1] != "Success":
                msg = "Error '{}'".format(reply)
                self.log.error(msg)
                print(msg)
                error_reply.append(reply[-1])
                return None
            if not reply:
                msg = "Server timeout"
                self.log.error(msg)
                print(msg)
                error_reply.append('Server timeout')
                return None
            return txid
        except Exception as e:
            self.log.error(e)
            print(str(e))
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            print(exc_type, fname, exc_tb.tb_lineno)

    def sign(self, message: str):
        """
        Signs the given message
        """
        try:
            signature = bismuthcrypto.sign_message_with_key(message, self._wallet.key)
            return signature
        except Exception as e:
            self.log.error(e)
            print(str(e))
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            print(exc_type, fname, exc_tb.tb_lineno)
            raise

    def encrypt(self, message: str, recipient:str):
        """
        Encrypts the given message for the recipient
        """
        try:
            # Fetch the pubkey of the recipient
            pubkey = self.command('pubkeyget', [recipient])
            # print("pubkey", pubkey, recipient)
            encrypted = bismuthcrypto.encrypt_message_with_pubkey(message, pubkey)
            return encrypted
        except Exception as e:
            self.log.error(e)
            print(str(e))
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            print(exc_type, fname, exc_tb.tb_lineno)
            raise

    def decrypt(self, message: str):
        """
        Decrypts the given message
        """
        try:
            decrypted = bismuthcrypto.decrypt_message_with_key(message, self._wallet.key)
            return decrypted
        except Exception as e:
            self.log.error(e)
            print(str(e))
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            print(exc_type, fname, exc_tb.tb_lineno)
            raise

    def status(self):
        """
        Returns the current status of the wallet server
        """
        try:
            cached = self._get_cached('status')
            if cached:
                return cached
            status = self.command("statusjson")
            # print("getstatus", status)
            try:
                status['uptime_human'] = str(timedelta(seconds=status['uptime']))
            except Exception as e:
                self.log.error(e)
                status['uptime_human'] = 'N/A'
            try:
                status['extended'] = self.command("wstatusget")
            except Exception as e:
                self.log.error(e)
                status['extended'] = None

            if 'server_timestamp' in status:
                self.time_drift = time() - float(status['server_timestamp'])
            else:
                self.time_drift = 0
            status['time_drift'] = self.time_drift

            self._set_cache('status', status)
        except Exception as e:
            self.log.error(e)
            status = {}
        return status

    def load_multi_wallet(self, wallet_file='wallet.json'):
        """
        Tries to load the wallet file

        :param wallet_file: string, a wallet.json file
        """
        # TODO: Refactor
        self.wallet_file = None
        self.address = None
        self._wallet = None
        self._wallet = BisMultiWallet(wallet_file, verbose=self.verbose, log=self.log)
        if len(self._wallet._data["addresses"]) == 0:
            # Create a first address by default
            self._wallet.new_address(label="default")
        self.wallet_file = wallet_file
        if self.address != self._wallet.address:
            self.clear_cache()
        self.address = self._wallet.address

    def set_address(self, address: str = ''):
        if not type(self._wallet) == BisMultiWallet:
            raise RuntimeWarning("Not a MultiWallet")
        self._wallet.set_address(address)
        if self.address != self._wallet.address:
            self.clear_cache()
        self.address = self._wallet.address

    def new_address(self, label, password, salt):
        try:
            self._wallet.new_address(label, password, salt)
        except RuntimeError as e:
            print(str(e))  # TODO: Test

    def addresses(self):
        return self._wallet._data['addresses']

    def import_der(self, wallet_der='wallet.der', label='', password=''):
        try:
            self._wallet.import_der(wallet_der=wallet_der, label=label, source_password=password)
        except Exception as e:
            print(str(e))
            raise e

    def wallet(self):
        """
        returns info about the currently loaded wallet
        """
        return self._wallet.info()

    def info(self):
        """
        returns a dict with server info: ip, port, latest server status
        """
        connected = False
        if self._connection:
            connected = bool(self._connection.sdef)
        info = {"wallet": self.wallet_file, "address": self.address, "server": self._current_server,
                "servers_list": self.servers, "full_servers_list": self.full_servers,
                "connected": connected}
        return info

    def command(self, command, options=None):
        """
        Makes sure we have a connection, runs a command and sends back the result.

        :param command: the command as a string
        :param options: optional options to the command, as a list if needed
        :return: the result as a native structure
        """
        if not self._current_server:
            # TODO: failsafe if can't connect
            self.get_server()
        if self.verbose:
            print("command {}, {}".format(command, options))
        return self._connection.command(command, options)
