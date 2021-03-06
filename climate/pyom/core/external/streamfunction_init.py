from ... import pyom_method
from .. import cyclic
from . import island, utilities, solve_poisson

@pyom_method
def streamfunction_init(pyom):
    """
    prepare for island integrals
    """
    maxipp = 10000
    mnisle = 1000
    allmap = np.zeros((pyom.nx+4, pyom.ny+4))
    boundary_map = np.zeros((pyom.nx+4, pyom.ny+4))
    forc = np.zeros((pyom.nx+4, pyom.ny+4))
    iperm = np.zeros(maxipp)
    jperm = np.zeros(maxipp)
    nippts = np.zeros(mnisle, dtype=np.int)
    iofs = np.zeros(mnisle, dtype=np.int)

    if pyom.backend_name == "bohrium":
        boundary_map = boundary_map.copy2numpy()
        allmap = allmap.copy2numpy()
        iperm = iperm.copy2numpy()
        jperm = jperm.copy2numpy()
        nippts = nippts.copy2numpy()
        iofs = iofs.copy2numpy()

    print("Initializing streamfunction method")
    verbose = pyom.enable_congrad_verbose
    """
    communicate kbot to get the entire land map
    """
    kmt = np.zeros((pyom.nx+4, pyom.ny+4)) # note that routine will modify kmt
    kmt[2:-2, 2:-2] = (pyom.kbot[2:-2, 2:-2] > 0) * 5

    if pyom.enable_cyclic_x:
        cyclic.setcyclic_x(kmt)

    """
    preprocess land map using MOMs algorithm for B-grid to determine number of islands
    """
    print(" starting MOMs algorithm for B-grid to determine number of islands")
    island.isleperim(pyom, kmt, allmap, iperm, jperm, iofs, nippts, pyom.nx+4, pyom.ny+4, mnisle, maxipp, change_nisle=True, verbose=True)
    if pyom.enable_cyclic_x:
        cyclic.setcyclic_x(allmap)
    _showmap(pyom, allmap)

    """
    allocate variables
    """
    pyom.boundary_mask = np.zeros((pyom.nx+4, pyom.ny+4, pyom.nisle)).astype(np.bool)
    pyom.line_dir_south_mask = np.zeros((pyom.nx+4, pyom.ny+4, pyom.nisle)).astype(np.bool)
    pyom.line_dir_north_mask = np.zeros((pyom.nx+4, pyom.ny+4, pyom.nisle)).astype(np.bool)
    pyom.line_dir_east_mask = np.zeros((pyom.nx+4, pyom.ny+4, pyom.nisle)).astype(np.bool)
    pyom.line_dir_west_mask = np.zeros((pyom.nx+4, pyom.ny+4, pyom.nisle)).astype(np.bool)
    pyom.psin = np.zeros((pyom.nx+4, pyom.ny+4, pyom.nisle))
    pyom.dpsin = np.zeros((pyom.nisle, 3))
    pyom.line_psin = np.zeros((pyom.nisle, pyom.nisle))

    if pyom.backend_name == "bohrium":
        pyom.boundary_mask = pyom.boundary_mask.copy2numpy()
        pyom.line_dir_south_mask = pyom.line_dir_south_mask.copy2numpy()
        pyom.line_dir_north_mask = pyom.line_dir_north_mask.copy2numpy()
        pyom.line_dir_east_mask  = pyom.line_dir_east_mask.copy2numpy()
        pyom.line_dir_west_mask  = pyom.line_dir_west_mask.copy2numpy()

    for isle in xrange(pyom.nisle): #isle=1,nisle
        print(" ------------------------")
        print(" processing island #{:d}".format(isle))
        print(" ------------------------")

        """
        land map for island number isle: 1 is land, -1 is perimeter, 0 is ocean
        """
        kmt[...] = allmap != isle+1
        island.isleperim(pyom, kmt, boundary_map, iperm, jperm, iofs, nippts, pyom.nx+4, pyom.ny+4, mnisle, maxipp)
        if verbose:
            _showmap(pyom, boundary_map)

        """
        find a starting point
        """
        n = 0
        # avoid starting close to cyclic bondaries
        (cont, ij, Dir, startPos) = _avoid_cyclic_boundaries(pyom, boundary_map, isle, n, (pyom.nx/2+1, pyom.nx+2))
        if not cont:
            (cont, ij, Dir, startPos) = _avoid_cyclic_boundaries(pyom, boundary_map, isle, n, (pyom.nx/2,-1,-1))
            if not cont:
                raise RuntimeError("found no starting point for line integral")

        print(" starting point of line integral is {!r}".format(startPos))
        print(" starting direction is {!r}".format(Dir))

        """
        now find connecting lines
        """
        n = 1
        pyom.boundary_mask[ij[0],ij[1], isle] = 1
        cont = True
        while cont:
            """
            consider map in front of line direction and to the right and decide where to go
            """
            if Dir[0]== 0 and Dir[1]== 1: # north
                ijp      = [ij[0]  ,ij[1]+1]
                ijp_right= [ij[0]+1,ij[1]+1]
            elif Dir[0]==-1 and Dir[1]== 0: # west
                ijp      = [ij[0]  ,ij[1]  ]
                ijp_right= [ij[0]  ,ij[1]+1]
            elif Dir[0]== 0 and Dir[1]==-1: # south
                ijp      = [ij[0]+1,ij[1]  ]
                ijp_right= [ij[0]  ,ij[1]  ]
            elif Dir[0]== 1 and Dir[1]== 0: # east
                ijp      = [ij[0]+1,ij[1]+1]
                ijp_right= [ij[0]+1,ij[1]  ]

            """
            4 cases are possible
            """

            if verbose:
                print(" ")
                print(" position is {!r}".format(ij))
                print(" direction is {!r}".format(Dir))
                print(" map ahead is {} {}".format(boundary_map[ijp[0],ijp[1]], boundary_map[ijp_right[0],ijp_right[1]]))

            if boundary_map[ijp[0],ijp[1]] == -1 and boundary_map[ijp_right[0],ijp_right[1]] == 1:
                if verbose:
                    print(" go forward")
            elif boundary_map[ijp[0],ijp[1]] == -1 and boundary_map[ijp_right[0],ijp_right[1]] == -1:
                if verbose:
                    print(" turn right")
                Dir = [Dir[1],-Dir[0]]
            elif boundary_map[ijp[0],ijp[1]] == 1 and boundary_map[ijp_right[0],ijp_right[1]] == 1:
                if verbose:
                    print(" turn left")
                Dir = [-Dir[1],Dir[0]]
            elif boundary_map[ijp[0],ijp[1]] == 1 and boundary_map[ijp_right[0],ijp_right[1]] == -1:
                if verbose:
                    print(" turn left")
                Dir = [-Dir[1],Dir[0]]
            else:
                print(" map ahead is {} {}".format(boundary_map[ijp[0],ijp[1]], boundary_map[ijp_right[0],ijp_right[1]]))
                raise RuntimeError("unknown situation or lost track")

            """
            go forward in direction
            """
            if Dir[0]== 0 and Dir[1]== 1: #north
                pyom.line_dir_north_mask[ij[0], ij[1], isle] = 1
            elif Dir[0]==-1 and Dir[1]== 0: #west
                pyom.line_dir_west_mask[ij[0], ij[1], isle] = 1
            elif Dir[0]== 0 and Dir[1]==-1: #south
                pyom.line_dir_south_mask[ij[0], ij[1], isle] = 1
            elif Dir[0]== 1 and Dir[1]== 0: #east
                pyom.line_dir_east_mask[ij[0], ij[1], isle] = 1
            ij = [ij[0] + Dir[0], ij[1] + Dir[1]]
            if startPos[0] == ij[0] and startPos[1] == ij[1]:
                cont = False

            """
            account for cyclic boundary conditions
            """
            if pyom.enable_cyclic_x and Dir[0] == 1 and Dir[1] == 0 and ij[0] > pyom.nx+1:
                if verbose:
                    print(" shifting to western cyclic boundary")
                ij[0] -= pyom.nx
            if pyom.enable_cyclic_x and Dir[0] == -1 and Dir[1] == 0 and ij[0] < 2:
                if verbose:
                    print(" shifting to eastern cyclic boundary")
                ij[0] += pyom.nx
            if startPos[0] == ij[0] and startPos[1] == ij[1]:
                cont = False

            if cont:
                n += 1
                pyom.boundary_mask[ij[0],ij[1],isle] = 1

        print(" number of points is {:d}".format(n+1))
        if verbose:
            print(" ")
            print(" Positions:")
            print(" boundary: {!r}".format(pyom.boundary_mask[...,isle]))

    if pyom.backend_name == "bohrium":
        pyom.boundary_mask = np.asarray(pyom.boundary_mask)
        pyom.line_dir_south_mask = np.asarray(pyom.line_dir_south_mask)
        pyom.line_dir_north_mask = np.asarray(pyom.line_dir_north_mask)
        pyom.line_dir_east_mask  = np.asarray(pyom.line_dir_east_mask)
        pyom.line_dir_west_mask  = np.asarray(pyom.line_dir_west_mask)

    """
    precalculate time independent boundary components of streamfunction
    """
    forc[...] = 0.0
    # initialize with noise to achieve uniform convergence
    pyom.psin[...] = np.random.rand(*pyom.psin.shape)

    for isle in xrange(pyom.nisle):
        print(" solving for boundary contribution by island {:d}".format(isle))
        solve_poisson.solve(pyom, forc, pyom.psin[:,:,isle], boundary_val=pyom.boundary_mask[:,:,isle])

    if pyom.enable_cyclic_x:
        cyclic.setcyclic_x(pyom.psin)

    """
    precalculate time independent island integrals
    """
    fpx = np.zeros((pyom.nx+4, pyom.ny+4, pyom.nisle))
    fpy = np.zeros((pyom.nx+4, pyom.ny+4, pyom.nisle))

    fpx[1:, 1:, :] = -pyom.maskU[1:, 1:, -1, np.newaxis] \
            * (pyom.psin[1:, 1:, :] - pyom.psin[1:, :-1, :]) \
            / pyom.dyt[np.newaxis,1:,np.newaxis] * pyom.hur[1:, 1:, np.newaxis]
    fpy[1:, 1:, ...] = pyom.maskV[1:, 1:, -1, np.newaxis] \
            * (pyom.psin[1:, 1:, :] - pyom.psin[:-1, 1:, :]) \
            / (pyom.cosu[np.newaxis,1:,np.newaxis] * pyom.dxt[1:, np.newaxis, np.newaxis]) \
            * pyom.hvr[1:, 1:, np.newaxis]
    pyom.line_psin[...] = utilities.line_integrals(pyom, fpx, fpy, kind="full")

