"""Validation des champs de ciblage HTML ; les données métier restent dans DRF."""
from django import forms


class DestinationForm(forms.Form):
    project_slug = forms.SlugField(label="Project slug", max_length=200,
                                  widget=forms.TextInput(attrs={"list": "project-slugs"}))
    page_slug = forms.SlugField(label="Page slug (facultatif)", max_length=200, required=False)


class PatchResourceForm(DestinationForm):
    resource_type = forms.ChoiceField(label="Type", choices=[("project", "Project"), ("page", "Page")])
    payload = forms.CharField(label="JSON partiel", strip=False,
                              widget=forms.Textarea(attrs={"rows": 12, "spellcheck": "false"}))

    def clean(self):
        data = super().clean()
        if data.get("resource_type") == "page" and not data.get("page_slug"):
            self.add_error("page_slug", "Indiquez le slug de la page à modifier.")
        if data.get("resource_type") == "project" and data.get("page_slug"):
            self.add_error("page_slug", "Laissez ce champ vide pour modifier le Project.")
        return data


class AddImageForm(DestinationForm):
    image_id = forms.UUIDField(label="UUID d'une image existante", required=False)
    file = forms.FileField(label="Nouvelle image", required=False,
                           widget=forms.ClearableFileInput(attrs={"accept": "image/*"}))
    alt = forms.CharField(label="Texte alternatif", required=False, max_length=255)
    theme = forms.CharField(label="Thème", required=False, max_length=50)

    def clean(self):
        data = super().clean()
        # Ne pas masquer une erreur UUID/fichier par une erreur de choix de source.
        if "image_id" in self.errors or "file" in self.errors:
            return data
        if bool(data.get("image_id")) == bool(data.get("file")):
            raise forms.ValidationError("Choisissez une seule source : un UUID OU un fichier image.")
        return data
