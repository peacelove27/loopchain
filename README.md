** We'll obsolete this project. Please visit https://github.com/icon-project/loopchain . ** 

#  loopchain

## What is loopchain?
  loopchain is a high-performance blockchain that can support real-time transactions based on efficient smart contract system.

![LoopChain logo](images/new_theloop_ci.png)

## Features

![Features](images/features.png)

### Consensus
loopchain supports quick, fork-less consensus through LFT,Loop Fault Tolerance , which supports BFT, Byzantine Fault Tolerance. In addition, faster consensus becomes possible by putting multiple nodes with mutual trust into one group based on LFT. It is also possible to freely set the number of votes allocated for such group/node, which allows the establishment of various consensus system.


### SCORE(Smart Contract On Reliable Environment)
SCORE refers to a smart contract supported by loopchain; it is a high-performance smart contract support function that runs directly in a node operating environment without any separate virtual machine (VM). SCORE is a smart contract with high productivity that can be easily created and operates in a separate process from the blockchain process, enabling you to develop various tasks. Please refer to the [SCORE document](score/README.md) for more detail.


### Multi Channel
Multi channel is a function that can make transaction request, agreement and smart contract for each channel by constructing a virtual network called “channel” for each task in one independent blockchain network. Integrity is guaranteed and consensuses are reached as channels are formed for each task in a node, with only the parties concerned with that task participating in that particular channel. Accordingly, only the concerned parties of a transaction can have access to the transaction data, which helps them respond to various regulations.


