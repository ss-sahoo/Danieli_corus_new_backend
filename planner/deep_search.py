"""
Deep optimisation: choose which of the offered parent block sizes to actually use.

Why this exists
---------------
`check_which_block_to_add` is greedy and scores a candidate size by how well it packs the
one prism triggering the block. It is blind to what the leftover slab is worth to every
*other* part type later. The consequence is that offering more sizes can make the result
worse, which is what optimisation #18 vs #19 showed on Sample_data_03:

    A + C + B                        79.9%   764 blocks
    A + C + B + 2 more sizes         78.8%   793 blocks   <- more choice, worse result

The extra size wins the local trade (same part count out of 12% less steel) and loses the
global one (50 mm less headroom above the packed layer, so its scrap hosts less).

Searching over subsets fixes this by construction: the old set is always still a candidate,
so adding a size can never make the answer worse. On the same data it found

    N350 + C                         81.4%   671 blocks

That is +2.5 points and 121 fewer blocks than the run that was actually submitted, out of
sizes the user had already offered.

Cost
----
Every candidate is a real, complete packing - there is no estimator. Exhaustive is 2^n - 1
runs; hill climbing is about n^2/2. Measured on Sample_data_03 at ~6.5 s per run:

    n=5   exhaustive 31 runs / ~4.5 min    hill climb 15 runs / ~1.5 min  (same answer)
    n=8   exhaustive 255 runs / ~36 min    hill climb ~36 runs / ~5 min

`auto` uses exhaustive up to EXHAUSTIVE_LIMIT free sizes and hill climbing beyond it.
`search_time_budget` bounds either one; the scan returns the best found so far rather than
failing, and the full offered set is always evaluated first so the reported improvement is
against the real baseline even when the scan is truncated.
"""
import itertools
import time
from typing import Any, Dict, List, Optional

from .modules.packing_orchestrator import prism_order, run_optimization_with_retries

# Above this many free sizes, 'auto' falls back to hill climbing. Exhaustive is 2^n - 1
# packings, so the wall clock roughly doubles per size added. At ~8.5 s per packing:
#
#     n=4    15 candidates   ~2 min
#     n=5    31              ~4.5 min
#     n=6    63              ~9 min
#     n=7   127              ~18 min
#     n=8   255              ~36 min
#
# Set deliberately high because thoroughness is wanted here. Two things keep it safe:
# `search_time_budget` truncates the scan and still returns the best found so far, and the
# full offered set is always evaluated first so the reported improvement stays honest even
# when the scan is cut short.
#
# Worth knowing when reading the results: repeat runs of the same subset differ by about
# 0.11 efficiency points, and the top candidates typically sit within that of each other,
# so the winner among the leaders is partly luck. The gap between good and bad subsets
# (~1-3 points) is well above the noise; the gap between first and second usually is not.
EXHAUSTIVE_LIMIT = 8

# Ordering perturbations to try on the winning subset. Each is one more full packing.
DEFAULT_ORDER_ATTEMPTS = 8


def _evaluate(excel_path, sizes, quantities, buffer, max_tries, recovered_stock, demand):
    """
    Pack once with this exact set of sizes and score it.

    Scored on material, not block count: fewer blocks can still mean more steel when the
    sizes differ. A candidate that cannot place every part is never preferred over one
    that can, however good its efficiency looks - efficiency over a partial packing is
    measuring the wrong thing.
    """
    helper, details = run_optimization_with_retries(
        excel_path=excel_path,
        parent_block_sizes=sizes,
        buffer=buffer,
        max_tries=max_tries,
        parent_block_quantities=quantities,
        recovered_stock=recovered_stock,
        # Force first-legal during the scan. search_attempts defaults to 5 whenever quotas
        # or scrap are present, which is a measured ~4.8x on every candidate - unaffordable
        # when the point is to run many of them. The winner is repacked properly later.
        search_attempts=1,
    )

    new_blocks = [b for b in helper.all_big_blocks if not getattr(b, 'is_recovered', False)]
    stock_volume = sum(b.volume for b in new_blocks)
    part_volume = sum(e['prism'].get_volume() * len(e['coordinates'])
                      for b in new_blocks for e in b.prism_details)
    packed = sum(len(e['coordinates'])
                 for b in helper.all_big_blocks for e in b.prism_details)

    return {
        'efficiency': (part_volume / stock_volume * 100) if stock_volume else 0.0,
        'blocks': len(new_blocks),
        'stock_volume': stock_volume,
        'packed': packed,
        'complete': packed >= demand,
    }


