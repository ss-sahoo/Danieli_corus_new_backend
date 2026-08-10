def place_box(starting_co, length, width, height):
    x, y, z = starting_co
    box_coordinate = [[x,y,z],[x+length,y,z], [x+length, y+width, z], [x, y+width, z], 
                            [x, y, z+height], [x+ length, y, z+height], [x+length, y+width, z+height], [x, y+ width, z+height]]
    return box_coordinate
def place_prism_flip(prism, buffer, coordinate=[0,0,0],flip = False):
    bottom_length = prism.bottom_length
    top_length = prism.top_length
    assert bottom_length >= top_length
    width = prism.width
    height = prism.height
    extra_length = (bottom_length - top_length)/2

    if not flip:
        x, y, z = coordinate
        co_ordinate1 = [x, y,z]
        x1, y1, z1 = co_ordinate1
        co_ordinate2 = [x1 + bottom_length, y1,z1]
        co_ordinate3 = [x1 + bottom_length, y1+ width, z1]
        co_ordinate4 = [x1, y1+ width, z1]
        co_ordinate5 = [x1+extra_length, y1, z1+height]
        co_ordinate6 = [x1+extra_length + top_length, y1, z1+height]
        co_ordinate7 = [x1+extra_length + top_length, y1+ width, z1+height]
        co_ordinate8 = [x1+extra_length,y1+ width, z1+height]

        x1max = x1 + bottom_length
        y1max = y1+ width
        z1max = z1 + height

    else:
        x, y, z = coordinate
        co_ordinate1 = [x, y,z]
        x1, y1, z1 = co_ordinate1
        co_ordinate2 = [x1 + top_length, y1,z1]
        co_ordinate3 = [x1 + top_length, y1+ width, z1]
        co_ordinate4 = [x1, y1+ width, z1]
        co_ordinate5 = [x1-extra_length, y1, z1+height]
        co_ordinate6 = [x1-extra_length + bottom_length, y1, z1+height]
        co_ordinate7 = [x1-extra_length + bottom_length, y1+ width, z1+height]
        co_ordinate8 = [x1-extra_length,y1+ width, z1+height]

        x1max = x1-extra_length + bottom_length
        y1max = y1+ width
        z1max = z1 + height

    return [co_ordinate1, co_ordinate2, co_ordinate3, co_ordinate4, co_ordinate5, co_ordinate6, co_ordinate7, co_ordinate8], x1max, y1max, z1max

