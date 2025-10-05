"""
Geofencing Forms for CRUD Operations
"""

from django import forms


class ZoneCreateForm(forms.Form):
    """Form for creating a new geofence zone"""
    
    zone_id = forms.CharField(
        max_length=50,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g., zone_malolos',
            'required': True
        }),
        help_text='Unique identifier for the zone'
    )
    
    name = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g., Malolos City Center',
            'required': True
        })
    )
    
    color_code = forms.CharField(
        max_length=7,
        initial='#3388ff',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'type': 'color',
            'required': True
        }),
        help_text='Color for displaying zone on map'
    )
    
    description = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Optional description of the zone'
        })
    )
    
    # Polygon points will be handled via JavaScript
    polygon_points = forms.CharField(
        widget=forms.HiddenInput(),
        required=True,
        help_text='Draw the zone boundary on the map'
    )
    
    def clean_zone_id(self):
        """Validate zone_id format"""
        zone_id = self.cleaned_data['zone_id'].lower().strip()
        
        # Remove special characters except dash and underscore
        if not zone_id.replace('_', '').replace('-', '').isalnum():
            raise forms.ValidationError('Zone ID can only contain letters, numbers, dashes, and underscores')
        
        return zone_id
    
    def clean_polygon_points(self):
        """Validate polygon points JSON"""
        import json
        
        points_json = self.cleaned_data['polygon_points']
        
        try:
            points = json.loads(points_json)
            
            if not isinstance(points, list):
                raise forms.ValidationError('Invalid polygon data format')
            
            if len(points) < 3:
                raise forms.ValidationError('A zone must have at least 3 points')
            
            # Validate each point has latitude and longitude
            for point in points:
                if 'latitude' not in point or 'longitude' not in point:
                    raise forms.ValidationError('Each point must have latitude and longitude')
                
                # Validate coordinate ranges
                lat = float(point['latitude'])
                lng = float(point['longitude'])
                
                if not (-90 <= lat <= 90):
                    raise forms.ValidationError(f'Invalid latitude: {lat}')
                if not (-180 <= lng <= 180):
                    raise forms.ValidationError(f'Invalid longitude: {lng}')
            
            return points_json
            
        except json.JSONDecodeError:
            raise forms.ValidationError('Invalid polygon data')


class ZoneUpdateForm(forms.Form):
    """Form for updating an existing zone"""
    
    name = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g., Malolos City Center'
        })
    )
    
    color_code = forms.CharField(
        max_length=7,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'type': 'color'
        })
    )
    
    description = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Optional description'
        })
    )
    
    is_active = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        })
    )
    
    # Polygon points
    polygon_points = forms.CharField(
        widget=forms.HiddenInput(),
        required=False,
        help_text='Update zone boundary on the map'
    )
    
    def clean_polygon_points(self):
        """Validate polygon points if provided"""
        import json
        
        points_json = self.cleaned_data.get('polygon_points')
        
        if not points_json:
            return points_json
        
        try:
            points = json.loads(points_json)
            
            if len(points) < 3:
                raise forms.ValidationError('A zone must have at least 3 points')
            
            return points_json
            
        except json.JSONDecodeError:
            raise forms.ValidationError('Invalid polygon data')


class ViolationFilterForm(forms.Form):
    """Form for filtering zone violations"""
    
    VIOLATION_TYPE_CHOICES = [
        ('', 'All Types'),
        ('EXIT_ZONE', 'Exit Zone'),
        ('UNAUTHORIZED_PARKING', 'Unauthorized Parking'),
        ('SPEED_LIMIT', 'Speed Limit Violation'),
    ]
    
    STATUS_CHOICES = [
        ('', 'All Status'),
        ('unresolved', 'Unresolved'),
        ('resolved', 'Resolved'),
    ]
    
    violation_type = forms.ChoiceField(
        choices=VIOLATION_TYPE_CHOICES,
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-select'
        })
    )
    
    status = forms.ChoiceField(
        choices=STATUS_CHOICES,
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-select'
        })
    )
    
    zone = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Filter by zone ID'
        })
    )
    
    bike_id = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Filter by bike ID'
        })
    )