import warnings

from .. import pyom_method
from .utilities import pad_z_edges

@pyom_method
def _calc_cr(pyom,rjp,rj,rjm,vel):
    """
    Calculates cr value used in superbee advection scheme
    """
    eps = 1e-20 # prevent division by 0
    mask_rj = rj == 0.
    mask_vel = vel > 0
    pyom.flush() # prevent precision problems
    mask1 = ~mask_rj & mask_vel
    cr = np.where(mask1, rjm / (rj + eps), np.zeros_like(rj))
    mask2 = ~mask_rj & ~mask_vel
    cr[...] = np.where(mask2, rjp / (rj + eps), cr)
    mask3 = mask_rj & mask_vel
    cr[...] = np.where(mask3, rjm * 1e20, cr)
    mask4 = mask_rj & ~mask_vel
    cr[...] = np.where(mask4, rjp * 1e20, cr)
    return cr

@pyom_method
def _adv_superbee(pyom, vel, var, mask, dx, axis):
    limiter = lambda cr: np.maximum(0.,np.maximum(np.minimum(1.,2*cr), np.minimum(2.,cr)))
    velfac = 1
    if axis == 0:
        sm1, s, sp1, sp2 = ((slice(1+n,-2+n or None),slice(2,-2),slice(None)) for n in range(-1,3))
        dx = pyom.cost[np.newaxis, 2:-2, np.newaxis] * dx[1:-2, np.newaxis, np.newaxis]
    elif axis == 1:
        sm1, s, sp1, sp2 = ((slice(2,-2),slice(1+n,-2+n or None),slice(None)) for n in range(-1,3))
        dx = (pyom.cost * dx)[np.newaxis, 1:-2, np.newaxis]
        velfac = pyom.cosu[np.newaxis, 1:-2, np.newaxis]
    elif axis == 2:
        vel, var, mask = (pad_z_edges(pyom, a) for a in (vel,var,mask))
        sm1, s, sp1, sp2 = ((slice(2,-2),slice(2,-2),slice(1+n,-2+n or None)) for n in range(-1,3))
        dx = dx[np.newaxis,np.newaxis,:-1]
    else:
        raise ValueError("axis must be 0, 1, or 2")
    uCFL = np.abs(velfac * vel[s] * pyom.dt_tracer / dx)
    rjp = (var[sp2] - var[sp1]) * mask[sp1]
    rj = (var[sp1] - var[s]) * mask[s]
    rjm = (var[s] - var[sm1]) * mask[sm1]
    cr = limiter(_calc_cr(pyom, rjp, rj, rjm, vel[s]))
    return velfac * vel[s] * (var[sp1] + var[s]) * 0.5 - np.abs(velfac * vel[s]) * ((1.-cr) + uCFL*cr) * rj * 0.5

@pyom_method
def adv_flux_2nd(pyom,adv_fe,adv_fn,adv_ft,var):
    """
    2th order advective tracer flux
    """
    adv_fe[1:-2, 2:-2, :] = 0.5*(var[1:-2, 2:-2, :] + var[2:-1, 2:-2, :]) * pyom.u[1:-2, 2:-2, :, pyom.tau] * pyom.maskU[1:-2, 2:-2, :]
    adv_fn[2:-2, 1:-2, :] = pyom.cosu[np.newaxis,1:-2,np.newaxis] * 0.5 * (var[2:-2, 1:-2, :] + var[2:-2, 2:-1, :]) \
                    * pyom.v[2:-2, 1:-2, :, pyom.tau] * pyom.maskV[2:-2, 1:-2, :]
    adv_ft[2:-2, 2:-2, :-1] = 0.5 * (var[2:-2, 2:-2, :-1] + var[2:-2, 2:-2, 1:]) * pyom.w[2:-2, 2:-2, :-1, pyom.tau] * pyom.maskW[2:-2, 2:-2, :-1]
    adv_ft[:,:,-1] = 0.