def fill_the_box(trapezoid_prisms, Block_size =  [2000,800, 400],starting_co= [0,0,0], buffer = 2):

    x_min,y_min,z_min = starting_co
    x,y,z = x_min, y_min, z_min
    length = Block_size[0]
    width = Block_size[1]
    height = Block_size[2]
    x_max, y_max, z_max = x_min + length, y_min+width, z_min+height
    big_block_coordinate = [[x,y,z],[x+length,y,z], [x+length, y+width, z], [x, y+width, z], 
                            [x, y, z+height], [x+ length, y, z+height], [x+length, y+width, z+height], [x, y+ width, z+height]]
    def kerf(value, wall):
        """
        Gap to leave in front of a part whose near face would sit at `value`.

        buffer is the saw kerf, so it is only needed where a cut is actually made -
        between one part and the next. The block's own face is already a finished
        surface, so the first part in a row, the first row in a column and the first
        column all sit flush against the wall. Insetting them, which is what this used
        to do, threw away a buffer-wide strip down three faces of every block and put
        the same phantom gap inside every scrap packed by this function.
        """
        return buffer if value > wall + 1e-9 else 0.0

    bottomsup = False
    pre_angle = 0
    co_ordinates_list=[]
    prism_count = 0
    is_new_row = True
    is_new_col = True
    new_row_coordinate = [x_min,y_min,z_min]
    new_col_coordinate = [x_min,y_min,z_min]
    #end_coordinates = {col_No:{row_no:[x,y,]}
    end_coordinates = {}
    row_no = 0
    col_no = 0
    
    for _ in range(trapezoid_prisms.prism_left):
        #print('start')
        prism = trapezoid_prisms
        angle= trapezoid_prisms.angle
        bottom_length = trapezoid_prisms.bottom_length
        top_length = trapezoid_prisms.top_length
        assert bottom_length >= top_length
        width = trapezoid_prisms.width
        height = trapezoid_prisms.height
        extra_length = (bottom_length - top_length)/2
        #print(prism_count,"---------------------------------------------")
        
        if not is_new_row and not is_new_col:
            if bottomsup :
                if angle == pre_angle:
                    x, y, z = co_ordinates_list[-1][1] # prvious prism's second coordinate
                    co_ordinates, x1max, y1max, z1max = place_prism_flip(prism,buffer, coordinate=[x+buffer,y,z],flip = False)
                    
                bottomsup = False
            else:
                if angle == pre_angle:
                    x, y, z = co_ordinates_list[-1][1] # prvious prism's second coordinate
                    co_ordinates, x1max, y1max, z1max = place_prism_flip(prism, buffer,coordinate=[x+buffer,y,z],flip = True)
                    
                bottomsup = True
            if x1max > x_max:
                is_new_row = True
            else:
                end_coordinates[col_no-1][row_no] = [x1max, y1max, z1max]

        if is_new_row and not is_new_col:
            row_no += 1
            x, y, z = new_row_coordinate
            bx, by, bz = kerf(x, x_min), kerf(y, y_min), kerf(z, z_min)
            co_ordinates, x1max, y1max, z1max = place_prism_flip(prism,buffer, coordinate=[x+bx,y+by,z+bz],flip = False)
            #print(x1max, y1max, z1max, x, y, z)

            '''if x1max > x_max:
                print('not possible to pack in x direction, May be prism length is more then Block length')
                return co_ordinates_list, big_block_coordinate, end_coordinates'''
    
            if y1max> y_max:
                is_new_row = True 
                is_new_col = True
            else:
                # Far face of this row; the next one gets its kerf from kerf(), which
                # now sees a value off the wall and so returns the buffer.
                new_row_coordinate = [x,y1max,z]
                is_new_col = False
                is_new_row = False
                end_coordinates[col_no-1][row_no] = [x1max, y1max, z1max]
                
    
            bottomsup = False
            
                
        if is_new_row and is_new_col:
            x, y, z = new_col_coordinate
            bx, by, bz = kerf(x, x_min), kerf(y, y_min), kerf(z, z_min)
            co_ordinates, x1max, y1max, z1max = place_prism_flip(prism, buffer,coordinate=[x+bx,y+by,z+bz],flip = False)

            new_row_coordinate = [x,y1max,z]
            new_col_coordinate = [x, y,z1max]
            is_new_col = False
            is_new_row = False

            if x1max > x_max:
                 ##print('not possible to pack in x direction, May be prism length is more then Block length')
                 return None, big_block_coordinate, None, prism_count
            if y1max > y_max or x1max >x_max:
                ##print('not possible to pack the prism in y direction. May be prism width is more then Block width')
                return None, big_block_coordinate, None, prism_count   
            if z1max > z_max:
                #print('end', z1max, z_max)
                break
            row_no = 0

            end_coordinates[col_no] = {}
            end_coordinates[col_no][row_no] = [x1max, y1max, z1max]

            col_no +=1

        #print(end_coordinates)
        pre_angle = angle
        prism_count += 1 
        #co_ordinates = [co_ordinate1, co_ordinate2, co_ordinate3, co_ordinate4, co_ordinate5, co_ordinate6, co_ordinate7, co_ordinate8]
        co_ordinates_list.append(co_ordinates)
    return co_ordinates_list, big_block_coordinate, end_coordinates, prism_count



import plotly.graph_objects as go
import numpy as np

import plotly.io as pio
pio.renderers.default = "browser"


