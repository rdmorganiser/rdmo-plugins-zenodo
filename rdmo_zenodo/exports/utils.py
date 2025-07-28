from django.http import HttpResponseBadRequest
from django.template import TemplateDoesNotExist, TemplateSyntaxError

from rdmo.core.utils import render_to_format
from rdmo.domain.models import Attribute
from rdmo.projects.models.snapshot import Snapshot
from rdmo.projects.models.value import Value
from rdmo.projects.utils import get_value_path

ATTRIBUTE_DOI_URI_PREFIX = "https://rdmorganiser.github.io/terms"
ATTRIBUTE_DOI_URI_KEY = "project/metadata/publication/zenodo_id"


def get_or_create_snapshot(project, snapshot_id=None):
    if snapshot_id is None:
        new_snapshot_count = project.snapshots.count() + 1
        description = f"{project.description}."
        description += f"\nThis snapshot({new_snapshot_count}.) was automatically generated."
        snapshot = Snapshot(
            project=project,
            title=f"{project.title} #{new_snapshot_count}",  # "Cool project #3"
            description=description
        )
        snapshot.save()
        return snapshot

    return project.snapshots.get(id=snapshot_id)


def get_project_value_with_record_id(project):
    record_id_attribute, _created = Attribute.objects.get_or_create(
        uri_prefix=ATTRIBUTE_DOI_URI_PREFIX,
        key=ATTRIBUTE_DOI_URI_KEY
    )
    project_doi_value = project.values.filter(attribute=record_id_attribute).first()
    return project_doi_value, record_id_attribute


def get_record_id_from_project_value(project):
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
        # create the value with the record_id and add it to the project
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


def render_and_export_project_from_view(project, snapshot, export_format, view):

    try:
        rendered_view = view.render(project, snapshot)
    except (TemplateDoesNotExist,TemplateSyntaxError) as e:
        return HttpResponseBadRequest(f"Render from view failed. {e}")

    try:
        response = render_to_format(
            None, export_format, project.title, 'projects/project_view_export.html', {
                'format': export_format,
                'title': project.title,
                'view': view,
                'rendered_view': rendered_view,
                'resource_path': get_value_path(project, snapshot)
            }
        )
    except RuntimeError as e:
        return HttpResponseBadRequest(f"Render to format failed. {e}")
    except (TemplateDoesNotExist,TemplateSyntaxError) as e:
        return HttpResponseBadRequest(f"Render to format failed, template error. {e}")
    else:
        return response
