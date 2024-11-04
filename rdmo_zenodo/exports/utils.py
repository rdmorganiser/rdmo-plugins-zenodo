from django.http import HttpResponse
from django.template import TemplateSyntaxError

from rdmo.core.utils import render_to_format
from rdmo.domain.models import Attribute
from rdmo.projects.models.snapshot import Snapshot
from rdmo.projects.models.value import Value
from rdmo.projects.utils import get_value_path
from rdmo.views.models import View

attribute_doi_uri_prefix = "https://rdmorganiser.github.io/terms"
attribute_doi_uri_key = "project/metadata/publication/zenodo_id"

def get_or_create_snapshot(project, snapshot_id=None):
    if snapshot_id is None:
        new_snapshot_title_id = project.snapshots.count() + 1
        description = f"{project.description}."
        description += f"\nThis snapshot({new_snapshot_title_id}.) was automatically generated."
        snapshot = Snapshot(project=project,
                            title=f"{project.title} {new_snapshot_title_id}",
                            description=description)
        snapshot.save()
    else:
        snapshot = project.snapshots.get(id=snapshot_id)

    return snapshot

def get_project_value_with_record_id(project):
    record_id_attribute, _created = Attribute.objects.get_or_create(uri_prefix=attribute_doi_uri_prefix,
                                                          key=attribute_doi_uri_key)
    project_doi_value = project.values.filter(attribute=record_id_attribute).first()
    return project_doi_value, record_id_attribute


def get_record_id_from_project_value(project):
    # get attribute

    project_doi_value, _ = get_project_value_with_record_id(project)

    if project_doi_value is not None:
        return project_doi_value.text
    else:
        return None

def set_record_id_on_project_value(project, record_id):
    if project is None or record_id is None:
        return

    project_doi_value, record_id_attribute = get_project_value_with_record_id(project)

    if project_doi_value is None:
        # create the value with text and add it
        value = Value(project=project, attribute=record_id_attribute, text=record_id)
        value.save()
        project.values.add(value)
    elif project_doi_value.text != record_id:
        # update and overwrite the value.text
        project_doi_value.text = record_id
        project_doi_value.save()

def clear_record_id_from_project_value(project):
    """Clear the record_id text from the project's values by setting it to an empty string."""
    set_record_id_on_project_value(project, '')

def render_project_views(project, snapshot, attachments_format, view=None):

    if view is None:
        view = View.objects.get(uri="https://rdmorganiser.github.io/terms/views/variable_check")

    try:
        rendered_view = view.render(project, snapshot)
    except TemplateSyntaxError:
        return HttpResponse()

    return render_to_format(
        None, attachments_format, project.title, 'projects/project_view_export.html', {
            'format': attachments_format,
            'title': project.title,
            'view': view,
            'rendered_view': rendered_view,
            'resource_path': get_value_path(project, snapshot)
        }
    )
