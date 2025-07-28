import logging

from django.conf import settings
from django.shortcuts import redirect, render
from django.utils.formats import localize
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _

import requests

from rdmo.projects.models import Project

from rdmo_zenodo.exports.metadata.snapshot import ZenodoMetadataSnapshotBuilder

from .base import BaseZenodoExportProvider
from .forms import ZenodoSnapshotForm
from .utils import (
    clear_record_id_from_project_value,
    get_or_create_snapshot,
    get_record_id_from_project_value,
    render_and_export_project_from_view,
    set_record_id_on_project_value,
)

logger = logging.getLogger(__name__)


class ZenodoPublishProvider(BaseZenodoExportProvider):

    view = None
    export_format = None

    def get_snapshot_choices(self):
        return [
            (i.id, f"{i.title} ({localize(i.created)})")
            for i in self.project.snapshots.order_by('-created')
        ]

    def get_view_choices(self):
        return [
            (i.id, f"{i.title}")
            for i in self.project.views.all()
        ]

    def get_from_session_and_set_on_self(self, request):
        self.project = self.get_project_from_session(request)
        self.snapshot = self.get_snapshot_from_session(request, self.project)
        self.view = self.get_view_from_session(request, self.project)
        self.export_format = self.get_from_session(request, 'export_format')

    def get_project_from_session(self, request):
        project_id = self.get_from_session(request, 'project_id')
        return Project.objects.filter_user(request.user).get(id=project_id)

    def get_snapshot_from_session(self, request, project):
        snapshot_id = self.get_from_session(request, 'snapshot_id')
        return project.snapshots.get(id=snapshot_id)

    def get_view_from_session(self, request, project):
        view_id = self.get_from_session(request, 'view_id')
        return project.views.get(id=view_id)

    def render(self):
        snapshot_choices = self.get_snapshot_choices()
        view_choices = self.get_view_choices()

        self.store_in_session(self.request, 'snapshot_choices', snapshot_choices)
        self.store_in_session(self.request, "view_choices", view_choices)

        form = ZenodoSnapshotForm(
            snapshot_choices=snapshot_choices,
            view_choices=view_choices,
        )
        context = {'form': form }

        record_id = get_record_id_from_project_value(self.project)
        if record_id:
            context['record_id'] = self.record_uploads_url(record_id)

        return render(self.request, 'plugins/publish_zenodo.html', context=context, status=200)

    def submit(self):
        snapshot_choices = self.get_from_session(self.request, 'snapshot_choices')
        view_choices = self.get_from_session(self.request, "view_choices")
        form = ZenodoSnapshotForm(self.request.POST, snapshot_choices=snapshot_choices, view_choices=view_choices)

        if 'cancel' in self.request.POST:
            return redirect('project', self.project.id)

        if form.is_valid():
            url = self.records_url  # deposit url
            snapshot_id = form.cleaned_data['snapshot'] or None
            self.snapshot = get_or_create_snapshot(self.project, snapshot_id=snapshot_id)
            view_id = form.cleaned_data['view'] or None
            self.view = self.project.views.get(pk=view_id)
            self.export_format = form.cleaned_data['export_format'] or None

            # store project and snapshot in session else they get lost after post
            self.store_in_session(self.request, 'project_id', self.project.id)
            self.store_in_session(self.request, 'snapshot_id', self.snapshot.id)
            self.store_in_session(self.request, 'view_id', self.view.id)
            self.store_in_session(self.request, 'export_format', self.export_format)

            record_versions_url = self.validate_record_id_from_project_value_at_zenodo()
            # TODO, currently the authentication can get stuck when trying out the dataset export
            # first and this one afterwards, a 403 needs to be handled in the Export class.
            if record_versions_url:
                # if record exists then post new version to zenodo, no data required
                return self.post(self.request, record_versions_url, {})
            else:
                # else create new draft record
                data = self.get_post_data()
                return self.post(self.request, url, data)
        else:
            return render(self.request, 'plugins/exports_zenodo.html', {'form': form}, status=200)

    def validate_record_id_from_project_value_at_zenodo(self):
        """Validate the Zenodo record_id stored in the project."""

        # Retrieve record_id from the project's stored values
        record_id = get_record_id_from_project_value(self.project)

        if not record_id:
            logger.warning("validate record_id: no record ID found in project values.")
            return

        # Send a GET request to Zenodo to validate the record ID
        response = requests.get(self.record_url(record_id), headers=self.authorization_header)

        # Check if the response was successful
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

    def post_success(self, request, response):
        # Retrieve project,snapshot,view and export_format from session
        self.get_from_session_and_set_on_self(request)
        self.request = request  # and set request on self
        if 'versions' in response.request.url and 'publication_date' not in response.json().get('metadata',{}):
            # metadata needs to be posted to the new version with a new request and response
            zenodo_api_url = response.json().get('links', {}).get('self')
            data = self.get_post_data()
            response = requests.put(zenodo_api_url, json=data, headers=self.authorized_json_header)
            logger.debug("PUT to %s", zenodo_api_url)

        payload = response.json()
        zenodo_url = payload.get("links", {}).get("self_html")

        if zenodo_url:
            record_id = payload.get('id')
            concept_record_id = payload["conceptrecid"]
            files_url = payload.get('links', {}).get('files')

            _data_commit_pdf_response = self.post_export_file_to_zenodo(
                record_id=record_id, files_url=files_url,
            )
            _publish_response = self.publish_draft_record(record_id=record_id)

            set_record_id_on_project_value(self.project, concept_record_id)

            return redirect(zenodo_url)
        else:
            return render(request, 'core/error.html', {
                'title': _('ZENODO error'),
                'errors': [_('The URL of the new dataset could not be retrieved.')]
            }, status=200)

    def post_export_file_to_zenodo(
            self, record_id=None, files_url=None
        ):
        # https://inveniordm.docs.cern.ch/reference/rest_api_drafts_records/#draft-files
        if record_id is None or files_url is None or self.export_format is None:
            logger.debug("post export file failed, missing args")
            return

        rdmo_render_response = render_and_export_project_from_view(
            self.project, self.snapshot, self.export_format, view=self.view
        )
        if rdmo_render_response.status_code != 200:
            logger.debug("Render failed: %s", rdmo_render_response.content.decode())
            return

        binary = rdmo_render_response.content
        export_filename = slugify(self.snapshot.title)
        filename = f"{export_filename}.{self.export_format}"

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
            logger.debug("POST to publish failed, missing record_id")
            return None
        publish_url = self.record_publish_url(record_id)
        response = requests.post(publish_url, headers=self.authorization_header)
        logger.debug("POST to %s", publish_url)
        return response

    def get_post_data(self):
        # see https://inveniordm.docs.cern.ch/reference/metadata/ for invenio metadata
        if self.project is None or self.snapshot is None:
            raise ValueError("Project and Snapshot are required to get post data.")

        title = f"{self.project.title} - Snapshot: {self.snapshot.title}"
        description = f"Data Management Plan for project {self.project.title}."
        if self.snapshot.description:
            description += f" {self.snapshot.description}"
        description += f" Exported to {self.export_format} with the {self.view.title} view."

        metadata_builder = ZenodoMetadataSnapshotBuilder(
            title=title,
            description=description,
            keywords=[
                i.text
                for i in self.get_values("project/research_question/keywords") if i.text
            ],
            rights_uri_paths=[
                i.option.uri_path
                for i in self.get_values("project/dataset/sharing/conditions") if i.option
            ],
            project_users=self.project.user.all() if settings.ZENODO_PROVIDER.get("add_project_members") else [],
        )
        return metadata_builder.to_post_data(filter_empty=True)
