from qick import *
# from q3diamond.Client_modules.socProxy import makeProxy
import matplotlib.pyplot as plt
import numpy as np
from qick.helpers import gauss
from q3diamond.Client_modules.Experiment import ExperimentClass
import datetime
from tqdm.notebook import tqdm
import time


class ChiProgram(AveragerProgram):
    def initialize(self):

        cfg = self.cfg
        cfg["rounds"] = 1
        self.declare_gen(ch=cfg["res_ch"], nqz=cfg["nqz"], mixer_freq=cfg["mixer_freq"], ro_ch=cfg["ro_chs"][0])  # Readout
        for ch in cfg["ro_chs"]:  # configure the readout lengths and downconversion frequencies
            self.declare_readout(ch=ch, length=self.us2cycles(cfg["read_length"]),
                                 freq=cfg["pulse_freq"], gen_ch=cfg["res_ch"])

        qubit_ch = cfg["qubit_ch"]
        self.declare_gen(ch=qubit_ch, nqz=cfg["qubit_nqz"])




        self.freq_01 = self.freq2reg(cfg["qubit_freq01"], gen_ch=qubit_ch)
        self.freq_12 = self.freq2reg(cfg["qubit_freq12"], gen_ch=qubit_ch)
        freq = self.freq2reg(cfg["pulse_freq"], gen_ch=cfg["res_ch"],
                             ro_ch=cfg["ro_chs"][0])  # convert frequency to dac frequency (ensuring it is an available adc frequency)

        self.FFDefinitions()
        #FF End

        if cfg["qubit_pulse_style"] == "arb":
            self.qubit_pulseLength = self.us2cycles(self.cfg["sigma"]) * 4

            self.add_gauss(ch=cfg["qubit_ch"], name="qubit",
                           sigma=self.us2cycles(self.cfg["sigma"]),
                           length= self.qubit_pulseLength)
        self.set_pulse_registers(ch=cfg["res_ch"], style="const", freq=freq, phase=0, gain=cfg["pulse_gain"],
                                 length=self.us2cycles(cfg["length"]))
        self.synci(200)  # give processor some time to configure pulses

    def body(self):

        self.FFPulses(self.FFExpts, self.qubit_pulseLength + self.us2cycles(2))
        if self.cfg['pulse_expt']['pulse_01'] or self.cfg['pulse_expt']['pulse_12']:
            self.setup_and_pulse(ch=self.cfg["qubit_ch"], style="arb", freq=self.freq_01, phase=0, gain=self.cfg["qubit_gain01"],
                                 waveform="qubit", t = self.us2cycles(2))

        if self.cfg['pulse_expt']['pulse_12']:
            self.setup_and_pulse(ch=self.cfg["qubit_ch"], style="arb", freq=self.freq_12, phase=0, gain=self.cfg["qubit_gain12"],
                                 waveform="qubit")

        self.sync_all()

        self.FFPulses(self.FFReadouts, self.us2cycles(self.cfg["length"]))

        self.measure(pulse_ch=self.cfg["res_ch"],
                     adcs=[0],
                     adc_trig_offset=self.us2cycles(self.cfg["adc_trig_offset"]),
                     wait=True,
                     syncdelay=self.us2cycles(20))

        self.FFPulses(-1 * self.FFExpts, self.qubit_pulseLength + self.us2cycles(2))
        self.FFPulses(-1 * self.FFReadouts, self.us2cycles(self.cfg["length"]))
        self.sync_all(self.us2cycles(self.cfg["relax_delay"]))


    def FFPulses(self, list_of_gains, length):
        for i, gain in enumerate(list_of_gains):
            self.set_pulse_registers(ch=self.FFChannels[i], style=self.ff_style, freq=self.ff_freq, phase=0,
                                     gain=gain,
                                     length=length)
        self.pulse(ch=self.FF_Channel1)
        self.pulse(ch=self.FF_Channel2)
        self.pulse(ch=self.FF_Channel3)

    def FFDefinitions(self):
        ### Start fast flux
        for FF_info in self.cfg["FF_list_readout"]:
            self.declare_gen(ch=FF_info[0], nqz=self.cfg["ff_nqz"])

        self.ff_freq = self.freq2reg(self.cfg["ff_freq"], gen_ch=self.cfg["ff_ch"])
        self.ff_style = self.cfg["ff_pulse_style"]

        ### Finish FF
        self.FF_Channel1, self.FF_Gain1_readout = self.cfg["FF_list_readout"][0]
        self.FF_Channel2, self.FF_Gain2_readout = self.cfg["FF_list_readout"][1]
        self.FF_Channel3, self.FF_Gain3_readout = self.cfg["FF_list_readout"][2]

        self.FF_Gain1_exp = self.cfg["FF_list_exp"][0][1]
        self.FF_Gain2_exp = self.cfg["FF_list_exp"][1][1]
        self.FF_Gain3_exp = self.cfg["FF_list_exp"][2][1]

        self.FFChannels = np.array([self.FF_Channel1, self.FF_Channel2, self.FF_Channel3])
        self.FFReadouts = np.array([self.FF_Gain1_readout, self.FF_Gain2_readout, self.FF_Gain3_readout])
        self.FFExpts = np.array([self.FF_Gain1_exp, self.FF_Gain2_exp, self.FF_Gain3_exp])
    # ====================================================== #

