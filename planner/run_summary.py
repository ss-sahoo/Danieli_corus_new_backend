"""
Run summary for a completed optimization.

Written for the person who has to cut the parts afterwards, not for reporting: every
figure here answers a question asked on the shop floor - what stock do I pull, how many
saw setups is this, how many offcuts go back on the rack, what settings was it run with.

Aggregates only. Per-block and per-scrap detail already exists in optimization_results
['blocks'] and ['scraps'] and is what the Blocks/Scraps tabs render; repeating any of it
here would just make the summary unreadable.

Built from the serialized blocks/scraps lists rather than from the live People_helper, so
the same function serves a fresh run and a history row read back out of the database.
"""
import hashlib

# Keep/discard uses the identical rule as the scrap inventory, so the summary and the
# Scraps tab can never disagree about how many pieces are worth racking.
from .inventory_views import MIN_USABLE_MM


def layout_signature(block):
    """
    Fingerprint of a live Block's cut layout: same signature means the same stock size cut
    into the same parts in the same positions, i.e. one saw setup that can be repeated.

    Comparing raw coordinates is only meaningful because every block is created at the
    origin (add_one_big_block always starts at [0,0,0]), so two blocks packed identically
    hold identical coordinates rather than translated ones.

    Returns None when the block carries no placement detail, which pushes the caller onto
    the coarser contents-based fallback in _pattern_key.
    """
    details = getattr(block, 'prism_details', None)
    if not details:
        return None

    placements = []
    for entry in details:
        try:
            code = entry['prism'].code
            for coords in entry['coordinates']:
                corners = sorted(tuple(round(float(c), 2) for c in point) for point in coords)
                placements.append((code, tuple(corners)))
        except (KeyError, TypeError, AttributeError):
            return None

    placements.sort()
    size = tuple(round(float(d), 2) for d in block.size)
    return hashlib.md5(repr((size, placements)).encode()).hexdigest()[:16]


def stock_sizes_from(parent_block_sizes, parent_labels):
    """Pair the selected parent dimensions with their user-given labels."""
    sizes = []
    for idx, size in enumerate(parent_block_sizes or []):
        try:
            dims = [float(d) for d in size]
        except (TypeError, ValueError):
            continue
        label = parent_labels[idx] if parent_labels and idx < len(parent_labels) else None
        sizes.append({'label': label, 'dimensions': dims})
    return sizes


def _size_key(dims):
    return tuple(round(float(d), 2) for d in dims)


def _sorted_size_key(dims):
    return tuple(sorted(round(float(d), 2) for d in dims))


def _pattern_key(block):
    """Layout fingerprint if the block carries one, otherwise same-stock-same-contents."""
    stored = block.get('pattern_key')
    if stored:
        return stored

    # History rows written before pattern_key existed only kept part counts, so blocks that
    # yield the same parts group together even if those parts sit in different positions.
    contents = sorted((p.get('code'), p.get('count', 0)) for p in block.get('prisms', []))
    return 'contents:' + repr((_size_key(block.get('size', [])), contents))


def _fits_any_stock(part, stock_sizes, clearance):
    """
    Whether a part fits any selected stock size in any orientation.

    Recomputed rather than read off the part because prism_summary rows written before
    'placeable' existed do not carry it, and reporting every shortfall as fixable would
    send the user off re-running a job that can never succeed.
    """
    try:
        need = sorted([
            float(part['bottom_length']) + clearance,
            float(part['width']) + clearance,
            float(part['height']) + clearance,
        ])
    except (KeyError, TypeError, ValueError):
        return None  # unknown - caller leaves the part out of the "does not fit" count

    for stock in stock_sizes:
        have = sorted(float(d) for d in stock['dimensions'])
        if all(n <= h for n, h in zip(need, have)):
            return True
    return False


