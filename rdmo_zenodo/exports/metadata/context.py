from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from django.conf import settings

from rdmo.projects.models import Project, Snapshot


@dataclass(frozen=True)
class MetadataContext:
    project: Project
    snapshot: Snapshot | None
    set_index: int | None
    get_values: Callable[..., list[Any]]
    get_text: Callable[..., str | None]
    zenodo_backend_type: str
    view: Any | None = None
    export_format: str | None = None

    @property
    def project_members(self) -> list:
        if (
            settings.ZENODO_PROVIDER.get("add_project_members")
            and self.project is not None
            ):
            return list(self.project.user.all())
        return []
