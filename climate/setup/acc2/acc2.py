from climate.pyom import PyOMLegacy, pyom_method

yt_start = -39.0
yt_end = 43
yu_start = -40.0
yu_end = 42

class ACC2(PyOMLegacy):
   """
   A simple global model with a Southern Ocean and Atlantic part
   """
   @pyom_method
   def set_parameter(self):
     m=self.main_module

     (m.nx,m.ny,m.nz) = (30,42,15)
     m.dt_mom = 4800
     m.dt_tracer = 86400/2.0

     m.coord_degree = 1
     m.enable_cyclic_x = 1

     m.congr_epsilon = 1e-12
     m.congr_max_iterations = 5000
     m.enable_streamfunction = 1

     m.enable_diag_snapshots = True
     m.enable_diag_averages = True
     m.aveint = 10 * 86400
     m.avefreq = 10 * 86400 / 24.

     i=self.isoneutral_module
     i.enable_neutral_diffusion = 1
     i.K_iso_0 = 1000.0
     i.K_iso_steep = 500.0
     i.iso_dslope = 0.005
     i.iso_slopec = 0.01
     i.enable_skew_diffusion = 1

     m.enable_hor_friction = 1
     m.A_h = (2*m.degtom)**3 * 2e-11
     m.enable_hor_friction_cos_scaling = 1
     m.hor_friction_cosPower = 1

     m.enable_bottom_friction = 1
     m.r_bot = 1e-5

     m.enable_implicit_vert_friction = 1
     t=self.tke_module
     t.enable_tke = 1
     t.c_k = 0.1
     t.c_eps = 0.7
     t.alpha_tke = 30.0
     t.mxl_min = 1e-8
     t.tke_mxl_choice = 2
     #t.enable_tke_superbee_advection = 1

     i.K_gm_0 = 1000.0
     e=self.eke_module
     e.enable_eke = 1
     e.eke_k_max  = 1e4
     e.eke_c_k    = 0.4
     e.eke_c_eps  = 0.5
     e.eke_cross  = 2.
     e.eke_crhin  = 1.0
     e.eke_lmin   = 100.0
     e.enable_eke_superbee_advection = 1
     e.enable_eke_isopycnal_diffusion = 1

     i=self.idemix_module
     i.enable_idemix = 1
     i.enable_idemix_hor_diffusion = 1
     i.enable_eke_diss_surfbot = 1
     i.eke_diss_surfbot_frac = 0.2
     i.enable_idemix_superbee_advection = 1

     m.eq_of_state_type = 3


   @pyom_method
   def set_grid(self):
     m=self.main_module
     ddz = np.array([50.,70.,100.,140.,190.,240.,290.,340.,390.,440.,490.,540.,590.,640.,690.])
     m.dxt[:] = 2.0
     m.dyt[:] = 2.0
     m.x_origin = 0.0
     m.y_origin = -40.0
     m.dzt[:] = ddz[::-1]/2.5

   @pyom_method
   def set_coriolis(self):
     m=self.main_module
     m.coriolis_t[:,:] = 2*m.omega*np.sin(m.yt[None,:]/180.*np.pi)

   @pyom_method
   def set_topography(self):
     m=self.main_module
     (X,Y)= np.meshgrid(m.xt,m.yt); X=X.transpose(); Y=Y.transpose()
     m.kbot[...] = (X > 1.0) | (Y < -20)

   @pyom_method
   def set_initial_conditions(self):
     m=self.main_module
     XT, YT = np.meshgrid(m.xt,m.yt); XT=XT.transpose(); YT=YT.transpose()
     XU, YU = np.meshgrid(m.xu,m.yu); XU=XU.transpose(); YU=YU.transpose()

     # initial conditions
     m.temp[:,:,:,0:2] = ((1-m.zt[None,None,:]/m.zw[0])*15*m.maskT)[...,None]
     m.salt[:,:,:,0:2] = 35.0*m.maskT[...,None]

     # wind stress forcing
     taux = np.zeros(m.ny+1)
     yt = m.yt[2:m.ny+3]
     taux = (.1e-3*np.sin(np.pi*(m.yu[2:m.ny+3]-yu_start)/(-20.0-yt_start)))*(yt < -20) \
             + (.1e-3*(1-np.cos(2*np.pi*(m.yu[2:m.ny+3]-10.0)/(yu_end-10.0))))*(yt > 10)
     m.surface_taux[:,2:m.ny+3] = taux * m.maskU[:,2:m.ny+3,-1]

     # surface heatflux forcing
     self.t_rest = np.zeros(m.u[:,:,1,0].shape)
     self.t_star = np.zeros(m.u[:,:,1,0].shape)
     self.t_star[:, 2:-2] = 15 * np.invert((m.yt[2:-2] < -20) | (m.yt[2:-2] > 20)) \
             + 15*(m.yt[2:-2] - yt_start)/(-20-yt_start)*(m.yt[2:-2] < -20) \
             + 15*(1-(m.yt[2:-2]-20)/(yt_end-20))*(m.yt[2:-2] > 20.)
     self.t_rest = m.dzt[None,-1]/(30.*86400.)*m.maskT[:,:,-1]

     t=self.tke_module
     if t.enable_tke:
        t.forc_tke_surface[2:-2,2:-2] = np.sqrt((0.5*(m.surface_taux[2:-2,2:-2]+m.surface_taux[1:-3,2:-2]))**2  \
                                              + (0.5*(m.surface_tauy[2:-2,2:-2]+m.surface_tauy[2:-2,1:-3]))**2)**(1.5)

     i=self.idemix_module
     if i.enable_idemix:
       i.forc_iw_bottom[:] =  1.0e-6*m.maskW[:,:,-1]
       i.forc_iw_surface[:] = 0.1e-6*m.maskW[:,:,-1]

   @pyom_method
   def set_forcing(self):
       m=self.main_module
       m.forc_temp_surface[:] = self.t_rest*(self.t_star-m.temp[:,:,-1,1])

   @pyom_method
   def set_diagnostics(self):
       m = self.main_module
       for var in ("salt", "temp", "u", "v", "w", "psi", "surface_taux", "surface_tauy"):
           m.variables[var].average = True


if __name__ == "__main__":
    simulation = ACC2()
    simulation.run(snapint = 86400*1., runlen = 86400 * 100.0) #365*86400.*200)