@pyom_method
def _avoid_cyclic_boundaries(pyom, boundary_map, isle, n, x_range):
    for i in xrange(*x_range):
        for j in xrange(1, pyom.ny+2):
            if boundary_map[i,j] == 1 and boundary_map[i,j+1] == -1:
                #initial direction is eastward, we come from the west
                cont = True
                Dir = [1,0]
                pyom.line_dir_east_mask[i-1, j, isle] = 1
                pyom.boundary_mask[i-1, j, isle] = 1
                return cont, (i,j), Dir, (i-1, j)
            if boundary_map[i,j] == -1 and boundary_map[i,j+1] == 1:
                # initial direction is westward, we come from the east
                cont = True
                Dir = [-1,0]
                pyom.line_dir_west_mask[i, j, isle] = 1
                pyom.boundary_mask[i, j, isle] = 1
                return cont, (i-1,j), Dir, (i,j)
    return False, None, [0,0], [0,0]

@pyom_method
def _showmap(pyom, boundary_map):
    linewidth = 125
    imt = pyom.nx + 4
    iremain = imt
    istart = 0
    print("")
    print(" "*(5+min(linewidth,imt)/2-13) + "Land mass and perimeter")
    for isweep in xrange(1, imt/linewidth + 2):
        iline = min(iremain, linewidth)
        iremain = iremain - iline
        if iline > 0:
            print(" ")
            print("".join(["{:5d}".format(istart+i+1-2) for i in xrange(1,iline+1,5)]))
            for j in xrange(pyom.ny+3, -1, -1):
                print("{:3d} ".format(j) + "".join([str(int(_mod10(boundary_map[istart+i -2,j]))) if _mod10(boundary_map[istart+i -2,j]) >= 0 else "*" for i in xrange(2, iline+2)]))
            print("".join(["{:5d}".format(istart+i+1-2) for i in xrange(1,iline+1,5)]))
            istart = istart + iline
    print("")

def _mod10(m):
    if m > 0:
        return m % 10
    else:
        return m
