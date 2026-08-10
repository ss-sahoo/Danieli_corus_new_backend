#!/usr/bin/env python
"""
Step-by-step inspector for the packing pipeline.

Runs each function of the live path in isolation and prints what it returned, so a
change can be checked one step at a time instead of only through the API response.

Usage
-----
    python inspect_pipeline.py                 # every step, in pipeline order
    python inspect_pipeline.py --list          # names and one-line descriptions
    python inspect_pipeline.py 6 7 8           # only these steps
    python inspect_pipeline.py scrap           # every step whose name matches 'scrap'
    python inspect_pipeline.py --excel "Sample_data_03 (1).xlsx" 17

Use the project interpreter, which has plotly and django-redis:

    PYTHONPATH=. /mnt/data_drive/cutting_blocks/env_cutting_block/bin/python inspect_pipeline.py

Everything runs against a throwaway test database and an in-process cache, so no step
touches real inventory rows, real history, or Redis. Steps 19-22 create and read rows in
that temporary database and it is destroyed on exit.
"""
import argparse
import io
import json
import os
import sys

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'cutting_backend.settings')

import django  # noqa: E402
django.setup()

from django.conf import settings  # noqa: E402
from django.core.cache import caches  # noqa: E402

# Redis is not always running locally and the view caches the helper there. locmem keeps
# the real code path intact without needing the service.
settings.CACHES = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
                               'LOCATION': 'inspect-pipeline'}}
caches._settings = settings.CACHES
try:
    del caches._caches.caches
except Exception:
    pass

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from planner.modules.fill import (  # noqa: E402
    place_box, place_prism_flip, fill_the_box, rotate,
    occupied_boxes_from_staircase, free_boxes, get_scrap_vol, CANDIDATE_DECOMPOSITIONS,
)
from planner.modules.packing_orchestrator import (  # noqa: E402
    Prisms, Block, Scrap, Rotation, People_helper,
    run_final_code, get_block_details, get_all_prisms, run_optimization_with_retries,
    find_overlaps, solids_overlap, aabb, boxes_overlap,
)
from planner.run_summary import build_summary, layout_signature, stock_sizes_from  # noqa: E402


# ----------------------------------------------------------------------------------
# Fixtures - small enough that every intermediate result is readable by eye
# ----------------------------------------------------------------------------------

BUFFER = 2.0

# [bottom_length, top_length, width, height]
PRISM_SIZE = [600, 500, 300, 200]
SMALL_PRISM_SIZE = [400, 400, 200, 150]

# [length, width, height]
SIZE_A = [1870, 800, 350]
SIZE_B = [2000, 800, 400]
PARENT_SIZES = [SIZE_A, SIZE_B]
PARENT_LABELS = ['A', 'B']

# Offcuts as they arrive from ScrapInventory
RECOVERED = [
    {'id': 101, 'scrap_id': 'B1-S1', 'size': [900, 700, 350]},
    {'id': 102, 'scrap_id': 'B1-S2', 'size': [50, 50, 50]},   # too small, gets pruned
]

PARTS_DF = pd.DataFrame([
    {'MARK': 'G1', 'Bottom Length': 600, 'Top Length': 500, 'Width': 300, 'Height': 200, 'Nos': 6},
    {'MARK': 'G2', 'Bottom Length': 400, 'Top Length': 400, 'Width': 200, 'Height': 150, 'Nos': 10},
])


def fresh_prism(size=None, qty=6, code='G1'):
    """A Prisms carries a mutable prism_left, so each step gets its own."""
    return Prisms(code, list(size or PRISM_SIZE), qty)


def fresh_helper(quantities=None, recovered=None):
    helper = People_helper(BUFFER, PARENT_SIZES, quantities)
    for piece in (recovered or []):
        helper.add_recovered_block(piece['size'], source=piece)
    return helper


# ----------------------------------------------------------------------------------
# Printing helpers
# ----------------------------------------------------------------------------------

def head(title):
    print(f"\n{'=' * 78}\n{title}\n{'=' * 78}")


def sub(title):
    print(f"\n--- {title} ---")


def kv(label, value):
    print(f"  {label:.<38} {value}")


def box(label, corners):
    """8-corner coordinate list -> min/max/size, which is what you actually want to see."""
    arr = np.asarray(corners, dtype=float)
    lo, hi = arr.min(axis=0), arr.max(axis=0)
    print(f"  {label:.<38} start={fmt(lo)} size={fmt(hi - lo)}")


def fmt(vec):
    return '[' + ', '.join(f'{float(v):g}' for v in np.asarray(vec).ravel()) + ']'


def table(rows, headers):
    if not rows:
        print("  (none)")
        return
    rows = [[str(c) for c in r] for r in rows]
    widths = [max(len(h), *(len(r[i]) for r in rows)) for i, h in enumerate(headers)]
    print('  ' + '  '.join(h.ljust(widths[i]) for i, h in enumerate(headers)))
    print('  ' + '  '.join('-' * widths[i] for i in range(len(headers))))
    for r in rows:
        print('  ' + '  '.join(r[i].ljust(widths[i]) for i in range(len(headers))))


def blocks_table(helper):
    table(
        [[b.unique_code,
          'recovered' if getattr(b, 'is_recovered', False) else 'new',
          getattr(b, 'source_scrap_id', None) or '-',
          getattr(b, 'size_index', None) if getattr(b, 'size_index', None) is not None else '-',
          fmt(b.size),
          sum(len(e['coordinates']) for e in b.prism_details),
          f"{b.get_efficiency():.2f}%",
          len(b.scraps)]
         for b in helper.all_big_blocks],
        ['code', 'origin', 'source', 'size_ix', 'size', 'parts', 'eff', 'scraps'])


# ----------------------------------------------------------------------------------
# Steps
# ----------------------------------------------------------------------------------

STEPS = []


def step(name, description):
    def register(fn):
        STEPS.append({'name': name, 'description': description, 'fn': fn})
        return fn
    return register


# ---- Geometry primitives ---------------------------------------------------------

