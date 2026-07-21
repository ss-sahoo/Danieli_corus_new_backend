import sys
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'danieli_corus.settings')
django.setup()

from planner.modules.svg_renderer import generate_svg_for_block_side

class DummyBlock:
    def __init__(self):
        self.size = [1000, 500, 200]
        self.prism_details = []
        self.scraps = []
        self.unique_code = "B_TEST"
        
    def get_efficiency(self):
        return 0

b = DummyBlock()
svg = generate_svg_for_block_side(b, "Front")
print(svg)