def draw(big_block_coordinate, co_ordinates_list, x_edges=[], y_edges=[], z_edges=[], 
         planes={"xy_planes":[],"zx_planes":[],"yz_planes":[],}, scrap_volumes =[], prism_colors=None):

    # Big block (8 corner coordinates)
    big_block = np.array(big_block_coordinate)
    
    prisms = [np.array(p) for p in co_ordinates_list]
    
    # ---------------------------
    # Helper function to draw triangular mesh faces
    # ---------------------------
    
    def prism_mesh(vertices, color='blue', opacity=1.0):
        # Vertices index for each triangular face (12 triangles for a prism)
        faces = np.array([
            [0,1,2], [0,2,3],   # bottom
            [4,5,6], [4,6,7],   # top
            [0,1,5], [0,5,4],   # side 1
            [1,2,6], [1,6,5],   # side 2
            [2,3,7], [2,7,6],   # side 3
            [3,0,4], [3,4,7]    # side 4
        ])
    
        x = vertices[:,0]
        y = vertices[:,1]
        z = vertices[:,2]
    
        i, j, k = faces[:,0], faces[:,1], faces[:,2]
    
        return go.Mesh3d(
            x=x, y=y, z=z,
            i=i, j=j, k=k,
            color=color,
            opacity=opacity,
            flatshading=True
        )

    def prism_edges(vertices, color='black', width=3):
        """Return a Scatter3d trace drawing all 12 edges of a box/prism."""
        # 12 edges of a rectangular prism (pairs of vertex indices)
        edges = [
            (0,1),(1,2),(2,3),(3,0),  # bottom face
            (4,5),(5,6),(6,7),(7,4),  # top face
            (0,4),(1,5),(2,6),(3,7),  # vertical edges
        ]
        ex, ey, ez = [], [], []
        for a, b in edges:
            ex += [vertices[a,0], vertices[b,0], None]
            ey += [vertices[a,1], vertices[b,1], None]
            ez += [vertices[a,2], vertices[b,2], None]
        return go.Scatter3d(
            x=ex, y=ey, z=ez,
            mode='lines',
            line=dict(color=color, width=width),
            showlegend=False,
            hoverinfo='skip',
        )
    def draw_line(p1, p2, color="black", width=6):
        return go.Scatter3d(
            x=[p1[0], p2[0]],
            y=[p1[1], p2[1]],
            z=[p1[2], p2[2]],
            mode="lines",
            line=dict(color=color, width=width)
        )

    # ---------------------------
    # Helper: draw YX plane (constant Z)
    # ---------------------------
    def draw_yx_plane(pl, color):
        z = pl['z']
        xs, xe = pl['x_start'], pl['x_end']
        ys, ye = pl['y_start'], pl['y_end']

        vertices = np.array([
            [xs, ys, z],
            [xe, ys, z],
            [xe, ye, z],
            [xs, ye, z]
        ])

        faces = np.array([[0,1,2], [0,2,3]])

        return go.Mesh3d(
            x=vertices[:,0],
            y=vertices[:,1],
            z=vertices[:,2],
            i=faces[:,0],
            j=faces[:,1],
            k=faces[:,2],
            color=color,
            opacity=0.3
        )

     # ---------------------------
    # Helper: draw XZ plane (constant Y)
    # ---------------------------
    def draw_xz_plane(pl, color):
        y = pl['y']
        xs, xe = pl['x_start'], pl['x_end']
        zs, ze = pl['z_start'], pl['z_end']
    
        vertices = np.array([
            [xs, y, zs],
            [xe, y, zs],
            [xe, y, ze],
            [xs, y, ze]
        ])
    
        faces = np.array([[0,1,2], [0,2,3]])
    
        return go.Mesh3d(
            x=vertices[:,0],
            y=vertices[:,1],
            z=vertices[:,2],
            i=faces[:,0],
            j=faces[:,1],
            k=faces[:,2],
            color= color,
            opacity=0.35
        )

    # ---------------------------
    # Helper: draw YZ plane (constant X)
    # ---------------------------
    def draw_yz_plane(pl, color):
        x = pl['x']
        zs, ze = pl['z_start'], pl['z_end']
        ys, ye = pl['y_start'], pl['y_end']

        vertices = np.array([
            [x, ys, zs],
            [x, ye, zs],
            [x, ye, ze],
            [x, ys, ze]
        ])

        faces = np.array([[0,1,2], [0,2,3]])

        return go.Mesh3d(
            x=vertices[:,0],
            y=vertices[:,1],
            z=vertices[:,2],
            i=faces[:,0],
            j=faces[:,1],
            k=faces[:,2],
            color= color,
            opacity=0.3
        )

    # ---------------------------
    # Build Plot
    # ---------------------------
    
    fig = go.Figure()
    
    # Draw big block (transparent with visible border)
    fig.add_trace(prism_mesh(big_block, color='lightgray', opacity=0.08))
    fig.add_trace(prism_edges(big_block, color='#555555', width=4))

    # Draw prisms with different colors
    colors = [
        "#4F46E5", "#10B981", "#F59E0B", "#EC4899", "#3B82F6", "#8B5CF6", "#06B6D4", "#F97316",
        "#84CC16", "#14B8A6", "#D946EF", "#0EA5E9", "#A855F7", "#E11D48", "#6366F1", "#059669",
        "#D97706", "#DB2777", "#2563EB", "#7C3AED", "#EA580C", "#65A30D", "#0D9488", "#C084FC",
        "#818CF8", "#34D399", "#FBBF24", "#F472B6", "#60A5FA", "#A78BFA", "#fb923c", "#a3e635",
        "#2dd4bf", "#38bdf8", "#1e1b4b", "#064e3b", "#78350f", "#50072b", "#1e3a8a", "#3b0764",
        "#083344", "#431407"
    ]

    for i, scrap_coordinate in enumerate(scrap_volumes):
        color = "#EF4444"  # Consistent light red color for scraps
        sv = np.array(scrap_coordinate)
        fig.add_trace(prism_mesh(sv, color=color, opacity=0.15))
        fig.add_trace(prism_edges(sv, color='rgba(239, 68, 68, 0.4)', width=2))

    for idx, p in enumerate(prisms):
        if prism_colors and idx < len(prism_colors):
            color = prism_colors[idx]
        else:
            color = colors[idx % len(colors)]
        fig.add_trace(prism_mesh(p, color=color, opacity=0.9))
        fig.add_trace(prism_edges(p, color='black', width=2))

        # Draw x_edges lines
    for edge in x_edges:
        p1, p2 = edge
        fig.add_trace(draw_line(p1, p2, color="black", width=8))

    for edge in y_edges:
        p1, p2 = edge
        #print(p2)
        fig.add_trace(draw_line(p1, p2, color="red", width=8))

    for edge in z_edges:
        p1, p2 = edge
        fig.add_trace(draw_line(p1, p2, color="green", width=8))

    # ------------- Add YX (Z-constant) planes -------------
   
    for pl in planes['xy_planes']:
        fig.add_trace(draw_yx_plane(pl, color='black'))

    # ------------- Add YZ (X-constant) planes -------------
    for pl in planes['yz_planes']:
        fig.add_trace(draw_yz_plane(pl, color='red'))

  
    for pl in planes['zx_planes']:
        fig.add_trace(draw_xz_plane(pl, color='green'))
    
   
    
    
    # ---------------------------
    # Layout / Axis settings
    # ---------------------------
    
    fig.update_layout(
        title="3D Interactive Plot: Trapezoidal Prisms Inside Big Block",
        scene=dict(
            xaxis_title="X",
            yaxis_title="Y",
            zaxis_title="Z",
            aspectmode='data',
            camera=dict(
                eye=dict(x=1.5, y=-1.8, z=1.2),
                up=dict(x=0, y=0, z=1),
            ),
            xaxis=dict(showgrid=True, gridcolor='rgba(200,200,200,0.5)', zeroline=False),
            yaxis=dict(showgrid=True, gridcolor='rgba(200,200,200,0.5)', zeroline=False),
            zaxis=dict(showgrid=True, gridcolor='rgba(200,200,200,0.5)', zeroline=False),
        ),
        scene_dragmode='orbit',
        margin=dict(l=0, r=0, t=40, b=0),
        width=900,
        height=700,
        paper_bgcolor='white',
        plot_bgcolor='white',
    )

    
    # fig.show()
    return fig

    