@step('place_box', 'place_box / place_prism_flip - the 8-corner primitives')
def s_place_box(ctx):
    sub('place_box(starting_co=[0,0,0], 600x300x200)')
    corners = place_box([0, 0, 0], length=600, width=300, height=200)
    for i, c in enumerate(corners):
        print(f"  corner[{i}] {fmt(c)}")
    box('derived', corners)

    prism = fresh_prism()
    # returns (8 vertices, x1max, y1max, z1max) - the far corner feeds end_coordinates
    sub(f'place_prism_flip(prism={PRISM_SIZE}, buffer={BUFFER}, flip=False)')
    up, xmax, ymax, zmax = place_prism_flip(prism, BUFFER, coordinate=[0, 0, 0], flip=False)
    for i, c in enumerate(up):
        print(f"  vertex[{i}] {fmt(c)}")
    kv('far corner (x1max, y1max, z1max)', fmt([xmax, ymax, zmax]))
    print("  vertices 0-3 are the bottom face, 4-7 the top face")

    sub('place_prism_flip(..., flip=True) - the alternating orientation that nests')
    down, xmax_d, ymax_d, zmax_d = place_prism_flip(prism, BUFFER, coordinate=[0, 0, 0],
                                                    flip=True)
    for i, c in enumerate(down):
        print(f"  vertex[{i}] {fmt(c)}")
    kv('far corner', fmt([xmax_d, ymax_d, zmax_d]))
    kv('bottom face differs from unflipped',
       not np.allclose(np.asarray(up[:4], dtype=float), np.asarray(down[:4], dtype=float)))
    print("  alternating flip is what lets tapered faces nest into each other")


@step('rotate', 'fill.rotate and Rotation - forward/reverse must round-trip')
def s_rotate(ctx):
    pts = [[0, 0, 0], [10, 0, 0], [10, 5, 0], [0, 5, 0]]

    sub("fill.rotate(points, 90, axis='z')")
    out = rotate(pts, 90, axis='z')
    for a, b in zip(pts, out):
        print(f"  {fmt(a)} -> {fmt(b)}")

    sub('1-D inputs (the reshape(-1, 3) case)')
    kv('single point (3,) -> shape', rotate([1, 2, 3], 90, axis='z').shape)
    empty = rotate([], 90, axis='z')
    kv('empty list (0,) -> shape', empty.shape)
    print("  an empty result is normal: a scrap can be packed with zero leftover")

    sub("Rotation(axis_order=['z','x'])")
    rot = Rotation(axis_order=['z', 'x'], pivot=(0, 0, 0))
    kv('get_new_lwh([1870, 800, 350])', fmt(rot.get_new_lwh(SIZE_A)))
    fwd = rot.rotate_in_order(pts)
    back = rot.rotate_in_reverse_order(fwd)
    kv('rotate_in_order', fmt(fwd[1]))
    kv('rotate_in_reverse_order', fmt(back[1]))
    kv('round-trips to the original', bool(np.allclose(np.asarray(pts), back)))

    start, size = rot.get_starting_co_and_size(place_box([0, 0, 0], 600, 300, 200),
                                               after_rotation=False)
    kv('get_starting_co_and_size', f"start={fmt(start)} size={fmt(size)}")


@step('fill_the_box', 'fill_the_box - the geometric core, one prism type into one box')
def s_fill_the_box(ctx):
    prism = fresh_prism(qty=50)
    coords, big, end_co, count = fill_the_box(prism, Block_size=SIZE_A,
                                              starting_co=[0, 0, 0], buffer=BUFFER)
    kv('prism', f"{prism.code} {fmt(PRISM_SIZE)} x{prism.prism_left} available")
    kv('Block_size', fmt(SIZE_A))
    kv('prism_count placed', count)
    kv('len(coordinates_list)', len(coords))
    box('big_block_coordinate', big)

    sub('end_coordinates {column(z): {row(y): far corner}}')
    for col in sorted(end_co):
        for row in sorted(end_co[col]):
            print(f"  col {col} row {row} -> {fmt(end_co[col][row])}")

    sub('first three placed prisms')
    for i, c in enumerate(coords[:3]):
        box(f'prism[{i}]', c)

    ctx['end_coordinates'] = end_co
    ctx['coords'] = coords
    ctx['fill_count'] = count


@step('occupied', 'occupied_boxes_from_staircase - what the prisms actually take up')
def s_occupied(ctx):
    if 'end_coordinates' not in ctx:
        s_fill_the_box(ctx)
    occ = occupied_boxes_from_staircase(ctx['end_coordinates'], [0, 0, 0])
    kv('boxes returned', len(occ))
    table([[i, fmt(b[:3]), fmt(np.subtract(b[3:], b[:3])),
            f"{np.prod(np.subtract(b[3:], b[:3])):.3e}"]
           for i, b in enumerate(occ)],
          ['#', 'start', 'size', 'volume'])
    total = sum(float(np.prod(np.subtract(b[3:], b[:3]))) for b in occ)
    kv('total occupied volume', f"{total:.4e} mm^3")
    kv('block volume', f"{np.prod(SIZE_A):.4e} mm^3")
    print("  the buffer gap counts as occupied on purpose - parts need that clearance")
    ctx['occupied'] = occ


@step('free_boxes', 'free_boxes - decomposition of the space the prisms do not cover')
def s_free_boxes(ctx):
    if 'occupied' not in ctx:
        s_occupied(ctx)
    occ = ctx['occupied']
    occ_vol = sum(float(np.prod(np.subtract(b[3:], b[:3]))) for b in occ)
    block_vol = float(np.prod(SIZE_A))

    sub('the same free space under different merge orders')
    rows = []
    for order in [(0, 1, 2), (2, 1, 0), (1, 0, 2)]:
        for flips in [(False, False, False), (True, True, True)]:
            boxes = free_boxes(occ, [0, 0, 0], SIZE_A, order=order, flips=flips)
            vol = sum(s[0] * s[1] * s[2] for _, s in boxes)
            biggest = max((s[0] * s[1] * s[2] for _, s in boxes), default=0)
            rows.append([str(order), str(flips), len(boxes), f"{vol:.4e}",
                         f"{biggest:.3e}",
                         'yes' if abs(vol + occ_vol - block_vol) < 1e-6 else 'NO'])
    table(rows, ['order', 'flips', 'boxes', 'free volume', 'largest box', 'volume conserved'])
    print("  every order describes the same space - only the fragmentation differs")


