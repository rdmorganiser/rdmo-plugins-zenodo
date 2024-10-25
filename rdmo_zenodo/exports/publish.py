import logging

from django import forms
from django.shortcuts import redirect, render
from django.utils.translation import gettext_lazy as _

from .base import BaseZenodoExportProvider

logger = logging.getLogger(__name__)


class ZenodoPublishProvider(BaseZenodoExportProvider):

    RDMO_PLUGIN_KEY = "zenodo-publish"

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
        snapshot_choices = [(i.id,i.title) for i in self.project.snapshots.all()]

        self.store_in_session(self.request, 'snapshot_choices', snapshot_choices)

        form = self.Form(
            snapshot_choices=snapshot_choices
        )

        return render(self.request, 'plugins/exports_zenodo.html', {'form': form}, status=200)

    def upload_file_to_zenodo(self, file):
        # placeholder for posting the file
        return

    def submit(self):
        snapshot_choices = self.project.snapshots.all()
        form = self.Form(self.request.POST, snapshot_choices=snapshot_choices)

        if 'cancel' in self.request.POST:
            return redirect('project', self.project.id)

        if form.is_valid():
            url = self.get_post_url()  # deposit url
            snapshot_id = form.cleaned_data['snapshot']
            snapshot = self.project.snapshots.get(id=snapshot_id)
            data = self.get_post_data(snapshot)
            zen_data_response = self.post(self.request, url, data)
            rdmo_pdf_response = self.render_snapshot_to_pdf(snapshot)
            _zen_pdf_response = self.upload_file_to_zenodo(rdmo_pdf_response.content)
            return zen_data_response
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

    def get_post_data(self, snapshot):
        # see https://inveniordm.docs.cern.ch/reference/metadata/ for invenio metadata
        metadata = {}

        # set the title from the title or id or the running index
        metadata['title'] = snapshot.title

        # set the resource_type from the settings
        metadata['resource_type'] = {'id': 'publication-datamanagementplan'}

        # set the description
        description = snapshot.description or \
                    f"Data Management Plan for project {snapshot.title}"
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
        # keywords = self.get_values('project/research_question/keywords', set_index=set_index)
        # for keyword in keywords:
        #     metadata['subjects'].append({
        #         'subject': keyword.text
        #     })

        return {
            'metadata': metadata
        }
