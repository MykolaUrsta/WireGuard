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


class UserAdminForm(forms.ModelForm):
    """Форма для додавання/редагування користувача адміністратором"""
    
    password = forms.CharField(
        required=False,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Залиште порожнім, щоб не змінювати'
        }),
        help_text='Залиште порожнім для редагування існуючого користувача'
    )
    
    confirm_password = forms.CharField(
        required=False,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Підтвердіть пароль'
        })
    )
    
    groups = forms.MultipleChoiceField(
        required=False,
        choices=[
            ('admin', 'Адміністратор'),
            ('staff', 'Персонал'),
            ('user', 'Користувач'),
        ],
        widget=forms.CheckboxSelectMultiple(),
        help_text='Виберіть групи користувача'
    )
    
    class Meta:
        model = CustomUser
        fields = [
            'username', 'email', 'first_name', 'last_name', 'phone',
            'department', 'position', 'is_active', 'is_staff', 'is_superuser',
            'is_wireguard_enabled', 'data_limit'
        ]
        widgets = {
            'username': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Логін користувача'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'Email адреса'
            }),
            'first_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ім\'я'
            }),
            'last_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Прізвище'
            }),
            'phone': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '+380...'
            }),
            'department': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Департамент'
            }),
            'position': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Посада'
            }),
            'data_limit': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ліміт у байтах (залиште порожнім для необмежено)'
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'is_staff': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'is_superuser': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'is_wireguard_enabled': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
        }
    
    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        confirm_password = cleaned_data.get('confirm_password')
        
        if password and password != confirm_password:
            raise forms.ValidationError('Паролі не співпадають')
        
        return cleaned_data
    
    def save(self, commit=True):
        user = super().save(commit=False)
        password = self.cleaned_data.get('password')
        
        if password:
            user.set_password(password)
        
        if commit:
            user.save()
            
        return user


class UserFilterForm(forms.Form):
    """Форма фільтрації користувачів"""
    
    FILTER_CHOICES = [
        ('all', 'Всі користувачі'),
        ('active', 'Активні'),
        ('inactive', 'Неактивні'),
        ('admin', 'Адміністратори'),
        ('staff', 'Персонал'),
        ('wireguard_enabled', 'З доступом до VPN'),
        ('wireguard_disabled', 'Без доступу до VPN'),
    ]
    
    filter_type = forms.ChoiceField(
        choices=FILTER_CHOICES,
        required=False,
        initial='all',
        widget=forms.Select(attrs={
            'class': 'filter-select',
            'onchange': 'this.form.submit()'
        })
    )
    
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'search-input',
            'placeholder': 'Знайти користувачів',
            'type': 'search'
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