@step('get_scrap_vol', 'get_scrap_vol - the sampled decomposition actually used')
def s_get_scrap_vol(ctx):
    if 'end_coordinates' not in ctx:
        s_fill_the_box(ctx)
    kv('CANDIDATE_DECOMPOSITIONS', CANDIDATE_DECOMPOSITIONS)

    volumes, boxes = get_scrap_vol(ctx['end_coordinates'], SIZE_A, st_co=[0, 0, 0],
                                   co_ordinates_list=ctx.get('coords', []), buffer=BUFFER)
    kv('scrap boxes returned', len(boxes))
    kv('8-corner lists returned', len(volumes))
    table([[i, fmt(b['starting_co']), fmt(b['Box_size']),
            f"{np.prod(b['Box_size']):.3e}"]
           for i, b in enumerate(sorted(boxes, key=lambda b: -np.prod(b['Box_size'])))],
          ['#', 'start', 'size', 'volume'])

    sub('it samples, so successive calls differ')
    for i in range(3):
        _, b = get_scrap_vol(ctx['end_coordinates'], SIZE_A, st_co=[0, 0, 0], buffer=BUFFER)
        kv(f'call {i + 1}', f"{len(b)} boxes, largest "
                            f"{max((np.prod(x['Box_size']) for x in b), default=0):.3e}")
    print("  this is also what gives run_optimization_with_retries a new layout each attempt")
    ctx['scrap_volumes'] = volumes


@step('Block', 'Block - place_box, can_fit_with_rotation, occupied_bounds, efficiency')
def s_block(ctx):
    b = Block('B1', SIZE_A, start_coord=[0, 0, 0])
    kv('unique_code', b.unique_code)
    kv('size / volume', f"{fmt(b.size)} / {b.volume:.4e}")
    kv('is_recovered (default)', b.is_recovered)
    kv('source_scrap_id (default)', b.source_scrap_id)
    box('box_coordinate', b.box_coordinate)

    sub('can_fit_with_rotation')
    for label, size in (('fits', PRISM_SIZE), ('too big', [5000, 5000, 900, 900])):
        p = Prisms('X', list(size), 1)
        cond, rots = b.can_fit_with_rotation(p, [[], ['z'], ['z', 'x'], ['z', 'y'], ['x'], ['y']])
        kv(f'{label} {fmt(size)}', f"cond={cond} valid rotations={rots}")
    print("  note: this ignores the buffer, so a pass here can still pack nothing")

    sub('occupied_bounds / get_efficiency before and after placing')
    lo, hi = b.occupied_bounds()
    kv('occupied_bounds (empty block)', f"{lo.shape} - nothing placed yet")
    kv('get_efficiency', f"{b.get_efficiency():.2f}%")

    prism = fresh_prism(qty=50)
    coords, _, _, count = fill_the_box(prism, Block_size=b.size,
                                       starting_co=b.start_coord, buffer=BUFFER)
    b.add_prisms_coordinates(prism, coords)
    lo, hi = b.occupied_bounds()
    kv(f'after placing {count}', f"bounds min={fmt(lo.min(axis=0))} max={fmt(hi.max(axis=0))}")
    kv('get_efficiency', f"{b.get_efficiency():.2f}%")
    kv('layout_signature (saw-setup key)', layout_signature({
        'code': b.unique_code, 'size': b.size,
        'prisms': [{'code': prism.code, 'count': count}]}))


@step('add_recovered', 'People_helper.add_recovered_block - supply stage 1 seeding')
def s_add_recovered(ctx):
    helper = People_helper(BUFFER, PARENT_SIZES)
    kv('all_big_blocks before', len(helper.all_big_blocks))
    kv('all_scrap before', len(helper.all_scrap))

    for piece in RECOVERED:
        blk = helper.add_recovered_block(piece['size'], source=piece)
        kv(f"seeded {piece['scrap_id']} {fmt(piece['size'])}",
           f"code={blk.unique_code} is_recovered={blk.is_recovered} "
           f"source={blk.source_scrap_id} scraps={len(blk.scraps)}")

    sub('resulting state')
    blocks_table(helper)
    kv('all_scrap', len(helper.all_scrap))
    kv('big_block_count (B-series, untouched)', helper.big_block_count)
    kv('recovered_block_count (R-series)', helper.recovered_block_count)
    kv('rejected_scrap_count', helper.rejected_scrap_count)

    sub('the seed scraps, tagged for inventory reporting')
    table([[s.unique_code, fmt(s.size), getattr(s, 'origin', '-'),
            getattr(s, 'inventory_scrap_id', '-'), s.parent_block.unique_code]
           for s in helper.all_scrap],
          ['code', 'size', 'origin', 'inventory_scrap_id', 'parent'])
    ctx['helper_recovered'] = helper


@step('add_scrap_list', 'add_update_scrap_list - the chokepoint that rejects unsound scrap')
def s_add_scrap_list(ctx):
    helper = People_helper(BUFFER, PARENT_SIZES)
    blk = helper.add_one_big_block(SIZE_A, size_index=0)

    prism = fresh_prism(qty=50)
    coords, _, end_co, count = fill_the_box(prism, Block_size=blk.size,
                                            starting_co=blk.start_coord, buffer=BUFFER)
    blk.add_prisms_coordinates(prism, coords)
    kv('prisms placed in the block', count)

    sub('sound candidates from get_scrap_vol')
    volumes, _ = get_scrap_vol(end_co, blk.size, st_co=blk.start_coord, buffer=BUFFER)
    accepted = helper.add_update_scrap_list(blk, volumes)
    kv('offered', len(volumes))
    kv('accepted', len(accepted))
    kv('rejected_scrap_count', f"{helper.rejected_scrap_count}  (expected 0)")
    table([[s.unique_code, fmt(s.start_coord), fmt(s.size), f"{s.volume:.3e}"]
           for s in accepted[:8]],
          ['code', 'start', 'size', 'volume'])

    sub('a deliberately unsound candidate covering placed prisms')
    before = helper.rejected_scrap_count
    bad = place_box([0, 0, 0], length=SIZE_A[0], width=SIZE_A[1], height=SIZE_A[2])
    helper.add_update_scrap_list(blk, [bad])
    kv('rejected_scrap_count delta', helper.rejected_scrap_count - before)
    print("  a scrap overlapping a prism would let a later pass cut into solid material")

    sub('is_small_size thresholds')
    for size in ([1, 100, 100], [100, 100, 100], [2, 2, 2], [1.5, 1.5, 1.5]):
        kv(fmt(size), 'discarded' if helper.is_small_size(size) else 'kept')


