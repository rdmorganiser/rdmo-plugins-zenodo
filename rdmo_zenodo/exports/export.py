import logging

from django.shortcuts import redirect, render
from django.utils.translation import gettext_lazy as _

from .base import BaseZenodoExportProvider
from .forms import ZenodoDatasetForm
from .metadata.exceptions import MetadataBuildError

logger = logging.getLogger(__name__)


class ZenodoExportProvider(BaseZenodoExportProvider):

    def get_dataset_choices(self):
        datasets = self.get_set('project/dataset/id')
        return [(dataset.set_index, dataset.value) for dataset in datasets]

    def render(self):
        dataset_choices = self.get_dataset_choices()

        self.store_in_session(self.request, 'dataset_choices', dataset_choices)

        form = ZenodoDatasetForm(
            dataset_choices=dataset_choices
        )

        return render(self.request, 'plugins/exports_zenodo.html', {'form': form}, status=200)

    def submit(self):
        dataset_choices = self.get_from_session(self.request, 'dataset_choices')
        form = ZenodoDatasetForm(self.request.POST, dataset_choices=dataset_choices)

        if 'cancel' in self.request.POST:
            return redirect('project', self.project.id)

        if form.is_valid():
            url = self.records_url
            try:
                payload = self.get_metadata(set_index=form.cleaned_data['dataset'])
            except MetadataBuildError as e:
                form.add_error(None, str(e))
                return render(self.request, 'plugins/exports_zenodo.html', {'form': form}, status=400)
            return self.post(self.request, url, payload)
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


