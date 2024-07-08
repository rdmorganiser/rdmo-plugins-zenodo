import logging

from django import forms
from django.conf import settings
from django.shortcuts import redirect, render, reverse
from django.utils.translation import gettext_lazy as _

from rdmo.projects.exports import Export
from rdmo.services.providers import OauthProviderMixin

logger = logging.getLogger(__name__)


class ZenodoExportProvider(OauthProviderMixin, Export):

    rights_uri_options = {
        'dataset_license_types/71': 'cc-by-4.0',
        'dataset_license_types/73': 'cc-by-nc-4.0',
        'dataset_license_types/74': 'cc-by-nd-4.0',
        'dataset_license_types/75': 'cc-by-sa-4.0',
        'dataset_license_types/cc0': 'cc-zero'
    }

    class Form(forms.Form):

        dataset = forms.CharField(label=_('Select dataset of your project'))

        def __init__(self, *args, **kwargs):
            dataset_choices = kwargs.pop('dataset_choices')
            super().__init__(*args, **kwargs)

            self.fields['dataset'].widget = forms.RadioSelect(choices=dataset_choices)

    def render(self):
        datasets = self.get_set('project/dataset/id')
        dataset_choices = [(dataset.set_index, dataset.value)for dataset in datasets]

        self.store_in_session(self.request, 'dataset_choices', dataset_choices)

        form = self.Form(
            dataset_choices=dataset_choices
        )

        return render(self.request, 'plugins/exports_zenodo.html', {'form': form}, status=200)

    def submit(self):
        dataset_choices = self.get_from_session(self.request, 'dataset_choices')
        form = self.Form(self.request.POST, dataset_choices=dataset_choices)

        if 'cancel' in self.request.POST:
            return redirect('project', self.project.id)

        if form.is_valid():
            url = self.get_post_url()
            data = self.get_post_data(form.cleaned_data['dataset'])
            return self.post(self.request, url, data)
        else:
            return render(self.request, 'plugins/exports_zenodo.html', {'form': form}, status=200)

    def post_success(self, request, response):
        zenodo_url = response.json().get('links', {}).get('html')
        if zenodo_url:
            return redirect(zenodo_url)
        else:
            return render(request, 'core/error.html', {
                'title': _('ZENODO error'),
                'errors': [_('The URL of the new dataset could not be retrieved.')]
            }, status=200)

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
        return f'{self.zenodo_url}/api/deposit/depositions'

    @property
    def redirect_path(self):
        return reverse('oauth_callback', args=['zenodo'])

    def get_post_url(self):
        return self.deposit_url

    def get_post_data(self, set_index):
        metadata = {}

        # set the title from the title or id or the running index
        metadata['title'] =  \
            self.get_text('project/dataset/title', set_index=set_index) or \
            self.get_text('project/dataset/id', set_index=set_index) or \
            f'Dataset #{set_index + 1}'

        # set the description
        description = self.get_text('project/dataset/description', set_index=set_index)
        if description:
            metadata['description'] = description

        # add the creators from the project members
        add_project_members = settings.ZENODO_PROVIDER.get('add_project_members')
        if add_project_members:
            metadata['creators'] = []
            for user in self.project.user.all():
                creator = {
                    'name': user.get_full_name()
                }
                #TODO: add ORCID
                metadata['creators'].append(creator)

        # set the resource_type from the settings
        upload_type = settings.ZENODO_PROVIDER.get('upload_type')
        if upload_type:
            metadata['upload_type'] = upload_type

        # set the access_right from the settings
        access_right = settings.ZENODO_PROVIDER.get('access_right')
        if access_right:
            metadata['access_right'] = access_right

        communities = settings.ZENODO_PROVIDER.get('communities')
        if communities:
            metadata['communities'] = [
                {'identifier': community_id} for community_id in communities
            ]

        for rights in self.get_values('project/dataset/sharing/conditions', set_index=set_index):
            if rights.option:
                metadata['license'] = self.rights_uri_options.get(rights.option.uri_path)
                break

        # # set the publisher from the settings
        # publisher = settings.ZENODO_PROVIDER.get('publisher')
        # if publisher:
        #     metadata['publisher'] = publisher

        # # set the funder from the settings
        # funding_references = settings.ZENODO_PROVIDER.get('fundingReferences')
        # if funding_references:
        #     metadata['funding_references'] = []
        #     for funding_reference in funding_references:
        #         metadata['funding_references'].append({
        #             'funderName': funding_reference.get('funderName'),
        #             'funderIdentifier': funding_reference.get('funderIdentifier'),
        #             'awardNumber': funding_reference.get('awardNumber'),
        #             'awardTitle': funding_reference.get('awardTitle'),
        #             'awardURI': funding_reference.get('awardURI'),
        #         })

        return {
            'metadata': metadata
        }

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