@step('check_block', 'check_which_block_to_add - tier and waste_per_part ranking')
def s_check_block(ctx):
    prism = fresh_prism(qty=50)

    sub('no quotas: both sizes unlimited (tier 1)')
    h = People_helper(BUFFER, PARENT_SIZES)
    idx = h.check_which_block_to_add(prism)
    kv('returned index', idx)
    kv('-> size', fmt(PARENT_SIZES[idx]) if idx is not None else None)
    kv('remaining_quantity', h.remaining_quantity)

    sub('capacity probe behind the ranking')
    rows = []
    for i, size in enumerate(PARENT_SIZES):
        tmp = h.get_a_temp_block(size, code='Temp')
        cond, rots = tmp.can_fit_with_rotation(prism, h.rotation_axis)
        best = 0
        for axis_order in rots:
            s = (Rotation(axis_order=axis_order, pivot=tmp.start_coord).get_new_lwh(tmp.size)
                 if axis_order else tmp.size)
            _, _, _, n = fill_the_box(prism, Block_size=s,
                                      starting_co=tmp.start_coord, buffer=BUFFER)
            best = max(best, n)
        vol = size[0] * size[1] * size[2]
        rows.append([i, PARENT_LABELS[i], fmt(size), f"{vol:.4e}", best,
                     f"{vol / best:.4e}" if best else 'n/a'])
    table(rows, ['index', 'label', 'size', 'block volume', 'best count', 'waste/part'])
    print("  lowest waste/part wins within a tier - that is what 'fewest blocks' means")

    sub('second size limited to 2 -> it becomes tier 0 and wins')
    h = People_helper(BUFFER, PARENT_SIZES, [None, 2])
    kv('remaining_quantity', h.remaining_quantity)
    kv('returned index', h.check_which_block_to_add(prism))
    print("  owned stock is spent before anything is bought")

    sub('quota spent -> that size is skipped')
    h = People_helper(BUFFER, PARENT_SIZES, [None, 0])
    kv('remaining_quantity', h.remaining_quantity)
    kv('returned index', h.check_which_block_to_add(prism))
    kv('any_quota_spent()', h.any_quota_spent())

    sub('everything spent -> None')
    h = People_helper(BUFFER, PARENT_SIZES, [0, 0])
    kv('returned index', h.check_which_block_to_add(prism))
    kv('any_quota_spent()', f"{h.any_quota_spent()}  -> shortfall reads 'stock_exhausted'")

    sub('nothing fits -> also None, but for the other reason')
    h = People_helper(BUFFER, PARENT_SIZES)
    huge = Prisms('HUGE', [5000, 5000, 900, 900], 1)
    kv('returned index', h.check_which_block_to_add(huge))
    kv('any_quota_spent()', f"{h.any_quota_spent()}  -> shortfall reads 'no_fit'")


@step('quota', 'add_one_big_block / refund_big_block - the stock ledger')
def s_quota(ctx):
    h = People_helper(BUFFER, PARENT_SIZES, [2, None])
    kv('remaining_quantity at start', h.remaining_quantity)

    b1 = h.add_one_big_block(SIZE_A, size_index=0)
    kv(f'after opening {b1.unique_code} (index 0)', h.remaining_quantity)
    b2 = h.add_one_big_block(SIZE_A, size_index=0)
    kv(f'after opening {b2.unique_code} (index 0)', h.remaining_quantity)
    kv('any_quota_spent()', h.any_quota_spent())

    b3 = h.add_one_big_block(SIZE_B, size_index=1)
    kv(f'after opening {b3.unique_code} (index 1, unlimited)', h.remaining_quantity)

    sub('refund after a failed fill')
    h.refund_big_block(b2)
    kv('remaining_quantity', h.remaining_quantity)
    kv('blocks left', [b.unique_code for b in h.all_big_blocks])
    kv('big_block_count', h.big_block_count)
    print("  without the refund a fill that placed nothing still burns a unit of scarce stock")


@step('fill_optimally', 'fill_the_prism_optimally - into a block, then into a scrap')
def s_fill_optimally(ctx):
    sub('into a fresh Block')
    h = People_helper(BUFFER, PARENT_SIZES)
    blk = h.add_one_big_block(SIZE_A, size_index=0)
    prism = fresh_prism(qty=50)
    before = prism.prism_left
    coords, big, scrap_vols, count, scraps = h.fill_the_prism_optimally(prism, blk)
    kv('prism_left before / after', f"{before} -> {prism.prism_left}")
    kv('prism_count', count)
    kv('scrap boxes harvested', len(scrap_vols))
    kv('scraps registered', len(scraps))
    kv('rejected_scrap_count', h.rejected_scrap_count)
    table([[s.unique_code, fmt(s.size), f"{s.volume:.3e}"] for s in scraps[:6]],
          ['code', 'size', 'volume'])

    sub('into one of those scraps (the Scrap branch)')
    target = max(scraps, key=lambda s: s.volume)
    small = fresh_prism(SMALL_PRISM_SIZE, qty=20, code='G2')
    kv('target scrap', f"{target.unique_code} {fmt(target.size)}")
    kv('all_scrap before', len(h.all_scrap))
    res = h.fill_the_prism_optimally(small, target)
    if res[0] is None:
        print("  nothing fitted in this scrap")
    else:
        kv('prism_count', res[3])
        kv('G2 prism_left', small.prism_left)
        kv('all_scrap after', len(h.all_scrap))
        kv('consumed_scraps recorded', len(h.consumed_scraps))
        for c in h.consumed_scraps:
            kv(f"  {c['code']}", f"origin={c['origin']} "
                                 f"inventory_scrap_id={c['inventory_scrap_id']} "
                                 f"parent={c['parent_block']}")
        print("  the consumed scrap is retired BEFORE its remnants are registered,")
        print("  otherwise they are rejected as overlapping their own parent")


@step('try_scrap', 'try_to_pack_inside_all_scrap - stage 1 consumption')
def s_try_scrap(ctx):
    helper = fresh_helper(recovered=RECOVERED)
    prism = fresh_prism(qty=6)
    kv('offered offcuts', [f"{p['scrap_id']} {fmt(p['size'])}" for p in RECOVERED])
    kv('prism_left before', prism.prism_left)
    kv('all_scrap before', len(helper.all_scrap))

    helper.try_to_pack_inside_all_scrap(prism)

    kv('prism_left after', prism.prism_left)
    kv('all_scrap after', f"{len(helper.all_scrap)}  (remnants of what was cut)")
    sub('blocks')
    blocks_table(helper)
    print("  no stock was opened - every part here cost nothing")


@step('prune', 'prune_unused_recovered_blocks - stops inventory double-counting')
def s_prune(ctx):
    helper = fresh_helper(recovered=RECOVERED)
    prism = fresh_prism(qty=6)
    helper.try_to_pack_inside_all_scrap(prism)

    sub('before pruning')
    blocks_table(helper)
    kv('all_scrap', len(helper.all_scrap))

    removed = helper.prune_unused_recovered_blocks()
    sub('after pruning')
    kv('removed', [b.unique_code for b in removed] or '(none)')
    blocks_table(helper)
    kv('all_scrap', len(helper.all_scrap))
    print("  an untouched R-block's seed scrap would otherwise be written to")
    print("  ScrapInventory a second time - the same offcut counted twice per run")


