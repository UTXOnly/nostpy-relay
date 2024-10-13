## v1.2.0

### Enhancements
**Added**
* Web of Trust authentication (Optional feature)
  * Users who have 3 mutal follows from the relay admin's 1st hop follows can post here


* Restructured project to use fit python standards
* Added more accurate HTTP response codes and relay ws replies 


**Removed**
* `.env` file encryption (may return at some point)

## v1.0.0

### Enhancements
**Added**
* Nginx reverse proxy container
* Support for OpenTelemetry
  * Traces and metrics over GRPC
  * OTel collector/Datadog exporter
* Support for both x86/ARM64 architecture for Python containers
* Upgraded Python containers to 3.11-slim base image
* Config option to configure seperate read/write database instances

**Removed**
* Nginx reverse proxy on host
* Python 3.9-slim base images
* Datadog Python tracer
* Datadog docker agent

**Bug fixes**
* Fixed [#53 Search functionality not getting relevent events to the search query](https://github.com/UTXOnly/nost-py/issues/53)
* Fixed [#55 Fail to add kind 0 notes, returns false positive OK "true" message](https://github.com/UTXOnly/nost-py/issues/55)

## v0.8

**Enhancements**
* Completed feature request [#37 [FR] Support for NIP-50 (search capability) for both content and tags](https://github.com/UTXOnly/nost-py/issues/37)
  * Support for [NIP-50](https://github.com/nostr-protocol/nips/blob/master/50.md#nip-50) search queries
  * Searches `tags` and `content` fields
  * Compatible with searching [NIP-99 Classified Listings](https://github.com/nostr-protocol/nips/blob/master/99.md)
 
* Completed feature request for [#38 [FR] Support NIP-09 Event Deletion](https://github.com/UTXOnly/nost-py/issues/38)
  * Add support for NIP-09 event deletions
  * Upon receiving a request from a client, relay will:
    * Check if event is `kind 5`
      * Validate the `sig` of the event
      * Delete events where `pubkey` = `pubkey` from `kind 5` event (can only delete your own events)
      * Respond to client with `["OK","true]` response

**Bug fixes**
* Fixed [#39 [BUG] Escape characters included in tag query](https://github.com/UTXOnly/nost-py/issues/39) 
* Fixed [#40 unbounded query limit](https://github.com/UTXOnly/nost-py/issues/40)

## v0.7
**Enhancements**
* Re-added redis cache to serve frequent queries faster
* Added event classes to `event_handler` service for readability and portability
* More efficient  use of coroutines
  * Use `asyncio.gather` to prepare and send responses to websocket client
  * Converted async methods to sync methods where appropriate to reduce overhead
* Added auto-multiline log detection for Datadog agent to more easily read stack traces
* Cleaned up noisy `DEBUG` log lines
* Better error handling for empty responses

**Bug Fixes**
* Fixed `websocket_handler` JSON loads error that occurred when loading empty payloads to no longer restart the websocket server
  * Server continues and maintains the websocket connection

## v0.6
**Enhancements**
* Obfuscate `client_ip` tag by using a hashed value for their ip address
  * Rate limiter is triggered off the hashed value, no `client ip` in any application logs
* Added docstrings for classes in `websocket_handler.py`
* Remove event verification from `handle_new_event` method (unnecessary as it is done by clients)
* Removed `SQLalchemy` in favor of async `psycopg3`
    * Faster
    * Smaller memory footprint
    * More control over dynamically constructed queries
* Slight redesign of database schema to store `tags `in `JSONB` format
  * Easier to query individual tags
  * Improved query performance from executing `tag` search as a function scan
  * Remove high cardinality `indexes` , leaving indexes only on `pubkey` and `kind`
* `event-handler` service broken up into smaller `async` functions , with better error handling and more specific error messages
* Updated [Database Monitoring setup script](https://github.com/DataDog/Miscellany/tree/master/dbm_setup)

**Bug Fixes**
* Tags not being added to query filter, [Issue #28](https://github.com/UTXOnly/nost-py/issues/28)
  * Tags are now stored in `JSONB` format and use valid and dynamically constructed queries


## v0.5

**Enhancements**
* Add `client_ip` and `nostr_client` tag to rate limit and current token count metrics 
* Add `stop_containers` option to main menu to be able to stop containers without having to rebuild
* [Database Monitoring](https://docs.datadoghq.com/database_monitoring/setup_postgres/selfhosted/?tab=postgres10) setup script added to main menu to create Datadog schema in every available databse and enable `pg_stat_statements` + explain statements
* Add pylint numerical score badge to readme

**Bug Fixes**
* Resolved bugs in `menu.py` that were made it necessary to exit the main menu or encryption sub-menu to continue running commands
    * Related issues
        * #16
        * #20

## v0.4

**Enhancements**
* Add token based websocket rate limiter to websocket handler
    * Closes websocket connection and sends client `"OK"` rate limit message
        * Limits by client IP address
        * Sends `gauge` metric with `client` tag to StatsD server to keep track of rate limited clients 
    * After some time passes, token bucket is refilled and client can make requests again provided they stay under their rate limit
* Reply to client with `"NOTICE"` message when subscription closes
    * Also sends `"OK"` `true` message to client when event successfully added
* Many organizational improvements in websocket handler
    * New `ExtractedResponse` and `WebsocketMessages` help organize and make for more readable code
        * Parse and format messages outside of the handler functions

**Bug Fixes**
* Fixed duplicate `EOSE` message returned to client from websocket subscription handler 
* Fixed `redis` cached result parsing bug that was returning a single `]` as content for a `REQ` message when `redis` cache returned  `b"[]"`
    * Try/except block for parsing, does not send `redis` results less than 2 charecters back to websocket handler, instead sends `EOSE` 

## v0.3

Updates installer to resolve the issues raised in #11 

**Addressed the following:**

* Shell injection vulnerability
    * `os.system()` calls have been replaced by `subprocess.run()` and checks the output before proceeding with the script
        * Reads though list of arguments
    * Environmental variables are loaded from `.env` file, overwriting any existing env var
* Insecure file permissions
    * Only file permission that is changed is the `.env` file to limit access (`600`)
    * Otherwise access is granted to file through an `ACL` by adding `relay_service` group read permissions
* Sensitive data exposure
    * No longer echo `script_user` in setup script
    * No longer need to learn the script user, took a different approach to granting file access
* Arbitrary File Deletion
    * Just use simple `rm` to delete the existing `default` NGINX config
* Unchecked return values
    * All `subprocess.run()` calls check return values
        * If not explicitly checked, nested withing `try`/`except` blocks
* Insecure Temporary File
    * Better error handling for checking if file exists before overwriting

**Enhancements**
* Added encryption to `.env` file when at rest
    * Gathers user supplied password, uses key stretching with a ` Fernet` key to encrypt file
    * Programmaticlly re-encrypts `.env` file after starting docker compose stack
    * Includes main menu option to `decrypt`/`encrypt` `.env` file for editing

**Bug fixes**
* Mounts Postgres data to host file system for persistent storage
   * Was left previously unmounted for testing purposes
