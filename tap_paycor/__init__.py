import os
import json
import singer
from singer import utils, metadata
from singer.catalog import Catalog, CatalogEntry
from singer.schema import Schema
import requests


REQUIRED_CONFIG_KEYS = ["access_token", "refresh_token", "api_subscription_key", "legal_entity_id"] 
LOGGER = singer.get_logger()
STATE = {}

def get_abs_path(path):
    return os.path.join(os.path.dirname(os.path.realpath(__file__)), path)


def load_schemas():
    """ Load schemas from schemas folder """
    schemas = {}
    for filename in os.listdir(get_abs_path('schemas')):
        path = get_abs_path('schemas') + '/' + filename
        file_raw = filename.replace('.json', '')
        with open(path) as file:
            schemas[file_raw] = Schema.from_dict(json.load(file))
    return schemas


def discover():
    raw_schemas = load_schemas()
    streams = []
    for stream_id, schema in raw_schemas.items():
        # TODO: populate any metadata and stream's key properties here..
        stream_metadata = []
        key_properties = []
        streams.append(
            CatalogEntry(
                tap_stream_id=stream_id,
                stream=stream_id,
                schema=schema,
                key_properties=key_properties,
                metadata=stream_metadata,
                replication_key=None,
                is_view=None,
                database=None,
                table=None,
                row_count=None,
                stream_alias=None,
                replication_method=None,
            )
        )
    return Catalog(streams)


def refresh_token(args):
    root_url = 'https://apis.paycor.com'
    config = args.config
    key = os.environ['PAYCOR_API_SUBSCRIPTION_KEY']
    url = f"{root_url}/sts/v1/common/token?subscription-key={key}"
    headers = { "content-type": "application/x-www-form-urlencoded" }
    data = {
        "grant_type": "refresh_token",
        "refresh_token": os.environ["PAYCOR_REFRESH_TOKEN"],
        "client_id": os.environ["PAYCOR_CLIENT_ID"],
        "client_secret": os.environ["PAYCOR_CLIENT_SECRET"],
    }
    response = requests.post(url, data=data, headers=headers)
    try:
        response.raise_for_status()
    except requests.exceptions.HTTPError as error:
        # todo need someway to log and notify. DAG is dead until this is fixed
        raise error

    # update args with new config
    args.config = response.json()

    # write new config to disk
    with open(args.config_path, 'w') as f:
        f.write(args.config)

def sync(config, STATE, catalog):
    bookmark_property = 'updated_at'

    """ Get request access credentials from config"""

    data = config
    access_token = "Bearer " + data["access_token"]
    subscription_key = data['api_subscription_key']
    entity_id = data['legal_entity_id']

    url = f"https://apis.paycor.com/v1/legalentities/{entity_id}/employees?include=All"
    headers = {
        "accept": "application/json",
        "Authorization" : access_token,
        "Ocp-Apim-Subscription-Key": subscription_key
    }

    """ Sync data from tap source """
    # Loop over selected streams in catalog, while we dont use state is require for get_selected_streams method
    for stream in catalog.get_selected_streams(STATE):
        LOGGER.info("Syncing stream:" + stream.tap_stream_id)

        bookmark_column = stream.replication_key
        is_sorted = True  # TODO: indicate whether data is sorted ascending on bookmark value

        singer.write_schema(
            stream_name=stream.tap_stream_id,
            schema=stream.schema.to_dict(),
            key_properties=stream.key_properties,
        )
        has_more_results = True
        
        while has_more_results:
            r = requests.get(url, headers=headers)
            tap_data = r.json()
            for row in tap_data['records']:
                LOGGER.info("Syncing {}".format(row))
    
            # write one or more rows to the stream:
                ##utils.update_state(STATE, row, singer.utils.now())
                singer.write_record(stream.tap_stream_id, row, time_extracted=singer.utils.now())
            if tap_data['hasMoreResults']:
                LOGGER.info("Grabbing another page")
                url = f"https://apis.paycor.com/{tap_data['additionalResultsUrl']}"
            else:
                has_more_results = False
    ##singer.write_state(STATE)
    return


@utils.handle_top_exception(LOGGER)
def main():
    # Parse command line arguments
    args = utils.parse_args(REQUIRED_CONFIG_KEYS)
    refresh_token(args)

    # If discover flag was passed, run discovery mode and dump output to stdout
    if args.discover:
        catalog = discover()
        catalog.dump()
    # Otherwise run in sync mode
    else:
        if args.catalog:
            catalog = args.catalog
        else:
            catalog = discover()
        sync(args.config, args.state, catalog)


if __name__ == "__main__":
    main()