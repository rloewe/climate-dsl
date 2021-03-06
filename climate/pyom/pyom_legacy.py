import imp

from . import PyOM

class LowercaseAttributeWrapper(object):
    """
    A simple wrapper class that converts attributes to lower case (needed for Fortran interface)
    """
    def __init__(self,wrapped_object):
        object.__setattr__(self,"_w",wrapped_object)

    def __getattr__(self, key):
        if key == "_w":
            return object.__getattribute__(self,"_w")
        return getattr(object.__getattribute__(self,"_w"),key.lower())

    def __setattr__(self, key, value):
        setattr(self._w,key.lower(),value)

class PyOMLegacy(PyOM):
    """
    PyOM class that supports the PyOM Fortran interface
    """
    def __init__(self, fortran=None, *args, **kwargs):
        """
        To use the pyom2 legacy interface point the fortran argument to the PyOM fortran library:

        > simulation = GlobalOneDegree(fortran = "pyOM_code.so")

        """
        if fortran:
            self.legacy_mode = True
            self.fortran = LowercaseAttributeWrapper(imp.load_dynamic("pyOM_code", fortran))
            self.main_module = LowercaseAttributeWrapper(self.fortran.main_module)
            self.isoneutral_module = LowercaseAttributeWrapper(self.fortran.isoneutral_module)
            self.idemix_module = LowercaseAttributeWrapper(self.fortran.idemix_module)
            self.tke_module = LowercaseAttributeWrapper(self.fortran.tke_module)
            self.eke_module = LowercaseAttributeWrapper(self.fortran.eke_module)
        else:
            self.legacy_mode = False
            self.fortran = self
            self.main_module = self
            self.isoneutral_module = self
            self.idemix_module = self
            self.tke_module = self
            self.eke_module = self

        super(PyOMLegacy,self).__init__(*args, **kwargs)

    def set_legacy_parameter(self, *args, **kwargs):
        m = self.fortran.main_module
        self.onx = 2
        self.is_pe = 2
        self.ie_pe = m.nx+2
        self.js_pe = 2
        self.je_pe = m.ny+2
        self.if2py = lambda i: i+self.onx-self.is_pe
        self.jf2py = lambda j: j+self.onx-self.js_pe
        self.ip2fy = lambda i: i+self.is_pe-self.onx
        self.jp2fy = lambda j: j+self.js_pe-self.onx
        self.get_tau = lambda: self.tau - 1 if self.legacy_mode else self.tau

        diag_legacy_settings = (
            (self.diagnostics["cfl_monitor"], "output_frequency", "ts_monint"),
            (self.diagnostics["tracer_monitor"], "output_frequency", "trac_cont_int"),
            (self.diagnostics["snapshot"], "output_frequency", "snapint"),
            (self.diagnostics["averages"], "output_frequency", "aveint"),
            (self.diagnostics["averages"], "sampling_frequency", "avefreq"),
            (self.diagnostics["overturning"], "output_frequency", "overint"),
            (self.diagnostics["overturning"], "sampling_frequency", "overfreq"),
            (self.diagnostics["energy"], "output_frequency", "energint"),
            (self.diagnostics["energy"], "sampling_frequency", "energfreq"),
            (self.diagnostics["particles"], "output_frequency", "particles_int"),
        )

        for diag, param, attr in diag_legacy_settings:
            if hasattr(self, attr):
                setattr(diag, param, getattr(self, attr))


    def setup(self, *args, **kwargs):
        if self.legacy_mode:
            self.fortran.my_mpi_init(0)
            self.set_parameter()
            self.set_legacy_parameter()
            self.fortran.pe_decomposition()
            self.fortran.allocate_main_module()
            self.fortran.allocate_isoneutral_module()
            self.fortran.allocate_tke_module()
            self.fortran.allocate_eke_module()
            self.fortran.allocate_idemix_module()
            self.set_grid()
            self.fortran.calc_grid()
            self.set_coriolis()
            self.fortran.calc_beta()
            self.set_topography()
            self.fortran.calc_topo()
            self.fortran.calc_spectral_topo()
            self.set_initial_conditions()
            self.fortran.calc_initial_conditions()
            self.set_forcing()
            if self.fortran.main_module.enable_streamfunction:
                self.fortran.streamfunction_init()
            self.fortran.check_isoneutral_slope_crit()
        else:
            # self.set_parameter() is called twice, but that shouldn't matter
            self.set_parameter()
            self.set_legacy_parameter()
            super(PyOMLegacy,self).setup(*args,**kwargs)


    def run(self, **kwargs):
        if not self.legacy_mode:
            super(PyOMLegacy,self).run(**kwargs)
            return

        f = self.fortran
        m = self.main_module
        idm = self.idemix_module
        ekm = self.eke_module
        tkm = self.tke_module

        m.runlen = kwargs["runlen"]
        m.snapint = kwargs["snapint"]

        with self.timers["setup"]:
            """
            Initialize model
            """
            self.setup()

            m.enditt = m.itt + int(m.runlen / m.dt_tracer)
            print("Starting integration for {:.2e}s".format(float(m.runlen)))
            print(" from time step {} to {}".format(m.itt,m.enditt))

        while m.itt < m.enditt:
            with self.timers["main"]:
                self.set_forcing()

                if idm.enable_idemix:
                    f.set_idemix_parameter()
                if idm.enable_idemix_M2 or idm.enable_idemix_niw:
                    f.set_spectral_parameter()

                f.set_eke_diffusivities()
                f.set_tke_diffusivities()

                with self.timers["momentum"]:
                    f.momentum()

                with self.timers["temperature"]:
                    f.thermodynamics()

                if ekm.enable_eke or tkm.enable_tke or idm.enable_idemix:
                    f.calculate_velocity_on_wgrid()

                with self.timers["eke"]:
                    if ekm.enable_eke:
                        f.integrate_eke()

                with self.timers["idemix"]:
                    if idm.enable_idemix_M2:
                        f.integrate_idemix_M2()
                    if idm.enable_idemix_niw:
                        f.integrate_idemix_niw()
                    if idm.enable_idemix:
                        f.integrate_idemix()
                    if idm.enable_idemix_M2 or idm.enable_idemix_niw:
                        f.wave_interaction()

                with self.timers["tke"]:
                    if tkm.enable_tke:
                        f.integrate_tke()

                """
                Main boundary exchange
                for density, temp and salt this is done in integrate_tempsalt.f90
                """
                f.border_exchg_xyz(m.is_pe-m.onx,m.ie_pe+m.onx,m.js_pe-m.onx,m.je_pe+m.onx,m.u[:,:,:,m.taup1-1],m.nz)
                f.setcyclic_xyz   (m.is_pe-m.onx,m.ie_pe+m.onx,m.js_pe-m.onx,m.je_pe+m.onx,m.u[:,:,:,m.taup1-1],m.nz)
                f.border_exchg_xyz(m.is_pe-m.onx,m.ie_pe+m.onx,m.js_pe-m.onx,m.je_pe+m.onx,m.v[:,:,:,m.taup1-1],m.nz)
                f.setcyclic_xyz   (m.is_pe-m.onx,m.ie_pe+m.onx,m.js_pe-m.onx,m.je_pe+m.onx,m.v[:,:,:,m.taup1-1],m.nz)

                if tkm.enable_tke:
                    f.border_exchg_xyz(m.is_pe-m.onx,m.ie_pe+m.onx,m.js_pe-m.onx,m.je_pe+m.onx,tkm.tke[:,:,:,m.taup1-1],m.nz)
                    f.setcyclic_xyz   (m.is_pe-m.onx,m.ie_pe+m.onx,m.js_pe-m.onx,m.je_pe+m.onx,tkm.tke[:,:,:,m.taup1-1],m.nz)
                if ekm.enable_eke:
                    f.border_exchg_xyz(m.is_pe-m.onx,m.ie_pe+m.onx,m.js_pe-m.onx,m.je_pe+m.onx,ekm.eke[:,:,:,m.taup1-1],m.nz)
                    f.setcyclic_xyz   (m.is_pe-m.onx,m.ie_pe+m.onx,m.js_pe-m.onx,m.je_pe+m.onx,ekm.eke[:,:,:,m.taup1-1],m.nz)
                if idm.enable_idemix:
                    f.border_exchg_xyz(m.is_pe-m.onx,m.ie_pe+m.onx,m.js_pe-m.onx,m.je_pe+m.onx,idm.e_iw[:,:,:,m.taup1-1],m.nz)
                    f.setcyclic_xyz   (m.is_pe-m.onx,m.ie_pe+m.onx,m.js_pe-m.onx,m.je_pe+m.onx,idm.e_iw[:,:,:,m.taup1-1],m.nz)
                if idm.enable_idemix_m2:
                    f.border_exchg_xyp(m.is_pe-m.onx,m.ie_pe+m.onx,m.js_pe-m.onx,m.je_pe+m.onx,idm.e_m2[:,:,:,m.taup1-1],idm.np)
                    f.setcyclic_xyp   (m.is_pe-m.onx,m.ie_pe+m.onx,m.js_pe-m.onx,m.je_pe+m.onx,idm.e_m2[:,:,:,m.taup1-1],idm.np)
                if idm.enable_idemix_niw:
                    f.border_exchg_xyp(m.is_pe-m.onx,m.ie_pe+m.onx,m.js_pe-m.onx,m.je_pe+m.onx,idm.e_niw[:,:,:,m.taup1-1],idm.np)
                    f.setcyclic_xyp   (m.is_pe-m.onx,m.ie_pe+m.onx,m.js_pe-m.onx,m.je_pe+m.onx,idm.e_niw[:,:,:,m.taup1-1],idm.np)

                # diagnose vertical velocity at taup1
                if m.enable_hydrostatic:
                    f.vertical_velocity()

            # shift time
            otaum1 = m.taum1 * 1
            m.taum1 = m.tau
            m.tau = m.taup1
            m.taup1 = otaum1
            m.itt += 1
            print("Current iteration: {}".format(m.itt))
            print("Time step took {}s".format(self.timers["main"].getLastTime()))


        print("Timing summary:")
        print(" setup time summary       = {}s".format(self.timers["setup"].getTime()))
        print(" main loop time summary   = {}s".format(self.timers["main"].getTime()))
        print("     momentum             = {}s".format(self.timers["momentum"].getTime()))
        print("     thermodynamics       = {}s".format(self.timers["temperature"].getTime()))
        print("     EKE                  = {}s".format(self.timers["eke"].getTime()))
        print("     IDEMIX               = {}s".format(self.timers["idemix"].getTime()))
        print("     TKE                  = {}s".format(self.timers["tke"].getTime()))
