import math

from .. import pyom_method
from . import cyclic, advection, utilities, numerics

@pyom_method
def set_tke_diffusivities(pyom):
    """
    set vertical diffusivities based on TKE model
    """
    Rinumber = np.zeros((pyom.nx+4, pyom.ny+4, pyom.nz))

    if pyom.enable_tke:
        pyom.sqrttke = np.sqrt(np.maximum(0., pyom.tke[:,:,:,pyom.tau]))
        """
        calculate buoyancy length scale
        """
        pyom.mxl[...] = math.sqrt(2) * pyom.sqrttke / np.sqrt(np.maximum(1e-12, pyom.Nsqr[:,:,:,pyom.tau])) * pyom.maskW

        """
        apply limits for mixing length
        """
        if pyom.tke_mxl_choice == 1:
            """
            bounded by the distance to surface/bottom
            """
            pyom.mxl[...] = np.minimum(
                                np.minimum(pyom.mxl, -pyom.zw[np.newaxis, np.newaxis, :] \
                                                    + pyom.dzw[np.newaxis, np.newaxis, :] * 0.5
                                          )
                                      , pyom.ht[:, :, np.newaxis] + pyom.zw[np.newaxis, np.newaxis, :]
                                      )
            pyom.mxl[...] = np.maximum(pyom.mxl, pyom.mxl_min)
        elif pyom.tke_mxl_choice == 2:
            """
            bound length scale as in mitgcm/OPA code

            Note that the following code doesn't vectorize. If critical for performance,
            consider re-implementing it in Cython.
            """
            if pyom.backend_name == "bohrium":
                mxl = pyom.mxl.copy2numpy()
                dzt = pyom.dzt.copy2numpy()
            else:
                mxl = pyom.mxl
                dzt = pyom.dzt
            for k in xrange(pyom.nz-2,-1,-1):
                mxl[:,:,k] = np.minimum(mxl[:,:,k], mxl[:,:,k+1] + dzt[k+1])
            mxl[:,:,-1] = np.minimum(mxl[:,:,-1], pyom.mxl_min + dzt[-1])
            for k in xrange(1,pyom.nz):
                mxl[:,:,k] = np.minimum(mxl[:,:,k], mxl[:,:,k-1] + dzt[k])
            pyom.mxl[...] = np.maximum(np.asarray(mxl), pyom.mxl_min)
        else:
            raise ValueError("unknown mixing length choice in tke_mxl_choice")

        """
        calculate viscosity and diffusivity based on Prandtl number
        """
        if pyom.enable_cyclic_x:
            cyclic.setcyclic_x(pyom.K_diss_v)
        pyom.kappaM = np.minimum(pyom.kappaM_max, pyom.c_k * pyom.mxl * pyom.sqrttke)
        Rinumber = pyom.Nsqr[:,:,:,pyom.tau] / np.maximum(pyom.K_diss_v / np.maximum(1e-12, pyom.kappaM), 1e-12)
        if pyom.enable_idemix:
            Rinumber = np.minimum(Rinumber, pyom.kappaM * pyom.Nsqr[:,:,:,pyom.tau] / np.maximum(1e-12, pyom.alpha_c * pyom.E_iw[:,:,:,pyom.tau]**2))
        pyom.Prandtlnumber = np.maximum(1., np.minimum(10, 6.6 * Rinumber))
        pyom.kappaH = pyom.kappaM / pyom.Prandtlnumber
        pyom.kappaM = np.maximum(pyom.kappaM_min, pyom.kappaM)
    else:
        pyom.kappaM[...] = pyom.kappaM_0
        pyom.kappaH[...] = pyom.kappaH_0
        if pyom.enable_hydrostatic:
            """
            simple convective adjustment
            """
            pyom.kappaH[...] = np.where(pyom.Nsqr[:,:,:,pyom.tau] < 0.0, 1.0, pyom.kappaH)

