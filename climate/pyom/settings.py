from collections import namedtuple, OrderedDict

Setting = namedtuple("setting", ("default", "description"))

SETTINGS = OrderedDict([
    # Model parameters
    ("nx", Setting(None, "Grid points in zonal (x) direction")),
    ("ny", Setting(None, "Grid points in meridional (y,j) direction")),
    ("nz", Setting(None, "Grid points in vertical (z,k) direction")),
    ("taum1", Setting(0, "pointer to last time step")),
    ("tau", Setting(1, "pointer to current time step")),
    ("taup1", Setting(2, "pointer to next time step")),
    ("dt_mom", Setting(0., "time step in seconds for momentum")),
    ("dt_tracer", Setting(0., "time step for tracer can be larger than for momentum")),
    ("dt_tke", Setting(0., "should be time step for momentum (set in tke.f90)")),
    ("itt", Setting(1, "time step number")),
    ("enditt", Setting(1, "last time step of simulation")),
    ("runlen", Setting(0., "length of simulation in seconds")),
    ("AB_eps", Setting(0.1, "deviation from Adam-Bashforth weighting")),

    # Logical switches for general model setup
    ("coord_degree", Setting(False, "either spherical (true) or cartesian False coordinates")),
    ("enable_cyclic_x", Setting(False, "enable cyclic boundary conditions")),
    ("eq_of_state_type", Setting(1, "equation of state: 1: linear, 3: nonlinear with comp., 5: TEOS")),
    ("enable_implicit_vert_friction", Setting(False, "enable implicit vertical friction")),
    ("enable_explicit_vert_friction", Setting(False, "enable explicit vertical friction")),
    ("enable_hor_friction", Setting(False, "enable horizontal friction")),
    ("enable_hor_diffusion", Setting(False, "enable horizontal diffusion")),
    ("enable_biharmonic_friction", Setting(False, "enable biharmonic horizontal friction")),
    ("enable_biharmonic_mixing", Setting(False, "enable biharmonic horizontal mixing")),
    ("enable_hor_friction_cos_scaling", Setting(False, "scaling of hor. viscosity with cos(latitude)**cosPower")),
    ("enable_ray_friction", Setting(False, "enable Rayleigh damping")),
    ("enable_bottom_friction", Setting(False, "enable bottom friction")),
    ("enable_bottom_friction_var", Setting(False, "enable bottom friction with lateral variations")),
    ("enable_quadratic_bottom_friction", Setting(False, "enable quadratic bottom friction")),
    ("enable_tempsalt_sources", Setting(False, "enable restoring zones, etc")),
    ("enable_momentum_sources", Setting(False, "enable restoring zones, etc")),
    ("enable_superbee_advection", Setting(False, "enable advection scheme with implicit mixing")),
    ("enable_conserve_energy", Setting(True, "exchange energy consistently")),
    ("enable_store_bottom_friction_tke", Setting(False, "transfer dissipated energy by bottom/rayleig fric. to TKE, else transfer to internal waves")),
    ("enable_store_cabbeling_heat", Setting(False, "transfer non-linear mixing terms to potential enthalpy, else transfer to TKE and EKE")),

    # External mode
    ("enable_free_surface", Setting(False, "implicit free surface")),
    ("enable_streamfunction", Setting(False, "solve for streamfct instead of surface pressure")),
    ("enable_congrad_verbose", Setting(False, "print some info")),
    ("congr_epsilon", Setting(1e-12, "convergence criteria for poisson solver")),
    ("congr_max_iterations", Setting(1000, "max. number of iterations")),

    # Mixing parameter
    ("A_h", Setting(0.0, "lateral viscosity in m^2/s")),
    ("K_h", Setting(0.0, "lateral diffusivity in m^2/s")),
    ("r_ray", Setting(0.0, "Rayleigh damping coefficient in 1/s")),
    ("r_bot", Setting(0.0, "bottom friction coefficient in 1/s")),
    ("r_quad_bot", Setting(0.0, "qudratic bottom friction coefficient")),
    ("hor_friction_cosPower", Setting(3, "")),
    ("A_hbi", Setting(0.0, "lateral biharmonic viscosity in m^4/s")),
    ("K_hbi", Setting(0.0, "lateral biharmonic diffusivity in m^4/s")),
    ("kappaH_0", Setting(0.0, "")),
    ("kappaM_0", Setting(0.0, "fixed values for vertical viscosity/diffusivity which are set for no TKE model")),

    # Options for isopycnal mixing
    ("enable_neutral_diffusion", Setting(False, "enable isopycnal mixing")),
    ("enable_skew_diffusion", Setting(False, "enable skew diffusion approach for eddy-driven velocities")),
    ("enable_TEM_friction", Setting(False, "TEM approach for eddy-driven velocities")),
    ("K_iso_0", Setting(0.0, "constant for isopycnal diffusivity in m^2/s")),
    ("K_iso_steep", Setting(0.0, "lateral diffusivity for steep slopes in m^2/s")),
    ("K_gm_0", Setting(0.0, "fixed value for K_gm which is set for no EKE model")),
    ("iso_dslope", Setting(0.0008, "parameters controlling max allowed isopycnal slopes")),
    ("iso_slopec", Setting(0.001, "parameters controlling max allowed isopycnal slopes")),

    # Idemix 1.0
    ("enable_idemix", Setting(False, "")),
    ("tau_v", Setting(1.0*86400.0, "time scale for vertical symmetrisation")),
    ("tau_h", Setting(15.0*86400.0, "time scale for horizontal symmetrisation")),
    ("gamma", Setting(1.57, "")),
    ("jstar", Setting(10.0, "spectral bandwidth in modes")),
    ("mu0", Setting(4.0/3.0, "dissipation parameter")),
    ("enable_idemix_hor_diffusion", Setting(False, "")),
    ("enable_eke_diss_bottom", Setting(False, "")),
    ("enable_eke_diss_surfbot", Setting(False, "")),
    ("eke_diss_surfbot_frac", Setting(1.0, "fraction which goes into bottom")),
    ("enable_idemix_superbee_advection", Setting(False, "")),
    ("enable_idemix_upwind_advection", Setting(False, "Idemix 2.0")),
    ("enable_idemix_M2", Setting(False, "")),
    ("enable_idemix_niw", Setting(False, "")),
    ("np", Setting(0, "TKE")),
    ("enable_tke", Setting(False, "")),
    ("c_k", Setting(0.1, "")),
    ("c_eps", Setting(0.7, "")),
    ("alpha_tke", Setting(1.0, "")),
    ("mxl_min", Setting(1e-12, "")),
    ("kappaM_min", Setting(0., "")),
    ("kappaM_max", Setting(100., "")),
    ("tke_mxl_choice", Setting(1, "")),
    ("enable_tke_superbee_advection", Setting(False, "")),
    ("enable_tke_upwind_advection", Setting(False, "")),
    ("enable_tke_hor_diffusion", Setting(False, "")),
    ("K_h_tke", Setting(2000., "lateral diffusivity for tke")),

    # Non-hydrostatic
    ("enable_hydrostatic", Setting(True, "enable hydrostatic approximation")),
    ("congr_itts_non_hydro", Setting(0, "number of iterations of poisson solver")),
    ("congr_epsilon_non_hydro", Setting(1e-12, "convergence criteria for poisson solver")),
    ("congr_max_itts_non_hydro", Setting(1000, "max. number of iterations")),

    # EKE default values
    ("enable_eke", Setting(False, "")),
    ("eke_lmin", Setting(100.0, "minimal length scale in m")),
    ("eke_c_k", Setting(1.0, "")),
    ("eke_cross", Setting(1.0, "Parameter for EKE model")),
    ("eke_crhin", Setting(1.0, "Parameter for EKE model")),
    ("eke_c_eps", Setting(1.0, "Parameter for EKE model")),
    ("eke_k_max", Setting(1e4, "maximum of K_gm")),
    ("alpha_eke", Setting(1.0, "factor vertical friction")),
    ("enable_eke_superbee_advection", Setting(False, "")),
    ("enable_eke_upwind_advection", Setting(False, "")),
    ("enable_eke_isopycnal_diffusion", Setting(False, "use K_gm also for isopycnal diffusivity")),

    ("enable_eke_leewave_dissipation", Setting(False, "")),
    ("c_lee0", Setting(1., "")),
    ("eke_Ri0", Setting(200., "")),
    ("eke_Ri1", Setting(50., "")),
    ("eke_int_diss0", Setting(1./(20*86400.), "")),
    ("kappa_EKE0", Setting(0.1, "")),
    ("eke_r_bot", Setting(0.0, "bottom friction coefficient")),
    ("eke_hrms_k0_min", Setting(0.0, "min value for bottom roughness parameter")),

    # New
    ("use_io_threads", Setting(True, "")),
    ("io_timeout", Setting(None, "")),
    ("enable_netcdf_zlib_compression", Setting(True, "")),
])


class Diagnostic:
    def __init__(self, description, sampling_frequency=None, output_frequency=None, outfile=None):
        self.sampling_frequency = sampling_frequency
        self.output_frequency = output_frequency
        self.description = description
        self.outfile = outfile

    def is_active(self):
        return self.sampling_frequency or self.output_frequency

DIAGNOSTICS_SETTINGS = OrderedDict([
    ("cfl_monitor", Diagnostic("CFL monitor")),
    ("tracer_monitor", Diagnostic("tracer content and variance monitor")),
    ("snapshot", Diagnostic("snapshot output", outfile="snapshot.nc")),
    ("averages", Diagnostic("time average output", outfile="averages_{itt}.nc")),
    ("energy", Diagnostic("energy diagnostics", outfile="energy.nc")),
    ("overturning", Diagnostic("isopycnal overturning diagnostic", outfile="overturning.nc")),
    ("particles", Diagnostic("particle integration", outfile="particles_{itt}.nc")),
])
