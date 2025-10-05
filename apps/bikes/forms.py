"""
Bike Forms for CRUD Operations
"""

from django import forms


class BikeCreateForm(forms.Form):
    """Form for creating a new bike"""
    
    BIKE_TYPE_CHOICES = [
        ('REGULAR', 'Regular'),
        ('ELECTRIC', 'Electric'),
        ('MOUNTAIN', 'Mountain'),
    ]
    
    STATUS_CHOICES = [
        ('AVAILABLE', 'Available'),
        ('OFFLINE', 'Offline'),
    ]
    
    bike_id = forms.CharField(
        max_length=50,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g., BIKE001',
            'required': True
        }),
        help_text='Unique identifier for the bike'
    )
    
    bike_model = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g., Mountain Bike Pro',
            'required': True
        })
    )
    
    bike_type = forms.ChoiceField(
        choices=BIKE_TYPE_CHOICES,
        widget=forms.Select(attrs={
            'class': 'form-select',
            'required': True
        })
    )
    
    status = forms.ChoiceField(
        choices=STATUS_CHOICES,
        initial='AVAILABLE',
        widget=forms.Select(attrs={
            'class': 'form-select',
            'required': True
        })
    )
    
    current_zone_id = forms.CharField(
        max_length=255,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g., zone_malolos'
        }),
        help_text='Leave blank if not assigned to a zone'
    )
    
    latitude = forms.DecimalField(
        max_digits=10,
        decimal_places=7,
        required=False,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g., 14.8433',
            'step': '0.0000001'
        }),
        help_text='GPS latitude (optional)'
    )
    
    longitude = forms.DecimalField(
        max_digits=10,
        decimal_places=7,
        required=False,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g., 120.8111',
            'step': '0.0000001'
        }),
        help_text='GPS longitude (optional)'
    )
    
    def clean_bike_id(self):
        """Validate bike_id format"""
        bike_id = self.cleaned_data['bike_id'].upper().strip()
        
        # Remove special characters except dash and underscore
        if not bike_id.replace('_', '').replace('-', '').isalnum():
            raise forms.ValidationError('Bike ID can only contain letters, numbers, dashes, and underscores')
        
        return bike_id


class BikeUpdateForm(forms.Form):
    """Form for updating an existing bike"""
    
    BIKE_TYPE_CHOICES = [
        ('REGULAR', 'Regular'),
        ('ELECTRIC', 'Electric'),
        ('MOUNTAIN', 'Mountain'),
    ]
    
    STATUS_CHOICES = [
        ('AVAILABLE', 'Available'),
        ('IN_USE', 'In Use'),
        ('MAINTENANCE', 'Maintenance'),
        ('OFFLINE', 'Offline'),
    ]
    
    bike_model = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g., Mountain Bike Pro'
        })
    )
    
    bike_type = forms.ChoiceField(
        choices=BIKE_TYPE_CHOICES,
        widget=forms.Select(attrs={
            'class': 'form-select'
        })
    )
    
    status = forms.ChoiceField(
        choices=STATUS_CHOICES,
        widget=forms.Select(attrs={
            'class': 'form-select'
        })
    )
    
    current_zone_id = forms.CharField(
        max_length=255,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g., zone_malolos'
        }),
        help_text='Leave blank to remove zone assignment'
    )
    
    latitude = forms.DecimalField(
        max_digits=10,
        decimal_places=7,
        required=False,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g., 14.8433',
            'step': '0.0000001'
        })
    )
    
    longitude = forms.DecimalField(
        max_digits=10,
        decimal_places=7,
        required=False,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g., 120.8111',
            'step': '0.0000001'
        })
    )