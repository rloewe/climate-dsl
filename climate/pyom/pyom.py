import numpy as np
from climate.io import wrapper
from climate import Timer
from climate.pyom import momentum, numerics, thermodynamics
from climate.pyom import isoneutral, idemix, external, diagnostics
import math
import sys

class PyOM:
    """
    Constants
    """
    pi = np.pi
    radius = 6370.0e3 # Earth radius in m
    degtom = radius / 180.0 * pi # conversion degrees latitude to meters
    mtodeg = 1 / degtom # reverse conversion
    omega = pi / 43082.0 # earth rotation frequency in 1/s
    rho_0 = 1024.0 # Boussinesq reference density in kg/m^3
    grav = 9.81 # gravitational constant in m/s^2

    def __init__(self):
        """
        Model parameters
        """
        #nx            # grid points in zonal (x,i) direction
        #ny            # grid points in meridional (y,j) direction
        #nz            # grid points in vertical (z,k) direction
        self.taum1 = 0 # pointer to last time step
        self.tau = 1 # pointer to current time step
        self.taup1 = 2 # pointer to next time step
        self.dt_mom = 0 # time step in seconds for momentum
        self.dt_tracer = 0 # time step for tracer can be larger than for momentum
        #dt_tke        # should be time step for momentum (set in tke.f90)
        #itt           # time step number
        #enditt        # last time step of simulation
        self.runlen = 0.   # length of simulation in seconds
        self.AB_eps = 0.1  # deviation from Adam-Bashforth weighting

        """
        Logical switches for general model setup
        """
        self.coord_degree = False # either spherical (true) or cartesian False coordinates
        self.enable_cyclic_x = False # enable cyclic boundary conditions
        self.eq_of_state_type = 1                      # equation of state: 1: linear, 3: nonlinear with comp., 5: TEOS
        self.enable_implicit_vert_friction = False # enable implicit vertical friction
        self.enable_explicit_vert_friction = False # enable explicit vertical friction
        self.enable_hor_friction = False # enable horizontal friction
        self.enable_hor_diffusion = False # enable horizontal diffusion
        self.enable_biharmonic_friction = False # enable biharmonic horizontal friction
        self.enable_biharmonic_mixing = False # enable biharmonic horizontal mixing
        self.enable_hor_friction_cos_scaling = False # scaling of hor. viscosity with cos(latitude)**cosPower
        self.enable_ray_friction = False # enable Rayleigh damping
        self.enable_bottom_friction = False # enable bottom friction
        self.enable_bottom_friction_var = False # enable bottom friction with lateral variations
        self.enable_quadratic_bottom_friction = False # enable quadratic bottom friction
        self.enable_tempsalt_sources = False # enable restoring zones, etc
        self.enable_momentum_sources = False # enable restoring zones, etc
        self.enable_superbee_advection = False # enable advection scheme with implicit mixing
        self.enable_conserve_energy = True  # exchange energy consistently
        self.enable_store_bottom_friction_tke = False # transfer dissipated energy by bottom/rayleig fric. to TKE
                                                       # else transfer to internal waves
        self.enable_store_cabbeling_heat = False # transfer non-linear mixing terms to potential enthalpy
                                                       # else transfer to TKE and EKE