def _rank(result):
    """Complete packings first, then most material-efficient."""
    return (1 if result['complete'] else 0, result['efficiency'])


def search_prism_order(excel_path: str,
                       parent_block_sizes: List[List[float]],
                       parent_quantities: List[Optional[int]],
                       demand: int,
                       buffer: float = 2.0,
                       max_tries: int = 200,
                       recovered_stock: List[Dict[str, Any]] = None,
                       attempts: int = DEFAULT_ORDER_ATTEMPTS,
                       time_budget: float = None) -> Dict[str, Any]:
    """
    Find a part-type processing order that beats plain volume-descending.

    The packer processes part types largest-first, and that ordering is the most sensitive
    input in the pipeline - reversing it costs about 13 efficiency points. Volume-descending
    is a good choice but not the best one: perturbing it with a few adjacent transpositions
    gained up to +0.3 points in testing, which is twice what exhaustive scrap decomposition
    is worth.

    Seed 0 is plain volume-descending and is always evaluated first, so this can only
    improve on the default, never fall below it.

    Runs on the already-chosen subset, so it costs `attempts` packings, not attempts x
    subsets.
    """
    started = time.time()
    recovered_stock = recovered_stock or []
    results = []

    for seed in range(attempts):
        with prism_order(seed):
            r = _evaluate(excel_path, parent_block_sizes, parent_quantities,
                          buffer, max_tries, recovered_stock, demand)
        r['seed'] = seed
        results.append(r)

        if time_budget and time.time() - started > time_budget:
            print(f"[DEEP] order search stopped at seed {seed} on time budget")
            break

    baseline = results[0]
    best = max(results, key=_rank)

    # Only accept a perturbation that actually beats the default. Ties go to seed 0: the
    # gain would be inside the run-to-run noise, and the default order is reproducible
    # without carrying a seed around.
    if _rank(best) <= _rank(baseline):
        best = baseline

    return {
        'seed': best['seed'],
        'efficiency': round(best['efficiency'], 2),
        'blocks': best['blocks'],
        'baseline_efficiency': round(baseline['efficiency'], 2),
        'baseline_blocks': baseline['blocks'],
        'improvement_points': round(best['efficiency'] - baseline['efficiency'], 2),
        'attempts': len(results),
        'search_seconds': round(time.time() - started, 1),
        'considered': [{'seed': r['seed'], 'efficiency': round(r['efficiency'], 2),
                        'blocks': r['blocks'], 'complete': r['complete']}
                       for r in sorted(results, key=_rank, reverse=True)],
    }


