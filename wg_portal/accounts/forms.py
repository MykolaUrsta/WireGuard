from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import authenticate
from .models import CustomUser


class UserRegistrationForm(UserCreationForm):
    """Форма реєстрації користувача"""
    
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Введіть email'
        })
    )
    first_name = forms.CharField(
        max_length=30,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Ім\'я'
        })
    )
    last_name = forms.CharField(
        max_length=30,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Прізвище'
        })
    )
    
    class Meta:
        model = CustomUser
        fields = ('username', 'email', 'first_name', 'last_name', 'password1', 'password2')
        widgets = {
            'username': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Введіть логін'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['password1'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Введіть пароль'
        })
        self.fields['password2'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Підтвердіть пароль'
        })
    
    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        if commit:
            user.save()
        return user


class UserLoginForm(forms.Form):
    """Форма входу користувача"""
    
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Введіть email',
            'required': True
        })
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Введіть пароль',
            'required': True
        })
    )
    
    def clean(self):
        cleaned_data = super().clean()
        email = cleaned_data.get('email')
        password = cleaned_data.get('password')
        
        if email and password:
            # Перевіряємо чи існує користувач з таким email
            try:
                user = CustomUser.objects.get(email=email)
                if not user.check_password(password):
                    raise forms.ValidationError('Невірний email або пароль')
            except CustomUser.DoesNotExist:
                raise forms.ValidationError('Невірний email або пароль')
        
        return cleaned_data


class Enable2FAForm(forms.Form):
    """Форма для увімкнення 2FA"""
    
    token = forms.CharField(
        max_length=6,
        min_length=6,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Введіть 6-значний код',
            'pattern': '[0-9]{6}',
            'required': True
        })
    )
    device_name = forms.CharField(
        max_length=100,
        initial='Мобільний пристрій',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Назва пристрою'
        })
    )


class Verify2FAForm(forms.Form):
    """Форма перевірки 2FA коду"""
    
    token = forms.CharField(
        max_length=6,
        min_length=6,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Введіть 6-значний код',
            'pattern': '[0-9]{6}',
            'required': True,
            'autofocus': True
        })
    )