@step('run_final_code', 'run_final_code - all three supply stages end to end')
def s_run_final(ctx):
    scenarios = [
        ('stage 3 only (baseline)', None, []),
        ('stages 2+3 (first size limited to 1)', [1, None], []),
        ('stage 2 exhausted (one size, qty 1)', [1], []),
        ('stages 1+3 (offcuts offered)', None, RECOVERED),
        ('stages 1+2+3', [1, None], RECOVERED),
    ]
    for label, quantities, recovered in scenarios:
        sizes = [SIZE_A] if quantities == [1] else PARENT_SIZES
        prisms = sorted([fresh_prism(qty=6), fresh_prism(SMALL_PRISM_SIZE, 10, 'G2')],
                        key=lambda p: p.get_volume(), reverse=True)
        h = run_final_code(prisms, buffer=BUFFER, parent_block_sizes=sizes,
                           parent_block_quantities=quantities, recovered_stock=recovered)
        new = [b for b in h.all_big_blocks if not b.is_recovered]
        rec = [b for b in h.all_big_blocks if b.is_recovered]
        packed = sum(len(e['coordinates']) for b in h.all_big_blocks for e in b.prism_details)

        sub(label)
        kv('quantities / offered', f"{quantities} / {len(recovered)}")
        kv('new blocks bought', len(new))
        kv('recovered blocks used', len(rec))
        kv('parts packed', f"{packed} of 16")
        kv('remaining_quantity', h.remaining_quantity)
        kv('shortfall_reasons', h.shortfall_reasons or '{}')
        kv('overlaps / rejected scrap', f"{len(find_overlaps(h))} / {h.rejected_scrap_count}")
        blocks_table(h)


@step('block_details', 'get_block_details - aggregates over new blocks only')
def s_block_details(ctx):
    prisms = sorted([fresh_prism(qty=6), fresh_prism(SMALL_PRISM_SIZE, 10, 'G2')],
                    key=lambda p: p.get_volume(), reverse=True)
    h = run_final_code(prisms, buffer=BUFFER, parent_block_sizes=PARENT_SIZES,
                       recovered_stock=RECOVERED)
    bd = get_block_details(h)

    for key in ('Total_number_of_blocks', 'Total_number_of_recovered_blocks',
                'Total_stock_volume', 'Total_prism_volume', 'Total_eff'):
        kv(key, bd[key])
    kv('len(blocks) / len(scraps)', f"{len(bd['blocks'])} / {len(bd['scraps'])}")

    sub('blocks')
    table([[b['code'], b['is_recovered'], b['source_scrap_id'] or '-', fmt(b['size']),
            f"{b['eff']}%", sum(p['number'] for p in b['prisms'])]
           for b in bd['blocks']],
          ['code', 'is_recovered', 'source', 'size', 'eff', 'parts'])
    print("  Total_stock_volume and Total_eff cover NEW blocks only: a recovered block is")
    print("  material already paid for. Both the stock and prism terms are restricted")
    print("  together, or efficiency exceeds 100% once most parts come from scrap.")

    sub('scraps left for the rack (first 8)')
    table([[s['code'], fmt(s['size']), f"{s['volume']:.3e}"] for s in bd['scraps'][:8]],
          ['code', 'size', 'volume'])


@step('overlaps', 'find_overlaps / solids_overlap - the soundness gate')
def s_overlaps(ctx):
    prisms = sorted([fresh_prism(qty=6), fresh_prism(SMALL_PRISM_SIZE, 10, 'G2')],
                    key=lambda p: p.get_volume(), reverse=True)
    h = run_final_code(prisms, buffer=BUFFER, parent_block_sizes=PARENT_SIZES,
                       recovered_stock=RECOVERED)
    kv('find_overlaps(helper)', find_overlaps(h) or '[]  (required)')
    kv('rejected_scrap_count', f"{h.rejected_scrap_count}  (expected 0)")

    sub('why bounding boxes are not enough')
    prism = fresh_prism(qty=50)
    coords, _, _, _ = fill_the_box(prism, Block_size=SIZE_A, starting_co=[0, 0, 0], buffer=BUFFER)
    a, b = coords[0], coords[1]
    lo_a, hi_a = aabb(a)
    lo_b, hi_b = aabb(b)
    kv('two adjacent nested prisms', f"{fmt(lo_a)}..{fmt(hi_a)} / {fmt(lo_b)}..{fmt(hi_b)}")
    kv('boxes_overlap (AABB test)', boxes_overlap(lo_a, hi_a, lo_b, hi_b))
    kv('solids_overlap (separating axis)', f"{solids_overlap(a, b):.6f}")
    print("  the packer interlocks alternating tapered prisms, so correctly nested")
    print("  neighbours DO share bounding-box volume. An AABB test would reject every")
    print("  valid tapered packing; only solids_overlap may be used between prisms.")


@step('retries', 'run_optimization_with_retries - retry gate and best-of-N')
def s_retries(ctx):
    path = ctx['excel']
    if not os.path.exists(path):
        print(f"  skipped: {path} not found (pass --excel <file>)")
        return

    sub('prism loading')
    prisms = get_all_prisms(path)
    kv('get_all_prisms', f"{len(prisms)} part types from {path}")
    table([[p.code, fmt([p.bottom_length, p.top_length, p.width, p.height]),
            p.prism_left, f"{p.get_volume():.3e}", f"{p.angle_from_height_length():.2f} deg"]
           for p in prisms[:8]],
          ['code', 'size', 'qty', 'volume', 'taper angle'])
    if len(prisms) > 8:
        print(f"  ... {len(prisms) - 8} more")

    sub('unconstrained -> search_attempts defaults to 1 (first legal result)')
    h, bd = run_optimization_with_retries(excel_path=path, parent_block_sizes=PARENT_SIZES,
                                          buffer=BUFFER, max_tries=200)
    packed = sum(p['number'] for b in bd['blocks'] for p in b['prisms'])
    kv('new blocks', bd['Total_number_of_blocks'])
    kv('parts packed', packed)
    kv('Total_eff', f"{bd['Total_eff']}%")
    kv('stock volume', f"{bd['Total_stock_volume']:.4e}")
    kv('overlaps', len(find_overlaps(h)))
    kv('blocks at >= 99% eff', sum(1 for b in bd['blocks']
                                   if b['eff'] >= 99 and not b['is_recovered']))
    print("  a >= 99% NEW block is rejected as a numerical artifact and the attempt retried;")
    print("  recovered blocks are exempt - an offcut barely larger than its part is normal")

    sub('constrained -> search_attempts defaults to 5, best of N kept')
    h2, bd2 = run_optimization_with_retries(
        excel_path=path, parent_block_sizes=PARENT_SIZES, buffer=BUFFER, max_tries=200,
        parent_block_quantities=[None, 40], recovered_stock=RECOVERED)
    packed2 = sum(p['number'] for b in bd2['blocks'] for p in b['prisms'])
    kv('new blocks', bd2['Total_number_of_blocks'])
    kv('recovered blocks', bd2['Total_number_of_recovered_blocks'])
    kv('parts packed', packed2)
    kv('stock volume', f"{bd2['Total_stock_volume']:.4e}")
    kv('remaining_quantity', h2.remaining_quantity)
    kv('shortfall_reasons', h2.shortfall_reasons or '{}')
    kv('stock volume vs unconstrained',
       f"{(bd2['Total_stock_volume'] - bd['Total_stock_volume']) / bd['Total_stock_volume'] * 100:+.2f}%")


