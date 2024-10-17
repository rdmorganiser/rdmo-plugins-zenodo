import logging

from django import forms
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.shortcuts import redirect, render
from django.utils.translation import gettext_lazy as _

from .base import BaseZenodoExportProvider

logger = logging.getLogger(__name__)



class ZenodoPublishProvider(BaseZenodoExportProvider):

    rights_uri_options = {
        'dataset_license_types/71': 'cc-by-4.0',
        'dataset_license_types/73': 'cc-by-nc-4.0',
        'dataset_license_types/74': 'cc-by-nd-4.0',
        'dataset_license_types/75': 'cc-by-sa-4.0',
        'dataset_license_types/cc0': 'cc-zero'
    }

    class Form(forms.Form):

        snapshot = forms.CharField(label=_('Select snapshot of your project'))

        def __init__(self, *args, **kwargs):
            snapshot_choices = kwargs.pop('snapshot_choices')
            super().__init__(*args, **kwargs)

            self.fields['snapshot'].widget = forms.RadioSelect(choices=snapshot_choices)

    def render(self):
        datasets = self.get_set('project/dataset/id')
        # get project snapshots
        snapshot_choices = [(dataset.set_index, dataset.value)for dataset in datasets]

        self.store_in_session(self.request, 'snapshot_choices', snapshot_choices)

        form = self.Form(
            snapshot_choices=snapshot_choices
        )

        return render(self.request, 'plugins/exports_zenodo.html', {'form': form}, status=200)

    def submit(self):
        snapshot_choices = self.get_from_session(self.request, 'snapshot_choices')
        form = self.Form(self.request.POST, snapshot_choices=snapshot_choices)

        if 'cancel' in self.request.POST:
            return redirect('project', self.project.id)

        if form.is_valid():
            url = self.get_post_url()
            data = self.get_post_data(form.cleaned_data['snapshot'])
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

        # set the title from the title or id or the running index
        metadata['title'] = self.project.title

        # set the resource_type from the settings
        metadata['resource_type'] = {'id': 'publication-datamanagementplan'}

        # set the description
        description = self.project.description or \
                    f"Data Management Plan for project {self.project.title}"
        # self.get_text('project/dataset/description', set_index=set_index)
        if description:
            metadata['description'] = description

        # set subjects
        metadata['subjects'] = [
            {
                'subject': 'Data Management Plan'
            },
            {
                'subject': 'DMP'
            }
        ]

        # set keywords
        keywords = self.get_values('project/research_question/keywords', set_index=set_index)
        for keyword in keywords:
            metadata['subjects'].append({
                'subject': keyword.text
            })

        return {
            'metadata': metadata
        }