import numpy as np

def rotate(points, angle_deg, axis='z', pivot=(0, 0, 0), roundingoff = 2):
    """
    Rotate 3D point(s) around a chosen axis with an optional pivot.
    Using positive angle (+θ):
    Rotate around X-axis → rotation is counter-clockwise when looking from +X toward the origin
    Rotate around Y-axis → rotation is counter-clockwise when looking from +Y toward the origin
    Rotate around Z-axis → rotation is counter-clockwise when looking from +Z toward the origin

    points : (N,3) array or (3,) single point
    angle_deg : rotation angle in degrees
    axis : 'x', 'y', or 'z'
    pivot : point to rotate around (default = origin)
    """
    pts = np.array(points, dtype=float)
    if pts.ndim == 1:
        # -1, not 1: a bare point is (3,) but an empty list is also 1-D, shape (0,),
        # which reshape(1, 3) cannot produce. See Rotation.rotate in packing_orchestrator.
        pts = pts.reshape(-1, 3)

    angle = np.radians(angle_deg)
    px, py, pz = pivot

    # ---- Shift points so pivot becomes origin ----
    shifted = pts - np.array([px, py, pz])

    # ---- Rotation matrix for X, Y, or Z axis ----
    if axis == 'x':
        R = np.array([
            [1, 0, 0],
            [0, np.cos(angle), -np.sin(angle)],
            [0, np.sin(angle), np.cos(angle)]
        ])
    elif axis == 'y':
        R = np.array([
            [np.cos(angle), 0, np.sin(angle)],
            [0, 1, 0],
            [-np.sin(angle), 0, np.cos(angle)]
        ])
    elif axis == 'z':
        R = np.array([
            [np.cos(angle), -np.sin(angle), 0],
            [np.sin(angle),  np.cos(angle), 0],
            [0, 0, 1]
        ])
    else:
        raise ValueError("axis must be one of 'x', 'y', 'z'")

    # ---- Apply rotation ----
    rotated = shifted @ R.T

    # ---- Shift back to original pivot ----
    rounded = np.round(rotated + np.array([px, py, pz]), roundingoff)
    return rounded



