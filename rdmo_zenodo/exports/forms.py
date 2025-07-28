from django import forms
from django.conf import settings
from django.utils.translation import gettext_lazy as _


class ZenodoDatasetForm(forms.Form):
    dataset = forms.CharField(label=_('Select dataset of your project'))

    def __init__(self, *args, **kwargs):
        dataset_choices = kwargs.pop('dataset_choices')
        super().__init__(*args, **kwargs)

        self.fields['dataset'].widget = forms.RadioSelect(choices=dataset_choices)


class ZenodoSnapshotForm(forms.Form):
    snapshot = forms.ChoiceField(
        label=_('Select snapshot of your project'),
        required=False,  # Allows empty selection
        widget=forms.RadioSelect
    )
    view = forms.ChoiceField(
        label=_("Select the view with which your project will be published"),
        required=False,  # Allows empty selection
        widget=forms.Select,
    )
    export_format = forms.ChoiceField(
        label=_("Select the export format"),
        required=False, widget=forms.Select,
        choices=settings.EXPORT_FORMATS
    )

    def __init__(self, *args, **kwargs):
        snapshot_choices = kwargs.pop('snapshot_choices', [])
        view_choices = kwargs.pop("view_choices", [])
        super().__init__(*args, **kwargs)
        snapshot_choices = [(None, _("Create new snapshot")), *snapshot_choices]
        self.fields['snapshot'].choices = snapshot_choices
        self.fields['snapshot'].initial = None
        self.fields['view'].choices = view_choices