@pyom_method
def adv_flux_superbee(pyom,adv_fe,adv_fn,adv_ft,var):
    """
    from MITgcm
    Calculates advection of a tracer
    using second-order interpolation with a flux limiter:
    \begin{equation*}
    F^x_{adv} = U \overline{ \theta }^i
    - \frac{1}{2} \left([ 1 - \psi(C_r) ] |U|
       + U \frac{u \Delta t}{\Delta x_c} \psi(C_r)
                 \right) \delta_i \theta
    \end{equation*}
    where the $\psi(C_r)$ is the limiter function and $C_r$ is
    the slope ratio.
    """
    adv_fe[1:-2, 2:-2, :] = _adv_superbee(pyom, pyom.u[..., pyom.tau], var, pyom.maskU, pyom.dxt, 0)
    adv_fn[2:-2, 1:-2, :] = _adv_superbee(pyom, pyom.v[..., pyom.tau], var, pyom.maskV, pyom.dyt, 1)
    adv_ft[2:-2, 2:-2, :-1] = _adv_superbee(pyom, pyom.w[..., pyom.tau], var, pyom.maskW, pyom.dzt, 2)
    adv_ft[..., -1] = 0.

@pyom_method
def calculate_velocity_on_wgrid(pyom):
    """
    calculates advection velocity for tracer on W grid

    Note: this implementation is not strictly equal to the Fortran version. They only match
    if maskW has exactly one true value across each depth slice.
    """
    # lateral advection velocities on W grid
    pyom.u_wgrid[:,:,:-1] = pyom.u[:,:,1:,pyom.tau] * pyom.maskU[:,:,1:] * 0.5 * pyom.dzt[np.newaxis,np.newaxis,1:] / pyom.dzw[np.newaxis,np.newaxis,:-1] \
                          + pyom.u[:,:,:-1,pyom.tau] * pyom.maskU[:,:,:-1] * 0.5 * pyom.dzt[np.newaxis,np.newaxis,:-1] / pyom.dzw[np.newaxis,np.newaxis,:-1]
    pyom.v_wgrid[:,:,:-1] = pyom.v[:,:,1:,pyom.tau] * pyom.maskV[:,:,1:] * 0.5 * pyom.dzt[np.newaxis,np.newaxis,1:] / pyom.dzw[np.newaxis,np.newaxis,:-1] \
                          + pyom.v[:,:,:-1,pyom.tau] * pyom.maskV[:,:,:-1] * 0.5 * pyom.dzt[np.newaxis,np.newaxis,:-1] / pyom.dzw[np.newaxis,np.newaxis,:-1]
    pyom.u_wgrid[:,:,-1] = pyom.u[:,:,-1,pyom.tau] * pyom.maskU[:,:,-1] * 0.5 * pyom.dzt[-1:] / pyom.dzw[-1:]
    pyom.v_wgrid[:,:,-1] = pyom.v[:,:,-1,pyom.tau] * pyom.maskV[:,:,-1] * 0.5 * pyom.dzt[-1:] / pyom.dzw[-1:]

    # redirect velocity at bottom and at topography
    pyom.u_wgrid[:,:,0] = pyom.u_wgrid[:,:,0] + pyom.u[:,:,0,pyom.tau] * pyom.maskU[:,:,0] * 0.5 * pyom.dzt[0:1] / pyom.dzw[0:1]
    pyom.v_wgrid[:,:,0] = pyom.v_wgrid[:,:,0] + pyom.v[:,:,0,pyom.tau] * pyom.maskV[:,:,0] * 0.5 * pyom.dzt[0:1] / pyom.dzw[0:1]
    mask = pyom.maskW[:-1, :, :-1] * pyom.maskW[1:, :, :-1]
    pyom.u_wgrid[:-1, :, 1:] += (pyom.u_wgrid[:-1, :, :-1] * pyom.dzw[np.newaxis, np.newaxis, :-1] / pyom.dzw[np.newaxis, np.newaxis, 1:]) * (1.-mask)
    pyom.u_wgrid[:-1, :, :-1] *= mask
    mask = pyom.maskW[:, :-1, :-1] * pyom.maskW[:, 1:, :-1]
    pyom.v_wgrid[:, :-1, 1:] += (pyom.v_wgrid[:, :-1, :-1] * pyom.dzw[np.newaxis, np.newaxis, :-1] / pyom.dzw[np.newaxis, np.newaxis, 1:]) * (1.-mask)
    pyom.v_wgrid[:, :-1, :-1] *= mask

    # vertical advection velocity on W grid from continuity
    pyom.w_wgrid[:, :, 0] = 0.
    pyom.w_wgrid[1:, 1:, :] = np.cumsum(-pyom.dzw[np.newaxis, np.newaxis, :] * \
                              ((pyom.u_wgrid[1:, 1:, :] - pyom.u_wgrid[:-1, 1:, :]) / (pyom.cost[np.newaxis, 1:, np.newaxis] * pyom.dxt[1:, np.newaxis, np.newaxis]) \
                               + (pyom.cosu[np.newaxis, 1:, np.newaxis] * pyom.v_wgrid[1:, 1:, :] - pyom.cosu[np.newaxis, :-1, np.newaxis] * pyom.v_wgrid[1:, :-1, :]) \
                                     / (pyom.cost[np.newaxis, 1:, np.newaxis] * pyom.dyt[np.newaxis, 1:, np.newaxis])), axis=2)


