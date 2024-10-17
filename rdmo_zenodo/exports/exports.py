import logging

from django import forms
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.shortcuts import redirect, render
from django.utils.translation import gettext_lazy as _

from .base import BaseZenodoExportProvider

logger = logging.getLogger(__name__)



class ZenodoExportProvider(BaseZenodoExportProvider):

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
        zenodo_url = response.json().get('links', {}).get('self_html')
        if zenodo_url:
            return redirect(zenodo_url)
        else:
            return render(request, 'core/error.html', {
                'title': _('ZENODO error'),
                'errors': [_('The URL of the new dataset could not be retrieved.')]
            }, status=200)

    def get_post_url(self):
        return self.deposit_url

    def get_post_data(self, set_index):
        # see https://inveniordm.docs.cern.ch/reference/metadata/ for invenio metadata
        metadata = {}

        # set the resource_type from the settings
        resource_type = settings.ZENODO_PROVIDER.get('resource_type')
        if resource_type:
            metadata['resource_type'] = {
                'id': resource_type
            }

        # add the creators from the project members
        add_project_members = settings.ZENODO_PROVIDER.get('add_project_members')
        if add_project_members:
            metadata['creators'] = []
            for user in self.project.user.all():
                creator = {
                    'family_name': user.last_name,
                    'given_name': user.first_name,
                    'type': 'personal'
                }

                try:
                    orcid_socialaccount = user.socialaccount_set.get(provider='orcid')
                    creator['identifiers'] = [
                        {
                            'scheme': 'orcid',
                            'identifier': orcid_socialaccount.uid
                        }
                    ]
                except (ObjectDoesNotExist, AttributeError):
                    pass

                metadata['creators'].append({
                    'person_or_org': creator
                })

        # set the title from the title or id or the running index
        metadata['title'] =  \
            self.get_text('project/dataset/title', set_index=set_index) or \
            self.get_text('project/dataset/id', set_index=set_index) or \
            f'Dataset #{set_index + 1}'

        # set the description
        description = self.get_text('project/dataset/description', set_index=set_index)
        if description:
            metadata['description'] = description

        # set the rights/licenses
        for rights in self.get_values('project/dataset/sharing/conditions', set_index=set_index):
            if rights.option:
                metadata['rights'] = [{
                    'id': self.rights_uri_options.get(rights.option.uri_path)
                }]
                break

        # set the language from the settings
        language = settings.ZENODO_PROVIDER.get('language')
        if language:
            metadata['languages'] = [
                {'id': language}
            ]

        # set the publisher from the settings
        publisher = settings.ZENODO_PROVIDER.get('publisher')
        if publisher:
            metadata['publisher'] = publisher

        # set the funding from the settings
        funding = settings.ZENODO_PROVIDER.get('funding')
        if funding:
            metadata['funding'] = funding

        return {
            'metadata': metadata
        }