#!---------------------------------------------------------------------------------
#!     variables related to numerical grid
#!---------------------------------------------------------------------------------
#      real*8, allocatable, dimension(:,:,:)   :: maskT     ! mask in physical space for tracer points
#      real*8, allocatable, dimension(:,:,:)   :: maskU     ! mask in physical space for U points
#      real*8, allocatable, dimension(:,:,:)   :: maskV     ! mask in physical space for V points
#      real*8, allocatable, dimension(:,:,:)   :: maskW     ! mask in physical space for W points
#      real*8, allocatable, dimension(:,:,:)   :: maskZ     ! mask in physical space for Zeta points
#      integer, allocatable, dimension(:,:)    :: kbot       ! 0 denotes land, 0<kmt<=nz denotes deepest cell zt(kmt)
#      real*8, allocatable, dimension(:)       :: xt,dxt     ! zonal (x) coordinate of T-grid point in meters
#      real*8, allocatable, dimension(:)       :: xu,dxu     ! zonal (x) coordinate of U-grid point in meters
#      real*8, allocatable, dimension(:)       :: yt,dyt     ! meridional (y) coordinate of T-grid point in meters
#      real*8, allocatable, dimension(:)       :: yu,dyu     ! meridional (y) coordinate of V-grid point in meters
#      real*8                                  :: x_origin,y_origin ! origin of grid in x and y direction, located at xu_1, yu_1
#      real*8, allocatable, dimension(:)       :: zt,zw      ! vertical coordinate in m
#      real*8, allocatable, dimension(:)       :: dzt,dzw    ! box thickness in m
#      real*8, allocatable, dimension(:,:)     :: area_t     ! Area of T-box in m^2
#      real*8, allocatable, dimension(:,:)     :: area_u     ! Area of U-box in m^2
#      real*8, allocatable, dimension(:,:)     :: area_v     ! Area of V-box in m^2
#      real*8, allocatable, dimension(:,:)     :: coriolis_t ! coriolis frequency at T grid point in 1/s
#      real*8, allocatable, dimension(:,:)     :: coriolis_h ! horizontal coriolis frequency at T grid point in 1/s
#      real*8, allocatable, dimension(:)       :: cost       ! metric factor for spherical coordinates on T grid
#      real*8, allocatable, dimension(:)       :: cosu       ! metric factor for spherical coordinates on U grid
#      real*8, allocatable, dimension(:)       :: tantr      ! metric factor for spherical coordinates
#      real*8, allocatable, dimension(:,:)     :: ht         ! total depth in m
#      real*8, allocatable, dimension(:,:)     :: hu,hur     ! total depth in m at u-grid
#      real*8, allocatable, dimension(:,:)     :: hv,hvr     ! total depth in m at v-grid
#      real*8, allocatable, dimension(:,:)     :: beta       ! df/dy in 1/ms
#!---------------------------------------------------------------------------------
#!     variables related to thermodynamics
#!---------------------------------------------------------------------------------
#      real*8, allocatable, dimension(:,:,:,:) :: temp,dtemp            ! conservative temperature in deg C and its tendency
#      real*8, allocatable, dimension(:,:,:,:) :: salt,dsalt            ! salinity in g/Kg and its tendency
#      real*8, allocatable, dimension(:,:,:,:) :: rho                   ! density in kg/m^3
#      real*8, allocatable, dimension(:,:,:,:) :: Hd                    ! dynamic enthalpy
#      real*8, allocatable, dimension(:,:,:,:) :: int_drhodT,int_drhodS ! partial derivatives of dyn. enthalpy
#      real*8, allocatable, dimension(:,:,:,:) :: Nsqr                  ! Square of stability frequency in 1/s^2
#      real*8, allocatable, dimension(:,:,:,:) :: dHd                   ! change of dynamic enthalpy due to advection
#      real*8, allocatable, dimension(:,:,:)   :: dtemp_vmix            ! change temperature due to vertical mixing
#      real*8, allocatable, dimension(:,:,:)   :: dtemp_hmix            ! change temperature due to lateral mixing
#      real*8, allocatable, dimension(:,:,:)   :: dtemp_iso             ! change temperature due to isopynal mixing plus skew mixing
#      real*8, allocatable, dimension(:,:,:)   :: dsalt_vmix            ! change salinity due to vertical mixing
#      real*8, allocatable, dimension(:,:,:)   :: dsalt_hmix            ! change salinity due to lateral mixing
#      real*8, allocatable, dimension(:,:,:)   :: dsalt_iso             ! change salinity due to isopynal mixing plus skew mixing
#      real*8, allocatable, dimension(:,:,:)   :: temp_source           ! non conservative source of temperature in K/s
#      real*8, allocatable, dimension(:,:,:)   :: salt_source           ! non conservative source of salinity in g/(kgs)
#!---------------------------------------------------------------------------------
#!     variables related to dynamics
#!---------------------------------------------------------------------------------
#      real*8, allocatable, dimension(:,:,:,:) :: u,du              ! zonal velocity and its tendency
#      real*8, allocatable, dimension(:,:,:,:) :: v,dv              ! meridional velocity and its tendency
#      real*8, allocatable, dimension(:,:,:,:) :: w                 ! vertical velocity
#      real*8, allocatable, dimension(:,:,:)   :: du_cor            ! change of u due to Coriolis force
#      real*8, allocatable, dimension(:,:,:)   :: dv_cor            ! change of v due to Coriolis force
#      real*8, allocatable, dimension(:,:,:)   :: du_mix            ! change of v due to implicit vert. mixing
#      real*8, allocatable, dimension(:,:,:)   :: dv_mix            ! change of v due to implicit vert. mixing
#      real*8, allocatable, dimension(:,:,:)   :: du_adv            ! change of v due to advection
#      real*8, allocatable, dimension(:,:,:)   :: dv_adv            ! change of v due to advection
#      real*8, allocatable, dimension(:,:,:)   :: u_source          ! non conservative source of zonal velocity
#      real*8, allocatable, dimension(:,:,:)   :: v_source          ! non conservative source of meridional velocity
#      real*8, allocatable, dimension(:,:,:)   :: p_hydro           ! hydrostatic pressure
#      real*8, allocatable, dimension(:,:,:)   :: psi               ! surface pressure or streamfunction
#      real*8, allocatable, dimension(:,:,:)   :: dpsi              ! change of streamfunction
#      real*8, allocatable, dimension(:,:,:)   :: psin              ! boundary contributions
#      real*8, allocatable, dimension(:,:)     :: dpsin             ! boundary contributions
#      real*8, allocatable, dimension(:,:)     :: line_psin         ! boundary contributions
#      real*8, allocatable, dimension(:,:)     :: surface_taux      ! zonal wind stress
#      real*8, allocatable, dimension(:,:)     :: surface_tauy      ! meridional wind stress
#      real*8, allocatable, dimension(:,:)     :: forc_rho_surface  ! surface pot. density flux
#      real*8, allocatable, dimension(:,:)     :: forc_temp_surface ! surface temperature flux
#      real*8, allocatable, dimension(:,:)     :: forc_salt_surface ! surface salinity flux
#      real*8, allocatable, dimension(:,:,:)   :: u_wgrid,v_wgrid,w_wgrid       ! velocity on W grid
#      real*8, allocatable, dimension(:,:,:)   :: flux_east,flux_north,flux_top ! multi purpose fluxes
#!---------------------------------------------------------------------------------
#!     variables related to dissipation
#!---------------------------------------------------------------------------------
#      real*8, allocatable, dimension(:,:,:)    :: K_diss_v          ! kinetic energy dissipation by vertical, rayleigh and bottom friction
#      real*8, allocatable, dimension(:,:,:)    :: K_diss_h          ! kinetic energy dissipation by horizontal friction
#      real*8, allocatable, dimension(:,:,:)    :: K_diss_gm         ! mean energy dissipation by GM (TRM formalism only)
#      real*8, allocatable, dimension(:,:,:)    :: K_diss_bot        ! mean energy dissipation by bottom and rayleigh friction
#      real*8, allocatable, dimension(:,:,:)    :: P_diss_v          ! potential energy dissipation by vertical diffusion
#      real*8, allocatable, dimension(:,:,:)    :: P_diss_nonlin     ! potential energy dissipation by nonlinear equation of state
#      real*8, allocatable, dimension(:,:,:)    :: P_diss_adv        ! potential energy dissipation by
#      real*8, allocatable, dimension(:,:,:)    :: P_diss_comp       ! potential energy dissipation by compress.
#      real*8, allocatable, dimension(:,:,:)    :: P_diss_hmix       ! potential energy dissipation by horizontal mixing
#      real*8, allocatable, dimension(:,:,:)    :: P_diss_iso        ! potential energy dissipation by isopycnal mixing
#      real*8, allocatable, dimension(:,:,:)    :: P_diss_skew       ! potential energy dissipation by GM (w/o TRM)
#      real*8, allocatable, dimension(:,:,:)    :: P_diss_sources    ! potential energy dissipation by restoring zones, etc

        """
        External mode stuff
        """
        self.enable_free_surface = False   # implicit free surface
        self.enable_streamfunction = False   # solve for streamfct instead of surface pressure
        self.enable_congrad_verbose = False # print some info
        self.congr_itts = 0                 # number of iterations of poisson solver NOTE: only has value 0 to init variable
        self.congr_epsilon = 1e-12            # convergence criteria for poisson solver
        self.congr_max_iterations = 1000    # max. number of iterations

        """
        Mixing parameter
        """
        A_h = 0.0    # lateral viscosity in m^2/s
        K_h = 0.0    # lateral diffusivity in m^2/s
        r_ray = 0.0  # Rayleigh damping coefficient in 1/s
        r_bot = 0.0  # bottom friction coefficient in 1/s
        r_quad_bot = 0.0  # qudratic bottom friction coefficient
        #real*8, allocatable :: r_bot_var_u(:,:)     # bottom friction coefficient in 1/s, on u points
        #real*8, allocatable :: r_bot_var_v(:,:)     # bottom friction coefficient in 1/s, on v points
        self.hor_friction_cosPower = 3
        self.A_hbi = 0.0  # lateral bihamronic viscosity in m^4/s
        self.K_hbi = 0.0  # lateral bihamronic diffusivity in m^4/s
        self.kappaH_0 = 0.0
        self.kappaM_0 = 0.0   # fixed values for vertical viscosity/diffusivity which are set for no TKE model
        #real*8, allocatable :: kappaM(:,:,:)       # vertical viscosity in m^2/s
        #real*8, allocatable :: kappaH(:,:,:)       # vertical diffusivity in m^2/s

        """
        Options for isopycnal mixing
        """
        self.enable_neutral_diffusion = False # enable isopycnal mixing
        self.enable_skew_diffusion = False # enable skew diffusion approach for eddy-driven velocities
        self.enable_TEM_friction = False # TEM approach for eddy-driven velocities
        self.K_iso_0 = 0.0 # constant for isopycnal diffusivity in m^2/s
        self.K_iso_steep = 0.0 # lateral diffusivity for steep slopes in m^2/s
        self.K_gm_0 = 0.0 # fixed value for K_gm which is set for no EKE model
        self.iso_dslope = 0.0008 # parameters controlling max allowed isopycnal slopes
        self.iso_slopec = 0.001 # parameters controlling max allowed isopycnal slopes

        """
        Idemix 1.0
        """
        self.enable_idemix = False
        # real*8, allocatable :: dE_iw(:,:,:,:) ! tendency due to advection using Adam Bashforth
        # real*8, allocatable :: E_iw(:,:,:,:),c0(:,:,:),v0(:,:,:),alpha_c(:,:,:)
        # real*8, allocatable :: forc_iw_bottom(:,:),forc_iw_surface(:,:),iw_diss(:,:,:)
        self.tau_v = 1.0*86400.0 # time scale for vertical symmetrisation
        self.tau_h = 15.0*86400.0 # time scale for horizontal symmetrisation
        self.gamma = 1.57 #
        self.jstar = 10.0 # spectral bandwidth in modes
        self.mu0 = 4.0/3.0 # dissipation parameter
        self.enable_idemix_hor_diffusion = False
        self.enable_eke_diss_bottom = False
        self.enable_eke_diss_surfbot = False
        self.eke_diss_surfbot_frac = 1.0 # fraction which goes into bottom
        self.enable_idemix_superbee_advection = False
        self.enable_idemix_upwind_advection = False

        """
        Idemix 2.0
        """
        self.enable_idemix_M2 = False
        self.enable_idemix_niw = False
        self.np = 0

        """
        TKE
        """
        self.c_k = 0.1
        self.c_eps = 0.7
        self.alpha_tke = 1.0
        self.mxl_min = 1e-12
        self.kappaM_min = 0.
        self.kappaM_max = 100.
        self.tke_mxl_choice = 1
        self.enable_tke_superbee_advection = False
        self.enable_tke_upwind_advection = False
        self.enable_tke_hor_diffusion = False
        self.K_h_tke = 2000. # lateral diffusivity for tke

        """
        Non-hydrostatic stuff
        """
        self.enable_hydrostatic = True         # enable hydrostatic approximation
        #real*8,allocatable ::  p_non_hydro(:,:,:,:)    # non-hydrostatic pressure
        #real*8,allocatable ::  dw(:,:,:,:)             # non-hydrostatic stuff
        #real*8,allocatable ::  dw_cor(:,:,:)
        #real*8,allocatable ::  dw_adv(:,:,:)
        #real*8,allocatable ::  dw_mix(:,:,:)
        #congr_itts_non_hydro                # number of iterations of poisson solver
        self.congr_epsilon_non_hydro = 1e-12       # convergence criteria for poisson solver
        self.congr_max_itts_non_hydro = 1000     # max. number of iterations

        """
        diagnostic options
        """
        self.enable_diag_ts_monitor = False
        self.enable_diag_ts_monitor = False # enable time step monitor
        self.enable_diag_energy = False # enable diagnostics for energy
        self.enable_diag_averages = False # enable time averages
        self.enable_diag_snapshots = False # enable snapshots
        self.enable_diag_overturning = False # enable isopycnal overturning diagnostic
        self.enable_diag_tracer_content = False # enable tracer content and variance monitor
        self.enable_diag_particles = False # enable integration of particles
        self.snap_file = 'pyOM.cdf'
        self.diag_energy_file = 'energy.cdf'
        self.snapint = 0. # intervall between snapshots to be written in seconds
        self.aveint = 0. # intervall between time averages to be written in seconds
        self.energint = 0. # intervall between energy diag to be written in seconds
        self.energfreq = 0. # diagnosing every energfreq seconds
        self.ts_monint = 0. # intervall between time step monitor in seconds
        self.avefreq = 0. # averaging every ave_freq seconds
        self.overint = 0. # intervall between overturning averages to be written in seconds
        self.overfreq = 0. # averaging overturning every ave_freq seconds
        self.trac_cont_int = 0. # intervall between tracer content monitor in seconds
        self.particles_int = 0. # intervall

        """
        Compatibility with legacy interface
        """
        self.fortran = self
        self.main_module = self
        self.isoneutral_module = self
        self.idemix_module = self
        self.tke_module = self
        self.eke_module = self


    def allocate(self):
        #ie_pe = nx
        #je_pe = ny
        self.xt = np.zeros(self.nx+4)
        self.xu = np.zeros(self.nx+4)
        self.yt = np.zeros(self.ny+4)
        self.yu = np.zeros(self.ny+4)
        self.dxt = np.zeros(self.nx+4)
        self.dxu = np.zeros(self.nx+4)
        self.dyt = np.zeros(self.ny+4)
        self.dyu = np.zeros(self.ny+4)

        self.zt = np.zeros(self.nz)
        self.dzt = np.zeros(self.nz)
        self.zw = np.zeros(self.nz)
        self.dzw = np.zeros(self.nz)

        self.cost = np.ones(self.ny+4)
        self.cosu = np.ones(self.ny+4)
        self.tantr = np.zeros(self.ny+4)
        self.coriolis_t = np.zeros((self.nx+4, self.ny+4))
        self.coriolis_h = np.zeros((self.nx+4, self.ny+4))

        self.kbot = np.zeros((self.nx+4, self.ny+4))
        self.ht = np.zeros((self.nx+4, self.ny+4))
        self.hu = np.zeros((self.nx+4, self.ny+4))
        self.hv = np.zeros((self.nx+4, self.ny+4))
        self.hur = np.zeros((self.nx+4, self.ny+4))
        self.hvr = np.zeros((self.nx+4, self.ny+4))
        self.beta = np.zeros((self.nx+4, self.ny+4))
        self.area_t = np.zeros((self.nx+4, self.ny+4))
        self.area_u = np.zeros((self.nx+4, self.ny+4))
        self.area_v = np.zeros((self.nx+4, self.ny+4))

        self.maskT = np.zeros((self.nx+4, self.ny+4, self.nz))
        self.maskU = np.zeros((self.nx+4, self.ny+4, self.nz))
        self.maskV = np.zeros((self.nx+4, self.ny+4, self.nz))
        self.maskW = np.zeros((self.nx+4, self.ny+4, self.nz))
        self.maskZ = np.zeros((self.nx+4, self.ny+4, self.nz))

        self.rho = np.zeros((self.nx+4, self.ny+4, self.nz, 3))
        self.Nsqr = np.zeros((self.nx+4, self.ny+4, self.nz, 3))
        self.Hd = np.zeros((self.nx+4, self.ny+4, self.nz, 3))
        self.dHd = np.zeros((self.nx+4, self.ny+4, self.nz, 3))

        self.drhodT = np.zeros((self.nx+4, self.ny+4, self.nz, 3))
        self.drhodS = np.zeros((self.nx+4, self.ny+4, self.nz, 3))

        self.temp = np.zeros((self.nx+4, self.ny+4, self.nz, 3))
        self.dtemp = np.zeros((self.nx+4, self.ny+4, self.nz, 3))
        self.salt = np.zeros((self.nx+4, self.ny+4, self.nz, 3))
        self.dsalt = np.zeros((self.nx+4, self.ny+4, self.nz, 3))
        self.dtemp_vmix = np.zeros((self.nx+4, self.ny+4, self.nz))
        self.dtemp_hmix = np.zeros((self.nx+4, self.ny+4, self.nz))
        self.dsalt_vmix = np.zeros((self.nx+4, self.ny+4, self.nz))
        self.dsalt_hmix = np.zeros((self.nx+4, self.ny+4, self.nz))
        self.dtemp_iso = np.zeros((self.nx+4, self.ny+4, self.nz))
        self.dsalt_iso = np.zeros((self.nx+4, self.ny+4, self.nz))
        self.forc_temp_surface = np.zeros((self.nx+4, self.ny+4))
        self.forc_salt_surface = np.zeros((self.nx+4, self.ny+4))

        if self.enable_tempsalt_sources:
            self.temp_source = np.zeros((self.nx+4, self.ny+4, self.nz))
            self.salt_source = np.zeros((self.nx+4, self.ny+4, self.nz))
        if self.enable_momentum_sources:
            self.u_source = np.zeros((self.nx+4, self.ny+4, self.nz))
            self.v_source = np.zeros((self.nx+4, self.ny+4, self.nz))

        self.flux_east = np.zeros((self.nx+4, self.ny+4, self.nz))
        self.flux_north = np.zeros((self.nx+4, self.ny+4, self.nz))
        self.flux_top = np.zeros((self.nx+4, self.ny+4, self.nz))

        self.u = np.zeros((self.nx+4, self.ny+4, self.nz, 3))
        self.v = np.zeros((self.nx+4, self.ny+4, self.nz, 3))
        self.w = np.zeros((self.nx+4, self.ny+4, self.nz, 3))
        self.du = np.zeros((self.nx+4, self.ny+4, self.nz, 3))
        self.dv = np.zeros((self.nx+4, self.ny+4, self.nz, 3))
        self.du_cor = np.zeros((self.nx+4, self.ny+4, self.nz))
        self.dv_cor = np.zeros((self.nx+4, self.ny+4, self.nz))
        self.du_mix = np.zeros((self.nx+4, self.ny+4, self.nz))
        self.dv_mix = np.zeros((self.nx+4, self.ny+4, self.nz))
        self.du_adv = np.zeros((self.nx+4, self.ny+4, self.nz))
        self.dv_adv = np.zeros((self.nx+4, self.ny+4, self.nz))
        self.p_hydro = np.zeros((self.nx+4, self.ny+4, self.nz))
        self.psi = np.zeros((self.nx+4, self.ny+4, 3))
        self.dpsi = np.zeros((self.nx+4, self.ny+4, 3))

        self.kappaM = np.zeros((self.nx+4, self.ny+4, self.nz))
        self.kappaH = np.zeros((self.nx+4, self.ny+4, self.nz))

        self.surface_taux = np.zeros((self.nx+4, self.ny+4))
        self.surface_tauy = np.zeros((self.nx+4, self.ny+4))
        self.forc_rho_surface = np.zeros((self.nx+4, self.ny+4))

        self.K_diss_v = np.zeros((self.nx+4, self.ny+4, self.nz))
        self.K_diss_h = np.zeros((self.nx+4, self.ny+4, self.nz))
        self.K_diss_gm = np.zeros((self.nx+4, self.ny+4, self.nz))
        self.K_diss_bot = np.zeros((self.nx+4, self.ny+4, self.nz))
        self.P_diss_v = np.zeros((self.nx+4, self.ny+4, self.nz))
        self.P_diss_nonlin = np.zeros((self.nx+4, self.ny+4, self.nz))
        self.P_diss_adv = np.zeros((self.nx+4, self.ny+4, self.nz))
        self.P_diss_comp = np.zeros((self.nx+4, self.ny+4, self.nz))
        self.P_diss_hmix = np.zeros((self.nx+4, self.ny+4, self.nz))
        self.P_diss_iso = np.zeros((self.nx+4, self.ny+4, self.nz))
        self.P_diss_skew = np.zeros((self.nx+4, self.ny+4, self.nz))
        self.P_diss_sources = np.zeros((self.nx+4, self.ny+4, self.nz))

        self.r_bot_var_u = np.zeros((self.nx+4, self.ny+4, self.nz))
        self.r_bot_var_v = np.zeros((self.nx+4, self.ny+4, self.nz))

        if self.enable_neutral_diffusion:
            # isopycnal mixing tensor components
            self.K_11 = np.zeros((self.nx+4, self.ny+4, self.nz))
            self.K_13 = np.zeros((self.nx+4, self.ny+4, self.nz))
            self.K_22 = np.zeros((self.nx+4, self.ny+4, self.nz))
            self.K_23 = np.zeros((self.nx+4, self.ny+4, self.nz))
            self.K_31 = np.zeros((self.nx+4, self.ny+4, self.nz))
            self.K_32 = np.zeros((self.nx+4, self.ny+4, self.nz))
            self.K_33 = np.zeros((self.nx+4, self.ny+4, self.nz))
            #
            self.Ai_ez = np.zeros((self.nx+4, self.ny+4, self.nz, 2, 2))
            self.Ai_nz = np.zeros((self.nx+4, self.ny+4, self.nz, 2, 2))
            self.Ai_bx = np.zeros((self.nx+4, self.ny+4, self.nz, 2, 2))
            self.Ai_by = np.zeros((self.nx+4, self.ny+4, self.nz, 2, 2))

        self.B1_gm = np.zeros((self.nx+4,self.ny+4,self.nz)) # zonal streamfunction (for diagnostic purpose only)
        self.B2_gm = np.zeros((self.nx+4,self.ny+4,self.nz)) # meridional streamfunction (for diagnostic purpose only)
        self.kappa_gm = np.zeros((self.nx+4,self.ny+4,self.nz)) # vertical viscosity due to skew diffusivity K_gm in m^2/s
        self.K_gm = np.zeros((self.nx+4,self.ny+4,self.nz)) # GM diffusivity in m^2/s, either constant or from EKE model
        self.K_iso = np.zeros((self.nx+4,self.ny+4,self.nz)) # along isopycnal diffusivity in m^2/s

        if self.enable_idemix:
            self.dE_iw = np.zeros((self.nx+4,self.ny+4,self.nz,3))
            self.E_iw = np.zeros((self.nx+4,self.ny+4,self.nz,3))
            self.c0 = np.zeros((self.nx+4,self.ny+4,self.nz))
            self.v0 = np.zeros((self.nx+4,self.ny+4,self.nz))
            self.alpha_c = np.zeros((self.nx+4,self.ny+4,self.nz))
            self.iw_diss = np.zeros((self.nx+4,self.ny+4,self.nz))
            self.forc_iw_surface = np.zeros((self.nx+4,self.ny+4))
            self.forc_iw_bottom = np.zeros((self.nx+4,self.ny+4))

        if self.enable_idemix_M2 or self.enable_idemix_niw:
            self.topo_shelf = np.zeros((self.nx+4,self.ny+4))
            self.topo_hrms = np.zeros((self.nx+4,self.ny+4))
            self.topo_lam = np.zeros((self.nx+4,self.ny+4))
            self.phit = np.zeros(self.np)
            self.dphit = np.zeros(self.np)
            self.phiu = np.zeros(self.np)
            self.dphiu = np.zeros(self.np)
            self.maskTp = np.zeros((self.nx+4,self.ny+4,self.np))
            self.maskUp = np.zeros((self.nx+4,self.ny+4,self.np))
            self.maskVp = np.zeros((self.nx+4,self.ny+4,self.np))
            self.maskWp = np.zeros((self.nx+4,self.ny+4,self.np))
            self.cn = np.zeros((self.nx+4,self.ny+4))
            self.phin = np.zeros((self.nx+4,self.ny+4,self.nz))
            self.phinz = np.zeros((self.nx+4,self.ny+4,self.nz))
            self.tau_M2 = np.zeros((self.nx+4,self.ny+4))
            self.tau_niw = np.zeros((self.nx+4,self.ny+4))
            self.alpha_M2_cont = np.zeros((self.nx+4,self.ny+4))
            self.bc_south = np.zeros((self.nx+4,self.ny+4,self.np))
            self.bc_north = np.zeros((self.nx+4,self.ny+4,self.np))
            self.bc_west = np.zeros((self.nx+4,self.ny+4,self.np))
            self.bc_east = np.zeros((self.nx+4,self.ny+4,self.np))
            self.M2_psi_diss = np.zeros((self.nx+4,self.ny+4,self.np))

        if self.enable_idemix_M2:
            self.E_M2 = np.zeros((self.nx+4,self.ny+4,self.np,3))
            self.dE_M2p = np.zeros((self.nx+4,self.ny+4,self.np,3))
            self.cg_M2 = np.zeros((self.nx+4,self.ny+4))
            self.kdot_x_M2 = np.zeros((self.nx+4,self.ny+4))
            self.kdot_y_M2 = np.zeros((self.nx+4,self.ny+4))
            self.forc_M2 = np.zeros((self.nx+4,self.ny+4,self.np))
            self.u_M2 = np.zeros((self.nx+4,self.ny+4,self.np))
            self.v_M2 = np.zeros((self.nx+4,self.ny+4,self.np))
            self.w_M2 = np.zeros((self.nx+4,self.ny+4,self.np))
            self.E_struct_M2 = np.zeros((self.nx+4,self.ny+4,self.nz))
            self.E_M2_int = np.zeros((self.nx+4,self.ny+4))

        if self.enable_idemix_niw:
            self.omega_niw = np.zeros((self.nx+4,self.ny+4))
            self.E_niw = np.zeros((self.nx+4,self.ny+4,self.np,3))
            self.dE_niwp = np.zeros((self.nx+4,self.ny+4,self.np,3))
            self.cg_niw = np.zeros((self.nx+4,self.ny+4))
            self.kdot_x_niw = np.zeros((self.nx+4,self.ny+4))
            self.kdot_y_niw = np.zeros((self.nx+4,self.ny+4))
            self.forc_niw = np.zeros((self.nx+4,self.ny+4,self.np))
            self.u_niw = np.zeros((self.nx+4,self.ny+4,self.np))
            self.v_niw = np.zeros((self.nx+4,self.ny+4,self.np))
            self.w_niw = np.zeros((self.nx+4,self.ny+4,self.np))
            self.E_struct_niw = np.zeros((self.nx+4,self.ny+4,self.nz))
            self.E_niw_int = np.zeros((self.nx+4,self.ny+4))

        if self.enable_tke:
            self.dtke = np.zeros((self.nx+4, self.ny+4, self.nz, 3))
            self.tke = np.zeros((self.nx+4, self.ny+4, self.nz, 3))
            self.mxl = np.zeros((self.nx+4, self.ny+4, self.nz))
            self.sqrttke = np.zeros((self.nx+4, self.ny+4, self.nz))
            self.Prandtlnumber = np.zeros((self.nx+4, self.ny+4))
            self.forc_tke_surface = np.zeros((self.nx+4, self.ny+4))
            self.tke_diss = np.zeros((self.nx+4, self.ny+4))
            self.tke_surf_corr = np.zeros((self.nx+4, self.ny+4))

        if not self.enable_hydrostatic:
            self.p_non_hydro = np.zeros((self.nx+4, self.ny+4, self.nz, 3))
            self.dw = np.zeros((self.nx+4, self.ny+4, self.nz, 3))
            self.dw_cor = np.zeros((self.nx+4, self.ny+4, self.nz))
            self.dw_adv = np.zeros((self.nx+4, self.ny+4, self.nz))
            self.dw_mix = np.zeros((self.nx+4, self.ny+4, self.nz))

        self.u_wgrid = np.zeros((self.nx+4, self.ny+4, self.nz))
        self.v_wgrid = np.zeros((self.nx+4, self.ny+4, self.nz))
        self.w_wgrid = np.zeros((self.nx+4, self.ny+4, self.nz))

        """
        Compatibility with legacy interface
        """
        self.onx = 2
        self.is_pe = 1
        self.ie_pe = self.nx
        self.js_pe = 1
        self.je_pe = self.ny
        self.if2py = lambda i: i+self.onx-self.is_pe
        self.jf2py = lambda j: j+self.onx-self.js_pe
        self.ip2fy = lambda i: i+self.is_pe-self.onx
        self.jp2fy = lambda j: j+self.js_pe-self.onx

        self.maskt = self.maskT.view()
        self.masku = self.maskU.view()
        self.maskv = self.maskV.view()
        self.maskw = self.maskW.view()


    def run(self, snapint, runlen):
        setupTimer = Timer("Setup")
        with setupTimer:
            """
            Initialize model
            """
            itt = 0
            self.setup()
            """
            read restart if present
            """
            print 'Reading restarts:'
            read_restart(itt)
            if enable_diag_averages:
                raise NotImplementedError()
                diag_averages_read_restart()
            if enable_diag_energy:
                raise NotImplementedError()
                diag_energy_read_restart()
            if enable_diag_overturning:
                raise NotImplementedError()
                diag_over_read_restart()
            if enable_diag_particles:
                raise NotImplementedError()
                particles_read_restart()

            enditt = itt + int(runlen/dt_tracer)
            print 'Starting integration for ',runlen,' s'
            print ' from time step ',itt,' to ',enditt

        mainTimer = Timer("Main")
        momTimer = Timer("mom")
        tempTimer = Timer("temp")
        ekeTimer = Timer("eke")
        idemixTimer = Timer("idemix")
        tkeTimer = Timer("tke")
        diagTimer = Timer("diag")
        pressTimer = Timer("press")
        fricTimer = Timer("fric")
        isoTimer = Timer("iso")
        vmixTimer = Timer("vmix")
        eqOfStateTimer = Timer("eq_of_state")
        while itt < endtt:
            with mainTimer:
                set_forcing()
                if enable_idemix:
                    raise NotImplementedError()
                    set_idemix_parameter()
                if enable_idemix_M2 or enable_idemix_niw:
                    raise NotImplementedError()
                    set_spectral_parameter()

                with momTimer:
                    momentum.momentum(self, fricTimer, pressTimer)

                with tempTimer:
                    thermodynamics.thermodynamics(self)

                if enable_eke or enable_tke or enable_idemix:
                    raise NotImplementedError()
                    calculate_velocity_on_wgrid()

                with ekeTimer:
                    if enable_eke:
                        raise NotImplementedError()
                        integrate_eke()

                with idemixTimer:
                    if enable_idemix_M2:
                        raise NotImplementedError()
                        integrate_idemix_M2()
                    if enable_idemix_niw:
                        raise NotImplementedError()
                        integrate_idemix_niw()
                    if enable_idemix:
                        raise NotImplementedError()
                        integrate_idemix()
                    if enable_idemix_M2 or enable_idemix_niw:
                        raise NotImplementedError()
                        wave_interaction()

                with tkeTimer:
                    if enable_tke:
                        raise NotImplementedError()
                        integrate_tke()

                """
                 Main boundary exchange
                 for density, temp and salt this is done in integrate_tempsalt.f90
                """
                #border_exchg_xyz(is_pe-onx,ie_pe+onx,js_pe-onx,je_pe+onx,nz,u[:,:,:,taup1])
                setcyclic_xyz(is_pe-onx,ie_pe+onx,js_pe-onx,je_pe+onx,nz,u[:,:,:,taup1])
                #border_exchg_xyz(is_pe-onx,ie_pe+onx,js_pe-onx,je_pe+onx,nz,v[:,:,:,taup1])
                setcyclic_xyz(is_pe-onx,ie_pe+onx,js_pe-onx,je_pe+onx,nz,v[:,:,:,taup1])

                if enable_tke:
                #    border_exchg_xyz(is_pe-onx,ie_pe+onx,js_pe-onx,je_pe+onx,nz,tke[:,:,:,taup1])
                    setcyclic_xyz(is_pe-onx,ie_pe+onx,js_pe-onx,je_pe+onx,nz,tke[:,:,:,taup1])
                if enable_eke:
                #    border_exchg_xyz(is_pe-onx,ie_pe+onx,js_pe-onx,je_pe+onx,nz,eke[:,:,:,taup1])
                    setcyclic_xyz(is_pe-onx,ie_pe+onx,js_pe-onx,je_pe+onx,nz,eke[:,:,:,taup1])
                if enable_idemix:
                #    border_exchg_xyz(is_pe-onx,ie_pe+onx,js_pe-onx,je_pe+onx,nz,E_iw[:,:,:,taup1])
                    setcyclic_xyz(is_pe-onx,ie_pe+onx,js_pe-onx,je_pe+onx,nz,E_iw[:,:,:,taup1])
                if enable_idemix_M2:
                #    border_exchg_xyp(is_pe-onx,ie_pe+onx,js_pe-onx,je_pe+onx,np,E_M2[:,:,:,taup1])
                    setcyclic_xyp(is_pe-onx,ie_pe+onx,js_pe-onx,je_pe+onx,np,E_M2[:,:,:,taup1])
                if enable_idemix_niw:
                #    border_exchg_xyp(is_pe-onx,ie_pe+onx,js_pe-onx,je_pe+onx,np,E_niw[:,:,:,taup1])
                    setcyclic_xyp(is_pe-onx,ie_pe+onx,js_pe-onx,je_pe+onx,np,E_niw[:,:,:,taup1])

                # diagnose vertical velocity at taup1
                if enable_hydrostatic:
                    raise NotImplementedError()
                    vertical_velocity()

            with diagTimer:
                raise NotImplementedError()
                diagnose()

            # shift time
            self.otaum1 = taum1
            self.taum1 = tau
            self.tau = taup1
            self.taup1 = otaum1
            itt = itt+1

        print 'Timing summary:'
        print ' setup time summary       = ',setupTimer.getTime(),' s'
        print ' main loop time summary   = ',mainTimer.getTime() ,' s'
        print '     momentum             = ',momTimer.getTime() ,' s'
        print '       pressure           = ',pressTimer.getTime() ,' s'
        print '       friction           = ',fricTimer.getTime() ,' s'
        print '     thermodynamics       = ',tempTimer.getTime() ,' s'
        print '       lateral mixing     = ',isoTimer.getTime() ,' s'
        print '       vertical mixing    = ',vmixTimer.getTime() ,' s'
        print '       equation of state  = ',eqOfStateTimer.getTime() ,' s'
        print '     EKE                  = ',ekeTimer.getTime() ,' s'
        print '     IDEMIX               = ',idemixTimer.getTime() ,' s'
        print '     TKE                  = ',tkeTimer.getTime() ,' s'
        print ' diagnostics              = ',diagTimer.getTime() ,' s'

    def setup(self):
        print 'setting up everything'

        """
        allocate everything
        """
        self.set_parameter()
        self.allocate()

        """
        Grid
        """
        self.set_grid()
        numerics.calc_grid(self)

        """
        Coriolis
        """
        self.set_coriolis()
        numerics.calc_beta(self)

        """
        topography
        """
        self.set_topography()
        numerics.calc_topo(self)
        idemix.calc_spectral_topo(self)

        """
        initial condition and forcing
        """
        self.set_initial_conditions()
        self.set_forcing()
        if self.enable_streamfunction:
            external.streamfunction_init(self)

        """
        initialize diagnostics
        """
        diagnostics.init_diagnostics(self)
        #self.set_diagnostics()

        """
        initialize EKE module
        """
        # eke.init_eke()

        """
        initialize isoneutral module
        """
        isoneutral.check_isoneutral_slope_crit(self)

        """
        check setup
        """
        if self.enable_tke and not self.enable_implicit_vert_friction:
            raise RuntimeError("ERROR: use TKE model only with implicit vertical friction\n"
                               "\t-> switch on enable_implicit_vert_fricton in setup")
