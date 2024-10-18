import logging

from django import forms
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.shortcuts import redirect, render
from django.utils.translation import gettext_lazy as _

from .base import BaseZenodoExportProvider

from rdmo.projects.models import Snapshot, Value
from rdmo.domain.models import Attribute

logger = logging.getLogger(__name__)

class ZenodoExportProvider(BaseZenodoExportProvider):

    RDMO_PLUGIN_KEY = "zenodo"

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

    def get_snapshots(self):
        """Retrieve all snapshots for the current project."""
        return Snapshot.objects.filter(project=self.project)

    def render(self):
        snapshots = self.get_snapshots()
        snapshot_choices = [(snapshot.id, snapshot.title or f"Snapshot {snapshot.id}") for snapshot in snapshots]

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
            snapshot_id = form.cleaned_data['snapshot']
            snapshot = Snapshot.objects.get(id=snapshot_id)

            url = self.get_post_url()
            data = self.get_post_data(snapshot)
            return self.post(self.request, url, data)
        else:
            return render(self.request, 'plugins/exports_zenodo.html', {'form': form}, status=200)

    def post_success(self, request, response):
        # Log the entire response for debugging
        logger.debug(f"Zenodo response status code: {response.status_code}")
        logger.debug(f"Zenodo response headers: {response.headers}")
        logger.debug(f"Zenodo response content: {response.content.decode('utf-8')}")

        # Parse the response JSON
        try:
            response_json = response.json()
            logger.debug(f"Zenodo response JSON: {response_json}")
        except ValueError:
            logger.error("Failed to parse JSON response from Zenodo.")
            return render(request, 'core/error.html', {
                'title': _('ZENODO error'),
                'errors': [_('Failed to parse JSON response from Zenodo.')]
            }, status=200)

        zenodo_url = response_json.get('links', {}).get('self_html')
        if zenodo_url:
            return redirect(zenodo_url)
        else:
            return render(request, 'core/error.html', {
                'title': _('ZENODO error'),
                'errors': [_('The URL of the new dataset could not be retrieved.')]
            }, status=200)

    def get_post_url(self):
        return self.deposit_url

    def get_values_from_snapshot(self, attribute_path, snapshot):
        """Retrieve values from a snapshot for a given attribute path."""
        try:
            attribute = Attribute.objects.get(path=attribute_path)
        except Attribute.DoesNotExist:
            return []

        return Value.objects.filter(project=self.project, snapshot=snapshot, attribute=attribute)

    def get_text_from_snapshot(self, attribute_path, snapshot):
        """Retrieve the text of the first value from a snapshot for a given attribute path."""
        values = self.get_values_from_snapshot(attribute_path, snapshot)
        if values:
            return values[0].text
        return ''

    def get_post_data(self, snapshot):
        # see https://inveniordm.docs.cern.ch/reference/metadata/ for invenio metadata
        metadata = {}

        # set the title from the snapshot's title or id
        metadata['title'] = snapshot.title or f"Snapshot {snapshot.id}"

        # set the resource_type from the settings
        metadata['resource_type'] = {'id': 'publication-datamanagementplan'}

        # set the description
        description = snapshot.description or f"Data Management Plan for project {self.project.title}"
        if description:
            metadata['description'] = description

        # set subjects
        metadata['subjects'] = [
            {'subject': 'Data Management Plan'},
            {'subject': 'DMP'}
        ]

        # set keywords from snapshot values
        keywords = self.get_values_from_snapshot('project/research_question/keywords', snapshot)
        for keyword in keywords:
            if keyword.text:
                metadata['subjects'].append({'subject': keyword.text})

        # Continue to add other metadata fields as required...

        return {'metadata': metadata}