# ---- View-level reporting ---------------------------------------------------------

@step('classifier', 'the per-part status classifier as views.py applies it')
def s_classifier(ctx):
    parts = [
        {'MARK': 'G1', 'Bottom Length': 600, 'Top Length': 500, 'Width': 300,
         'Height': 200, 'Nos': 6},
        {'MARK': 'HUGE', 'Bottom Length': 5000, 'Top Length': 5000, 'Width': 900,
         'Height': 900, 'Nos': 2},
    ]

    def envelope(part):
        return sorted([float(part['Bottom Length']) + BUFFER,
                       float(part['Width']) + BUFFER,
                       float(part['Height']) + BUFFER])

    def parents_fit(part):
        need = envelope(part)
        return [{'index': i, 'label': PARENT_LABELS[i], 'dimensions': s}
                for i, s in enumerate(PARENT_SIZES)
                if all(n <= h for n, h in zip(need, sorted(float(d) for d in s)))]

    def scraps_fit(part):
        need = envelope(part)
        return [{'scrap_id': p['scrap_id'], 'dimensions': p['size']} for p in RECOVERED
                if all(n <= h for n, h in zip(need, sorted(float(d) for d in p['size'])))]

    sub('fit tests (all six orientations reduce to comparing sorted dimensions)')
    for part in parts:
        kv(f"{part['MARK']} {part['Bottom Length']}x{part['Width']}x{part['Height']}",
           f"parents={[f['label'] for f in parents_fit(part)] or '[]'} "
           f"scraps={[f['scrap_id'] for f in scraps_fit(part)] or '[]'}")

    sub('status for each (packed, shortfall_reason) combination')
    rows = []
    for part in parts:
        for packed, reason in ((part['Nos'], None), (0, 'stock_exhausted'),
                               (0, None), (1, None)):
            remaining = part['Nos'] - packed
            fits, fscrap = parents_fit(part), scraps_fit(part)
            if remaining == 0:
                status = 'packed'
            elif reason == 'stock_exhausted':
                status = 'stock_exhausted'
            elif not fits and not fscrap:
                status = 'does_not_fit_any_parent_block'
            elif not fits:
                status = 'not_placed' if packed == 0 else 'partially_placed'
            elif packed == 0:
                status = 'not_placed'
            else:
                status = 'partially_placed'
            severity = ('none' if status == 'packed'
                        else 'ERROR (unpackable_parts)'
                        if status == 'does_not_fit_any_parent_block'
                        else 'warning (unplaced_parts)')
            rows.append([part['MARK'], f"{packed}/{part['Nos']}", reason or '-',
                         status, severity])
    table(rows, ['part', 'packed', 'shortfall_reason', 'status', 'class'])
    print("  stock_exhausted is checked BEFORE the not-placeable branch and is a warning:")
    print("  the part fits, there is simply none of that stock left. Its wording must")
    print("  never say 'does not fit' - that is reserved for the error class.")


@step('stock_usage', 'stock_usage / scrap_inventory_used - the response ledgers')
def s_stock_usage(ctx):
    prisms = sorted([fresh_prism(qty=6), fresh_prism(SMALL_PRISM_SIZE, 10, 'G2')],
                    key=lambda p: p.get_volume(), reverse=True)
    quantities = [1, None]
    h = run_final_code(prisms, buffer=BUFFER, parent_block_sizes=PARENT_SIZES,
                       parent_block_quantities=quantities, recovered_stock=RECOVERED)
    new = [b for b in h.all_big_blocks if not b.is_recovered]
    rec = [b for b in h.all_big_blocks if b.is_recovered]

    sub('stock_usage')
    rows = []
    for i, size in enumerate(PARENT_SIZES):
        used = sum(1 for b in new if getattr(b, 'size_index', None) == i)
        allowed = quantities[i]
        rows.append([i, PARENT_LABELS[i], fmt(size), allowed if allowed is not None else 'unlimited',
                     used, 'n/a' if allowed is None else max(0, allowed - used)])
    table(rows, ['index', 'label', 'dimensions', 'allowed', 'used', 'remaining'])

    sub('scrap_inventory_used')
    table([[getattr(b, 'source_inventory_id', None), b.source_scrap_id, b.unique_code,
            fmt(b.size), f"{b.get_efficiency():.2f}%",
            sum(len(e['coordinates']) for e in b.prism_details)]
           for b in rec],
          ['inventory_id', 'scrap_id', 'block', 'dimensions', 'utilisation', 'parts'])
    kv('consumed_scrap_inventory_ids', [b.source_inventory_id for b in rec])
    print("  persisted to OptimizationHistory.parameters and read on execute")

    sub('volume split')
    new_stock = sum(b.volume for b in new)
    rec_stock = sum(b.volume for b in rec)
    new_parts = sum(e['prism'].get_volume() * len(e['coordinates'])
                    for b in new for e in b.prism_details)
    rec_parts = sum(e['prism'].get_volume() * len(e['coordinates'])
                    for b in rec for e in b.prism_details)
    kv('total_stock_volume (new only)', f"{new_stock:.4e}")
    kv('recovered_volume_used', f"{rec_stock:.4e}")
    kv('total_prism_volume (from new)', f"{new_parts:.4e}")
    kv('material_saved_volume (from scrap)', f"{rec_parts:.4e}")
    kv('efficiency', f"{new_parts / new_stock * 100 if new_stock else 0:.2f}%")
    kv('overall_efficiency',
       f"{(new_parts + rec_parts) / (new_stock + rec_stock) * 100 if (new_stock + rec_stock) else 0:.2f}%")
    if not new_stock:
        print("  NOTE: nothing was bought, so efficiency is 0 by definition.")
        print("  Read overall_efficiency instead - this is a good run, not a failed one.")