@pyom_method
def adv_flux_superbee_wgrid(pyom,adv_fe,adv_fn,adv_ft,var):
    """
    Calculates advection of a tracer defined on Wgrid
    """
    maskUtr = np.zeros_like(adv_fe)
    maskUtr[:-1, :, :] = pyom.maskW[1:, :, :] * pyom.maskW[:-1, :, :]
    adv_fe[1:-2, 2:-2, :] = _adv_superbee(pyom, pyom.u_wgrid, var, maskUtr, pyom.dxt, 0)

    maskVtr = np.zeros_like(adv_fn)
    maskVtr[:, :-1, :] = pyom.maskW[:, 1:, :] * pyom.maskW[:, :-1, :]
    adv_fn[2:-2, 1:-2, :] = _adv_superbee(pyom, pyom.v_wgrid, var, maskVtr, pyom.dyt, 1)

    maskWtr = np.zeros_like(adv_ft)
    maskWtr[:, :, :-1] = pyom.maskW[:, :, 1:] * pyom.maskW[:, :, :-1]
    adv_ft[2:-2, 2:-2, :-1] = _adv_superbee(pyom, pyom.w_wgrid, var, maskWtr, pyom.dzw, 2)
    adv_ft[..., -1] = 0.0


@pyom_method
def adv_flux_upwind_wgrid(pyom,adv_fe,adv_fn,adv_ft,var):
    """
    Calculates advection of a tracer defined on Wgrid
    """
    maskUtr = pyom.maskW[2:-1, 2:-2, :] * pyom.maskW[1:-2, 2:-2, :]
    rj = (var[2:-1, 2:-2, :] - var[1:-2, 2:-2, :]) * maskUtr
    adv_fe[1:-2, 2:-2, :] = pyom.u_wgrid[1:-2, 2:-2, :] * (var[2:-1, 2:-2, :] + var[1:-2, 2:-2, :]) * 0.5 \
                            - np.abs(pyom.u_wgrid[1:-2, 2:-2, :]) * rj * 0.5

    maskVtr = pyom.maskW[2:-2, 2:-1, :] * pyom.maskW[2:-2, 1:-2, :]
    rj = (var[2:-2, 2:-1, :] - var[2:-2, 1:-2, :]) * maskVtr
    adv_fn[2:-2, 1:-2, :] = pyom.cosu[np.newaxis, 1:-2, np.newaxis] * pyom.v_wgrid[2:-2, 1:-2, :] * \
                            (var[2:-2, 2:-1, :] + var[2:-2, 1:-2, :]) * 0.5 \
                            - np.abs(pyom.cosu[np.newaxis, 1:-2, np.newaxis] * pyom.v_wgrid[2:-2, 1:-2, :]) * rj * 0.5

    maskWtr = pyom.maskW[2:-2, 2:-2, 1:] * pyom.maskW[2:-2, 2:-2, :-1]
    rj = (var[2:-2, 2:-2, 1:] - var[2:-2, 2:-2, :-1]) * maskWtr
    adv_ft[2:-2, 2:-2, :-1] = pyom.w_wgrid[2:-2, 2:-2, :-1] * (var[2:-2, 2:-2, 1:] + var[2:-2, 2:-2, :-1]) * 0.5 \
                              - np.abs(pyom.w_wgrid[2:-2, 2:-2, :-1]) * rj * 0.5
    adv_ft[:,:,-1] = 0.
