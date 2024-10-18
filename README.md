# rdmo-plugins-zenodo

This plugin implements an [export provider](https://rdmo.readthedocs.io/en/latest/plugins/index.html#export-providers) for RDMO, which lets users push metadata from RDMO to Zenodo work packages. The plugin uses [OAUTH 2.0](https://oauth.net/2/), so that users use their respective accounts in both systems. It creates only the metadata in Zenodo, so that users need to upload the actual data on Zenodo themselfes.

Setup
-----

Install the plugin in your RDMO virtual environment using pip (directly from GitHub):

```bash
pip install git+https://github.com/rdmorganiser/rdmo-plugins-zenodo
```

Add the plugin to `INSTALLED_APPS` in `config/settings/local.py`:

```python
INSTALLED_APPS += ['rdmo_zenodo']
```

Add the plugin to `PROJECT_EXPORTS` in `config/settings/local.py`:

```python
PROJECT_EXPORTS += [
    ('zenodo', _('Directly to Zenodo'), 'rdmo_zenodo.exports.ZenodoExportProvider'),
    ('zenodo-publish', _('Publish to Zenodo'), 'rdmo_zenodo.exports.ZenodoPublishProvider')
]
```

An *Developer applications* has to be registered with Zenodo here: https://zenodo.org/account/settings/applications/. For development, you can also use the sandbox instance provided by Zenodo: https://sandbox.zenodo.org/account/settings/applications/. During the registration, you need to enter a **Redirect URI** for your RDMO instance:

```
https://rdmo.example.com/services/oauth/zenodo/callback/
http://localhost:8000/services/oauth/zenodo/callback/     # for development
```

After registration, you are provided with a `client_id` and a `client_secret`, which need to be added to the RDMO settings, along with some other optional entries:

```python
ZENODO_PROVIDER = {
    'client_id': os.getenv('ZENODO_CLIENT_ID'),
    'client_secret':  os.getenv('ZENODO_CLIENT_SECRET'),
    'add_project_members': True,  # add the members of the project as creators to each dataset
    'resource_type': 'dataset',   # specify the resource type
    'language': 'eng',            # specify the language
    'publisher': '',              # specify the publisher
    'funding': [                  # specify funding information
        {
            'funder': {
                'name': 'Deutsche Forschungsgemeinschaft'
            },
            'award': {
                'title': {
                    'en': 'Excellence Strategy'
                },
                'number': 'EXC12345/6',
                'identifiers': [
                    {
                        'scheme': 'url',
                        'identifier': 'https://www.dfg.de/en/research-funding/funding-initiative/excellence-strategy'
                    }
                ]
            }
        }
    ]
}
```

Usage
-----

The plugins apears as export options on the RDMO project overview.