def search_parent_subsets(excel_path: str,
                          parent_block_sizes: List[List[float]],
                          parent_labels: List[str],
                          parent_quantities: List[Optional[int]],
                          demand: int,
                          buffer: float = 2.0,
                          max_tries: int = 200,
                          recovered_stock: List[Dict[str, Any]] = None,
                          strategy: str = 'auto',
                          time_budget: float = None) -> Dict[str, Any]:
    """
    Find the subset of parent_block_sizes that packs the demand with the least material.

    Sizes carrying a quantity are pinned in and never dropped: a quantity means "we own
    this many and want them used", so excluding them is not the caller's intent.

    strategy: 'exhaustive' | 'hill_climb' | 'auto' (exhaustive when the free sizes are few
    enough to enumerate, hill climbing otherwise).

    Returns a dict with the winning indices and the full table of what was tried, so the
    caller can show why sizes were dropped rather than silently ignoring them.
    """
    started = time.time()
    recovered_stock = recovered_stock or []

    pinned = [i for i, q in enumerate(parent_quantities) if q is not None]
    free = [i for i, q in enumerate(parent_quantities) if q is None]

    def label_of(i):
        return parent_labels[i] if i < len(parent_labels) else f'size {i}'

    def evaluate(idx):
        idx = tuple(sorted(idx))
        if idx in cache:
            return cache[idx]
        r = _evaluate(excel_path,
                      [parent_block_sizes[i] for i in idx],
                      [parent_quantities[i] for i in idx],
                      buffer, max_tries, recovered_stock, demand)
        r['indices'] = list(idx)
        r['labels'] = [label_of(i) for i in idx]
        cache[idx] = r
        tried.append(r)
        return r

    cache, tried = {}, []

    # Nothing to choose between - one candidate is the answer.
    if len(free) <= 1:
        best = evaluate(pinned + free)
        return _result(best, tried, 'trivial', started, pinned, parent_labels,
                       all_indices=pinned + free)

    if strategy == 'auto':
        strategy = 'exhaustive' if len(free) <= EXHAUSTIVE_LIMIT else 'hill_climb'

    if strategy == 'exhaustive':
        total = 2 ** len(free) - 1
        print(f"[DEEP] exhaustive over {len(free)} free sizes: {total} candidates")

        # Evaluate the complete set first, always. It is the baseline every reported
        # improvement is measured against, and with a time budget the scan can be cut off
        # part way - if the full set had not been evaluated by then, 'all_sizes_efficiency'
        # would silently report the largest subset that happened to fit in the budget
        # instead, making the improvement figure wrong rather than merely incomplete.
        evaluate(pinned + list(free))

        stopped_early = False
        for r in range(1, len(free) + 1):
            for combo in itertools.combinations(free, r):
                evaluate(pinned + list(combo))
                if time_budget and time.time() - started > time_budget:
                    print(f"[DEEP] time budget {time_budget}s reached after "
                          f"{len(tried)} of {total} candidates")
                    stopped_early = True
                    break
            if stopped_early:
                break

        best = max(tried, key=_rank)

    else:
        # Hill climb: start from everything, repeatedly drop whichever single size helps
        # most, stop when no drop helps. About n^2/2 packings instead of 2^n.
        current = pinned + list(free)
        best = evaluate(current)
        droppable = list(free)

        while len(droppable) > 1:
            candidates = []
            for drop in droppable:
                trial = [i for i in current if i != drop]
                candidates.append((evaluate(trial), drop))
                if time_budget and time.time() - started > time_budget:
                    break

            winner, dropped = max(candidates, key=lambda c: _rank(c[0]))
            if _rank(winner) <= _rank(best):
                break  # local optimum

            print(f"[DEEP] dropping {label_of(dropped)}: "
                  f"{best['efficiency']:.2f}% -> {winner['efficiency']:.2f}%")
            best = winner
            current = winner['indices']
            droppable = [i for i in droppable if i != dropped]

            if time_budget and time.time() - started > time_budget:
                print(f"[DEEP] time budget {time_budget}s reached")
                break

    return _result(best, tried, strategy, started, pinned, parent_labels,
                   all_indices=pinned + list(free))


def _result(best, tried, strategy, started, pinned, parent_labels, all_indices=None):
    considered = sorted(tried, key=_rank, reverse=True)

    # The baseline is "use every size the caller offered", which is what the improvement is
    # quoted against. Every strategy evaluates it first, so look it up by its exact indices
    # rather than inferring it from whichever candidate happens to be largest - under a
    # truncated budget those are not the same thing.
    baseline = None
    if all_indices is not None:
        wanted = sorted(all_indices)
        baseline = next((r for r in tried if r['indices'] == wanted), None)
    if baseline is None:
        baseline = tried[0] if tried else None

    return {
        'strategy': strategy,
        'chosen_indices': best['indices'],
        'chosen_labels': best['labels'],
        'chosen_efficiency': round(best['efficiency'], 2),
        'chosen_blocks': best['blocks'],
        'pinned_indices': pinned,
        'candidates_evaluated': len(tried),
        'search_seconds': round(time.time() - started, 1),
        # What using every offered size would have given, so the gain is visible.
        'all_sizes_efficiency': round(baseline['efficiency'], 2) if baseline else None,
        'all_sizes_blocks': baseline['blocks'] if baseline else None,
        'improvement_points': (round(best['efficiency'] - baseline['efficiency'], 2)
                               if baseline else None),
        'considered': [{
            'labels': r['labels'],
            'efficiency': round(r['efficiency'], 2),
            'blocks': r['blocks'],
            'packed': r['packed'],
            'complete': r['complete'],
        } for r in considered],
    }
