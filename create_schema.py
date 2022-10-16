# This is a script I (chriscauley) used to generate the schema from the sample data.
# TODO do we want to keep this for reference/future use?

import json
import sys
import re

def snake_case(s):
  return '_'.join(
      re.sub(
          '([A-Z][a-z]+)',
          r' \1',
          re.sub('([A-Z]+)', r' \1', s.replace('-', ' '))
      ).split()).lower()

targets = ['Person', 'EmployeeTimeOffRequest', 'EmployeeCustomField']

with open('swagger.json', 'r') as f:
    swagger = json.loads(f.read())

def de_ref(field):
    if not '$ref' in field:
        return
    path = field.pop('$ref')
    name = path.split('/')[-1]
    field.update(resolve(swagger['components']['schemas'][name]))

def resolve(schema):
    de_ref(schema)
    schema.pop('x-enumNames', '')
    if not 'properties' in schema:
        return schema
    required = []
    for key in list(schema['properties'].keys()):
        new_key = key[0].lower() + key[1:]
        schema['properties'][new_key] = schema['properties'].pop(key)
    for key, field in schema['properties'].items():
        # remove references
        de_ref(field)
        de_ref(field.get('items', {}))
        for child_schema in field.get('allOf', []):
            resolve(child_schema)
        if field.get('type') == 'object':
            schema[key] = resolve(field)

        # clear out some non-jsonschema irregularities
        if 'description' in field:
            field['description'] = field['description'].strip()
        field.pop('example', None)
        field.pop('xml', None)
        if field.pop('nullable', False):
            if not 'type' in field:
                print('missing type for', key)
                continue
            if isinstance(field.get('type'), str):
                field['type'] = [field['type']]
            field['type'].append('null')
        else:
            required.append(key)

    if required:
        schema['required'] = required
    return schema

for target in targets:
    result = json.dumps(resolve(swagger['components']['schemas'][target]), indent=4)
    slug = snake_case(target)
    if slug == 'employee_time_off_request':
        slug = 'time_off_request'

    fname = f'tap_paycor/schemas/{slug}s.json'
    with open(fname, 'w') as f:
        f.write(result)
    print(f'wrote {target} as {fname}')