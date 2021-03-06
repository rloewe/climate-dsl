import os
import numpy as np
from netCDF4 import Dataset
from PIL import Image
import scipy.ndimage
import matplotlib.pyplot as plt

from climate import tools
from climate.pyom import PyOM, pyom_method
from climate.pyom.core import cyclic

class WavePropagation(PyOM):
    """
    Global model with flexible resolution and idealized geometry in the
    Atlantic to examine coastal wave propagation.
    """

    @pyom_method
    def set_parameter(self):
        self.nx = 140
        self.ny = 120
        self.nz = 50
        self._max_depth = 5600.
        self.dt_mom = 3600.0
        self.dt_tracer = 3600.0

        self.coord_degree = True
        self.enable_cyclic_x = True

        self.congr_epsilon = 1e-10
        self.congr_max_iterations = 10000
        self.enable_streamfunction = True

        self.enable_hor_friction = True
        self.A_h = 5e4
        self.enable_hor_friction_cos_scaling = True
        self.hor_friction_cosPower = 1
        self.enable_tempsalt_sources = True
        self.enable_implicit_vert_friction = True

        self.eq_of_state_type = 5

        self.enable_neutral_diffusion = True
        self.K_iso_0 = 1000.0
        self.K_iso_steep = 50.0
        self.iso_dslope = 0.005
        self.iso_slopec = 0.005
        self.enable_skew_diffusion = True

        self.enable_tke = True
        self.c_k = 0.1
        self.c_eps = 0.7
        self.alpha_tke = 30.0
        self.mxl_min = 1e-8
        self.tke_mxl_choice = 2
        self.enable_tke_superbee_advection = True

        self.enable_eke = True
        self.eke_k_max = 1e4
        self.eke_c_k = 0.4
        self.eke_c_eps = 0.5
        self.eke_cross = 2.
        self.eke_crhin = 1.0
        self.eke_lmin = 100.0
        self.enable_eke_superbee_advection = True
        self.enable_eke_isopycnal_diffusion = True

        self.enable_idemix = True
        self.enable_eke_diss_surfbot = True
        self.eke_diss_surfbot_frac = 0.2
        self.enable_idemix_superbee_advection = True
        self.enable_idemix_hor_diffusion = True

    def _set_parameters(self,module,parameters):
        for key, attribute in parameters.items():
            setattr(module,key,attribute)

    def _get_data(self, var):
        with Dataset("forcing_1deg_global_smooth.nc", "r") as forcing_file:
            return forcing_file.variables[var][...].T

    def set_grid(self):
        self.dzt[...] = tools.gaussian_spacing(self.nz, self._max_depth, min_spacing=10.)[::-1]
        self.dxt[...] = 360. / self.nx
        self.dyt[...] = 160. / self.ny
        self.y_origin = -80. + 160. / self.ny
        self.x_origin = 90. + 360. / self.nx

    def set_coriolis(self):
        self.coriolis_t[...] = 2 * self.omega * np.sin(self.yt[np.newaxis, :] / 180. * self.pi)

    def _shift_longitude_array(self, lon, arr):
        wrap_i = np.where((lon[:-1] < self.xt.min()) & (lon[1:] > self.xt.min()))[0][0]
        new_lon = np.concatenate((lon[wrap_i:-1], lon[:wrap_i] + 360.))
        new_arr = np.concatenate((arr[wrap_i:-1, ...], arr[:wrap_i, ...]))
        return new_lon, new_arr

    def set_topography(self):
        with Dataset("ETOPO5_Ice_g_gmt4.nc","r") as topography_file:
            topo_x, topo_y, topo_z = (topography_file.variables[k][...].T.astype(np.float) for k in ("x","y","z"))
        topo_z[topo_z > 0] = 0.
        topo_mask = np.flipud(np.asarray(Image.open("topo_mask_1deg_idealized.png"))).T / 255
        topo_z_smoothed = scipy.ndimage.gaussian_filter(topo_z,
                                      sigma = (0.5 * len(topo_x) / self.nx, 0.5 * len(topo_y) / self.ny))
        topo_z_smoothed[~topo_mask.astype(np.bool) & (topo_z_smoothed >= 0.)] = -100.
        topo_masked = np.where(topo_mask, 0., topo_z_smoothed)

        na_mask_image = np.flipud(np.asarray(Image.open("na_mask_1deg.png"))).T / 255.
        topo_x_shifted, na_mask_shifted = self._shift_longitude_array(topo_x, na_mask_image)
        self._na_mask = ~tools.interpolate((topo_x_shifted, topo_y), na_mask_shifted, (self.xt[2:-2], self.yt[2:-2]), kind="nearest", fill=False).astype(np.bool)

        topo_x_shifted, topo_masked_shifted = self._shift_longitude_array(topo_x, topo_masked)
        z_interp = tools.interpolate((topo_x_shifted, topo_y), topo_masked_shifted, (self.xt[2:-2], self.yt[2:-2]), kind="nearest", fill=False)
        z_interp[self._na_mask] = -4000
        depth_levels = 1 + np.argmin(np.abs(z_interp[:, :, np.newaxis] - self.zt[np.newaxis, np.newaxis, :]), axis=2)
        self.kbot[2:-2, 2:-2] = np.where(z_interp < 0., depth_levels, 0)
        self.kbot *= self.kbot < self.nz

    def _fix_north_atlantic(self, arr):
        newaxes = (slice(None),slice(None)) + (np.newaxis,) * (arr.ndim - 2)
        arr_masked = np.ma.masked_where(~self._na_mask[newaxes] * np.ones(arr.shape), arr)
        zonal_mean_na = arr_masked.mean(axis=0)
        return np.where(~arr_masked.mask, zonal_mean_na[np.newaxis, ...], arr)

    def set_initial_conditions(self):
        self._t_star = np.zeros((self.nx+4, self.ny+4, 12))
        self._s_star = np.zeros((self.nx+4, self.ny+4, 12))
        self._qnec = np.zeros((self.nx+4, self.ny+4, 12))
        self._qnet = np.zeros((self.nx+4, self.ny+4, 12))
        self._qsol = np.zeros((self.nx+4, self.ny+4, 12))
        self._divpen_shortwave = np.zeros(self.nz)
        self._taux = np.zeros((self.nx+4, self.ny+4, 12))
        self._tauy = np.zeros((self.nx+4, self.ny+4, 12))

        rpart_shortwave = 0.58
        efold1_shortwave = 0.35
        efold2_shortwave = 23.0

        t_grid = (self.xt[2:-2], self.yt[2:-2], self.zt)
        xt_forc, yt_forc, zt_forc = (self._get_data(k) for k in ("xt", "yt", "zt"))
        zt_forc = zt_forc[::-1]

        # initial conditions
        temp_data = tools.interpolate((xt_forc, yt_forc, zt_forc), self._get_data("temperature")[:,:,::-1], t_grid, missing_value=0.)
        self.temp[2:-2, 2:-2, :, 0] = temp_data * self.maskT[2:-2, 2:-2, :]
        self.temp[2:-2, 2:-2, :, 1] = temp_data * self.maskT[2:-2, 2:-2, :]

        salt_data = tools.interpolate((xt_forc, yt_forc, zt_forc), self._get_data("salinity")[:,:,::-1], t_grid, missing_value=0.)
        self.salt[2:-2, 2:-2, :, 0] = salt_data * self.maskT[2:-2, 2:-2, :]
        self.salt[2:-2, 2:-2, :, 1] = salt_data * self.maskT[2:-2, 2:-2, :]

        # wind stress on MIT grid
        time_grid = (self.xt[2:-2], self.yt[2:-2], np.arange(12))
        taux_data = tools.interpolate((xt_forc, yt_forc, np.arange(12)), self._get_data("tau_x"), time_grid, missing_value=0.)
        self._taux[2:-2, 2:-2, :] = taux_data / self.rho_0

        tauy_data = tools.interpolate((xt_forc, yt_forc, np.arange(12)), self._get_data("tau_y"), time_grid, missing_value=0.)
        self._tauy[2:-2, 2:-2, :] = tauy_data / self.rho_0

        if self.enable_cyclic_x:
            cyclic.setcyclic_x(self._taux)
            cyclic.setcyclic_x(self._tauy)

        # Qnet and dQ/dT and Qsol
        qnet_data = tools.interpolate((xt_forc, yt_forc, np.arange(12)), self._get_data("q_net"), time_grid, missing_value=0.)
        self._qnet[2:-2, 2:-2, :] = -qnet_data * self.maskT[2:-2, 2:-2, -1, np.newaxis]

        qnec_data = tools.interpolate((xt_forc, yt_forc, np.arange(12)), self._get_data("dqdt"), time_grid, missing_value=0.)
        self._qnec[2:-2, 2:-2, :] = qnec_data * self.maskT[2:-2, 2:-2, -1, np.newaxis]

        qsol_data = tools.interpolate((xt_forc, yt_forc, np.arange(12)), self._get_data("swf"), time_grid, missing_value=0.)
        self._qsol[2:-2, 2:-2, :] = -qsol_data * self.maskT[2:-2, 2:-2, -1, np.newaxis]

        # SST and SSS
        sst_data = tools.interpolate((xt_forc, yt_forc, np.arange(12)), self._get_data("sst"), time_grid, missing_value=0.)
        self._t_star[2:-2, 2:-2, :] = sst_data * self.maskT[2:-2, 2:-2, -1, np.newaxis]

        sss_data = tools.interpolate((xt_forc, yt_forc, np.arange(12)), self._get_data("sss"), time_grid, missing_value=0.)
        self._s_star[2:-2, 2:-2, :] = sss_data * self.maskT[2:-2, 2:-2, -1, np.newaxis]

        for k in (self._taux, self._tauy, self.temp, self.salt):
            k[2:-2, 2:-2, ...] = self._fix_north_atlantic(k[2:-2, 2:-2, ...])

        for k in (self._qnet, self._qnec, self._qsol, self._t_star, self._s_star):
            plt.figure()
            plt.imshow(k[2:-2, 2:-2, 0])
        plt.show()

        if self.enable_idemix:
            tidal_energy_data = tools.interpolate((xt_forc, yt_forc), self._get_data("tidal_energy"), t_grid[:-1], missing_value=0.)
            mask_x, mask_y = (i+2 for i in np.indices((self.nx, self.ny)))
            mask_z = np.maximum(0, self.kbot[2:-2, 2:-2] - 1)
            tidal_energy_data[:, :] *= self.maskW[mask_x, mask_y, mask_z] / self.rho_0
            self.forc_iw_bottom[2:-2, 2:-2] = tidal_energy_data

        """
        Initialize penetration profile for solar radiation
        and store divergence in divpen
        note that pen(nz) is set 0.0 instead of 1.0 to compensate for the
        shortwave part of the total surface flux
        """
        swarg1 = self.zw / efold1_shortwave
        swarg2 = self.zw / efold2_shortwave
        pen = rpart_shortwave * np.exp(swarg1) + (1.0 - rpart_shortwave) * np.exp(swarg2)
        self._divpen_shortwave = np.zeros(self.nz)
        self._divpen_shortwave[1:] = (pen[1:] - pen[:-1]) / self.dzt[1:]
        self._divpen_shortwave[0] = pen[0] / self.dzt[0]

    @pyom_method
    def set_forcing(self):
        t_rest = 30. * 86400.
        cp_0 = 3991.86795711963 # J/kg /K

        year_in_seconds = 360 * 86400.
        (n1, f1), (n2, f2) = tools.get_periodic_interval(self.itt * self.dt_tracer, year_in_seconds, year_in_seconds / 12., 12)

        # linearly interpolate wind stress and shift from MITgcm U/V grid to this grid
        self.surface_taux[...] = f1 * self._taux[:, :, n1] + f2 * self._taux[:, :, n2]
        self.surface_tauy[...] = f1 * self._tauy[:, :, n1] + f2 * self._tauy[:, :, n2]

        if self.enable_tke:
            self.forc_tke_surface[1:-1, 1:-1] = np.sqrt((0.5 * (self.surface_taux[1:-1, 1:-1] + self.surface_taux[:-2, 1:-1])) ** 2 \
                                                      + (0.5 * (self.surface_tauy[1:-1, 1:-1] + self.surface_tauy[1:-1, :-2])) ** 2) ** (3./2.)

        # W/m^2 K kg/J m^3/kg = K m/s
        fxa = f1 * self._t_star[..., n1] + f2 * self._t_star[..., n2]
        self._qqnec = f1 * self._qnec[..., n1] + f2 * self._qnec[..., n2]
        self._qqnet = f1 * self._qnet[..., n1] + f2 * self._qnet[..., n2]
        self.forc_temp_surface[...] = (self._qqnet + self._qqnec * (fxa - self.temp[..., -1, self.tau])) \
                                            * self.maskT[..., -1] / cp_0 / self.rho_0
        fxa = f1 * self._s_star[..., n1] + f2 * self._s_star[..., n2]
        self.forc_salt_surface[...] = 1. / t_rest * (fxa - self.salt[..., -1, self.tau]) * self.maskT[..., -1] * self.dzt[-1]

        # apply simple ice mask
        ice = np.ones((self.nx+4, self.ny+4), dtype=np.uint8)
        mask1 = self.temp[:, :, -1, self.tau] * self.maskT[:, :, -1] <= -1.8
        mask2 = self.forc_temp_surface <= 0
        mask = ~(mask1 & mask2)
        self.forc_temp_surface[...] *= mask
        self.forc_salt_surface[...] *= mask
        ice *= mask

        # solar radiation
        self.temp_source[..., :] = (f1 * self._qsol[..., n1, None] + f2 * self._qsol[..., n2, None]) \
                                        * self._divpen_shortwave[None, None, :] * ice[..., None] \
                                        * self.maskT[..., :] / cp_0 / self.rho_0

    @pyom_method
    def set_diagnostics(self):
        self.diagnostics["cfl_monitor"].output_frequency = 86400.0
        self.diagnostics["snapshot"].output_frequency = 0.5 * 86400.
        self.diagnostics["overturning"].output_frequency = 365 * 86400
        self.diagnostics["overturning"].sampling_frequency = 365 * 86400 / 24.
        self.diagnostics["energy"].output_frequency = 365 * 86400
        self.diagnostics["energy"].sampling_frequency = 365 * 86400 / 24.
        self.diagnostics["averages"].output_frequency = 365 * 86400
        self.diagnostics["averages"].sampling_frequency = 365 * 86400 / 24.

        average_vars = ("surface_taux", "surface_tauy", "forc_temp_surface", "forc_salt_surface",
                        "psi", "temp", "salt", "u", "v", "w", "Nsqr", "Hd", "rho",
                        "K_diss_v", "P_diss_v", "P_diss_nonlin", "P_diss_iso", "kappaH")
        if self.enable_skew_diffusion:
            average_vars += ("B1_gm", "B2_gm")
        if self.enable_TEM_friction:
            average_vars += ("kappa_gm", "K_diss_gm")
        if self.enable_tke:
            average_vars += ("tke", "Prandtlnumber", "mxl", "tke_diss",
                             "forc_tke_surface", "tke_surf_corr")
        if self.enable_idemix:
            average_vars += ("E_iw", "forc_iw_surface", "forc_iw_bottom", "iw_diss",
                             "c0", "v0")
        if self.enable_eke:
            average_vars += ("eke", "K_gm", "L_rossby", "L_rhines")

        for var in average_vars:
            self.variables[var].average = True


if __name__ == "__main__":
    WavePropagation().run(runlen=86400. * 10)
