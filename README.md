# Nostpy

![Pylint_score](./pylint.svg) 

A containerized, fully Python-based Nostr relay designed for portability and ease of deployment. It leverages asyncio and websockets to efficiently serve Nostr clients, making it simple to deploy and manage across various environments.


![Image 2023-09-15 at 9 53 46 AM](https://github.com/UTXOnly/nost-py/assets/49233513/724cfbeb-03a0-4d10-b0d1-6b638ac153c4)


### Requirements

* Ubuntu 22.04 server (Will likely work on other versions but this is all that has been tested)
  * Both `arm64` and `amd64` supported
* At least 2 GB of available RAM (2 vCPU and 4GB RAM for heavy load)
* Your own domain


## Instructions

### Setup

To setup this relay:

* Git repo should be cloned in user's `$HOME` directory (you can install elsewhere but will need to adjust a number of variables w/ filepaths to function properly)
* Copy example env file:

```
cp ~/nostpy-relay/docker/env.example ~/nostpy-relay/docker/.env 
```

Update variables in the `~/nostpy-relay/docker/.env`, for example:
* All fields except for `DD_API_KEY` are mandatory
* Most of the existing values can be left but you will need to update/add:
  * Postgres `read/write` passwords:
    * `PGPASSWORD_WRITE`
    * `PGPASSWORD_READ`
  * `ADMIN_PUBKEY`
  * `DOMAIN`
  * `CONTACT`

```
PGDATABASE_WRITE=nostr
PGUSER_WRITE=nostr
PGPASSWORD_WRITE=nostr #CHANGEME
PGPORT_WRITE=5432
PGHOST_WRITE=172.28.0.4
PGDATABASE_READ=nostr
PGUSER_READ=nostr
PGPASSWORD_READ=nostr #CHANGEME
PGPORT_READ=5432
PGHOST_READ=172.28.0.4
EVENT_HANDLER_PORT=8009
EVENT_HANDLER_SVC=172.28.0.3 # hostname or IP for event handler service
WS_PORT=8008 #Websocket handler port
REDIS_HOST=redis
REDIS_PORT=6379
DD_API_KEY=#(If using Datadog exporter for OTel collector)
DOMAIN= #update to your own 
ADMIN_PUBKEY= #hexidecimal format
CONTACT= #YOUR_EMAIL, must be valid email for certbot to issue you a TLS certificate
ENV_FILE_PATH=./docker/.env
NGINX_FILE_PATH=/etc/nginx/sites-available/default
VERSION=v1.2.0
WOT_ENABLED=True #True or False
ICON="https://image.nostr.build/ca2fd20bdd90fe91525ffdd752a2773eb85c2d5a144154d4a0e6227835fa4ae1.jpg" #link to image or relay NIP11 doc, can replace with your own
DB_CONN_STRING="postgresql://nostr:nostr@127.0.0.1:5432/nostr"

```

Aside from adding the environmental variables, all you need to do is run the `menu.py` script to load the menu. Once you select the `Execute server setup script` option, the script will install all dependencies, create all service containers locally, including setting up your NGINX reverse proxy server, requesting TLS certificate. From there you are ready to start relaying notes!

To get started run the command below from the main repo direcotory to bring up the NostPy menu:

```
python3 menu.py
```

This will bring up the menu below and you can control the program from there!

**Usage notes**
* Option 1 `Execute server setup script` needs to be run to install all dependencies!!!




![image](https://github.com/user-attachments/assets/c662940b-9832-44fc-8993-ae982a0ab0d7)



![Screenshot from 2024-02-23 21-15-49](https://github.com/UTXOnly/nost-py/assets/49233513/2119a053-3ebf-42b5-a996-2ccb87651c9e)



### Install demo

* [Youtube video showing you how to clone and run nostpy](https://www.youtube.com/watch?v=9Fmu7K2_t6Y)

## Monitoring

This compose stack comes with a preconfigured OpenTelemety collector container and some custom instrumentation. the existing configuration collects system metrics about the host and docker containers as well as distributed tracing between the services. 

Will be adding log support soon, giving you full visibility into the health of your relay. 

![Screenshot from 2024-06-15 10-45-06](https://github.com/UTXOnly/nost-py/assets/49233513/36afbaf4-cf7d-497b-8bb1-d2a90b7fa0af)


## Web of Trust

Web of Trust (WoT) filters which users can post based on social connections.
* The relay scans the admin's follows and the follow lists of those users to build a trust network
* Only public keys followed by the admin and/or at least three others from this network can post
* This approach ensures that only trusted users can interact with the relay, preventing spam

### Web of Trust Setup

There are 2 options for setting up the web of trust:
* Select option 2 `Manually build Web of Trust` from `menu.py`
  * You should run this when you first deploy the relay if `WOT_ENABLED=True` otherwise no one will be able to write to the relay

* Set the `wot_builder.py` to run as a cronjob so your WoT is updated daily

To set the script to run every 24 hours a cronjob using the below example as a guide:

```bash
crontab -e
```
```bash
0 * * * * /usr/bin/python3 /home/ubuntu/nostpy-relay/docker/nostpy_relay/wot_builder.py >> /home/ubuntu/nostpy-relay/wot.log 2>&1
```

## Tor

Nostpy relay supports serving clients over clearnet and tor simultaneously. Simply select option 3 `Start Nostpy relay (Clearnet + Tor)` to spin up the comose stack with a tor proxy. Your tor hidden service name will be shared in the `menu.py` landing page or you can run `sudo cat ~/nostpy-relay/docker/tor/data/hidden_service/hostname` to find it.

## Relay Architecture 




### Future plans

This is relay is actively worked on, it's is only a proof of concept right now. Will contine to add features, bug fixes and documentation weekly, check back for updates. 

## Supported NIPs
*unchecked NIPS are on the roadmap*

- [x] NIP-01: Basic protocol flow description
- [x] NIP-02: Contact list and petnames
- [x] NIP-04: Encrypted Direct Message
- [x] NIP-09: Event deletion
- [x] NIP-11: Relay information document
- [] NIP-11a: Relay Information Document Extensions
- [] NIP-13: Proof of Work
- [x] NIP-15: End of Stored Events Notice
- [x] NIP-16: Event Treatment
- [x] NIP-25: Reactions
- [x] NIP-50: Search Capability
- [x] NIP-99: Classified Listings

### Contributing

If you would like to contribute feel free to fork and put in a PR! Also please report any bugs in the issues section of this repo.
