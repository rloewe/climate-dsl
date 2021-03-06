"""
      solve two dimensional Possion equation
           A * dpsi = forc,  where A = nabla_h^2
      with Neumann boundary conditions
      used for surface pressure or free surface
      method same as pressure method in MITgcm
"""
import warnings

from .. import cyclic
from ... import pyom_method

@pyom_method
def solve_pressure(pyom):
    fpx = np.zeros((pyom.nx+4, pyom.ny+4))
    fpy = np.zeros((pyom.nx+4, pyom.ny+4))
    forc = np.zeros((pyom.nx+4, pyom.ny+4))

    # hydrostatic pressure
    fxa = pyom.grav / pyom.rho_0
    pyom.p_hydro[:,:,pyom.nz-1] = 0.5*pyom.rho[:,:,pyom.nz-1,pyom.tau]*fxa*pyom.dzw[pyom.nz-1]*pyom.maskT[:,:,pyom.nz-1]
    for k in xrange(pyom.nz-2, 0, -1): #k=pyom.nz-1,1,-1
        pyom.p_hydro[:,:,k] = pyom.maskT[:,:,k]*(pyom.p_hydro[:,:,k+1] + 0.5*(pyom.rho[:,:,k+1,pyom.tau]+pyom.rho[:,:,k,pyom.tau])*fxa*pyom.dzw[k])

    # add hydrostatic pressure gradient to tendencies
    for j in xrange(pyom.js_pe, pyom.je_pe+1): #j=pyom.js_pe,pyom.je_pe
        for i in xrange(pyom.is_pe, pyom.ie_pe): #i=pyom.is_pe,pyom.ie_pe
            pyom.du[i,j,:,pyom.tau] -= (pyom.p_hydro[i+1,j,:]-pyom.p_hydro[i,j,:]) / (pyom.dxu[i] * pyom.cost[j]) * pyom.maskU[i,j,:]
            pyom.dv[i,j,:,pyom.tau] -= (pyom.p_hydro[i,j+1,:]-pyom.p_hydro[i,j,:]) / pyom.dyu[j] * pyom.maskV[i,j,:]

    # integrate forward in time
    pyom.u[:,:,:,pyom.taup1] = pyom.u[:,:,:,pyom.tau] + pyom.dt_mom * \
                                                        (pyom.du_mix + (1.5+pyom.AB_eps) \
                                                                     * pyom.du[:,:,:,pyom.tau] \
                                                        - (0.5+pyom.AB_eps) * pyom.du[:,:,:,pyom.taum1]) * pyom.maskU
    pyom.v[:,:,:,pyom.taup1] = pyom.v[:,:,:,pyom.tau] + pyom.dt_mom * \
                                                        (pyom.dv_mix + (1.5+pyom.AB_eps) \
                                                                     * pyom.dv[:,:,:,pyom.tau] \
                                                        - (0.5+pyom.AB_eps) * pyom.dv[:,:,:,pyom.taum1]) * pyom.maskV

    # forcing for surface pressure
    for k in xrange(pyom.nz): #k=1,pyom.nz
        for j in xrange(pyom.js_pe, pyom.je_pe): #j=pyom.js_pe,pyom.je_pe
            for i in xrange(pyom.is_pe, pyom.ie_pe): #i=pyom.is_pe,pyom.ie_pe
                fpx[i,j] += pyom.u[i,j,k,pyom.taup1] * pyom.maskU[i,j,k] * pyom.dzt[k] / pyom.dt_mom
                fpy[i,j] += pyom.v[i,j,k,pyom.taup1] * pyom.maskV[i,j,k] * pyom.dzt[k] / pyom.dt_mom
    if pyom.enable_cyclic_x:
        cyclic.setcyclic_x(fpx)
        cyclic.setcyclic_x(fpy)

    # forc = 1/cos (u_x + (cos pyom.v)_y )
    for j in xrange(pyom.js_pe, pyom.je_pe+1): #j=pyom.js_pe,pyom.je_pe
        for i in xrange(pyom.is_pe, pyom.ie_pe+1): #i=pyom.is_pe,pyom.ie_pe
            forc[i,j] = (fpx[i,j]-fpx[i-1,j])/(pyom.cost[j]*pyom.dxt[i])+(pyom.cosu[j]*fpy[i,j]-pyom.cosu[j-1]*fpy[i,j-1])/(pyom.cost[j]*pyom.dyt[j])
    if pyom.enable_free_surface:
        for j in xrange(pyom.js_pe, pyom.je_pe+1): #j=pyom.js_pe,pyom.je_pe
            for i in xrange(pyom.is_pe, pyom.ie_pe+1): #i=pyom.is_pe,pyom.ie_pe
                forc[i,j] -= pyom.psi[i,j,pyom.tau]/(pyom.grav*pyom.dt_mom**2)*pyom.maskT[i,j,pyom.nz]

    pyom.psi[:,:,pyom.taup1] = 2*pyom.psi[:,:,pyom.tau]-pyom.psi[:,:,pyom.taum1] # first guess
    #solve for surface pressure
    congrad_surf_press(forc,pyom.congr_itts,pyom)
    if pyom.enable_cyclic_x:
        cyclic.setcyclic_x(pyom.psi[:,:,pyom.taup1])

    # remove surface pressure gradient
    for j in xrange(pyom.js_pe, pyom.je_pe+1): #j=pyom.js_pe,pyom.je_pe
        for i in xrange(pyom.is_pe, pyom.ie_pe+1): #i=pyom.is_pe,pyom.ie_pe
            pyom.u[i,j,:,pyom.taup1] -= pyom.dt_mom*( pyom.psi[i+1,j,pyom.taup1]-pyom.psi[i,j,pyom.taup1])/(pyom.dxu[i]*pyom.cost[j]) *pyom.maskU[i,j,:]
            pyom.v[i,j,:,pyom.taup1] -= pyom.dt_mom*( pyom.psi[i,j+1,pyom.taup1]-pyom.psi[i,j,pyom.taup1]) /pyom.dyu[j]*pyom.maskV[i,j,:]

