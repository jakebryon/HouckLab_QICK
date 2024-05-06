#### code to sweep power and see cavity shift
from qick import *
from qick import helpers
import matplotlib.pyplot as plt
from WorkingProjects.QM_Team.qubit_measurements.Client_modules.Calib.initialize import *
import numpy as np
from WorkingProjects.QM_Team.qubit_measurements.Client_modules.CoreLib.Experiment import ExperimentClass
# from STFU.Client_modules.Experiments.mTransmission import LoopbackProgramTrans
from WorkingProjects.QM_Team.qubit_measurements.Client_modules.Experiments.mTransmission_SaraTest import LoopbackProgramTrans
from tqdm.notebook import tqdm
import time
import datetime

class TransVsGain(ExperimentClass):
    """
    Find the non-linearity in the cavity by sweeping the cavity gain and monitoring the cavity frequency
    """

    def __init__(self, soc=None, soccfg=None, path='', outerFolder='', prefix='data', cfg=None, config_file=None, progress=None):
        super().__init__(soc=soc, soccfg=soccfg, path=path, prefix=prefix,outerFolder=outerFolder, cfg=cfg, config_file=config_file, progress=progress)


    def acquire(self, progress=False, debug=False, plotDisp = True, plotSave = True, figNum = 1):
        expt_cfg = {
            ### define the gainuator parameters
            "trans_gain_start": self.cfg["trans_gain_start"],
            "trans_gain_stop": self.cfg["trans_gain_stop"],
            "trans_gain_num": self.cfg["trans_gain_num"],
            ### transmission parameters
            "trans_freq_start": self.cfg["trans_freq_start"],  # [MHz] actual frequency is this number + "cavity_LO"
            "trans_freq_stop": self.cfg["trans_freq_stop"],  # [MHz] actual frequency is this number + "cavity_LO"
            "TransNumPoints": self.cfg["TransNumPoints"],  ### number of points in the transmission frequecny
        }


        gainVec = np.linspace(expt_cfg["trans_gain_start"], expt_cfg["trans_gain_stop"], expt_cfg["trans_gain_num"],
                               dtype=int) ### for current simplicity set it to an int


        ### create the figure and subplots that data will be plotted on
        while plt.fignum_exists(num = figNum):
            figNum += 1
        fig, axs = plt.subplots(2, 2, figsize = (16,10), num = figNum)

        ### create the frequency array
        ### also create empty array to fill with transmission data
        self.trans_fpts = np.linspace(expt_cfg["trans_freq_start"], expt_cfg["trans_freq_stop"], expt_cfg["TransNumPoints"])

        X = (self.trans_fpts + self.cfg["cavity_LO"] / 1e6) / 1e3
        X_step = X[1] - X[0]
        Y = gainVec
        Y_step = Y[1] - Y[0]
        Z = np.full((expt_cfg["trans_gain_num"], expt_cfg["TransNumPoints"]), np.nan)
        Z1 = np.full((expt_cfg["trans_gain_num"], expt_cfg["TransNumPoints"]), np.nan)

        Z_I = np.full((expt_cfg["trans_gain_num"], expt_cfg["TransNumPoints"]), np.nan)
        Z_Q = np.full((expt_cfg["trans_gain_num"], expt_cfg["TransNumPoints"]), np.nan)

        ### create an initial data dictionary that will be filled with data as it is taken during sweeps
        self.Imat = np.zeros((expt_cfg["trans_gain_num"], expt_cfg["TransNumPoints"]))
        self.Qmat = np.zeros((expt_cfg["trans_gain_num"], expt_cfg["TransNumPoints"]))
        self.data= {
            'config': self.cfg,
            'data': {'Imat': self.Imat, 'Qmat': self.Qmat, 'trans_fpts':self.trans_fpts,
                        'gainVec': gainVec
                     }
        }

        #### start a timer for estimating the time for the scan
        startTime = datetime.datetime.now()
        print('') ### print empty row for spacing
        print('starting date time: ' + startTime.strftime("%Y/%m/%d %H:%M:%S"))
        start = time.time()

        for i in range(expt_cfg["trans_gain_num"]):
            self.cfg["read_pulse_gain"] = gainVec[i]

            data_I, data_Q = self._acquireTransData()
            self.data['data']['Imat'][i, :] = data_I
            self.data['data']['Qmat'][i, :] = data_Q

            ### store the I and Q data
            Z_I[i, :] = data_I
            Z_Q[i, :] = data_Q

            #### plot out the transmission data
            sig = data_I + 1j * data_Q
            avgamp0 = np.abs(sig)
            # Haven't gotten this to work yet, maybe come back later
            avgphase = np.unwrap(np.angle(sig * np.exp(-X * 10j), deg = True), period = 360)
            Z1[i, :] = avgphase
            # Z[i, :] = avgamp0

            ### normalize transmission data for plotting
            avgamp0_offset = avgamp0 - np.min(avgamp0)
            avgamp0_norm = avgamp0_offset / (np.max(avgamp0_offset))
            Z[i, :] = avgamp0_norm

            if i == 0:  #### if first sweep add a colorbar
                ax_plot_00 = axs[0,0].imshow(
                    Z,
                    aspect='auto',
                    extent=[X[0] - X_step / 2, X[-1] + X_step / 2,
                            Y[0] - Y_step / 2, Y[-1] + Y_step / 2],
                    origin='lower',
                    interpolation='none',
                )
                cbar00 = fig.colorbar(ax_plot_00, ax=axs[0,0], extend='both')
                cbar00.set_label('a.u.', rotation=90)

                ax_plot_10 = axs[1, 0].imshow(
                    Z1,
                    aspect = 'auto',
                    extent = [X[0] - X_step / 2, X[-1] + X_step / 2,
                             Y[0] - Y_step / 2, Y[-1] + Y_step / 2],
                    origin = 'lower',
                    interpolation = 'none',
                )
                cbar10 = fig.colorbar(ax_plot_10, ax = axs[1, 0], extend = 'both')
                cbar10.set_label('deg', rotation = 90)

                ### plot the I data
                ax_plot_01 = axs[0, 1].imshow(
                    Z_I,
                    aspect = 'auto',
                    extent = [X[0] - X_step / 2, X[-1] + X_step / 2,
                             Y[0] - Y_step / 2, Y[-1] + Y_step / 2],
                    origin = 'lower',
                    interpolation = 'none',
                )
                cbar01 = fig.colorbar(ax_plot_01, ax = axs[0, 1], extend = 'both')
                cbar01.set_label('deg', rotation = 90)

                ### plot the Q data
                ax_plot_11 = axs[1, 1].imshow(
                    Z_Q,
                    aspect='auto',
                    extent=[X[0] - X_step / 2, X[-1] + X_step / 2,
                            Y[0] - Y_step / 2, Y[-1] + Y_step / 2],
                    origin='lower',
                    interpolation='none',
                )
                cbar11 = fig.colorbar(ax_plot_11, ax=axs[1, 1], extend='both')
                cbar11.set_label('deg', rotation=90)


            else:
                ax_plot_00.set_data(Z)
                cbar00.remove()
                cbar00 = fig.colorbar(ax_plot_00, ax=axs[0, 0], extend='both')
                cbar00.set_label('a.u.', rotation=90)

                ax_plot_10.set_data(Z1)
                cbar10.remove()
                cbar10 = fig.colorbar(ax_plot_10, ax=axs[1, 0], extend='both')
                cbar10.set_label('deg', rotation=90)

                ax_plot_01.set_data(Z_I)
                cbar01.remove()
                cbar01 = fig.colorbar(ax_plot_01, ax=axs[0, 1], extend='both')
                cbar01.set_label('I (a.u.)', rotation=90)

                ax_plot_11.set_data(Z_Q)
                cbar11.remove()
                cbar11 = fig.colorbar(ax_plot_11, ax=axs[1, 1], extend='both')
                cbar11.set_label('Q (a.u.)', rotation=90)

            axs[0, 0].set_ylabel("Cavity Gain (a.u.)")
            axs[0, 0].set_xlabel("Cavity Frequency (GHz)")
            axs[0, 0].set_title("Cavity Transmission Magnitude Normalized")
            # axs.set_yscale('log')

            axs[1, 0].set_ylabel("Cavity Gain (a.u.)")
            axs[1, 0].set_xlabel("Cavity Frequency (GHz)")
            axs[1, 0].set_title("Cavity Transmission Phase")

            axs[0, 1].set_ylabel("Cavity Gain (a.u.)")
            axs[0, 1].set_xlabel("Cavity Frequency (GHz)")
            axs[0, 1].set_title("Cavity Transmission I")

            axs[1, 1].set_ylabel("Cavity Gain (a.u.)")
            axs[1, 1].set_xlabel("Cavity Frequency (GHz)")
            axs[1, 1].set_title("Cavity Transmission Q")

            if plotDisp:
                plt.show(block=False)
                plt.pause(0.1)

            if i ==0: ### during the first run create a time estimate for the data aqcuisition
                t_delta = time.time() - start ### time for single full row in seconds
                timeEst = t_delta*expt_cfg["trans_gain_num"] ### estimate for full scan
                StopTime = startTime + datetime.timedelta(seconds=timeEst)
                print('Time for 1 sweep: ' + str(round(t_delta/60, 2)) + ' min')
                print('estimated total time: ' + str(round(timeEst/60, 2)) + ' min')
                print('estimated end: ' + StopTime.strftime("%Y/%m/%d %H:%M:%S"))

        print('actual end: '+ datetime.datetime.now().strftime("%Y/%m/%d %H:%M:%S"))

        if plotSave:
            plt.savefig(self.iname) #### save the figure

        if plotDisp == False:
            fig.clf(True)
            plt.close(fig)

        return self.data

    def _acquireTransData(self):
        ##### code to aquire just the cavity transmission data
        expt_cfg = {
            ### transmission parameters
            "trans_freq_start": self.cfg["trans_freq_start"],  # [MHz] actual frequency is this number + "cavity_LO"
            "trans_freq_stop": self.cfg["trans_freq_stop"],  # [MHz] actual frequency is this number + "cavity_LO"
            "TransNumPoints": self.cfg["TransNumPoints"],  ### number of points in the transmission frequecny
        }
        ### take the transmission data
        self.cfg["reps"] = self.cfg["trans_reps"]
        fpts = np.linspace(expt_cfg["trans_freq_start"], expt_cfg["trans_freq_stop"], expt_cfg["TransNumPoints"])
        results = []
        start = time.time()
        for f in tqdm(fpts, position=0, disable=True):
            self.cfg["read_pulse_freq"] = f
            prog = LoopbackProgramTrans(self.soccfg, self.cfg)
            results.append(prog.acquire(self.soc, load_pulses=True))
        results = np.transpose(results)
        #### pull out I and Q data
        data_I = results[0][0][0]
        data_Q = results[0][0][1]

        return data_I, data_Q


    def save_data(self, data=None):
        ##### save the data to a .h5 file
        print(f'Saving {self.fname}')
        super().save_data(data=data['data'])




