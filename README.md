# tap-paycor

This is a [Singer](https://singer.io) tap that produces JSON-formatted data following the [Singer spec](https://github.com/singer-io/getting-started/blob/master/SPEC.md).

## Useful links

- [Paycor Developer Guides](https://developers.paycor.com/guides)
- [Paycor App Creator Portal](https://developers.paycor.com/app-creator/summary)
- [Paycor OpenAPI test console](https://developers.paycor.com/try)

## Gaining API access

Paycor uses a very strict implementation of OAuth. Access tokens expire after 30 minutes, and refresh tokens **are only valid for a single use**. This means that after any successful call to get a new access token, the new refresh token returned along side it **must be captured** or the customer admin will have to be asked to go through "activation" again for us.

### Obtaining initial tokens

Once an initial set of access+refresh tokens are obtained, they can be continuously refreshed by your application via the refresh token. Initially obtaining the token requires the following steps be taken by a user with administrative access to Paycor. No other type of user will be able to complete the process, despite it appearing in the Paycor developer UI like you can.

1. Open <https://hcm.paycor.com/appactivation/clientactivation>
2. Login with your admin Paycor account
3. Select your client application (there is likely only one available) and accept terms
4. Fill in Client ID and Client Secret from the developer portal
5. Capture both the access and refresh tokens provided

## API Sandbox

The `./api-sandbox` directory contains a set of bash scripts for demonstrating access to desired data as well as for managing authorization credentials. The directory contains scripts that developers may find helpful in exploring the API. The `access-refresh` and the `get-employees` scripts are particularly helpful for testing.
### Getting started

1. Create new `.env` file:

    ```bash
    cd ./api-sandbox/
    cp env.example .env
    ```

2. Edit `.env` and populate API credentials and entity/tenant IDs

    **Ensure that this file is never committed to source control, the `api-sandbox` directory is already configured to ignore it**

3. Populate initial `api-sandbox/.tokens.json` with access+refresh tokens obtained during activation:

    ```json
    {
        "access_token": "ey...",
        "refresh_token": "12ef..."
    }
    ```

    **Ensure that this file is never committed to source control, the `api-sandbox` directory is already configured to ignore it**

### Working with access token

Assumming you've already run `cd ./api-sandbox/`:

- Check whether the current access token is valid without touching anything:

    ```console
    $ ./access-validate
    Connection successful, found access to 1 entities
    ```

- Ensure that an access token is available by checking and then refreshing it if needed:

    ```console
    $ ./access-refresh

    ==> access-refresh: checking if existing token is valid???
    curl: (22) The requested URL returned error: 401
    Failed to access entities list

    ==> access-refresh: requesting new tokens from Paycor API???
    New token acquired, writing to .tokens.json
    renamed '.tokens.tmp.json' -> '.tokens.json'
    ```

### Working with test requests

Assumming you've already run `cd ./api-sandbox/` and verified an access token is available:

- List activated legal entities:

    ```bash
    ./get-entities
    ```

### Testing schema

The included `employees.json` schema can be verified by testing it against real API results:

1. Install `ajv` command:

    ```bash
    npm install -g ajv-cli ajv-formats
    ```

2. Validate API results against schema wrapped in array definition:

    ```bash
    ajv validate \
        --strict=true \
        -c ajv-formats \
        -s <(jq '{type: "array", items: .}' ../tap-paycor/schemas/employees.json) \
        -d <(./get-employees)

    ```
## Working with Paycor's API console

Paycor has an OpenAPI console hosted at <https://developers.paycor.com/try>

To make authenticated calls with it:

1. Ensure local API sandbox has valid tokens (see above)
2. Print the current access token to your console and copy it:

    ```bash
    jq -r '.access_token' .tokens.json
    ```

3. In the online API console, click the **Authorize** button at the top right of the page
4. For **Access Token**, type in the prefix `Bearer ` and then paste the access token, so that it looks like `Bearer eyABC...`
5. For **Apim-Subscription-Key**, paste the subscription key available in the developer portal

## Using the tap

Once proper access has been verified, run the tap:
1. Install

    pip install tap-paycor

2. Create the config file

    Create a JSON file called `config.json`. Its contents should look like:

   ```json

    {
        "client_id": "your-application-oauth-client-id",
        "client_secret": "your-application-oauth-client-secret",
        "access_token": "your-token",
        "expires_in": 1800,
        "token_type": "Bearer",
        "refresh_token": "your-refresh-token",
        "api_subscription_key": "your-key",
        "tenant_id": "123456",
        "start_date": "YYYY-MM-DD",
        "legal_entity_id": "678910"
    }

    ```

    CONFIG is a required argument that points to a JSON file containing any
    configuration parameters the Tap needs. This tap supports [discovery mode](DISCOVERY_MODE.md), which is used to obtain the catalog.

3. Obtain the catalog

```bash
tap-paycor --config config.json --discover > catalog.json
```

4. Alter the catalog
    Within the catalog.json file, you may need to add metadata in the catalog for [stream/field selection](SYNC_MODE.md#streamfield-selection) or [replication-method](SYNC_MODE.md#replication-method).

    Below `"stream": "employees",` Add

    ```json
    "metadata": [
            {
            "breadcrumb": [],
            "metadata": {
            "selected": true
            }
            }
        ]
    ```

    This will select the employee stream.
5. Run the Tap in sync mode

```bash
tap-paycor --config tap_config.json --catalog catalog.json
```
The output should consist of Schema and Record messages

### Helpful debugging
When running the tap, [singer-tools](https://github.com/singer-io/singer-tools) is helpful to verify the tap information.

Sometimes it's convenient to validate the output of a tap, rather have
`singer-check-tap` actually run the tap. You can do that by omitting the
`--tap` argument and providing the Tap output on STDIN. For example:

```bash
tap-paycor --config config.json | singer-check-tap
```

In this mode of operation, `singer-check-tap` will just validate the data
on stdin and exit with a status of zero if it's valid or non-zero
otherwise.

#### Sample data

You can try `singer-check-tap` out on the data in the `samples` directory.

##### A good run:

```
$ singer-check-tap < samples/fixerio-valid-initial.json
Checking stdin for valid Singer-formatted data
The output is valid.
It contained 328 messages for 1 streams.

      1 schema messages
     328 record messages
     0 state messages

Details by stream:
+---------------+---------+---------+
| stream        | records | schemas |
+---------------+---------+---------+
| employees     | 328     | 1       |
+---------------+---------+---------+
```



#### A bad run:

```
$ singer-check-tap < samples/fixerio-invalid-no-key-properties.json
Checking stdin for valid Singer-formatted data
Traceback (most recent call last):
  File "/opt/code/singer-tools/venv/bin/singer-check-tap", line 11, in <module>
    load_entry_point('singer-tools', 'console_scripts', 'singer-check-tap')()
  File "/opt/code/singer-tools/singertools/check_tap.py", line 195, in main
    summary = summarize_output(sys.stdin)
  File "/opt/code/singer-tools/singertools/check_tap.py", line 90, in summarize_output
    summary.add(singer.parse_message(line))
  File "/opt/code/singer-tools/venv/lib/python3.4/site-packages/singer_python-0.2.1-py3.4.egg/singer/__init__.py", line 117, in parse_message
    key_properties=_required_key(o, 'key_properties'))
  File "/opt/code/singer-tools/venv/lib/python3.4/site-packages/singer_python-0.2.1-py3.4.egg/singer/__init__.py", line 101, in _required_key
    k, msg))
Exception: Message is missing required key 'key_properties': {'stream': 'exchange_rate', 'schema': {'properties': {'date': {'format': 'date-time', 'type': 'string'}}, 'additionalProperties': True, 'type': 'object'}, 'type': 'SCHEMA'}
```

### Common Error responses

If you return this message when running singer-check-tap:

`simplejson.scanner.JSONDecodeError: Expecting value: line 1 column 1 (char 0)`

It means you need to refresh the token.
