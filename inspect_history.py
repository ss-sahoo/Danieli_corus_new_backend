import os
import sys
import django

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "cutting_backend.settings")
django.setup()

from planner.models import OptimizationHistory

try:
    record = OptimizationHistory.objects.get(id=28)
    blocks = record.optimization_results.get('blocks', [])
    for b in blocks:
        print(f"Block {b.get('code')}: size={b.get('size')}, efficiency={b.get('efficiency'):.2f}%, prisms={b.get('prisms')}")
except Exception as e:
    print(f"Error: {e}")
