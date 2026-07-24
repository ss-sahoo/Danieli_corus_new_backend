import os
import sys
import django

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "cutting_backend.settings")
django.setup()

from django.core.cache import cache
from planner.views import get_helper_for_job

helper = get_helper_for_job(28, cache)
print(f"Reconstructed blocks count: {len(helper.all_big_blocks)}")
for idx, b in enumerate(helper.all_big_blocks):
    counts = {}
    for pd in b.prism_details:
        prism = pd['prism']
        count = len(pd['coordinates'])
        counts[prism.code] = count
    
    print(f"Reconstructed Block B{idx+1}: prisms={counts}")
