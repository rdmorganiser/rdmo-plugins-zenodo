import logging

from django.conf import settings
from django.shortcuts import reverse
from django.utils.translation import gettext_lazy as _
from django.http import HttpResponse
from django.template import TemplateSyntaxError

from rdmo.core.utils import render_to_format
from rdmo.projects.exports import Export
from rdmo.projects.utils import get_value_path
from rdmo.services.providers import OauthProviderMixin
from rdmo.views.models import View

logger = logging.getLogger(__name__)

json_header = {
    'Content-Type': 'application/json',
    }
binary_header= {
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
    def deposit_url(self):
        return f'{self.zenodo_url}/api/records'

    @property
    def redirect_path(self):
        if self.RDMO_PLUGIN_KEY is None:
            raise ValueError("the RDMO_PLUGIN_KEY should be set as a class attribute")
        return reverse('oauth_callback', args=[self.RDMO_PLUGIN_KEY])

    def record_file_url(self, record_id):
        return f"{self.deposit_url}/records/{record_id}/draft/files"

    def record_file_content_url(self, record_id, file_key):
        return f"{self.record_file_url(record_id)}/{file_key}/content"

    def record_file_commit_url(self, record_id, file_key):
        return f"{self.record_file_url(record_id)}/{file_key}/commit"

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

    def render_project_views(self, project, snapshot, attachments_format, view=None):

        if view is None:
            view = View.objects.get(uri="https://rdmorganiser.github.io/terms/views/variable_check")

        try:
            rendered_view = view.render(project, snapshot)
        except TemplateSyntaxError:
            return HttpResponse()

        return render_to_format(
            None, attachments_format, project.title, 'projects/project_view_export.html', {
                'format': attachments_format,
                'title': project.title,
                'view': view,
                'rendered_view': rendered_view,
                'resource_path': get_value_path(project, snapshot)
            }
        )

    def render_snapshot_to_pdf(self, snapshot):
        # get the pdf
        return self.render_project_views(self.project, snapshot, "pdf")


    def upload_file(self, record_id, binary=None):
        """
        takes the record_id of the draft record and the file contents as binary data.
        API_URL should be the zenodo API URL, e.g. 
        """
        # POST data / PDF
        files_url = self.record_file_url(record_id)
        file_data = [{"key": "DMP.pdf"}]
        data_initialization_response = self.post(self.request, files_url, json=file_data)

        # upload the actual file content as binary stream
        # extract files/content URL from the data upload response
        breakpoint()
        # files_content_url = data_initialization_response.json()["entries"][0]["links"]["content"]
        files_content_url = self.record_file_content_url(record_id, file_data[0]['key'])
        # self.deposit_url+f"records/{record_id}/draft/files/{file_data[0]['key']}/content"
        ## multiple files as upload even possible???                     ^^^

        # upload with binary data
        data_content_response = self.put(self.request, files_content_url, data=binary) #headers=binary_header,

        # commit the file upload
        file_commit_url = self.deposit_url+f"records/{record_id}/draft/files/{file_data[0]['key']}/commit"

        data_commit_response = self.post(self.request, file_commit_url)
        return data_commit_response
