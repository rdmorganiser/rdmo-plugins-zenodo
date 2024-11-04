import logging

from django.shortcuts import redirect, render
from django.utils.formats import localize
from django.utils.translation import gettext_lazy as _

import requests

from rdmo.projects.models import Project

from .base import BaseZenodoExportProvider
from .forms import ZenodoSnapshotForm
from .metadata import ZenodoMetadataExport
from .utils import (
    clear_record_id_from_project_value,
    get_or_create_snapshot,
    get_record_id_from_project_value,
    render_project_views,
    set_record_id_on_project_value,
)

logger = logging.getLogger(__name__)


class ZenodoPublishProvider(BaseZenodoExportProvider):

    RDMO_PLUGIN_KEY = "zenodo-publish"

    def get_snapshot_choices(self):
        snapshots = self.project.snapshots.order_by('-created')
        formatted_list = [(i.id, f"{i.title} (id={i.id}, {localize(i.created)})")
                            for i in snapshots]
        return formatted_list

    def render(self):
        snapshot_choices = self.get_snapshot_choices()

        self.store_in_session(self.request, 'snapshot_choices', snapshot_choices)

        form = ZenodoSnapshotForm(
            snapshot_choices=snapshot_choices
        )
        context = {'form': form }

        record_id = get_record_id_from_project_value(self.project)
        if record_id:
            context['record_id'] = self.record_uploads_url(record_id)

        return render(self.request, 'plugins/exports_zenodo.html', context=context, status=200)

    def submit(self):
        snapshot_choices = self.get_from_session(self.request, 'snapshot_choices')
        form = ZenodoSnapshotForm(self.request.POST, snapshot_choices=snapshot_choices)

        if 'cancel' in self.request.POST:
            return redirect('project', self.project.id)

        if form.is_valid():
            url = self.records_url  # deposit url
            snapshot_id = form.cleaned_data['snapshot'] or None
            snapshot = get_or_create_snapshot(self.project, snapshot_id=snapshot_id)
            self.snapshot = snapshot  # set class attribute for Export.get_values

            # store project and snapshot in session else they get lost after post
            self.store_in_session(self.request, 'project_id', self.project.id)
            self.store_in_session(self.request, 'snapshot_id', self.snapshot.id)

            record_versions_url = self.validate_record_id_from_project_value_at_zenodo()
            if record_versions_url:
                # if record exists then post new version to zenodo, no data required
                url = record_versions_url
                return self.post(self.request, url, {})
            else:
                # else create new draft record
                data = self.get_post_data(self.project, self.snapshot)
                return self.post(self.request, url, data)
        else:
            return render(self.request, 'plugins/exports_zenodo.html', {'form': form}, status=200)

    def validate_record_id_from_project_value_at_zenodo(self):
        """Validate the Zenodo record_id stored in the project."""

        # Retrieve record_id from the project's stored values
        record_id = get_record_id_from_project_value(self.project)

        if not record_id:
            logger.warning("No record ID found in project values.")
            return

        # Send a GET request to Zenodo to validate the record ID
        response = requests.get(self.record_url(record_id), headers=self.authorization_header)
        # response = self.get(self.request, record_url)

        # Check if the response is successful
        if response.status_code == 200:
            logger.info(f"Record ID {record_id} is valid.")
            # the conceptrecid is the  concept record identifier for all verions of this zenodo record
            # https://inveniordm.docs.cern.ch/reference/metadata/#system-managed-persistent-identifiers
            # in invenioRDM it is the parent.id field
            concept_record_id = response.json()['conceptrecid']
            set_record_id_on_project_value(self.project, concept_record_id)

            versions_url = response.json().get('links', {}).get('versions')
            return versions_url
        elif response.status_code == 404:
            logger.warning(f"Record ID {record_id} is invalid or not found in Zenodo.")
            # the record_id does not exist, delete it from the project.value.text
            clear_record_id_from_project_value(self.project)
        else:
            # Log any other unexpected response code
            logger.error(f"Error validating record ID {record_id}: {response.status_code}")

    def get_project_and_snapshot_from_session(self, request):
        project_id = self.get_from_session(request, 'project_id')
        snapshot_id = self.get_from_session(request, 'snapshot_id')
        project = Project.objects.filter_user(request.user).get(id=project_id)
        snapshot = project.snapshots.get(id=snapshot_id)
        return project, snapshot

    def post_success(self, request, response):
        # the class attributes on self need to be redefined
        # Retrieve project,snapshot from session
        project, snapshot = self.get_project_and_snapshot_from_session(request)
        self.project = project
        self.snapshot = snapshot

        # and set request on self
        self.request = request


        if 'versions' in response.request.url and 'publication_date' not in response.json().get('metadata',{}):
            # metadata needs to be posted to the new version
            zenodo_api_url = response.json().get('links', {}).get('self')
            data = self.get_post_data(self.project, self.snapshot)
            version_update_response = requests.put(zenodo_api_url, json=data, headers=self.authorized_json_header)
            logger.debug("PUT to %s", zenodo_api_url)
            zenodo_url = response.json().get('links', {}).get('self_html')
            response = version_update_response
        else:
            zenodo_url = response.json().get('links', {}).get('self_html')

        if zenodo_url:
            record_id = response.json().get('id')
            concept_record_id = response.json().get('conceptrecid')
            files_url = response.json().get('links', {}).get('files')
            _data_commit_pdf_response = self.post_export_file_to_zenodo(record_id=record_id, files_url=files_url,
                                                                       attachment_format=self.export_file_format)
            _publish_response = self.publish_draft_record(record_id=record_id)

            set_record_id_on_project_value(self.project, concept_record_id)

            return redirect(zenodo_url)
        else:
            return render(request, 'core/error.html', {
                'title': _('ZENODO error'),
                'errors': [_('The URL of the new dataset could not be retrieved.')]
            }, status=200)

    def post_export_file_to_zenodo(self, record_id=None, files_url=None, attachment_format=None, export_filename=None):
        # https://inveniordm.docs.cern.ch/reference/rest_api_drafts_records/#draft-files
        if record_id is None or files_url is None or attachment_format is None:
            return

        rdmo_pdf_response = render_project_views(self.project, self.snapshot, attachment_format)
        binary = rdmo_pdf_response.content
        export_filename = export_filename or "rdmo_dmp"
        filename = f"{export_filename}.{attachment_format}"

        # get access token from the session
        draft_file_post_response = requests.post(files_url, headers=self.authorization_header, json=[{'key': filename}])
        entries = draft_file_post_response.json().get('entries', [])
        draft_file_entry = next(filter(lambda i: i["key"] == filename, entries), None)
        if draft_file_entry is None:
            return

        content_url = draft_file_entry.get('links', {}).get('content')
        _data_content_response = requests.put(content_url, headers=self.authorized_binary_header, data=binary)
        logger.debug("PUT to %s", content_url)

        commit_url = draft_file_entry.get('links', {}).get('commit')
        data_commit_response = requests.post(commit_url, headers=self.authorization_header)
        logger.debug("POST to %s", commit_url)

        return data_commit_response

    def publish_draft_record(self, record_id=None):
        # https://inveniordm.docs.cern.ch/reference/rest_api_drafts_records/#publish-a-draft-record
        if record_id is None:
            return
        publish_url = self.record_publish_url(record_id)
        response = requests.post(publish_url, headers=self.authorization_header)
        logger.debug("POST to %s", publish_url)
        return response

    def get_post_data(self, project, snapshot):
        # see https://inveniordm.docs.cern.ch/reference/metadata/ for invenio metadata
        metadata_builder = ZenodoMetadataExport(project=project, snapshot=snapshot)
        return metadata_builder.build_metadata()