### Tiered System
When participating in a blockchain network, transactions are verified and secured through PKI-based authentication. It also supports the function to give a specific node the ability to audit transaction details as needed, even if it does not participate in the transaction.
Please refer to the [white paper](https://loopchain.files.wordpress.com/2017/07/lft-e18487e185a2e186a8e18489e185a5.pdf) for more detail.


## Components

![LoopChain components](images/system_diagrams.png)

### Peer
It creates a new Tx(Transaction) and requests validation. It also collects the newly verified blocks, stores them in a blockchain, and allows you to read them.

### Peer (Leader)
It is a module that periodically collects transactions of the network, generates blocks, and requests other peers for verification; multiple peers verify these blocks and store them.

### Radio Station
It is a module which, when adding/removing/restarting a peer, informs other peers' address in order to maintain the communication between peers.

### loopchain proxy
It is a module that exposes RESTful API in order to make it easier to access each peer.

### log collector
It is a module that collects log for each peer’s operation.


## Getting stated
This is how to run loopchain in a local machine:

### Prerequisites

* Linux (CentOS, Ubuntu), macOS 10.12, Windows 10
* Python: 3.6 and above
* Virtualenv: 15.1.0 and above
* docker: 17.x and above


### Installation
 First, clone this project. Then go to the project folder and create a user environment. This is how to create a user environment:


```
$ virtualenv -p python3 .  # Create a virtual environment
$ source bin/activate    # Enter the virtual environment
$ pip3 install -r requirements.txt  # Install necessary packages in the virtual environment
$ ./generate_code.sh #  gRPC generates codes necessary for communication
```

Or you can do this easily as follows:

```
$ ./setup.sh
$ source bin/activate
$ ./setup.sh
$ ./generate_code.sh
```

## Running the unit tests
After installation, execute the whole unit test like the following in order to check whether it operates well.
```
$ ./run_test.sh
```

## loopchain configuration settings

Basically, loopchain settings are managed by files.
* ./loopchain/**configure_default.py**
    - This is the file that records the default setting of loopchain.
    - It's an essential file that must exists.

* ./loopchain/**configure_user.py**
    - This is the file that records the custom settings of loopchain.
    - You can add this file if necessary. It's not a required file.
    - It has a higher priority over the configure_default.py file.
    - You can record the configurations that need to be changed depending on your development environment.
    - For example, if you want to change the value of "IP_LOCAL", add the configuration you want to change to the `configure_user.py` file. : **IP_LOCAL = '123.456.789.10'**

* ./loopchain/**configure.json**
    - This file is also a configuration file that can be customized depending on your development environment.
    - You can add the configuration settings according to the json format.
    - It has **the highest priority** of all configuation files (configure_default.py, configure_user.py, etc.).
    - When you run `peer.py` or `radiostation.py`, you can apply it by appending `-o {JSON FILE PATH}` or `--configure_file_path {JSON FILE PATH}` option.

#### Example

Let's say you want to change the "PORT_PEER" path to 7500. 
First, you should add the following setting to the `/loopchain/configure.json` file.
```json
{
  “PORT_PEER”: 7500
}
```

Later when you launch peer, you should add one of these following options:
```
$ ./peer.py -o loopchain/configure.json                      # or
$ ./peer.py --configure_file_path loopchain/configure.json
```

This will modify your default "PORT_PEER" path 7100 to 7500. You can also apply the same logic to `radiostation.py` as well.


## Multichannel 
 To use Multichannel, You have to know the SCORE and peer information. 

### 1. Create the file including channel information. 
   
  In this file, we'll put 1. name of channel, 2. the name of SCORE to execute in this channel, 3. the list of peer to join. 
  For example, you can make ```channel_manage_data.json``` like below.  

``` channel_manage_data.json```
```json
{
  "%CHANNEL_NAME1%": { // 1st channel name
    "score_package": "your_score_package", // The name of SCORE to execute in this channel.
    "peers": [
      {
        "peer_target": "%IP%:%PORT%" // The list of eer targets
      },
     ........
    ]
  },
  "%CHANNEL_NAME2%": {  // 2nd channel name
    "score_package": "your_score_package", // The name of SCORE to execute in this channel
    "peers": [
      {
        "peer_target": ""%IP%:%PORT%"   // The list of eer targets
      },
      .......
    ]
  }
}

```
  TIP: If no peer list information. You can ignore ```peers``` list.
  
  For example, the channel names are ```kofia_0``` and ```kofia_1``` and assign the SCORE ```score/code1``` and ```score/code2``` on each channel, then create file like below. 
  
 ```json
{
  "kofia_0": { 
    "score_package": "score/code1", 
    "peers": [
      {
        "peer_target": "~~~~" 
      },
      ......
    ]
  },
  "kofia_1": { 
    "score_package": "score/code2", 
    "peers": [
      {
        "peer_target": "~~~~"  
      },
      ........
    ]
  }
}

```
  
### 2. Configure and execute RadioStation with configuration file. 

 Now, let's load ```channel_manage_data.json``` made in previous step and execute RadioStation with Multichannel. 
 
 Create configuration file for RadioStation like below.
```json
{
    "CHANNEL_MANAGE_DATA_PATH" : "your channel_manage_data path",
    "ENABLE_CHANNEL_AUTH" : true
}
```

 The meaning of each parameter is, 
  * ```CHANNEL_MANAGE_DATA_PATH```: The path of multichannel configuration file. It have to include file name.  
  * ```ENABLE_CHANNEL_AUTH``` :  
     - ```true``` = Allow to join peer registered in channel manage data file.
     - ```false```= You can add peer randomly. You can use this when you don't have the peer list.

 
 For example, you can create ```rs_config.json```and put the contents like below. 
 
 ``` rs_config.js```
 ```json
 {
    "CHANNEL_MANAGE_DATA_PATH" : "./channel_manage_data.json",
    "ENABLE_CHANNEL_AUTH" : true
  }
 ``` 
 
 And load this configuration file with ```-o``` option.
 
 ```
$ ./radiostation.py -o rs_config.js
```

### 3. Configure and execute peer. 

 Now you have to configure 1. default channel to use and 2. branch of SCORE to execute. Why we need this configuration is to avoid malfunction.

```json
{
    "LOOPCHAIN_DEFAULT_CHANNEL" : "basic channel path",
    "DEFAULT_SCORE_BRANCH": "your working branch name"
}
```
The meaning of each parameter is,
 * LOOPCHAIN_DEFAULT_CHANNEL : Default channel for this peer. 
 * DEFAULT_SCORE_BRANCH : Branch of SCORE to use. Default value is ```master```.


For example, 

```peer_config.js```

```json
{
    "LOOPCHAIN_DEFAULT_CHANNEL" : "kofia_0",
    "DEFAULT_SCORE_BRANCH": "master"
}
```

You can run peer with configuration like below. 
```
$ ./peer.py -o peer_config.js
```


## Deployment
There are two ways to run a loopchain:

### Launch blockchain in on-premise.

 Launch blockchain network in the following order:

#### 1. Launch RadioStation

 ```
 $  ./radiostation.py  # Execute RadioStation.
   ```

   You should now see the following log. This means that **it is waiting at Local for another peer to connect to the 9002 port.** So now you have successfully lauched RadioStation service.

```buildoutcfg
..........
'2017-07-20 15:57:09,315 DEBUG RestServerRS run... 9002'
'2017-07-20 15:57:09,373 INFO  * Running on http://0.0.0.0:9002/ (Press CTRL+C to quit)'
'2017-07-20 15:57:11,302 DEBUG Leader Peer Count: (0)'
'2017-07-20 15:57:11,303 ERROR There is no leader in this network.'
```

####  2. Launch multiple peers

 Open a new terminal and go to the LoopChain folder. Then type the following.
  ```
 $ source bin/activate  # Open python virtual workspace.
 $ ./peer.py            # Launch peer.
   ```
 
 However, if you have additional settings in configure.json file, type the following when you launch peer.
 ```
 $ ./peer.py -o loopchain/configure.json
 ```
 
 Then you will see the following log.

 ```buildoutcfg
 ...........
'2017-07-20 16:05:13,480 DEBUG peer list update: 1:192.168.18.153:7100 PeerStatus.connected c3c5f2f0-6d19-11e7-875d-14109fdb09f5 (<class 'str'>)'
'2017-07-20 16:05:13,480 DEBUG peer_id: c3c5f2f0-6d19-11e7-875d-14109fdb09f5'
'2017-07-20 16:05:13,480 DEBUG peer_self: <loopchain.baseservice.peer_list.Peer object at 0x106249b00>'
'2017-07-20 16:05:13,481 DEBUG peer_leader: <loopchain.baseservice.peer_list.Peer object at 0x106249b00>'
'2017-07-20 16:05:13,481 DEBUG Set Peer Type Block Generator!'
'2017-07-20 16:05:13,481 INFO LOAD SCORE AND CONNECT TO SCORE SERVICE!'
```

 You can launch another peer in the same way. This time, however, you need to connect to RadioStation by using another Port.

```
$ source bin/activate
$ ./peer.py -p 7101
```
 When connecting to RadioStation, each peer receives new port starting from 7100 port. Each time a new peer is connected, RadioStation delivers a list of existing peers to the new peer and informs existing peers that a new peer has been added.


#### 3. Check each peer’s status
 It's possible to connect to each peer via RESTful API so that the status of each peer and RadioStation can be read.

```
$ curl http://localhost:9002/api/v1/peer/list  # Shows a list of peers that are currently configuring the blockchain network in Radiostation.
$ curl http://localhost:9000/api/v1/status/peer # Shows the current status of peer0
$ curl http://localhost:9100/api/v1/status/peer # Shows the current status of peer1
```
 Please refer to the Peer [Peer RESTful API](proxy_rest_api.md), [Radiostation RESTful API](radiostation_proxy_restful_api.md) documents for more detail on RESTful APIs.



#### 4. Create a new transaction
 To send a new transaction to Peer0, call the RESTful API as follows.

```
$ curl -H "Content-Type: application/json" -d '{"data":"hello"}' http://localhost:9000/api/v1/transactions

{"response_code": "0", "tx_hash": "9dc7e5ed17cc5f3258f9b11614b33295e87d80d49b101b7571f444524accee5f", "more_info": ""}
```


#### 5. Check the height of a newly created transaction

```
$ curl http://localhost:9000/api/v1/blocks

{
 "response_code": 0,
 "block_hash": "f7956cb168ac80e5fd569c53c95b55a92254f7a1c372ad06e936cc35357a8ead",
 "block_data_json":
   {
        "prev_block_hash": "af5570f5a1810b7af78caf4bc70a660f0df51e42baf91d4de5b2328de0e83dfc",
        "merkle_tree_root_hash": "1726e6d64a17cb1e0d664f4239f20b7176fc046ae6aa423922fb0ef6eb48512b",
        "time_stamp": "1501132106740684",
        "height": "1",  # Increased block height.
        "peer_id": "15e6d814-7289-11e7-bb81-14109fdb09f5"
   }
}
```

### Tutorial
  A [Tutorial](Tutorial.md) with more details, including SCORE.


## License
 This project follows the Apache 2.0 License. Please refer to [LICENSE](https://www.apache.org/licenses/LICENSE-2.0) for details.

## Acknowledgments
 This project is sponsored by the “NIPA Promising Public Software Technology Development Support Project”.
