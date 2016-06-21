{% extends "email_template" %}
{% block content %}
Thank you for using {{SITE_NAME}} to make a contribution to {{pledge.targets_summary}}.

{% if not pledge.is_executed %}We need to confirm your email address before we can schedule your contribution. Please click the link below to confirm.{% else %}Please confirm your email address by clicking the link below so that you can come back to {{SITE_NAME}} later to see the status of your contributions.{% endif %}

[{{confirmation_url}}]({{confirmation_url}})

You may need to copy the address into your web browser.

Thanks!
{% endblock %}