import itertools as _itertools
from contextlib import contextmanager as _contextmanager

# How many merge orders get_scrap_vol tries before keeping the least fragmented one.
CANDIDATE_DECOMPOSITIONS = 8

# Every (order, flips) setting free_boxes accepts: 3! axis orders x 2^3 flip choices.
# Enumerating all of them is what the deep optimisation uses instead of sampling.
ALL_DECOMPOSITIONS = [(o, f) for o in _itertools.permutations(range(3))
                             for f in _itertools.product([False, True], repeat=3)]

# Off by default, so the ordinary path samples exactly as before. The deep optimisation
# flips this on around a run via the exhaustive_decomposition() context manager.
# Module-level rather than an argument because get_scrap_vol is called from deep inside
# fill_the_prism_optimally and threading a flag through would touch the whole call chain.
EXHAUSTIVE_DECOMPOSITION = False


@_contextmanager
def exhaustive_decomposition(enabled=True):
    """
    Make get_scrap_vol enumerate every merge order instead of sampling 8 at random.

    Measured on Sample_data_03: about +0.15 to +0.25 efficiency points for roughly 3x the
    packing time, so it belongs in the deep optimisation only. Not thread-safe - it sets
    module state, so do not run a deep search concurrently with a quick one in the same
    process.
    """
    global EXHAUSTIVE_DECOMPOSITION
    previous = EXHAUSTIVE_DECOMPOSITION
    EXHAUSTIVE_DECOMPOSITION = enabled
    try:
        yield
    finally:
        EXHAUSTIVE_DECOMPOSITION = previous


