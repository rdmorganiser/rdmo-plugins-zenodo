import logging

from django.conf import settings
from django.shortcuts import reverse
from django.utils.translation import gettext_lazy as _

from rdmo.projects.exports import Export
from rdmo.services.providers import OauthProviderMixin

logger = logging.getLogger(__name__)


class BaseZenodoExportProvider(OauthProviderMixin, Export):

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
    def deposit_url(self):
        return f'{self.zenodo_url}/api/records'

    @property
    def redirect_path(self):
        return reverse('oauth_callback', args=['zenodo'])

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

    def get_error_message(self, response):
        return response.json().get('errors')
