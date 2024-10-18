import json
import tempfile
from typing import Dict, Any, Tuple, Optional, List, Union
from contextlib import contextmanager
from django import forms
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
import requests
from rdmo.projects.exports import Export
from rdmo.services.providers import OauthProviderMixin
from rdmo.projects.models.snapshot import Snapshot

class ZenodoExportProvider(OauthProviderMixin, Export):
    """
    A provider for exporting project snapshots to Zenodo.
    
    Attributes:
        RIGHTS_URI_OPTIONS (Dict[str, str]): Mapping of rights URI options to their corresponding license names.
    """

    RIGHTS_URI_OPTIONS = {
        'dataset_license_types/71': 'cc-by-4.0',
        'dataset_license_types/73': 'cc-by-nc-4.0',
        'dataset_license_types/74': 'cc-by-nd-4.0',
        'dataset_license_types/75': 'cc-by-sa-4.0',
        'dataset_license_types/cc0': 'cc-zero'
    }

    @property
    def client_id(self) -> str:
        """Return the Zenodo client ID from settings."""
        return settings.ZENODO_PROVIDER['client_id']

    @property
    def client_secret(self) -> str:
        """Return the Zenodo client secret from settings."""
        return settings.ZENODO_PROVIDER['client_secret']

    @property
    def zenodo_url(self) -> str:
        """Return the base Zenodo URL from settings, defaulting to the sandbox URL."""
        return settings.ZENODO_PROVIDER.get('zenodo_url', 'https://sandbox.zenodo.org').rstrip('/')

    @property
    def authorize_url(self) -> str:
        """Construct the Zenodo authorization URL."""
        return f'{self.zenodo_url}/oauth/authorize'

    @property
    def token_url(self) -> str:
        """Construct the Zenodo token URL."""
        return f'{self.zenodo_url}/oauth/token'

    @property
    def deposit_url(self) -> str:
        """Construct the Zenodo deposit URL."""
        return f'{self.zenodo_url}/api/deposit/depositions'

    @property
    def redirect_path(self) -> str:
        """Return the redirect path for the OAuth callback."""
        return reverse('oauth_callback', args=['zenodo'])

    class Form(forms.Form):
        """
        Form for selecting a project snapshot to export to Zenodo.
        
        Attributes:
            snapshot (forms.ChoiceField): Field for selecting a snapshot.
        """
        snapshot = forms.ChoiceField(label=_('Select a snapshot of your project'))

        def __init__(self, *args, **kwargs):
            """
            Initialize the form with snapshot choices.
            
            :param args: Standard form arguments.
            :param kwargs: Standard form keyword arguments, including'snapshot_choices'.
            """
            snapshot_choices = kwargs.pop('snapshot_choices')
            super().__init__(*args, **kwargs)
            self.fields['snapshot'].choices = snapshot_choices

    def render(self) -> HttpResponse:
        """
        Render the form for selecting a snapshot to export to Zenodo.
        
        :return: An HTTP response with the rendered form.
        """
        request = self.request  # Local variable for readability
        snapshots = Snapshot.objects.filter(project=self.project)
        snapshot_choices = [(str(snapshot.id), f"Snapshot {snapshot.title} - {snapshot.created}") for snapshot in snapshots]

        self.store_in_session(request,'snapshot_choices', snapshot_choices)

        form = self.Form(snapshot_choices=snapshot_choices)

        return render(request, 'plugins/exports_zenodo.html', {'form': form}, status=200)

    def submit(self) -> HttpResponse:
        """
        Handle the form submission for exporting a snapshot to Zenodo.
        
        :return: An HTTP response redirecting to the project or initiating the export.
        """
        request = self.request
        snapshot_choices = self.get_from_session(request,'snapshot_choices')
        form = self.Form(request.POST, snapshot_choices=snapshot_choices)

        if 'cancel' in request.POST:
            return redirect('project', self.project.id)

        if form.is_valid():
            url = self.deposit_url
            data = self.get_post_data(form.cleaned_data['snapshot'])
            return self.post(request, url, data)
        else:
            return render(request, 'plugins/exports_zenodo.html', {'form': form}, status=200)

    def get_post_data(self, snapshot_id: str) -> Dict[str, Any]:
        """
        Prepare the data for the POST request to Zenodo.
        
        :param snapshot_id: The ID of the selected snapshot.
        :return: A dictionary containing the metadata and file.
        """
        snapshot = Snapshot.objects.get(id=snapshot_id)
        metadata = self._prepare_metadata(snapshot)
        docx_file = self._generate_docx(snapshot)

        return {
           'metadata': metadata,
            'file': docx_file
        }

    def _prepare_metadata(self, snapshot: Snapshot) -> Dict[str, Any]:
        """
        Prepare the metadata for the Zenodo deposition.
        
        :param snapshot: The snapshot to generate metadata for.
        :return: A dictionary containing the metadata.
        """
        metadata = {
            'title': f"{self.project.title} - Snapshot: {snapshot.title}",
            'upload_type': settings.ZENODO_PROVIDER.get('upload_type', 'dataset'),
            'description': f"{self.project.description or 'No description provided.'}\n\nSnapshot of project '{self.project.title}' taken on {snapshot.created}",
            'publication_date': timezone.now().date().isoformat(),
        }

        # Add additional metadata fields as needed
        resource_type = settings.ZENODO_PROVIDER.get('resource_type')
        if resource_type:
            metadata['resource_type'] = resource_type

        if settings.ZENODO_PROVIDER.get('add_project_members'):
            metadata['creators'] = self._get_creators()

        rights = snapshot.values.filter(attribute__uri='project/dataset/sharing/conditions').first()
        if rights and rights.option:
            metadata['license'] = self.RIGHTS_URI_OPTIONS.get(rights.option.uri_path)

        language = settings.ZENODO_PROVIDER.get('language')
        if language:
            metadata['language'] = language

        keywords = self.get_values('project/research_question/keywords')
        if keywords:
            metadata['keywords'] = [keyword.text for keyword in keywords]

        notes = settings.ZENODO_PROVIDER.get('notes')
        if notes:
            metadata['notes'] = notes

        return metadata

    def _get_creators(self) -> List[Dict[str, str]]:
        """
        Retrieve the creators (project members) for the metadata.
        
        :return: A list of dictionaries containing creator information.
        """
        creators = []
        for user in self.project.user.all():
            creator = {
                'name': f"{user.first_name} {user.last_name}"
            }
            try:
                orcid_socialaccount = user.socialaccount_set.get(provider='orcid')
                creator['orcid'] = orcid_socialaccount.uid
            except (ObjectDoesNotExist, AttributeError):
                pass
            creators.append(creator)
        return creators

    @contextmanager
    def _temp_file(self, suffix='.docx'):
        """
        Context manager for creating a temporary file.
        
        :param suffix: The file suffix (default: '.docx').
        :yield: The temporary file path.
        """
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
            yield temp_file.name

    def _generate_docx(self, snapshot: Snapshot) -> Tuple[str, bytes]:
        """
        Generate a DOCX file for the given snapshot.
        
        :param snapshot: The snapshot to generate the DOCX for.
        :return: A tuple containing the file name and content.
        """
        request = self.request
        docx_url = request.build_absolute_uri(
            f'/projects/{self.project.id}/snapshots/{snapshot.id}/answers/export/docx/'
        )

        with requests.Session() as session:
            session.cookies.update(request.COOKIES)
            try:
                response = session.get(docx_url)
                response.raise_for_status()
                with self._temp_file() as temp_file_path:
                    with open(temp_file_path, 'wb') as temp_file:
                        temp_file.write(response.content)
                    with open(temp_file_path, 'rb') as file:
                        file_content = file.read()
                file_name ='snapshot_answers.docx'
                return file_name, file_content
            except requests.exceptions.RequestException as e:
                raise Exception(f"Failed to generate DOCX. Error: {str(e)}")

    def post(self, request: HttpRequest, url: str, data: Dict[str, Any]) -> HttpResponse:
        """
        Handle the POST request to Zenodo.
        
        :param request: The HTTP request.
        :param url: The URL for the POST request.
        :param data: The data to be sent.
        :return: An HTTP response.
        """
        access_token = self.get_from_session(request, 'access_token')
        if not access_token:
            self.store_in_session(request,'request', ('post', url, data))
            return self.authorize(request)

        json_headers = self.get_authorization_headers(access_token)
        json_headers['Content-Type'] = 'application/json'

        deposition = self._create_deposition(url, data['metadata'], json_headers)
        if isinstance(deposition, HttpResponse):
            return deposition

        if 'file' in data:
            file_upload_result = self._upload_file(deposition, data['file'], access_token)
            if isinstance(file_upload_result, HttpResponse):
                return file_upload_result

        publish_result = self._publish_deposition(deposition['id'], json_headers)
        return publish_result if isinstance(publish_result, HttpResponse) else self.success_response(request, publish_result)

    def _handle_zenodo_response(self, response: requests.Response) -> Optional[HttpResponse]:
        """
        Handle a response from Zenodo, returning an HTTP response if an error occurs.
        
        :param response: The Zenodo response.
        :return: An HTTP response if an error occurs, otherwise None.
        """
        if response.status_code == 401:
            self.pop_from_session(self.request, 'access_token')
            self.store_in_session(self.request,'request', ('post', response.url, {}))
            return self.authorize(self.request)
        elif response.status_code not in [200, 201, 202]:
            return self.error_response(self.request, response)

    def _create_deposition(self, url: str, metadata: Dict[str, Any], headers: Dict[str, str]) -> Union[Dict[str, Any], HttpResponse]:
        """
        Create a new deposition on Zenodo.
        
        :param url: The URL for the deposition creation.
        :param metadata: The metadata for the deposition.
        :param headers: The headers for the request.
        :return: The deposition data or an HTTP response if an error occurs.
        """
        response = requests.post(url, json={'metadata': metadata}, headers=headers)
        result = self._handle_zenodo_response(response)
        if result:
            return result
        return response.json()

    def _upload_file(self, deposition: Dict[str, Any], file_data: Tuple[str, bytes], access_token: str) -> Optional[HttpResponse]:
        """
        Upload a file to the deposition on Zenodo.
        
        :param deposition: The deposition data.
        :param file_data: The file name and content.
        :param access_token: The access token for authentication.
        :return: An HTTP response if an error occurs, otherwise None.
        """
        file_name, file_content = file_data
        bucket_url = deposition['links']['bucket']
        file_url = f"{bucket_url}/{file_name}"
        
        binary_headers = self.get_authorization_headers(access_token)
        binary_headers['Content-Type'] = 'application/octet-stream'

        response = requests.put(file_url, headers=binary_headers, data=file_content)
        return self._handle_zenodo_response(response)

    def _publish_deposition(self, deposition_id: str, headers: Dict[str, str]) -> Union[requests.Response, HttpResponse]:
        """
        Publish the deposition on Zenodo.
        
        :param deposition_id: The ID of the deposition to publish.
        :param headers: The headers for the request.
        :return: The response from Zenodo or an HTTP response if an error occurs.
        """
        publish_url = f"{self.deposit_url}/{deposition_id}/actions/publish"
        response = requests.post(publish_url, headers=headers)
        result = self._handle_zenodo_response(response)
        if result:
            return result
        return response

    def get_authorize_params(self, request: HttpRequest, state: str) -> Dict[str, str]:
        """
        Prepare the parameters for the authorization request.
        
        :param request: The HTTP request.
        :param state: The state parameter.
        :return: A dictionary containing the authorization parameters.
        """
        return {
           'response_type': 'code',
            'client_id': self.client_id,
           'scope': 'deposit:write',
           'redirect_uri': request.build_absolute_uri(self.redirect_path),
           'state': state
        }

    def get_callback_data(self, request: HttpRequest) -> Dict[str, str]:
        """
        Prepare the data for the callback request.
        
        :param request: The HTTP request.
        :return: A dictionary containing the callback data.
        """
        return {
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'grant_type': 'authorization_code',
           'redirect_uri': request.build_absolute_uri(self.redirect_path),
            'code': request.GET.get('code')
        }

    def error_response(self, request: HttpRequest, response: requests.Response) -> HttpResponse:
        """
        Generate an error response based on the Zenodo response.
        
        :param request: The HTTP request.
        :param response: The Zenodo response.
        :return: An HTTP error response.
        """
        error_message = self._get_error_message(response)
        return render(request, 'core/error.html', {
            'title': _('Zenodo error'),
            'errors': [error_message]
        }, status=response.status_code)

    def success_response(self, request: HttpRequest, response: requests.Response) -> HttpResponse:
        """
        Generate a success response after a successful deposition.
        
        :param request: The HTTP request.
        :param response: The Zenodo response.
        :return: An HTTP response redirecting to the deposition or an error page.
        """
        zenodo_url = response.json().get('links', {}).get('html')
        if zenodo_url:
            return redirect(zenodo_url)
        else:
            return render(request, 'core/error.html', {
                'title': _('Zenodo error'),
                'errors': [_('The URL of the new deposition could not be retrieved.')]
            }, status=200)

    def _get_error_message(self, response: requests.Response) -> str:
        """
        Extract a user-friendly error message from the Zenodo response.
        
        :param response: The Zenodo response.
        :return: A formatted error message.
        """
        try:
            error_json = response.json()
            error_message = error_json.get('message', str(response.content))
            if 'errors' in error_json:
                error_details = '; '.join([f"{error.get('field', '')}: {error.get('message', '')}" for error in error_json['errors']])
                error_message += f" Details: {error_details}"
            return error_message
        except json.JSONDecodeError:
            return str(response.content)
