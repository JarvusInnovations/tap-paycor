# tap-paycor

A Singer tap for Paycor

## API Sandbox

The `./api-sandbox` directory contains a set of bash scripts for demonstrating access to desired data as well as for managing authorization credentials.

### Authorization credentials

Paycor uses a very strict implementation of OAuth. Access tokens expire after 30 minutes, and refresh tokens **are only valid for a single use**. This means that after any successful call to get a new access token, the new refresh token returned along side it **must be captured** or the customer admin will have to be asked to go through "activation" again for us.

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

    ==> access-refresh: checking if existing token is valid…
    curl: (22) The requested URL returned error: 401
    Failed to access entities list

    ==> access-refresh: requesting new tokens from Paycor API…
    New token acquired, writing to .tokens.json
    renamed '.tokens.tmp.json' -> '.tokens.json'
    ```

### Working with test requests

Assumming you've already run `cd ./api-sandbox/` and verified an access token is available:

- List activated legal entities:

    ```bash
    ./get-entities
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