class ChiShift(ExperimentClass):
    """
    Transmission Experiment basic
    """

    def __init__(self, soc=None, soccfg=None, path='', outerFolder='', prefix='data', cfg=None, config_file=None, progress=None):
        super().__init__(soc=soc, soccfg=soccfg, path=path, outerFolder=outerFolder, prefix=prefix, cfg=cfg, config_file=config_file, progress=progress)

    def acquire(self, progress=False, debug=False):
        expt_cfg = {
                "center": self.cfg["pulse_freq"],
                "span": self.cfg["TransSpan"],
                "expts": self.cfg["TransNumPoints"]
        }
        expt_cfg["step"] = 2 * expt_cfg["span"] / expt_cfg["expts"]
        expt_cfg["start"] = expt_cfg["center"] - expt_cfg["span"]
        fpts = expt_cfg["start"] + expt_cfg["step"] * np.arange(expt_cfg["expts"])
        results_ground = []
        results_01 = []
        results_12 = []

        start = time.time()
        for f in tqdm(fpts, position=0, disable=True):
            start_inital = time.time()
            self.cfg["pulse_freq"] = f

            self.cfg["pulse_expt"]["pulse_01"] = False
            self.cfg["pulse_expt"]["pulse_12"] = False
            prog = ChiProgram(self.soccfg, self.cfg)
            results_ground.append(prog.acquire(self.soc, load_pulses=True))

            self.cfg["pulse_expt"]["pulse_01"] = True
            self.cfg["pulse_expt"]["pulse_12"] = False
            prog = ChiProgram(self.soccfg, self.cfg)
            results_01.append(prog.acquire(self.soc, load_pulses=True))

            self.check_f = self.cfg["pulse_expt"]["check_12"]
            if self.check_f:
                self.cfg["pulse_expt"]["pulse_01"] = True
                self.cfg["pulse_expt"]["pulse_12"] = True
                prog = ChiProgram(self.soccfg, self.cfg)
                results_12.append(prog.acquire(self.soc, load_pulses=True))
        print(f'Time: {time.time() - start}')
        results_ground = np.transpose(results_ground)
        results_01 = np.transpose(results_01)
        if self.check_f:
            results_12 = np.transpose(results_12)

        data={'config': self.cfg, 'data': {'results_ground': results_ground, 'results_01': results_01,
                                           'results_12': results_12, 'fpts':fpts}}
        self.data=data

        # #### find the frequency corresponding to the peak
        # sig = data['data']['results_ground'][0][0][0] + 1j * data['data']['results_ground'][0][0][1]
        # avgamp0 = np.abs(sig)
        # peak_loc = np.argmin(avgamp0)
        # self.peakFreq_min = data['data']['fpts'][peak_loc]
        # peak_loc = np.argmax(avgamp0)
        # self.peakFreq_max = data['data']['fpts'][peak_loc]

        return data

    def display(self, data=None, plotDisp = False, figNum = 1, **kwargs):
        if data is None:
            data = self.data

        x_pts = (data['data']['fpts'] + self.cfg["cavity_LO"] / 1e6) / 1e3  #### put into units of frequency GHz

        #Ground Data
        avgi = data['data']['results_ground'][0][0][0]
        avgq = data['data']['results_ground'][0][0][1]
        sig = data['data']['results_ground'][0][0][0] + 1j * data['data']['results_ground'][0][0][1]
        avgamp_ground= np.abs(sig)

        #01 Data
        sig = data['data']['results_01'][0][0][0] + 1j * data['data']['results_01'][0][0][1]
        avgamp_01 = np.abs(sig)

        #12 Data
        if self.check_f:
            sig = data['data']['results_12'][0][0][0] + 1j * data['data']['results_12'][0][0][1]
            avgamp_12 = np.abs(sig)


        # plt.figure(figNum)
        # plt.plot(x_pts, avgi, '.-', color = 'Orange', label="I")
        # plt.plot(x_pts, avgq, '.-', color = 'Blue', label="Q")
        # plt.ylabel("a.u.")
        # plt.xlabel("Cavity Frequency (GHz)")
        # plt.title(self.titlename)
        # plt.legend()
        #
        # plt.savefig(self.iname[:-4] + '_IQ.png')
        #
        # if plotDisp:
        #     plt.show(block=True)
        #     plt.pause(0.1)


        plt.figure(figNum + 1)
        plt.plot(x_pts, avgamp_ground, label="Ground", color = 'red', ls = '-', marker = '.')
        plt.plot(x_pts, avgamp_01, label="01", color = 'blue', ls = '-', marker = '.')
        if self.check_f:
            plt.plot(x_pts, avgamp_12, label="12", color = 'g', ls = '-', marker = '.')

        plt.ylabel("a.u.")
        plt.xlabel("Cavity Frequency (GHz)")
        plt.legend()
        plt.title(self.titlename)

        plt.savefig(self.iname)

        if plotDisp:
            plt.show(block=True)
            plt.pause(0.1)


    def save_data(self, data=None):
        print(f'Saving {self.fname}')
        super().save_data(data=data['data'])