def occupied_boxes_from_staircase(end_coordinates, st_co):
    """
    The region taken up by the prisms fill_the_box placed, as axis-aligned boxes.

    fill_the_box lays prisms out column by column in z, row by row in y, running along
    x, and records the far corner [x1max, y1max, z1max] of every (column, row) strip in
    end_coordinates. Each strip is therefore a box running from where the previous strip
    ended to that corner, and the union of them is exactly the occupied region.

    The near face of each strip is the previous strip's far face, so the buffer gap
    between prisms is counted as occupied. That is deliberate: parts need that clearance,
    so it must never be handed back out as usable scrap.
    """
    boxes = []
    z_prev = st_co[2]

    for col in sorted(end_coordinates):
        rows = end_coordinates[col]
        if not rows:
            continue

        y_prev = st_co[1]
        z_top = max(corner[2] for corner in rows.values())

        for row in sorted(rows):
            x_far, y_far, z_far = rows[row]
            boxes.append([st_co[0], y_prev, z_prev, x_far, y_far, z_far])
            y_prev = y_far

        z_prev = z_top

    return boxes


def free_boxes(occupied, st_co, Block_size, order=None, flips=None):
    """
    Decompose the space in a block that the occupied boxes do not cover.

    Cutting the block along every face of every occupied box gives a grid whose cells
    are each wholly free or wholly occupied, so the free cells are exactly the free
    space. Greedily growing each free cell into a maximal run then yields disjoint
    boxes whose union is that space - sound by construction, no case analysis.

    order/flips choose which axis a run grows along first and from which end. Different
    settings give different, equally valid decompositions; callers vary them to explore
    alternative layouts.

    Returns:
        List of (start_coord, size) pairs.
    """
    lo = np.asarray(st_co, dtype=float)
    hi = lo + np.asarray(Block_size, dtype=float)

    cuts = []
    for axis in range(3):
        marks = {lo[axis], hi[axis]}
        for box in occupied:
            for value in (box[axis], box[axis + 3]):
                if lo[axis] < value < hi[axis]:
                    marks.add(float(value))
        cuts.append(np.array(sorted(marks)))

    dims = [len(c) - 1 for c in cuts]
    if min(dims) <= 0:
        return []

    used = np.zeros(dims, dtype=bool)
    for box in occupied:
        span = []
        for axis in range(3):
            a = np.searchsorted(cuts[axis], max(box[axis], lo[axis]))
            b = np.searchsorted(cuts[axis], min(box[axis + 3], hi[axis]))
            span.append(slice(a, b))
        used[tuple(span)] = True

    if order is None:
        order = (0, 1, 2)
    if flips is None:
        flips = (False, False, False)

    def walk(axis):
        rng = range(dims[axis])
        return reversed(rng) if flips[axis] else rng

    out = []
    for i in walk(0):
        for j in walk(1):
            for k in walk(2):
                if used[i, j, k]:
                    continue

                start = [i, j, k]
                extent = [1, 1, 1]

                # Grow the run one axis at a time, keeping it a solid box of free cells.
                for axis in order:
                    while start[axis] + extent[axis] < dims[axis]:
                        probe = [slice(start[d], start[d] + extent[d]) for d in range(3)]
                        probe[axis] = slice(start[axis] + extent[axis],
                                            start[axis] + extent[axis] + 1)
                        if used[tuple(probe)].any():
                            break
                        extent[axis] += 1

                claimed = tuple(slice(start[d], start[d] + extent[d]) for d in range(3))
                used[claimed] = True

                corner = [float(cuts[d][start[d]]) for d in range(3)]
                size = [float(cuts[d][start[d] + extent[d]] - cuts[d][start[d]])
                        for d in range(3)]
                out.append((corner, size))

    return out


