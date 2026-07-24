import os
import sys
import django

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "cutting_backend.settings")
django.setup()

from rest_framework.test import APIRequestFactory, force_authenticate
from django.contrib.auth.models import User
from planner.views import generate_block_visualization
from django.conf import settings

factory = APIRequestFactory()
user = User.objects.all()[0]

def get_html_content(job_id):
    request = factory.post('/api/visualization/block/B1/', {'job_id': job_id}, format='json')
    force_authenticate(request, user=user)
    response = generate_block_visualization(request, block_code='B1')
    url = response.data['visualization_url']
    local_path = os.path.join(settings.MEDIA_ROOT, url.replace('/media/', ''))
    with open(local_path, 'r') as f:
        return f.read()

content_28 = get_html_content(28)
content_36 = get_html_content(36)

print("Job 28 has 'G21':", 'G21' in content_28)
print("Job 28 has 'G4':", 'G4' in content_28)
print("Job 36 has 'G21':", 'G21' in content_36)
print("Job 36 has 'G4':", 'G4' in content_36)
