import os
import sys
import django

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "cutting_backend.settings")
django.setup()

from rest_framework.test import APIRequestFactory, force_authenticate
from django.contrib.auth.models import User
from planner.views import generate_block_visualization
from planner.models import OptimizationHistory

factory = APIRequestFactory()
user = User.objects.all()[0]

# Let's test with job_id=28 and job_id=36
for job_id in [28, 36]:
    print(f"\n--- Testing API generate_block_visualization for Job {job_id} ---")
    try:
        # Check if record exists
        if not OptimizationHistory.objects.filter(id=job_id).exists():
            print(f"Job {job_id} does not exist in DB, skipping.")
            continue
            
        request = factory.post(f'/api/visualization/block/B1/', {'job_id': job_id}, format='json')
        force_authenticate(request, user=user)
        
        response = generate_block_visualization(request, block_code='B1')
        print(f"Status code: {response.status_code}")
        print(f"Data: {response.data}")
    except Exception as e:
        import traceback
        traceback.print_exc()