def apply_kerf(boxes, st_co, Block_size, buffer):
    """
    Pull each free box in by one kerf width on the faces a saw has to cut.

    free_boxes returns the exact geometric complement of the occupied region, so a
    scrap box sits flush against the prisms beside it and against its neighbouring
    scrap boxes. Every one of those faces is a cut, and the cut destroys `buffer` of
    material, so the piece that actually comes off the saw is smaller than the box.
    Reporting the nominal size over-promises: it goes to ScrapInventory at that size
    and comes back on a later run as an R-block bigger than the steel on the floor.

    Faces lying on the frame boundary are left alone - that is the outer surface of
    the stock block, or, when a scrap is being subdivided, of a scrap whose kerf was
    already taken when it was created. No saw passes there.

    The full buffer is taken on both sides of a scrap-to-scrap face even though one
    cut separates the pair. Splitting it would be more exact, but scrap that
    over-promises is the failure this is fixing, so the conservative side is right.
    """
    if buffer <= 0:
        return boxes

    lo = np.asarray(st_co, dtype=float)
    hi = lo + np.asarray(Block_size, dtype=float)
    tol = 1e-6

    out = []
    for corner, size in boxes:
        new_corner = list(corner)
        new_size = list(size)

        for axis in range(3):
            if corner[axis] > lo[axis] + tol:
                new_corner[axis] += buffer
                new_size[axis] -= buffer
            if corner[axis] + size[axis] < hi[axis] - tol:
                new_size[axis] -= buffer

        # A sliver narrower than the cut that would free it is not a piece of steel.
        if min(new_size) <= 0:
            continue

        out.append((new_corner, new_size))

    return out


def get_scrap_vol(end_coordinates, Block_size, st_co= [0,0,0], co_ordinates_list = [], buffer = 0.0):
    """
    Free space left in a block after fill_the_box has packed it, as scrap boxes.

    buffer is the saw kerf; it is deducted from every cut face (see apply_kerf), so
    the boxes returned are what can physically be lifted out, not the nominal gaps.

    Returns:
        (scrap_volumes, scrap_Boxes) - 8-corner coordinate lists, and
        {'starting_co', 'Box_size'} dicts describing the same boxes.
    """
    import random

    occupied = occupied_boxes_from_staircase(end_coordinates, st_co)

    # Which axis a run grows along first decides how the same free space gets carved up,
    # and the spread is wide: the poor orders shatter it into thin slivers nothing fits
    # in, while good ones leave a few fat boxes. Try a handful of settings and keep the
    # least fragmented. Sampling rather than fixing the order also keeps successive
    # attempts different, which is what run_optimization_with_retries explores with.
    #
    # The deep optimisation enumerates all 48 instead. That removes the run-to-run
    # variation as well as the sampling miss, which is fine there: deep mode is not
    # relying on retries to explore.
    if EXHAUSTIVE_DECOMPOSITION:
        settings_to_try = ALL_DECOMPOSITIONS
    else:
        settings_to_try = [(tuple(random.sample([0, 1, 2], 3)),
                            tuple(random.random() < 0.5 for _ in range(3)))
                           for _ in range(CANDIDATE_DECOMPOSITIONS)]

    candidates = []
    for order, flips in settings_to_try:
        boxes = free_boxes(occupied, st_co, Block_size, order=order, flips=flips)
        biggest = max((size[0] * size[1] * size[2] for _, size in boxes), default=0.0)
        candidates.append((len(boxes), -biggest, boxes))

    boxes = min(candidates, key=lambda c: (c[0], c[1]))[2]

    # Kerf comes off the winner, not off every candidate before ranking. Ranking on the
    # cut sizes was measured worse: it trades a fraction of a percent of scrap volume for
    # ~20% more pieces, each smaller, which is the fragmentation this whole step exists to
    # avoid. It also lets a candidate whose boxes are all culled as slivers score as the
    # least fragmented of the lot. Which carving is least fragmented is a question about
    # the free space itself; the kerf is a uniform inset that does not change the answer.
    boxes = apply_kerf(boxes, st_co, Block_size, buffer)

    scrap_volumes = []
    scrap_Boxes_new = []
    for corner, size in boxes:
        if min(size) <= 0:
            continue
        scrap_Boxes_new.append({'starting_co': corner, 'Box_size': size})
        scrap_volumes.append(place_box(corner, length=size[0], width=size[1], height=size[2]))

    return scrap_volumes, scrap_Boxes_new