@step('summary', 'build_summary - the shop-floor view')
def s_summary(ctx):
    prisms = sorted([fresh_prism(qty=6), fresh_prism(SMALL_PRISM_SIZE, 10, 'G2')],
                    key=lambda p: p.get_volume(), reverse=True)
    h = run_final_code(prisms, buffer=BUFFER, parent_block_sizes=PARENT_SIZES,
                       recovered_stock=RECOVERED)

    blocks_info = [{'code': b.unique_code, 'size': [float(d) for d in b.size],
                    'prisms': [{'code': e['prism'].code, 'count': len(e['coordinates'])}
                               for e in b.prism_details],
                    'pattern_key': layout_signature(b),
                    'is_recovered': b.is_recovered}
                   for b in h.all_big_blocks]
    scraps_info = [{'code': s.unique_code, 'size': [float(d) for d in s.size],
                    'volume': float(s.volume)} for s in h.all_scrap]
    prism_summary = [{'code': p.code, 'requested': p.quantity,
                      'packed': p.quantity - p.prism_left,
                      'remaining': p.prism_left, 'placeable': True,
                      'bottom_length': p.bottom_length, 'width': p.width,
                      'height': p.height}
                     for p in prisms]
    consumed = [c for c in h.consumed_scraps if c.get('origin') == 'inventory']

    for label, given in (('ALL blocks (wrong)', blocks_info),
                         ('new blocks only (what views.py passes)',
                          [b for b in blocks_info if not b['is_recovered']])):
        s = build_summary(blocks=given, scraps=scraps_info, prism_summary=prism_summary,
                          stock_sizes=stock_sizes_from(PARENT_SIZES, PARENT_LABELS),
                          blade_thickness=BUFFER, source_file='inspect', run_by='inspect',
                          run_at='now', scrap_inventory_enabled=True, consumed_scraps=consumed)
        sub(label)
        kv('total_blocks (stock to pull)', s['stock_used']['total_blocks'])
        table([[e['label'] or '(UNLABELLED OFFCUT)', fmt(e['dimensions']), e['quantity']]
               for e in s['stock_used']['by_size']],
              ['label', 'dimensions', 'quantity'])
        kv('scrap_pieces_used', s['stock_used']['scrap_pieces_used'])
        kv('scrap_volume_used_mm3', s['stock_used']['scrap_volume_used_mm3'])
    print("  build_summary counts every block it is given as stock to fetch, so recovered")
    print("  blocks must be filtered out or the operator is told to buy steel they have")

    sub('other summary sections')
    s = build_summary(blocks=[b for b in blocks_info if not b['is_recovered']],
                      scraps=scraps_info, prism_summary=prism_summary,
                      stock_sizes=stock_sizes_from(PARENT_SIZES, PARENT_LABELS),
                      blade_thickness=BUFFER, scrap_inventory_enabled=True,
                      consumed_scraps=consumed)
    for key in s:
        if key != 'stock_used':
            print(f"  {key}: {json.dumps(s[key], default=str)[:220]}")


# ---- Database-backed steps (temporary test DB) -------------------------------------

@step('inventory', 'ScrapInventory round trip: save -> execute -> consume')
def s_inventory(ctx):
    from planner.models import ScrapInventory, OptimizationHistory
    from planner.inventory_views import (auto_save_scraps_from_optimization,
                                         mark_scraps_as_executed,
                                         mark_consumed_inventory_scraps)
    from django.contrib.auth.models import User

    user = User.objects.filter(username='inspect').first() or \
        User.objects.create_user('inspect', 'i@i.com', 'x')

    piece = ScrapInventory.objects.create(
        scrap_id='INSPECT-1', parent_block_code='OLD', length=900, width=700, height=350,
        volume=900 * 700 * 350, usability='usable', is_in_inventory=True)
    kv('racked offcut', f"{piece.scrap_id} {piece.dimensions_str} id={piece.id}")

    prisms = sorted([fresh_prism(qty=6), fresh_prism(SMALL_PRISM_SIZE, 10, 'G2')],
                    key=lambda p: p.get_volume(), reverse=True)
    recovered = [{'id': piece.id, 'scrap_id': piece.scrap_id,
                  'size': [piece.length, piece.width, piece.height]}]
    h = run_final_code(prisms, buffer=BUFFER, parent_block_sizes=PARENT_SIZES,
                       recovered_stock=recovered)
    rec = [b for b in h.all_big_blocks if b.is_recovered]
    consumed_ids = [b.source_inventory_id for b in rec if b.source_inventory_id]
    kv('recovered blocks used', [b.unique_code for b in rec])
    kv('consumed_scrap_inventory_ids', consumed_ids)

    history = OptimizationHistory.objects.create(
        user=user, job_name='inspect', uploaded_file_name='inspect.xlsx',
        uploaded_file_data=[], parameters={'consumed_scrap_inventory_ids': consumed_ids},
        optimization_results={}, efficiency=0, total_blocks_created=0,
        total_parts_packed=0, total_parts_requested=0, prism_summary=[])

    sub('auto_save_scraps_from_optimization')
    before = ScrapInventory.objects.count()
    saved = auto_save_scraps_from_optimization(h, history, user)
    kv('rows written', ScrapInventory.objects.count() - before)
    kv('sample ids', saved[:6])
    traced = [s for s in saved if s.startswith('INSPECT-1')]
    kv('remnants traced to the source offcut', traced[:4] or '(none)')
    print("  remnants of a racked piece key off its scrap_id, not the opaque R-code")

    sub('state before execute')
    kv('offcut in inventory', ScrapInventory.objects.get(id=piece.id).is_in_inventory)
    kv('new rows in inventory',
       ScrapInventory.objects.filter(optimization_history=history,
                                     is_in_inventory=True).count())

    sub('on execute')
    kv('mark_scraps_as_executed ->', f"{mark_scraps_as_executed(history)} remnants racked")
    kv('mark_consumed_inventory_scraps ->', f"{mark_consumed_inventory_scraps(history)} retired")

    sub('state after execute')
    piece.refresh_from_db()
    kv('offcut still in inventory', f"{piece.is_in_inventory}  (must be False)")
    kv('offcut notes', piece.notes)
    kv('remnants now in inventory',
       ScrapInventory.objects.filter(optimization_history=history,
                                     is_in_inventory=True).count())
    kv('duplicate rows for the offcut',
       f"{ScrapInventory.objects.filter(scrap_id='INSPECT-1').count()}  (must be 1)")
    print("  consumption happens on execute, not at run time: a plan that is never")
    print("  executed must not hide material from later jobs")


