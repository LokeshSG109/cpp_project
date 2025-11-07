from django import forms

class MultiFileField(forms.FileField):
    def clean(self, data, initial=None):
        # accept list of files instead of single file
        if not data:
            return []
        if not isinstance(data, (list, tuple)):
            data = [data]
        return data


class RegisterForm(forms.Form):
    full_name = forms.CharField(max_length=150, label="Full name", widget=forms.TextInput(attrs={"class":"form-control"}))
    email = forms.EmailField(label="Email", widget=forms.EmailInput(attrs={"class":"form-control"}))
    password = forms.CharField(label="Password", widget=forms.PasswordInput(attrs={"class":"form-control"}))
    password_confirm = forms.CharField(label="Confirm password", widget=forms.PasswordInput(attrs={"class":"form-control"}))

    def clean(self):
        cleaned = super().clean()
        p = cleaned.get("password")
        pc = cleaned.get("password_confirm")
        if p and pc and p != pc:
            self.add_error("password_confirm", "Passwords do not match")
        return cleaned


class LoginForm(forms.Form):
    email = forms.EmailField(label="Email", widget=forms.EmailInput(attrs={"class":"form-control"}))
    password = forms.CharField(label="Password", widget=forms.PasswordInput(attrs={"class":"form-control"}))


class MultiFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class AppointmentForm(forms.Form):
    issue = forms.CharField(
        label="Describe the issue",
        widget=forms.Textarea(attrs={"class":"form-control", "rows":3})
    )
    preferred_datetime = forms.CharField(
        label="Preferred date/time",
        widget=forms.TextInput(attrs={"class":"form-control", "placeholder":"YYYY-MM-DD HH:MM"})
    )
    photos = MultiFileField(
        label="Photos (you may upload multiple)",
        widget=MultiFileInput(attrs={"multiple": True, "class": "form-control"}),
        required=False
    )