def get_scrap_vol_legacy(end_coordinates, Block_size, st_co= [0,0,0], co_ordinates_list = []):
    """Superseded by get_scrap_vol. Kept for reference; its output is not sound."""
    from edges import get_type, process_groups, pre_z_edges, connect_lines_same_x, pre_x_edges, process_groups_yxz, group_by_common_y, pre_y_edges, group_by_common_x, y_edges_process, x_edges_process
    from scrap import get_scrap_volume_of_type4, get_scrap_volume_of_type3, get_scrap_volume_of_type2, get_scrap_volume_of_type1
    z_edges = pre_z_edges(end_coordinates)
    z_edges = connect_lines_same_x(z_edges)
    x_edges = pre_x_edges(end_coordinates)
    x_edges = process_groups_yxz(group_by_common_y(x_edges))
    x_edges = x_edges_process(x_edges)
    y_edges = pre_y_edges(end_coordinates)
    groups = group_by_common_x(y_edges)
    y_edges = process_groups(groups)
    y_edges = y_edges_process(y_edges)
    edges = {'x_edges': x_edges, 'y_edges': y_edges, 'z_edges': z_edges}

    num_x = len(edges['x_edges'])
    num_y = len(edges['y_edges'])
    num_z = len(edges['z_edges'])
    num = num_x + num_y + num_z
    num_cond = num == 3 or num == 6 or num == 9
    num_x_cond = num_x == 1 or num_x == 2 or num_x == 3
    num_y_cond = num_y == 1 or num_y == 2 or num_y == 3
    num_z_cond = num_z == 1 or num_z == 2 or num_z == 3
    
    if  not num_x_cond or not num_y_cond or not num_z_cond or not num_cond:
        # assert False
        big_block_coordinate = place_box(st_co, Block_size[0], Block_size[1], Block_size[2])
        draw(big_block_coordinate, co_ordinates_list , x_edges= edges['x_edges'], y_edges= edges['y_edges'], z_edges=edges['z_edges'], 
             planes={"xy_planes":[],"zx_planes":[],"yz_planes":[],}, scrap_volumes =[])
    
    
    #print('This is type: ', get_type(edges))
    t = get_type(edges)
    if t ==1:
        scrap_Boxes= get_scrap_volume_of_type1(Block_size, edges, st_co)
    elif t==2:
        scrap_Boxes= get_scrap_volume_of_type2(Block_size, edges, st_co)
    elif t==3:
        scrap_Boxes= get_scrap_volume_of_type3(Block_size, edges, st_co)
    elif t==4:
        scrap_Boxes= get_scrap_volume_of_type4(Block_size, edges, st_co)
    
    scrap_volumes = []
    scrap_Boxes_new = []
    for box in scrap_Boxes:
        if box['Box_size'][0] * box['Box_size'][1] * box['Box_size'][2] < 0:
                continue
        scrap_Boxes_new.append(box)
        scrap_coordinate = place_box(box['starting_co'], length= box['Box_size'][0], width= box['Box_size'][1], height= box['Box_size'][2])
        scrap_volumes.append(scrap_coordinate)
    return scrap_volumes,  scrap_Boxes_new