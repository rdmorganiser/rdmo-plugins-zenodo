import logging

from django.conf import settings
from django.shortcuts import reverse

from rdmo.projects.exports import Export
from rdmo.services.providers import OauthProviderMixin

from rdmo_zenodo.exports.metadata.builder import METADATA_METHODS, extract_metadata, serialize_payload, validate_schema
from rdmo_zenodo.exports.metadata.context import MetadataContext

logger = logging.getLogger(__name__)

json_header = {
    'Content-Type': 'application/json',
    }
binary_header = {
    'Content-Type': 'application/octet-stream',
}


class BaseZenodoExportProvider(OauthProviderMixin, Export):

    @property
    def client_id(self):
        return settings.ZENODO_PROVIDER['client_id']

    @property
    def client_secret(self):
        return settings.ZENODO_PROVIDER['client_secret']

    @property
    def zenodo_url(self):
        return settings.ZENODO_PROVIDER.get('zenodo_url', 'https://zenodo.org').strip('/')

    @property
    def zenodo_backend_type(self):
        if 'zenodo' in self.zenodo_url:
            return 'zenodo'
        return 'invenio'

    @property
    def authorize_url(self):
        return f'{self.zenodo_url}/oauth/authorize'

    @property
    def token_url(self):
        return f'{self.zenodo_url}/oauth/token'

    @property
    def redirect_path(self):
        return reverse('oauth_callback', args=[self.key])

    @property
    def authorization_header(self):
        return self.get_authorization_headers(self.get_from_session(self.request, 'access_token'))

    @property
    def authorization_scope(self):
        if scope := settings.ZENODO_PROVIDER.get('zenodo_auth_scope'):
            return scope
        if self.zenodo_backend_type == 'zenodo':
            return 'deposit:write'
        return 'user:email'

    @property
    def authorized_binary_header(self):
        return {**binary_header, **self.authorization_header}

    @property
    def authorized_json_header(self):
        return {**json_header, **self.authorization_header}

    def record_uploads_url(self, record_id):
        return f"{self.zenodo_url}/uploads/{record_id}"

    @property
    def records_url(self):
        return f'{self.zenodo_url}/api/records'

    def record_url(self, record_id):
        return f"{self.records_url}/{record_id}"

    def record_draft_url(self, record_id):
        return f"{self.records_url}/{record_id}/draft"

    def record_versions_url(self, record_id):
        return f"{self.records_url}/{record_id}/versions"

    def record_file_url(self, record_id):
        return f"{self.record_draft_url(record_id)}/files"

    def record_file_content_url(self, record_id, file_key):
        return f"{self.record_file_url(record_id)}/{file_key}/content"

    def record_file_commit_url(self, record_id, file_key):
        return f"{self.record_file_url(record_id)}/{file_key}/commit"

    def record_publish_url(self, record_id):
        return f"{self.record_draft_url(record_id)}/actions/publish"

    def get_authorize_params(self, request, state):
        return {
            'response_type': 'code',
            'client_id': self.client_id,
            'scope': self.authorization_scope,
            'redirect_uri': request.build_absolute_uri(self.redirect_path),
            'state': state
        }

    def get_callback_data(self, request):
        return {
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'grant_type': 'authorization_code',
            'redirect_uri': request.build_absolute_uri(self.redirect_path),
            'code': request.GET.get('code')
        }

    def post_with_retry(self, request, url, data):
        response = self.post(request, url, data)
        # Hacky way: in case of OAuth error (from e.g. 403), pop access_token and re-try
        if 'OAuth' in response.content.decode():
            self.pop_from_session(request, 'access_token')
            response = self.post(request, url, data)
        return response

    def get_metadata_context(self, set_index=None):
        return MetadataContext(
            project=self.project,
            snapshot=self.snapshot,
            set_index=set_index,
            get_values=self.get_values,
            get_text=self.get_text,
            zenodo_backend_type=self.zenodo_backend_type,
        )

    def get_metadata(self, set_index=None):

        context = self.get_metadata_context(set_index=set_index)

        mapper, schema, payload_cls = METADATA_METHODS[self.zenodo_backend_type]
        metadata_dict = extract_metadata(context, mapper)
        metadata_obj = validate_schema(metadata_dict, schema)

        payload_obj = payload_cls(metadata=metadata_obj)
        return serialize_payload(payload_obj)
