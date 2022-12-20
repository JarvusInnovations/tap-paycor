import datetime
import os
import json
import singer
from singer import utils, metadata
from singer.catalog import Catalog, CatalogEntry
from singer.schema import Schema
import requests


REQUIRED_CONFIG_KEYS = [
    "access_token",
    "refresh_token",
    "api_subscription_key",
    "legal_entity_id",
    "tenant_id",
    "legal_entity_id",
    "client_secret",
    "client_id",
    "api_host",
]


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
            data = json.load(file)
            schemas[file_raw] = {
                "schema": Schema.from_dict(data['schema']),
                "key_properties": data['key_properties']
            }
    return schemas


def discover():
    raw_schemas = load_schemas()
    streams = []
    for stream_id, stream_data in raw_schemas.items():
        stream_metadata = []
        streams.append(
            CatalogEntry(
                tap_stream_id=stream_id,
                stream=stream_id,
                schema=stream_data['schema'],
                key_properties=stream_data['key_properties'],
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
    root_url = 'https://' + args.config.get('api_host', 'apis.paycor.com')
    LOGGER.info(f"refreshing secret token against {root_url}")
    key = args.config['api_subscription_key']
    url = f"{root_url}/sts/v1/common/token?subscription-key={key}"
    headers = { "content-type": "application/x-www-form-urlencoded" }
    data = {
        "grant_type": "refresh_token",
        "refresh_token": args.config['refresh_token'],
        "client_id": args.config['client_id'],
        "client_secret": args.config['client_secret'],
    }
    response = requests.post(url, data=data, headers=headers)
    try:
        response.raise_for_status()
    except requests.exceptions.HTTPError as error:
        # todo need someway to log and notify. DAG is dead until this is fixed
        LOGGER.error(f"Token refresh response: {response.content}")
        raise error

    # update args with new config
    data = response.json()
    args.config['access_token'] = data['access_token']
    args.config['refresh_token'] = data['refresh_token']

    # write new config to disk
    with open(args.config_path, 'w') as f:
        f.write(json.dumps(args.config, indent=2))
        LOGGER.info(f"wrote updated secret tokens to {args.config_path}")


def sync(args, STATE, catalog):
    config = args.config
    bookmark_property = 'updated_at'
    employee_ids = None
    for stream in catalog.get_selected_streams(STATE):
        singer.write_schema(
            stream_name=stream.tap_stream_id,
            schema=stream.schema.to_dict(),
            key_properties=stream.key_properties,
        )
        if stream.tap_stream_id == 'employee_custom_fields':
            if employee_ids is None:
                # this must be handled in employees
                raise ValueError('You must tap employees before employee_custom_fields')
            for employee_id in employee_ids:
                get_records(args, stream, employee_id)
            continue
        elif stream.tap_stream_id == 'time_off_requests':
            start_date = datetime.date.today() + datetime.timedelta(days=-364)
            final_date = datetime.date.today() + datetime.timedelta(days=365)
            while start_date < final_date:
                get_records(args, stream, start_date=start_date)
                start_date += datetime.timedelta(days=91)
        else:
            record_ids = get_records(args, stream)
        if stream.tap_stream_id == 'employees':
            employee_ids = record_ids


def get_headers(args):
    access_token = "Bearer " + args.config["access_token"]
    subscription_key = args.config['api_subscription_key']

    return {
        "accept": "application/json",
        "Authorization" : access_token,
        "Ocp-Apim-Subscription-Key": subscription_key
    }


def get_request(url, args):
    response = requests.get(url, headers=get_headers(args))
    if response.status_code == 401:
        refresh_token(args)
        response = requests.get(url, headers=get_headers(args))
    return response


def get_records(args, stream, employee_id=None, start_date=None):
    config = args.config
    entity_id = config['legal_entity_id']
    tap_stream_id = stream.tap_stream_id
    if tap_stream_id == 'employees':
        path = f"/v1/legalentities/{entity_id}/employees?include=All"
    elif tap_stream_id == 'persons':
        path = f'/v1/legalEntities/{entity_id}/persons'
    elif tap_stream_id == 'employee_custom_fields':
        path = f'/v1/employees/{employee_id}/customfields'
    elif tap_stream_id == 'time_off_requests':
        end_date = start_date + datetime.timedelta(90)
        qs = f'startDate={start_date}&endDate={end_date}'
        path = f'/v1/legalentities/{entity_id}/timeoffrequests?{qs}'
    else:
        raise NotImplementedError(f'Unknown tap stream: {tap_stream_id}')

    root_url = 'https://' + config.get('api_host', 'apis.paycor.com')

    url = f"{root_url}{path}"

    bookmark_column = stream.replication_key
    is_sorted = True  # TODO: indicate whether data is sorted ascending on bookmark value

    has_more_results = True
    ids = []

    while True:
        LOGGER.info(f"getting {stream.tap_stream_id} at url {url}")
        start = datetime.datetime.now()
        r = get_request(url, args)
        LOGGER.info(f'{r.status_code} {(datetime.datetime.now()-start).total_seconds()}')
        tap_data = r.json()
        if 'is invalid or has no' in tap_data.get('Detail', ''):
            # When there are no entities, Paycor sends back a 400 with a message like
            # 'Either Legal Entity ID ### is invalid or has no TimeOff requests.'
            break
        for row in tap_data['records']:
            # LOGGER.info(f"Syncing {stream.tap_stream_id} {row}")

            singer.write_record(stream.tap_stream_id, row, time_extracted=singer.utils.now())
            record = row.get('record', row)
            ids.append(row.get('id') or row.get('customFieldId'))
        if not tap_data['hasMoreResults']:
            break
        LOGGER.info("Grabbing another page")
        url = f"{root_url}{tap_data['additionalResultsUrl']}"

    return ids


@utils.handle_top_exception(LOGGER)
def main():
    # Parse command line arguments
    args = utils.parse_args(REQUIRED_CONFIG_KEYS)

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
        sync(args, args.state, catalog)


if __name__ == "__main__":
    main()