def build_summary(blocks, scraps, prism_summary, stock_sizes, blade_thickness,
                  source_file=None, run_by=None, run_at=None,
                  scrap_inventory_enabled=False, consumed_scraps=None):
    """
    Args:
        blocks: serialized blocks - {'code', 'size', 'prisms': [{'code','count'}],
                'pattern_key' (optional)}
        scraps: serialized scraps - {'code', 'size', 'volume'}
        prism_summary: per-part rows - {'requested', 'packed', 'remaining', 'status'?,
                'placeable'?, 'bottom_length', 'width', 'height'}
        stock_sizes: [{'label', 'dimensions'}] as selected for the run
        blade_thickness: buffer left around every part, i.e. the saw kerf (mm)
        consumed_scraps: People_helper.consumed_scraps, or None
    """
    blocks = blocks or []
    scraps = scraps or []
    prism_summary = prism_summary or []
    stock_sizes = stock_sizes or []
    clearance = float(blade_thickness or 0)

    # ---- stock: how many blocks of each selected size to pull -------------------------
    by_size = []
    exact = {}
    loose = {}
    for stock in stock_sizes:
        entry = {
            'label': stock['label'],
            'dimensions': stock['dimensions'],
            'quantity': 0,
        }
        by_size.append(entry)
        exact.setdefault(_size_key(stock['dimensions']), entry)
        loose.setdefault(_sorted_size_key(stock['dimensions']), entry)

    for block in blocks:
        size = block.get('size') or []
        # A block is opened at one of the selected sizes verbatim, so the exact match
        # normally hits. The sorted fallback covers a size recorded in a different axis
        # order, and the final branch covers history rows whose parameters were lost -
        # a block must never be dropped from the pull list just because it is unmatched.
        entry = exact.get(_size_key(size)) or loose.get(_sorted_size_key(size))
        if entry is None:
            entry = {
                'label': None,
                'dimensions': [float(d) for d in size],
                'quantity': 0,
            }
            by_size.append(entry)
            exact[_size_key(size)] = entry
        entry['quantity'] += 1

    # Only pieces pulled off the rack count as material consumed. A 'generated' scrap is
    # leftover space inside a stock block already counted above, so counting it here would
    # book the same steel twice.
    from_inventory = [c for c in (consumed_scraps or []) if c.get('origin') == 'inventory']

    stock_used = {
        'total_blocks': len(blocks),
        'by_size': by_size,
        'scrap_pieces_used': len(from_inventory),
        'scrap_volume_used_mm3': round(sum(float(c.get('volume', 0)) for c in from_inventory), 2),
    }

    # ---- parts: what comes out, and what will be missing ------------------------------
    requested = 0
    packed = 0
    short_types = 0
    unfittable_types = 0
    for part in prism_summary:
        req = int(part.get('requested', 0) or 0)
        pac = int(part.get('packed', 0) or 0)
        requested += req
        packed += pac

        remaining = part.get('remaining')
        if remaining is None:
            remaining = max(0, req - pac)
        if remaining <= 0:
            continue

        status = part.get('status')
        if status == 'does_not_fit_any_parent_block':
            fits = False
        elif status in ('not_placed', 'partially_placed'):
            fits = True
        elif part.get('placeable') is not None:
            fits = bool(part['placeable'])
        else:
            fits = _fits_any_stock(part, stock_sizes, clearance)

        if fits is False:
            unfittable_types += 1
        else:
            # Unknown dimensions count as merely short: a re-run is cheap advice, telling
            # someone to buy bigger stock on a guess is not.
            short_types += 1

    parts = {
        'requested': requested,
        'packed': packed,
        'part_types_short': short_types,
        'part_types_not_fitting_any_stock': unfittable_types,
    }

    # ---- offcuts: rack it or bin it ---------------------------------------------------
    to_rack = 0
    largest = None
    largest_volume = -1.0
    for scrap in scraps:
        size = [float(d) for d in (scrap.get('size') or [])]
        if size and min(size) > MIN_USABLE_MM:
            to_rack += 1
        volume = float(scrap.get('volume', 0) or 0)
        if volume > largest_volume:
            largest_volume = volume
            largest = {'dimensions': size}

    offcuts = {
        'total': len(scraps),
        'to_rack': to_rack,
        'to_discard': len(scraps) - to_rack,
        'largest': largest,
    }

    # ---- cutting effort ---------------------------------------------------------------
    patterns = {_pattern_key(b) for b in blocks}
    parts_in_blocks = sum(
        sum(int(p.get('count', 0) or 0) for p in (b.get('prisms') or []))
        for b in blocks
    )

    cutting = {
        'distinct_patterns': len(patterns),
        'avg_parts_per_block': round(parts_in_blocks / len(blocks), 1) if blocks else 0,
    }

    return {
        'settings': {
            'blade_thickness_mm': clearance,
            'stock_sizes_selected': stock_sizes,
            'scrap_inventory_enabled': bool(scrap_inventory_enabled),
            'source_file': source_file,
            'part_types': len(prism_summary),
            'run_by': run_by,
            'run_at': run_at,
        },
        'stock_used': stock_used,
        'parts': parts,
        'offcuts': offcuts,
        'cutting': cutting,
    }


def summary_for_history(history):
    """
    Rebuild the summary for a stored optimization.

    History rows keep the full blocks/scraps lists, so everything except scrap consumption
    (never recorded before now) can be recovered - which is what lets runs saved before
    this code existed show a summary without being re-run.
    """
    results = history.optimization_results or {}
    params = history.parameters or {}

    return build_summary(
        blocks=results.get('blocks'),
        scraps=results.get('scraps'),
        prism_summary=history.prism_summary,
        stock_sizes=stock_sizes_from(
            params.get('parent_blocks_used'),
            params.get('parent_labels') or history.selected_parents,
        ),
        blade_thickness=params.get('buffer_spacing', 2),
        source_file=history.uploaded_file_name,
        run_by=history.user.username if history.user_id else None,
        run_at=history.created_at.isoformat() if history.created_at else None,
        scrap_inventory_enabled=bool(params.get('scrap_inventory_enabled', False)),
        consumed_scraps=params.get('consumed_scraps'),
    )
