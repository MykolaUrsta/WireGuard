# WireGuard Panel Images

This directory contains images for the WireGuard Panel application:

- logo.svg - Main application logo
- favicon.ico - Browser favicon
- icons/ - Various UI icons
- backgrounds/ - Background images for different themes

## Usage

Images can be referenced in templates using:
```html
{% load static %}
<img src="{% static 'images/logo.svg' %}" alt="WireGuard Panel">
```
