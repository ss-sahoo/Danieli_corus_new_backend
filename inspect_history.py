import os
import sys
import django

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "cutting_backend.settings")
django.setup()

import logging
logging.disable(logging.CRITICAL + 1)

from django.contrib.auth.models import User
from planner.models import OptimizationHistory

test_user = User.objects.get(username="test_admin")
# Assign some items to test_user
items = OptimizationHistory.objects.order_by('-id')[:5]
for idx, item in enumerate(items):
    item.user = test_user
    item.is_executed = False
    item.save()
    print(f"Assigned item ID {item.id} to test_user, reset is_executed to False")
