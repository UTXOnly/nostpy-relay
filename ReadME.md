# Nostpy

A simple and easy to deploy nostr relay using `asyncio` & `websockets` to server Nostr clients

## Description

![nostpy_auto_x2_colored_toned_light_ai](https://user-images.githubusercontent.com/49233513/236724405-bea4f3da-8728-4b0f-b583-1944faf52d09.jpg)


A containerized Python relay paried with a Postgres databse, reachable via a NGINX reverse proxy. This has been tested on Iris and Snort.social clients and works for the NIPS listed below.

Numerous branches in development,trying to improve performance, reliability and ease of use. The Datadog branch deploys a Datadog agent container to collect logs, metrics and traces to better observe application performance.

### Requirements

* Ubuntu amd64 host server
* At least 1 GB of available RAM ( 4GB recomended )
* Your own domain

## Instructions

To run this program run the command below from the main repo direcotory to bring up the NostPy menu

```
python3 menu.py
```

This will bring up the menu below and you can control the program from there!

![image](https://user-images.githubusercontent.com/49233513/236729712-bb3963f9-0a13-4c8e-940b-6afd7dd7da4b.png)

### Future plans

This is relay is actively worked on, it's is only a proof of concept right now. Will contine to add features, bug fixes and documentation weekly, check back for updates. 

## Supported NIPs
*unchecked NIPS are on the roadmap*

- [x] NIP-01: Basic protocol flow description
- [x] NIP-02: Contact list and petnames
- [x] NIP-04: Encrypted Direct Message
- [] NIP-09: Event deletion
- [] NIP-11: Relay information document
- [] NIP-11a: Relay Information Document Extensions
- [] NIP-12: Generic tag queries
- [] NIP-13: Proof of Work
- [x] NIP-15: End of Stored Events Notice
- [x] NIP-16: Event Treatment
- [x] NIP-25: Reactions

### Contributing

If you would like to contribute feel free to fork and put in a PR! Also please report any bugs int he issues section of this repo.