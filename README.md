# Tansanit
Command line wallet for the [Bismuth](https://bismuth.cz) cryptocurrency (BIS)

## Starting
Start Tansanit on the command line

```
./tansanit.py
```

## Arguments
Use `./tansanit.py -h` to show all available arguments

```
➜  Tansanit git:(master) ✗ ./tansanit.py -h
|usage: tansanit.py [-h] [-s SERVER] [-l {10,20,30,40,50}]

Command line wallet for Bismuth (BIS)

optional arguments:
  -h, --help           show this help message and exit
  -s SERVER            connect to server (host:port)
  -l {10,20,30,40,50}  Debug, Info, Warning, Error, Critical
```

### Connect to a specific server
Use the `-s <ip>:<port>` argument to connect to a specific server

```
./tansanit.py -s 46.101.186.35:8150
```

### Enable logging to logfile
Use the `-l <log level>` argument to save log messages to the `log` folder

```
./tansanit.py -l 20
```

Available log levels are  
`10` ➜ Debug  
`20` ➜ Info  
`30` ➜ Warning  
`40` ➜ Error  
`50` ➜ Critical  

## Usage
After you started Tansanit, list all available commands by entering `help`

```
➜  Tansanit git:(master) ✗ ./tansanit.py 
  ______                             _ __ 
 /_  __/___ _____  _________ _____  (_) /_
  / / / __ `/ __ \/ ___/ __ `/ __ \/ / __/
 / / / /_/ / / / (__  ) /_/ / / / / / /_  
/_/  \__,_/_/ /_/____/\__,_/_/ /_/_/\__/  
                                          

> help

Documented commands (type help <topic>):
========================================
balance  quit     send     status        version
help     refresh  servers  transactions  wallet 

> 
```

Or for help regarding a specific command, use `help <command>`

```
> help balance
 Show wallet balance 
```

### Commands
Commands can be auto-completed with TAB. Scroll thru last used commands with the arrow keys

`balance` ➜ Show current wallet balance  

```
> balance

12.257 BIS
```

`send` ➜ Send BIS to an address  

```
> send 542c92ff1bf22ef1fe9b030b4b8e2c71e15ad1c3c563dce234766b10 20

? Send 20 BIS?  (Use arrow keys)
  > Yes
    No
```

`wallet` ➜ Show address and other wallet info  

```
> wallet

{'address': '542c92ff1bf22ef1fe9b030b4b8e2c71e15ad1c3c563dce234766b10', 'file': 'wallet.der', 'encrypted': False}
```

`status` ➜ Show info about the connected server  

```
> status

{'wallet': 'wallet.der', 'address': '542c92ff1bf22ef1fe9b030b4b8e2c71e15ad1c3c563dce234766b10', 'server': '62.112.10.156:8150', 'servers_list': ['62.112.10.156:8150', '188.165.209.184:8150', '51.15.226.30:8150', '46.101.186.35:8150'], 'full_servers_list': [{'ip': '62.112.10.156', 'port': 8150, 'load': '4', 'height': 1230526}, {'ip': '188.165.209.184', 'port': 8150, 'load': '8', 'height': 1230526}, {'ip': '51.15.226.30', 'port': 8150, 'load': '16', 'height': 1230526}, {'ip': '46.101.186.35', 'port': 8150, 'load': '37', 'height': 1230525}], 'connected': True}
```

`transactions` ➜ Show last 10 transactions  

```
> transactions

[]
```

`server` ➜ Show all available servers  

```
> servers

['62.112.10.156:8150', '188.165.209.184:8150', '51.15.226.30:8150', '46.101.186.35:8150']
```

`refresh` ➜ Refresh list of available servers  

```
> refresh

['62.112.10.156:8150', '51.15.226.30:8150', '46.101.186.35:8150', '188.165.209.184:8150']
```

`version` ➜ Show version number of Tansanit  

```
> version

Tansanit Version 0.2
```

`quit` ➜ Exit Tansanit  

```
> quit

? Do you really want to quit?  (Use arrow keys)
  > Yes
    No
```