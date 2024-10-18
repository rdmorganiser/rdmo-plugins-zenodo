import json
import tempfile
from typing import Dict, Any, Tuple, Optional, List, Union

import requests
from django import forms
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.utils import timezone

from rdmo.projects.exports import Export
from rdmo.services.providers import OauthProviderMixin
from rdmo.projects.models.snapshot import Snapshot

class ZenodoExportProvider(OauthProviderMixin, Export):

    RIGHTS_URI_OPTIONS = {
        'dataset_license_types/71': 'cc-by-4.0',
        'dataset_license_types/73': 'cc-by-nc-4.0',
        'dataset_license_types/74': 'cc-by-nd-4.0',
        'dataset_license_types/75': 'cc-by-sa-4.0',
        'dataset_license_types/cc0': 'cc-zero'
    }

    @property
    def client_id(self) -> str:
        return settings.ZENODO_PROVIDER['client_id']

    @property
    def client_secret(self) -> str:
        return settings.ZENODO_PROVIDER['client_secret']

    @property
    def zenodo_url(self) -> str:
        return settings.ZENODO_PROVIDER.get('zenodo_url', 'https://sandbox.zenodo.org').rstrip('/')

    @property
    def authorize_url(self) -> str:
        return f'{self.zenodo_url}/oauth/authorize'

    @property
    def token_url(self) -> str:
        return f'{self.zenodo_url}/oauth/token'

    @property
    def deposit_url(self) -> str:
        return f'{self.zenodo_url}/api/deposit/depositions'

    @property
    def redirect_path(self) -> str:
        return reverse('oauth_callback', args=['zenodo'])

    class Form(forms.Form):
        snapshot = forms.ChoiceField(label=_('Select a snapshot of your project'))

        def __init__(self, *args, **kwargs):
            snapshot_choices = kwargs.pop('snapshot_choices')
            super().__init__(*args, **kwargs)
            self.fields['snapshot'].choices = snapshot_choices

    def render(self) -> HttpResponse:
        snapshots = Snapshot.objects.filter(project=self.project)
        snapshot_choices = [(str(snapshot.id), f"Snapshot {snapshot.title} - {snapshot.created}") for snapshot in snapshots]

        self.store_in_session(self.request, 'snapshot_choices', snapshot_choices)

        form = self.Form(snapshot_choices=snapshot_choices)

        return render(self.request, 'plugins/exports_zenodo.html', {'form': form}, status=200)

    def submit(self) -> HttpResponse:
        snapshot_choices = self.get_from_session(self.request, 'snapshot_choices')
        form = self.Form(self.request.POST, snapshot_choices=snapshot_choices)

        if 'cancel' in self.request.POST:
            return redirect('project', self.project.id)

        if form.is_valid():
            url = self.deposit_url
            data = self.get_post_data(form.cleaned_data['snapshot'])
            return self.post(self.request, url, data)
        else:
            return render(self.request, 'plugins/exports_zenodo.html', {'form': form}, status=200)

    def get_post_data(self, snapshot_id: str) -> Dict[str, Any]:
        snapshot = Snapshot.objects.get(id=snapshot_id)
        metadata = self._prepare_metadata(snapshot)
        docx_file = self._generate_docx(snapshot)

        return {
            'metadata': metadata,
            'file': docx_file
        }

    def _prepare_metadata(self, snapshot: Snapshot) -> Dict[str, Any]:
        metadata = {
            'title': f"{self.project.title} - Snapshot: {snapshot.title}",
            'upload_type': settings.ZENODO_PROVIDER.get('upload_type', 'dataset'),
            'description': f"{self.project.description or 'No description provided.'}\n\nSnapshot of project '{self.project.title}' taken on {snapshot.created}",
            'publication_date': timezone.now().date().isoformat(),
        }

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

    def _generate_docx(self, snapshot: Snapshot) -> Tuple[str, bytes]:
        docx_url = self.request.build_absolute_uri(
            f'/projects/{self.project.id}/snapshots/{snapshot.id}/answers/export/docx/'
        )

        session = requests.Session()
        session.cookies.update(self.request.COOKIES)

        try:
            response = session.get(docx_url)
            response.raise_for_status()

            with tempfile.NamedTemporaryFile(delete=False, suffix='.docx') as temp_file:
                temp_file.write(response.content)
                temp_file_path = temp_file.name

            with open(temp_file_path, 'rb') as f:
                file_content = f.read()

            return ('snapshot_answers.docx', file_content)
        except requests.exceptions.RequestException as e:
            raise Exception(f"Failed to generate DOCX. Error: {str(e)}")

    def post(self, request: HttpRequest, url: str, data: Dict[str, Any]) -> HttpResponse:
        access_token = self.get_from_session(request, 'access_token')
        if not access_token:
            self.store_in_session(request, 'request', ('post', url, data))
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

    def _create_deposition(self, url: str, metadata: Dict[str, Any], headers: Dict[str, str]) -> Union[Dict[str, Any], HttpResponse]:
        response = requests.post(url, json={'metadata': metadata}, headers=headers)
        
        if response.status_code == 401:
            self.pop_from_session(self.request, 'access_token')
            self.store_in_session(self.request, 'request', ('post', url, {'metadata': metadata}))
            return self.authorize(self.request)

        if response.status_code != 201:
            return self.error_response(self.request, response)

        return response.json()

    def _upload_file(self, deposition: Dict[str, Any], file_data: Tuple[str, bytes], access_token: str) -> Optional[HttpResponse]:
        file_name, file_content = file_data
        bucket_url = deposition['links']['bucket']
        file_url = f"{bucket_url}/{file_name}"
        
        binary_headers = self.get_authorization_headers(access_token)
        binary_headers['Content-Type'] = 'application/octet-stream'

        upload_response = requests.put(file_url, headers=binary_headers, data=file_content)

        if upload_response.status_code not in [200, 201]:
            return self.error_response(self.request, upload_response)

    def _publish_deposition(self, deposition_id: str, headers: Dict[str, str]) -> Union[requests.Response, HttpResponse]:
        publish_url = f"{self.deposit_url}/{deposition_id}/actions/publish"
        publish_response = requests.post(publish_url, headers=headers)

        if publish_response.status_code != 202:
            return self.error_response(self.request, publish_response)

        return publish_response

    def get_authorize_params(self, request: HttpRequest, state: str) -> Dict[str, str]:
        return {
            'response_type': 'code',
            'client_id': self.client_id,
            'scope': 'deposit:write',
            'redirect_uri': request.build_absolute_uri(self.redirect_path),
            'state': state
        }

    def get_callback_data(self, request: HttpRequest) -> Dict[str, str]:
        return {
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'grant_type': 'authorization_code',
            'redirect_uri': request.build_absolute_uri(self.redirect_path),
            'code': request.GET.get('code')
        }

    def error_response(self, request: HttpRequest, response: requests.Response) -> HttpResponse:
        error_message = self._get_error_message(response)
        return render(request, 'core/error.html', {
            'title': _('Zenodo error'),
            'errors': [error_message]
        }, status=response.status_code)

    def success_response(self, request: HttpRequest, response: requests.Response) -> HttpResponse:
        zenodo_url = response.json().get('links', {}).get('html')
        if zenodo_url:
            return redirect(zenodo_url)
        else:
            return render(request, 'core/error.html', {
                'title': _('Zenodo error'),
                'errors': [_('The URL of the new deposition could not be retrieved.')]
            }, status=200)

    def _get_error_message(self, response: requests.Response) -> str:
        try:
            error_json = response.json()
            error_message = error_json.get('message', str(response.content))
            if 'errors' in error_json:
                error_details = '; '.join([f"{error.get('field', '')}: {error.get('message', '')}" for error in error_json['errors']])
                error_message += f" Details: {error_details}"
            return error_message
        except ValueError:
            return str(response.content)