@pyom_method
def make_coeff_surf_press(pyom):
    """
    -----------------------------------------------------------------------
             A * p = forc
             res = A * p
             res = res +  cf(...,ii,jj,kk) * p(i+ii,j+jj,k+kk)

             forc = (h p_x)_x +(h p_y)_y
             forc = [ hu(i)(p(i+1) - p(i))/pyom.dxu(i) - hu(i-1)(p(i)-p(i-1))/pyom.dxu(i-1) ] /pyom.dxt(i)
             forc = hu(i) p(i+1)/pyom.dxu(i)/pyom.dxt(i)  - p(i) hu(i)/pyom.dxu(i)/pyom.dxt(i) -p(i)*hu(i-1)/pyom.dxu(i-1)/pyom.dxt(i)  + hu(i-1) p(i-1)/pyom.dxu(i-1)/pyom.dxt(i)

             in spherical coord.:
             forc = 1/cos^2 ( (h p_x)_x + cos (cos h p_y )_y )
    -----------------------------------------------------------------------
    """
    maskM = pyom.maskT[:,:,-1]
    cf = np.zeros((pyom.nx+4, pyom.ny+4, 3, 3))
    for j in xrange(pyom.js_pe, pyom.je_pe+1): #j=pyom.js_pe,pyom.je_pe
        for i in xrange(pyom.is_pe, pyom.ie_pe+1): #i=pyom.is_pe,pyom.ie_pe
            mp = maskM[i,j] * maskM[i+1,j]
            mm = maskM[i,j] * maskM[i-1,j]
            cf[i,j, 1, 1] -= mp*pyom.hu[i  ,j]/pyom.dxu[i  ]/pyom.dxt[i] /pyom.cost[j]**2
            cf[i,j, 2, 1] += mp*pyom.hu[i  ,j]/pyom.dxu[i  ]/pyom.dxt[i] /pyom.cost[j]**2
            cf[i,j, 1, 1] -= mm*pyom.hu[i-1,j]/pyom.dxu[i-1]/pyom.dxt[i] /pyom.cost[j]**2
            cf[i,j, 0, 1] += mm*pyom.hu[i-1,j]/pyom.dxu[i-1]/pyom.dxt[i] /pyom.cost[j]**2

            mp = maskM[i,j] * maskM[i,j+1]
            mm = maskM[i,j] * maskM[i,j-1]
            cf[i,j, 1, 1] -= mp*pyom.hv[i,j  ]/pyom.dyu[j  ]/pyom.dyt[j] *pyom.cosu[j  ]/pyom.cost[j]
            cf[i,j, 1, 2] += mp*pyom.hv[i,j  ]/pyom.dyu[j  ]/pyom.dyt[j] *pyom.cosu[j  ]/pyom.cost[j]
            cf[i,j, 1, 1] -= mm*pyom.hv[i,j-1]/pyom.dyu[j-1]/pyom.dyt[j] *pyom.cosu[j-1]/pyom.cost[j]
            cf[i,j, 1, 0] += mm*pyom.hv[i,j-1]/pyom.dyu[j-1]/pyom.dyt[j] *pyom.cosu[j-1]/pyom.cost[j]

    if pyom.enable_free_surface:
        for j in xrange(pyom.js_pe, pyom.je_pe+1): #j=pyom.js_pe,pyom.je_pe
            for i in xrange(pyom.is_pe, pyom.ie_pe+1): #i=pyom.is_pe,pyom.ie_pe
                cf[i,j,1,1] += -1./(pyom.grav*pyom.dt_mom**2) *maskM[i,j]
    return cf

