import logging

from django.conf import settings
from django.shortcuts import reverse

from rdmo.projects.exports import Export
from rdmo.services.providers import OauthProviderMixin

logger = logging.getLogger(__name__)

json_header = {
    'Content-Type': 'application/json',
    }
binary_header = {
    'Content-Type': 'application/octet-stream',
}


class BaseZenodoExportProvider(OauthProviderMixin, Export):

    RDMO_PLUGIN_KEY = None

    @property
    def client_id(self):
        return settings.ZENODO_PROVIDER['client_id']

    @property
    def client_secret(self):
        return settings.ZENODO_PROVIDER['client_secret']

    @property
    def zenodo_url(self):
        return settings.ZENODO_PROVIDER.get('zenodo_url', 'https://sandbox.zenodo.org').strip('/')

    @property
    def authorize_url(self):
        return f'{self.zenodo_url}/oauth/authorize'

    @property
    def token_url(self):
        return f'{self.zenodo_url}/oauth/token'

    @property
    def redirect_path(self):
        if self.RDMO_PLUGIN_KEY is None:
            raise ValueError("the RDMO_PLUGIN_KEY should be set as a class attribute")
        return reverse('oauth_callback', args=[self.RDMO_PLUGIN_KEY])

    @property
    def authorization_header(self):
        return self.get_authorization_headers(self.get_from_session(self.request, 'access_token'))

    @property
    def authorized_binary_header(self):
        return {**binary_header, **self.authorization_header}

    @property
    def authorized_json_header(self):
        return {**json_header, **self.authorization_header}

    @property
    def export_file_format(self):
        return settings.ZENODO_PROVIDER.get('export_format', 'pdf')

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
            'scope': 'deposit:write',
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
