# Nostpy

A simple and easy to deploy nostr relay using `asyncio` & `websockets` to server Nostr clients

## Description

![nostpy_auto_x2_colored_toned_light_ai](https://user-images.githubusercontent.com/49233513/236724405-bea4f3da-8728-4b0f-b583-1944faf52d09.jpg)


A containerized Python relay paried with a Postgres databse and reachable via a NGINX reverse proxy. This has been tested on Iris and Snort.social clients and works for the NIPS listed below.

Numerous branches in development,trying to improve performance, reliability and ease of use. The Datadog branch deploys a Datadog agent container to collect logs, metrics and traces to better observe application performance.

### Requirements

* Ubuntu amd64 host server
* At least 1 GB of available RAM ( 4GB recomended )
* Your own domain


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

