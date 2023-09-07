#### code to sweep power and see cavity shift
from qick import *
from qick import helpers
import matplotlib.pyplot as plt
from WTF.Client_modules.Calib.initialize import *
import numpy as np
from WTF.Client_modules.CoreLib.Experiment import ExperimentClass
from WTF.Client_modules.Experiments.mTransmission import LoopbackProgramTrans
from tqdm.notebook import tqdm
import time
import datetime

class TransVsAtten(ExperimentClass):
    """
    Find the non-linearity in the cavity by sweeping the cavity attenuation and monitoring the cavity frequency
    """

    def __init__(self, soc=None, soccfg=None, path='', outerFolder='', prefix='data', cfg=None, config_file=None, progress=None):
        super().__init__(soc=soc, soccfg=soccfg, path=path, prefix=prefix,outerFolder=outerFolder, cfg=cfg, config_file=config_file, progress=progress)


    def acquire(self, progress=False, debug=False, plotDisp = True, plotSave = True, figNum = 1):
        expt_cfg = {
            ### define the attenuator parameters
            "trans_attn_start": self.cfg["trans_attn_start"],
            "trans_attn_stop": self.cfg["trans_attn_stop"],
            "trans_attn_num": self.cfg["trans_attn_num"],
            ### transmission parameters
            "trans_freq_start": self.cfg["trans_freq_start"],  # [MHz] actual frequency is this number + "cavity_LO"
            "trans_freq_stop": self.cfg["trans_freq_stop"],  # [MHz] actual frequency is this number + "cavity_LO"
            "TransNumPoints": self.cfg["TransNumPoints"],  ### number of points in the transmission frequecny
        }

        #### define attenuator, currently only set to use specific one at BF1
        cavityAtten = attenuator(27787, attenuation_int=35, print_int=False)
        cavityAtten.SetAttenuation(self.cfg["cav_Atten"])

        AttenVec = np.linspace(expt_cfg["trans_attn_start"], expt_cfg["trans_attn_stop"], expt_cfg["trans_attn_num"],
                               dtype=int) ### for current simplicity set it to an int


        ### create the figure and subplots that data will be plotted on
        while plt.fignum_exists(num = figNum):
            figNum += 1
        fig, axs = plt.subplots(1,1, figsize = (8,10), num = figNum)

        ### create the frequency array
        ### also create empty array to fill with transmission data
        self.trans_fpts = np.linspace(expt_cfg["trans_freq_start"], expt_cfg["trans_freq_stop"], expt_cfg["TransNumPoints"])

        X = (self.trans_fpts + self.cfg["cavity_LO"] / 1e6) / 1e3
        X_step = X[1] - X[0]
        Y = AttenVec
        Y_step = Y[1] - Y[0]
        Z = np.full((expt_cfg["trans_attn_num"], expt_cfg["TransNumPoints"]), np.nan)

        ### create an initial data dictionary that will be filled with data as it is taken during sweeps
        self.Imat = np.zeros((expt_cfg["trans_attn_num"], expt_cfg["TransNumPoints"]))
        self.Qmat = np.zeros((expt_cfg["trans_attn_num"], expt_cfg["TransNumPoints"]))
        self.data= {
            'config': self.cfg,
            'data': {'Imat': self.Imat, 'Qmat': self.Qmat, 'trans_fpts':self.trans_fpts,
                        'AttenVec': AttenVec
                     }
        }

        #### start a timer for estimating the time for the scan
        startTime = datetime.datetime.now()
        print('') ### print empty row for spacing
        print('starting date time: ' + startTime.strftime("%Y/%m/%d %H:%M:%S"))
        start = time.time()

        for i in range(expt_cfg["trans_attn_num"]):
            cavityAtten.SetAttenuation(AttenVec[i])

            ### take the transmission data
            data_I, data_Q = self._acquireTransData()
            self.data['data']['Imat'][i, :] = data_I
            self.data['data']['Qmat'][i, :] = data_Q

            #### plot out the transmission data
            sig = data_I + 1j * data_Q
            avgamp0 = np.abs(sig)
            Z[i, :] = avgamp0
            ax_plot_0 = axs.imshow(
                Z,
                aspect='auto',
                extent=[X[0] - X_step / 2, X[-1] + X_step / 2,
                        Y[0] - Y_step / 2, Y[-1] + Y_step / 2],
                origin='lower',
                interpolation='none',
            )
            if i == 0:  #### if first sweep add a colorbar
                cbar0 = fig.colorbar(ax_plot_0, ax=axs, extend='both')
                cbar0.set_label('a.u.', rotation=90)
            else:
                cbar0.remove()
                cbar0 = fig.colorbar(ax_plot_0, ax=axs, extend='both')
                cbar0.set_label('a.u.', rotation=90)

            axs.set_ylabel("Cavity Attenuation (dB)")
            axs.set_xlabel("Cavity Frequency (GHz)")
            axs.set_title("Cavity Transmission")

            if plotDisp:
                plt.show(block=False)
                plt.pause(0.1)

            if i ==0: ### during the first run create a time estimate for the data aqcuisition
                t_delta = time.time() - start ### time for single full row in seconds
                timeEst = t_delta*expt_cfg["trans_attn_num"] ### estimate for full scan
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




