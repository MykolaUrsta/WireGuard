from django import forms
from locations.models import Location, Device, DeviceGroup, ACLRule, UserLocationAccess


class LocationForm(forms.ModelForm):
    class Meta:
        model = Location
        fields = ['name', 'description', 'server_ip', 'server_port', 'subnet', 
                 'interface_name', 'dns_servers', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Назва локації'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Опис локації'}),
            'server_ip': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '95.46.73.218'}),
            'server_port': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '51820'}),
            'subnet': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '10.13.13.0/24'}),
            'interface_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'wg0'}),
            'dns_servers': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '1.1.1.1,8.8.8.8'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class DeviceForm(forms.ModelForm):
    class Meta:
        model = Device
        fields = ['location', 'group', 'name', 'description']
        widgets = {
            'location': forms.Select(attrs={'class': 'form-select'}),
            'group': forms.Select(attrs={'class': 'form-select'}),
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Назва пристрою (наприклад: iPhone, Laptop)'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Опис пристрою'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['group'].required = False
        self.fields['description'].required = False


class DeviceGroupForm(forms.ModelForm):
    class Meta:
        model = DeviceGroup
        fields = ['name', 'description', 'color']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Назва групи'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Опис групи'}),
            'color': forms.TextInput(attrs={'class': 'form-control', 'type': 'color'}),
        }


class ACLRuleForm(forms.ModelForm):
    class Meta:
        model = ACLRule
        fields = ['name', 'description', 'source_group', 'source_ip', 'destination_ip', 
                 'protocol', 'destination_port', 'action', 'priority', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Назва правила'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Опис правила'}),
            'source_group': forms.Select(attrs={'class': 'form-select'}),
            'source_ip': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '10.0.0.0/24 або any'}),
            'destination_ip': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '10.0.0.0/24 або any'}),
            'protocol': forms.Select(attrs={'class': 'form-select'}),
            'destination_port': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '80, 80-90 або any'}),
            'action': forms.Select(attrs={'class': 'form-select'}),
            'priority': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '100'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class UserLocationAccessForm(forms.ModelForm):
    class Meta:
        model = UserLocationAccess
        fields = ['location', 'is_admin', 'max_devices']
        widgets = {
            'location': forms.Select(attrs={'class': 'form-select'}),
            'is_admin': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'max_devices': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '5'}),
        }
