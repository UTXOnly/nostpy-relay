# Nostpy

![Pylint_score](./pylint.svg) 

A purely Python, easy to deploy nostr relay using `asyncio` & `websockets` to serve Nostr clients

## Description

![Image 2023-09-15 at 9 53 46 AM](https://github.com/UTXOnly/nost-py/assets/49233513/724cfbeb-03a0-4d10-b0d1-6b638ac153c4)



A 100% containerized Python relay backed by a Postgres database, behind a NGINX reverse proxy. This has been tested on [Nostrudel](https://nostrudel.ninja/), [Iris.to](https://Iris.to) and [Snort.social](https://Snort.social, [Damus.io](https://damus.io/)) clients and works for the NIPS listed below.

Numerous branches in development, trying to improve performance, reliability and ease of use. 

### Requirements

* Ubuntu 22.04 server (Will likely work on other versions but this is all that has been tested)
  * Both `arm64` and `amd64` supported
* At least 2 GB of available RAM
* Your own domain


## Instructions

### Setup

To setup this program, you need to update the variables in the `nostpy/docker_stuff/.env`, for example:

```
PGDATABASE_WRITE=<POSTGRES_WRITE_DATABASE>
PGUSER_WRITE=<POSTGRES_WRITE_USER>
PGPASSWORD_WRITE=<POSTGRES_WRITE_PASSWORD>
PGPORT_WRITE=<POSTGRES_WRITE_PORT>
PGHOST_WRITE=<POSTGRES_WRITE_HOST>
PGDATABASE_READ=<POSTGRES_READ_DATABASE>
PGUSER_READ=<POSTGRES_READ_USER>
PGPASSWORD_READ=<POSTGRES_READ_PASSWORD>
PGPORT_READ=<POSTGRES_READ_PORT>
PGHOST_READ=<POSTGRES_READ_HOST>
DD_ENV=<DATADOG_ENV_TAG>
EVENT_HANDLER_PORT=8009
EVENT_HANDLER_SVC=172.28.0.3 # hostname or IP for event handler service
WS_PORT=8008 #Websocket handler port
REDIS_HOST=redis
REDIS_PORT=6379
DD_API_KEY=<DATADOG_API_KEY_> (If using Datadog exporter for OTel collector)
DOMAIN=<YOUR_DOMAIN_NAME>
HEX_PUBKEY=<RELAY_ADMIN_HEX_PUBKEY>
CONTACT=<RELAY_ADMIN_EMAIL>
ENV_FILE_PATH=./docker_stuff/.env
NGINX_FILE_PATH=/etc/nginx/sites-available/default
VERSION=v1.0.0

```

Aside from adding the environmental variables, all you need to do is run the `menu.py` script to load the menu. Once you select the `Execute server setup script` option, the script will install all dependencies, create all service containers locally, including setting up your NGINX reverse proxy server, requesting TLS certificate. From there you are ready to start relaying notes!

To get started run the command below from the main repo direcotory to bring up the NostPy menu:

```
python3 menu.py
```

This will bring up the menu below and you can control the program from there!

**Usage notes**
* Option 1 `Execute server setup script` needs to be run to create the `relay_service` user and set proper file permissions
* After creating the `.env` that file is meant to stay encrypted(encrypted suring `Execute server script`), option2 `Start Nostpy relay` will not run unless the file is encypted
  * You can encrypt/decrypt the file with option 5 



![Image 2023-09-15 at 8 44 45 AM](https://github.com/UTXOnly/nost-py/assets/49233513/ee40d91c-2e6a-48a8-a0a8-c14e25e8ff07)


![Screenshot from 2024-02-23 21-15-49](https://github.com/UTXOnly/nost-py/assets/49233513/2119a053-3ebf-42b5-a996-2ccb87651c9e)



### Install demo

* [Youtube video showing you how to clone and run nostpy](https://www.youtube.com/watch?v=9Fmu7K2_t6Y)

## Monitoring

This compose stack comes with a preconfigured OpenTelemety collector container and some custom instrumentation. the existing configuration collects system metrics about the host and docker containers as well as distributed tracing between the services. 

Will be adding log support soon, giving you full visibility into the health of your relay. 

![Screenshot from 2024-06-15 10-45-06](https://github.com/UTXOnly/nost-py/assets/49233513/36afbaf4-cf7d-497b-8bb1-d2a90b7fa0af)


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
