# Nostpy

![Pylint_score](./pylint.svg) 

A purely Python, easy to deploy nostr relay using `asyncio` & `websockets` to server Nostr clients

## Description

![Image 2023-09-15 at 9 53 46 AM](https://github.com/UTXOnly/nost-py/assets/49233513/724cfbeb-03a0-4d10-b0d1-6b638ac153c4)



A containerized Python relay paried with a Postgres databse, reachable via a NGINX reverse proxy. This has been tested on [Nostrudel](https://nostrudel.ninja/), [Iris.to](https://Iris.to) and [Snort.social](https://Snort.social) clients and works for the NIPS listed below.

Numerous branches in development, trying to improve performance, reliability and ease of use. The Datadog branch deploys a Datadog agent container to collect logs, metrics and traces to better observe application performance.

### Requirements

* Ubuntu 22.04 amd64 host server (Will likely work on other versions but this is all that has been tested)
* At least 2 GB of available RAM ( 4GB recomended )
* Your own domain
* Right now the main branch deploys the Datadog agent along with the application containers and has APM, DBM, and NPM preconfigured as well as some custom nostr StatsD metrics.
  * If you don't have a Datadog developer account, you can apply for a developer account [here](https://partners.datadoghq.com/s/login/?ec=302&startURL=%2Fs%2F), or sign up for a trial [here](https://www.datadoghq.com/free-datadog-trial/) to get a Datadog API key. 
  * If you don't want to use the Datadog agent, simply don't enter the `DD_API_KEY` variable in the `.env` file and comment the service out from the `docker-compose.yaml` file.

## Instructions

### Setup

To setup this program, you need to update the variables in the `nostpy/docker_stuff/.env`, for example:

```
POSTGRES_DB=nostr
POSTGRES_USER=nostr
POSTGRES_PASSWORD=nostr
POSTGRES_PORT=5432
POSTGRES_HOST=localhost
DD_ENV=<DATADOG_ENV_TAG>
DD_API_KEY=<YOUR_DATADOG_API_KEY>
DOMAIN_NAME=<YOUR_DOMAIN_NAME>
HEX_PUBKEY=<YOUR_HEX_PUBLIC_KEY_FOR_NIP_11>
CONTACT=<YOUR_EMAIL_OR_NPUB>
ENV_FILE_PATH=./docker_stuff/.env
NGINX_FILE_PATH=/etc/nginx/sites-available/default
VERSION=v0.8

```

Aside from adding the environmental variables, all you need to do is run the `menu.py` script to load the menu. Once you select the `Execute server setup script` option, the script will install all dependencies, setup your NGINX reverse proxy server and request an TLS certificate, load environmental variables, build and launch the application and database containers. From there you are ready to start relaying notes!

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


![image](https://github.com/UTXOnly/nost-py/assets/49233513/c970f4a8-8af3-4b23-a6fe-3fc9bac49ec0)


### Install demo

* [Youtube video showing you how to clone and run nostpy](https://www.youtube.com/watch?v=9Fmu7K2_t6Y)




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