@pyom_method
def integrate_tke(pyom):
    """
    integrate Tke equation on W grid with surface flux boundary condition
    """
    pyom.dt_tke = pyom.dt_mom  # use momentum time step to prevent spurious oscillations

    """
    Sources and sinks by vertical friction, vertical mixing, and non-conservative advection
    """
    forc = pyom.K_diss_v - pyom.P_diss_v - pyom.P_diss_adv

    """
    store transfer due to vertical mixing from dyn. enthalpy by non-linear eq.of
    state either to TKE or to heat
    """
    if not pyom.enable_store_cabbeling_heat:
        forc[...] += -pyom.P_diss_nonlin

    """
    transfer part of dissipation of EKE to TKE
    """
    if pyom.enable_eke:
        forc[...] += pyom.eke_diss_tke

    if pyom.enable_idemix:
        """
        transfer dissipation of internal waves to TKE
        """
        forc[...] += pyom.iw_diss
        """
        store bottom friction either in TKE or internal waves
        """
        if pyom.enable_store_bottom_friction_tke:
            forc[...] += pyom.K_diss_bot
    else: # short-cut without idemix
        if pyom.enable_eke:
            forc[...] += pyom.eke_diss_iw
        else: # and without EKE model
            if pyom.enable_store_cabbeling_heat:
                forc[...] += pyom.K_diss_gm + pyom.K_diss_h - pyom.P_diss_skew \
                        - pyom.P_diss_hmix  - pyom.P_diss_iso
            else:
                forc[...] += pyom.K_diss_gm + pyom.K_diss_h - pyom.P_diss_skew
        forc[...] += pyom.K_diss_bot

    """
    vertical mixing and dissipation of TKE
    """
    ks = pyom.kbot[2:-2, 2:-2] - 1

    a_tri = np.zeros((pyom.nx,pyom.ny,pyom.nz))
    b_tri = np.zeros((pyom.nx,pyom.ny,pyom.nz))
    c_tri = np.zeros((pyom.nx,pyom.ny,pyom.nz))
    d_tri = np.zeros((pyom.nx,pyom.ny,pyom.nz))
    delta = np.zeros((pyom.nx,pyom.ny,pyom.nz))

    delta[:,:,:-1] = pyom.dt_tke / pyom.dzt[np.newaxis, np.newaxis, 1:] * pyom.alpha_tke * 0.5 \
                    * (pyom.kappaM[2:-2, 2:-2, :-1] + pyom.kappaM[2:-2, 2:-2, 1:])

    a_tri[:,:,1:-1] = -delta[:,:,:-2] / pyom.dzw[np.newaxis,np.newaxis,1:-1]
    a_tri[:,:,-1] = -delta[:,:,-2] / (0.5 * pyom.dzw[-1])

    b_tri[:,:,1:-1] = 1 + (delta[:, :, 1:-1] + delta[:, :, :-2]) / pyom.dzw[np.newaxis, np.newaxis, 1:-1] \
                        + pyom.dt_tke * pyom.c_eps * pyom.sqrttke[2:-2, 2:-2, 1:-1] / pyom.mxl[2:-2, 2:-2, 1:-1]
    b_tri[:,:,-1] = 1 + delta[:,:,-2] / (0.5 * pyom.dzw[-1]) \
                        + pyom.dt_tke * pyom.c_eps / pyom.mxl[2:-2, 2:-2, -1] * pyom.sqrttke[2:-2, 2:-2, -1]
    b_tri_edge = 1 + delta / pyom.dzw[np.newaxis,np.newaxis,:] \
                        + pyom.dt_tke * pyom.c_eps / pyom.mxl[2:-2, 2:-2, :] * pyom.sqrttke[2:-2, 2:-2, :]

    c_tri[:,:,:-1] = -delta[:,:,:-1] / pyom.dzw[np.newaxis,np.newaxis,:-1]

    d_tri[...] = pyom.tke[2:-2, 2:-2, :, pyom.tau] + pyom.dt_tke * forc[2:-2, 2:-2, :]
    d_tri[:,:,-1] += pyom.dt_tke * pyom.forc_tke_surface[2:-2, 2:-2] / (0.5 * pyom.dzw[-1])

    sol, water_mask = utilities.solve_implicit(pyom, ks, a_tri, b_tri, c_tri, d_tri, b_edge=b_tri_edge)
    pyom.tke[2:-2, 2:-2, :, pyom.taup1] = np.where(water_mask, sol, pyom.tke[2:-2, 2:-2, :, pyom.taup1])

    """
    store tke dissipation for diagnostics
    """
    pyom.tke_diss[...] = pyom.c_eps / pyom.mxl * pyom.sqrttke * pyom.tke[:,:,:,pyom.taup1]

    """
    Add TKE if surface density flux drains TKE in uppermost box
    """
    mask = pyom.tke[2:-2, 2:-2, -1, pyom.taup1] < 0.0
    pyom.tke_surf_corr[...] = 0.
    pyom.tke_surf_corr[2:-2, 2:-2] = np.where(mask, -pyom.tke[2:-2, 2:-2, -1, pyom.taup1] * 0.5 * pyom.dzw[-1] / pyom.dt_tke, 0.)
    pyom.tke[2:-2, 2:-2, -1, pyom.taup1] = np.maximum(0., pyom.tke[2:-2, 2:-2, -1, pyom.taup1])

    if pyom.enable_tke_hor_diffusion:
        """
        add tendency due to lateral diffusion
        """
        pyom.flux_east[:-1, :, :] = pyom.K_h_tke * (pyom.tke[1:, :, :, pyom.tau] - pyom.tke[:-1, :, :, pyom.tau]) \
                                    / (pyom.cost[np.newaxis, :, np.newaxis] * pyom.dxu[:-1, np.newaxis, np.newaxis]) * pyom.maskU[:-1, :, :]
        pyom.flux_east[-5,:,:] = 0. # NOTE: probably a mistake in the fortran code, first index should be -1
        pyom.flux_north[:, :-1, :] = pyom.K_h_tke * (pyom.tke[:, 1:, :, pyom.tau] - pyom.tke[:, :-1, :, pyom.tau]) \
                                     / pyom.dyu[np.newaxis, :-1, np.newaxis] * pyom.maskV[:, :-1, :] * pyom.cosu[np.newaxis, :-1, np.newaxis]
        pyom.flux_north[:,-1,:] = 0.
        pyom.tke[2:-2, 2:-2, :, pyom.taup1] += pyom.dt_tke * pyom.maskW[2:-2, 2:-2, :] * \
                                ((pyom.flux_east[2:-2, 2:-2, :] - pyom.flux_east[1:-3, 2:-2, :]) \
                                   / (pyom.cost[np.newaxis, 2:-2, np.newaxis] * pyom.dxt[2:-2, np.newaxis, np.newaxis]) \
                                + (pyom.flux_north[2:-2, 2:-2, :] - pyom.flux_north[2:-2, 1:-3, :]) \
                                   / (pyom.cost[np.newaxis, 2:-2, np.newaxis] * pyom.dyt[np.newaxis, 2:-2, np.newaxis]))

    """
    add tendency due to advection
    """
    if pyom.enable_tke_superbee_advection:
        advection.adv_flux_superbee_wgrid(pyom,pyom.flux_east,pyom.flux_north,pyom.flux_top,pyom.tke[:,:,:,pyom.tau])
    if pyom.enable_tke_upwind_advection:
        advection.adv_flux_upwind_wgrid(pyom,pyom.flux_east,pyom.flux_north,pyom.flux_top,pyom.tke[:,:,:,pyom.tau])
    if pyom.enable_tke_superbee_advection or pyom.enable_tke_upwind_advection:
        pyom.dtke[2:-2, 2:-2, :, pyom.tau] = pyom.maskW[2:-2, 2:-2, :] * (-(pyom.flux_east[2:-2, 2:-2, :] - pyom.flux_east[1:-3, 2:-2, :]) \
                                                                           / (pyom.cost[np.newaxis, 2:-2, np.newaxis] * pyom.dxt[2:-2, np.newaxis, np.newaxis]) \
                                                                         - (pyom.flux_north[2:-2, 2:-2, :] - pyom.flux_north[2:-2, 1:-3, :]) \
                                                                           / (pyom.cost[np.newaxis, 2:-2, np.newaxis] * pyom.dyt[np.newaxis, 2:-2, np.newaxis]))
        pyom.dtke[:,:,0,pyom.tau] += -pyom.flux_top[:,:,0] / pyom.dzw[0]
        pyom.dtke[:,:,1:-1,pyom.tau] += -(pyom.flux_top[:,:,1:-1] - pyom.flux_top[:,:,:-2]) / pyom.dzw[1:-1]
        pyom.dtke[:,:,-1,pyom.tau] += -(pyom.flux_top[:,:,-1] - pyom.flux_top[:,:,-2]) / (0.5 * pyom.dzw[-1])
        """
        Adam Bashforth time stepping
        """
        pyom.tke[:,:,:,pyom.taup1] += pyom.dt_tracer * ((1.5 + pyom.AB_eps) * pyom.dtke[:,:,:,pyom.tau] \
                                        - (0.5 + pyom.AB_eps) * pyom.dtke[:,:,:,pyom.taum1])
