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