@step('api', 'POST /api/upload-optimize/ - the whole live path')
def s_api(ctx):
    from django.test import Client
    from django.contrib.auth.models import User
    from rest_framework_simplejwt.tokens import RefreshToken
    from planner.models import ScrapInventory

    user = User.objects.filter(username='inspect-api').first() or \
        User.objects.create_superuser('inspect-api', 'a@a.com', 'x')
    client = Client(HTTP_AUTHORIZATION=f'Bearer {RefreshToken.for_user(user).access_token}')

    offcut = ScrapInventory.objects.create(
        scrap_id='API-1', parent_block_code='OLD', length=900, width=700, height=350,
        volume=900 * 700 * 350, usability='usable', is_in_inventory=True)

    def post(**extra):
        buf = io.BytesIO()
        PARTS_DF.to_excel(buf, index=False, engine='openpyxl')
        buf.seek(0)
        buf.name = 'parts.xlsx'
        payload = {
            'file': buf,
            'parent_blocks': json.dumps([
                {'label': 'A', 'dimensions': dict(zip(('length', 'width', 'height'), SIZE_A))},
                {'label': 'B', 'dimensions': dict(zip(('length', 'width', 'height'), SIZE_B))},
            ]),
            'selected_blocks': '[]', 'buffer_spacing': str(BUFFER),
            'max_retries': '200', 'retry_enabled': 'true',
        }
        payload.update(extra)
        r = client.post('/api/upload-optimize/', payload)
        assert r.status_code == 200, (r.status_code, r.content[:400])
        return r.json()

    for label, extra in (
        ('default payload (unchanged behaviour)', {}),
        ('with quantity on the first size', {'parent_blocks': json.dumps([
            {'label': 'A', 'dimensions': dict(zip(('length', 'width', 'height'), SIZE_A)),
             'quantity': 1},
            {'label': 'B', 'dimensions': dict(zip(('length', 'width', 'height'), SIZE_B))}])}),
        ('with scrap inventory', {'use_scrap_inventory': 'true',
                                  'scrap_inventory_ids': json.dumps([offcut.id])}),
    ):
        d = post(**extra)
        sub(label)
        for key in ('total_blocks_created', 'total_recovered_blocks', 'efficiency',
                    'overall_efficiency', 'material_saved_volume', 'recovered_volume_used',
                    'scrap_inventory_offered', 'has_stock_exhausted',
                    'has_unpackable_parts', 'has_unplaced_parts',
                    'total_parts_packed', 'total_parts_requested'):
            kv(key, d.get(key))
        kv('parent_block_quantities', d.get('parent_block_quantities'))
        print(f"  message: {d['message']}")
        table([[s['label'], s['quantity_allowed'] if s['quantity_allowed'] is not None
                else 'unlimited', s['quantity_used'],
                s['quantity_remaining'] if s['quantity_remaining'] is not None else 'n/a']
               for s in d['stock_usage']],
              ['stock', 'allowed', 'used', 'remaining'])
        if d['scrap_inventory_used']:
            table([[e['scrap_id'], e['block_code'], fmt(e['dimensions']),
                    f"{e['utilisation']}%", sum(p['count'] for p in e['parts'])]
                   for e in d['scrap_inventory_used']],
                  ['scrap_id', 'block', 'dimensions', 'utilisation', 'parts'])
        table([[p['code'], f"{p['packed']}/{p['requested']}", p['status'], p['placeable'],
                ','.join(f['label'] for f in p['fits_parent_blocks']) or '-',
                len(p['fits_scrap_inventory'])]
               for p in d['prism_summary']],
              ['part', 'packed', 'status', 'placeable', 'fits', 'fits scrap'])

    sub('per-part reason strings (rendered verbatim by the UI)')
    for p in d['prism_summary']:
        if p['reason']:
            print(f"  {p['code']} [{p['status']}]: {p['reason']}")


# ----------------------------------------------------------------------------------
# Entry point
# ----------------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description='Run each step of the packing pipeline and print what it returned.')
    parser.add_argument('steps', nargs='*',
                        help='step numbers or name fragments; default is all')
    parser.add_argument('--list', action='store_true', help='list the steps and exit')
    parser.add_argument('--excel', default='Sample_data_03 (1).xlsx',
                        help='workbook for the retries step')
    args = parser.parse_args()

    if args.list:
        print('\nSteps:\n')
        for i, s in enumerate(STEPS, 1):
            print(f"  {i:2d}  {s['name']:<16} {s['description']}")
        print('\n  Run a subset by number or name, e.g.  '
              'python inspect_pipeline.py 6 scrap\n')
        return 0

    selected = STEPS
    if args.steps:
        picked, unknown = [], []
        for token in args.steps:
            if token.isdigit():
                i = int(token)
                if 1 <= i <= len(STEPS):
                    picked.append(STEPS[i - 1])
                else:
                    unknown.append(token)
                continue
            matched = [s for s in STEPS
                       if token.lower() in s['name'].lower()
                       or token.lower() in s['description'].lower()]
            if matched:
                picked.extend(matched)
            else:
                unknown.append(token)
        if unknown:
            print(f"Unknown step(s): {', '.join(unknown)}. Use --list to see them.")
            return 2
        seen, selected = set(), []
        for s in picked:
            if s['name'] not in seen:
                seen.add(s['name'])
                selected.append(s)

    # Every step runs against a throwaway database, so no real inventory or history row
    # is read or written.
    from django.test.utils import setup_test_environment
    from django.test.runner import DiscoverRunner

    setup_test_environment()
    runner = DiscoverRunner(verbosity=0, interactive=False)
    old_config = runner.setup_databases()

    ctx = {'excel': args.excel}
    failures = []
    try:
        for step_def in selected:
            number = STEPS.index(step_def) + 1
            head(f"STEP {number}  {step_def['name']}  -  {step_def['description']}")
            try:
                step_def['fn'](ctx)
            except Exception:
                import traceback
                failures.append(step_def['name'])
                print(f"\n  !! step raised:\n")
                traceback.print_exc()
    finally:
        runner.teardown_databases(old_config)

    head('DONE')
    print(f"  ran {len(selected)} step(s)")
    if failures:
        print(f"  raised: {', '.join(failures)}")
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
