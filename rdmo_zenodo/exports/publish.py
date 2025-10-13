import logging

from django.http import HttpResponseBadRequest
from django.shortcuts import redirect, render
from django.utils.formats import localize
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _

import requests

from rdmo.projects.models import Project

from .base import BaseZenodoExportProvider
from .forms import ZenodoSnapshotForm
from .metadata.exceptions import MetadataBuildError
from .utils import (
    clear_record_id_from_project_value,
    get_concept_or_parent_id_from_payload,
    get_or_create_snapshot,
    get_record_id_from_project_value,
    render_and_export_project_from_view,
    save_record_id_in_project_value,
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

            if record_versions_url := self.validate_record_id_from_project_value_at_zenodo():
                # if record exists then post new version to zenodo, no data required
                # a 403 post_with_retry handled in retry.
                return self.post_with_retry(self.request, record_versions_url, {})
            else:
                # else create new draft record
                try:
                    payload = self.get_metadata()
                except MetadataBuildError as e:
                    form.add_error(None, str(e))
                    return render(
                        self.request, 'plugins/exports_zenodo.html', {'form': form}, status=400
                    )
                return self.post_with_retry(self.request, self.records_url, payload)
        else:
            return render(self.request, 'plugins/exports_zenodo.html', {'form': form}, status=200)

    def validate_record_id_from_project_value_at_zenodo(self):
        # Retrieve record_id from the project's stored values
        record_id = get_record_id_from_project_value(self.project)

        if not record_id:
            logger.warning("validate record_id: no record ID found in project values.")
            return None

        # Send a GET request to Zenodo to validate the record ID
        response = requests.get(self.record_url(record_id), headers=self.authorization_header)

        # Check if the response was successful
        if response.status_code == 200:
            logger.info(f"Record ID {record_id} is valid.")

            concept_record_id = get_concept_or_parent_id_from_payload(response.json())
            save_record_id_in_project_value(self.project, concept_record_id)
            versions_url = response.json().get('links', {}).get('versions')
            return versions_url
        elif response.status_code == 404:
            logger.warning(f"Record ID {record_id} is invalid or not found in {response.request.url}.")
            # the record_id does not exist, delete it from the project.value.text
            clear_record_id_from_project_value(self.project)
        else:
            # Log any other unexpected response code
            logger.error(f"Error validating record ID {record_id}: {response.status_code}")
        return None

    def post_success(self, request, response):
        # Retrieve project,snapshot,view and export_format from session
        self.get_from_session_and_set_on_self(request)
        self.request = request  # and set request on self
        if not response.json()['is_draft']:  # and ... response.json()['status'] == ...
            # metadata needs to be posted to the new version with a new request and response
            zenodo_api_url = response.json().get('links', {}).get('self')
            try:
                data = self.get_metadata()
            except MetadataBuildError as e:
                return render(request, 'core/error.html', {
                    'title': _('Metadata error'),
                    'errors': [_('Error in the metadata'), str(e)]
                }, status=200)

            response = requests.put(zenodo_api_url, json=data, headers=self.authorized_json_header)
            logger.debug("PUT to %s", zenodo_api_url)

        payload = response.json()
        zenodo_url = payload.get("links", {}).get("self_html")

        if zenodo_url:
            record_id = payload.get('id')
            concept_record_id = get_concept_or_parent_id_from_payload(payload)
            files_url = payload.get('links', {}).get('files')
            export_response = self.post_export_file_to_zenodo(
                record_id=record_id, files_url=files_url,
            )
            if 500 > export_response.status_code >= 400:
                if isinstance(export_response, HttpResponseBadRequest):
                    if export_response.content.decode().startswith('Render to format failed.'):
                        message = 'Render to format failed. Try another view or format.'
                    else:
                        message = export_response.content.decode()

                    return render(request, 'core/error.html', {
                        'title': _('Export error'),
                        'errors': [_('The project could not be exported.'), message],
                    }, status=200)

                if export_response.url.startswith(self.zenodo_url):
                    return render(request, 'core/error.html', {
                        'title': _('Export error'),
                        'errors': [_('The project could not be uploaded.'), response.json().get('message')],
                    }, status=200)


            publish_response = self.publish_draft_record(record_id=record_id)
            if 500 > publish_response.status_code >= 400:
                return render(request, 'core/error.html', {
                    'title': _('Publish error'),
                    'errors': [_('The project could not be published.'),
                        publish_response.json()['message'],
                        publish_response.json()['errors'],
                   ],
                }, status=200)

            save_record_id_in_project_value(self.project, concept_record_id)
            return redirect(zenodo_url)
        else:
            return render(request, 'core/error.html', {
                'title': _('ZENODO error'),
                'errors': [_('The URL of the new publication could not be retrieved.')]
            }, status=200)

    def post_export_file_to_zenodo(
            self, record_id=None, files_url=None
        ):
        # https://inveniordm.docs.cern.ch/reference/rest_api_drafts_records/#draft-files
        if record_id is None or files_url is None or self.export_format is None:
            logger.debug("post export file failed, missing args")
            return None

        rdmo_render_response = render_and_export_project_from_view(
            self.project, self.snapshot, self.export_format, view=self.view
        )
        if rdmo_render_response.status_code != 200:
            logger.error("Render failed: %s", rdmo_render_response.content.decode())
            return rdmo_render_response

        binary = rdmo_render_response.content
        export_filename = slugify(self.snapshot.title)
        filename = f"{export_filename}.{self.export_format}"

        # get access token from the session
        draft_file_post_response = requests.post(files_url, headers=self.authorization_header, json=[{'key': filename}])
        entries = draft_file_post_response.json().get('entries', [])
        draft_file_entry = next(filter(lambda i: i["key"] == filename, entries), None)
        if draft_file_entry is None:
            breakpoint()
            return draft_file_post_response

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
        logger.debug("POST to %s with response ", publish_url, response)
        return response