@pyom_method
def congrad_surf_press(pyom, forc, iterations):
    """
    simple conjugate gradient solver
    """
    #real*8  :: forc(is_:ie_,js_:je_)
    #logical, save :: first = .true.
    #real*8 , allocatable,save :: cf(:,:,:,:)
    #real*8  :: res(pyom.is_pe-onx:pyom.ie_pe+onx,pyom.js_pe-onx:pyom.je_pe+onx)
    #real*8  :: p(pyom.is_pe-onx:pyom.ie_pe+onx,pyom.js_pe-onx:pyom.je_pe+onx)
    #real*8  :: Ap(pyom.is_pe-onx:pyom.ie_pe+onx,pyom.js_pe-onx:pyom.je_pe+onx)
    #real*8  :: rsold,alpha,rsnew,dot_sfp,absmax_sfp
    #real*8  :: step,step1=0,convergence_rate,estimated_error,smax,rs_min=0
    res = np.zeros((pyom.nx+4, pyom.ny+4))
    p = np.zeros((pyom.nx+4, pyom.ny+4))
    Ap = np.zeros((pyom.nx+4, pyom.ny+4))

    # congrad_surf_press.first is basically like a static variable
    if congrad_surf_press.first:
        cf = make_coeff_surf_press(pyom)
        congrad_surf_press.first = False

    apply_op(cf, pyom.psi[:,:,pyom.taup1], res, pyom) #  res = A *pyom.psi
    for j in xrange(pyom.js_pe, pyom.je_pe): #j=pyom.js_pe,pyom.je_pe
        for i in xrange(pyom.is_pe, pyom.ie_pe): #i=pyom.is_pe,pyom.ie_pe
            res[i,j] = forc[i,j]-res[i,j]

    p[...] = res

    if pyom.enable_cyclic_x:
        cyclic.setcyclic_x(p)
    rsold = dot_sfp(res,res,pyom)

    for n in xrange(1, pyom.congr_max_iterations + 1): #n=1,congr_max_iterations
        """
        key algorithm
        """
        apply_op(cf, p, Ap, pyom) #  Ap = A *p
        alpha = rsold/dot_sfp(p,Ap,pyom)
        pyom.psi[:,:,pyom.taup1] += alpha*p
        res -= alpha*Ap
        rsnew = dot_sfp(res,res,pyom)
        p = res+rsnew/rsold*p
        if pyom.enable_cyclic_x:
            cyclic.setcyclic_x(p)
        rsold = rsnew
        """
        test for divergence
        """
        if n == 1:
            rs_min = abs(rsnew)
        elif n > 2:
            rs_min = min(rs_min, abs(rsnew))
            if abs(rsnew) > 100.0 * rs_min:
                warnings.warn("solver diverging after {} iterations".format(n))
                fail(n, pyom.enable_congrad_verbose, estimated_error, pyom.congr_epsilon)
        """
        test for convergence
        """
        smax = absmax_sfp(p, pyom)
        step = abs(alpha) * smax
        if n == 1:
            step1 = step
            estimated_error = step
            if step < pyom.congr_epsilon:
                info(n, pyom.enable_congrad_verbose, estimated_error, pyom.congr_epsilon)
                return
        elif step < pyom.congr_epsilon:
            convergence_rate = np.exp(np.log(step/step1)/(n-1))
            estimated_error = step*convergence_rate/(1.0-convergence_rate)
            if estimated_error < pyom.congr_epsilon:
                info(n, pyom.enable_congrad_verbose, estimated_error, pyom.congr_epsilon)
                return
        """
        check for NaN
        """
        if np.isnan(estimated_error):
            warnings.warn("estimated error is NaN at iteration step {}".format(n))
            fail(n, pyom.enable_congrad_verbose, estimated_error, pyom.congr_epsilon)

    warnings.warn("max iterations exceeded at itt={}".format(pyom.itt))
    fail(n, pyom.enable_congrad_verbose, estimated_error, pyom.congr_epsilon)

congrad_surf_press.first = True

def info(n, enable_congrad_verbose, estimated_error, congr_epsilon):
    if enable_congrad_verbose:
        print ' estimated error=',estimated_error,'/',congr_epsilon
        print ' iterations=',n

def fail(n, enable_congrad_verbose, estimated_error, congr_epsilon):
    print ' estimated error=',estimated_error,'/',congr_epsilon
    print ' iterations=',n
    # check for NaN
    if np.isnan(estimated_error):
        raise RuntimeError("error is NaN, stopping integration")
