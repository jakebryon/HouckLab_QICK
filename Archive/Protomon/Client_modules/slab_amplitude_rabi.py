import matplotlib.pyplot as plt
import numpy as np
from qick import *
from qick.helpers import gauss

from slab import Experiment, dsfit, AttrDict
from tqdm import tqdm_notebook as tqdm


class AmplitudeRabiProgram(RAveragerProgram):
    def initialize(self):
        cfg = AttrDict(self.cfg)
        self.cfg.update(cfg.expt)
        
        self.res_ch = cfg.hw.soc.dacs.readout.ch[cfg.device.readout.dac]
        self.qubit_ch = cfg.hw.soc.dacs.qubit.ch[cfg.device.qubit.dac]
    
        self.q_rp = self.ch_page(self.qubit_ch) # get register page for qubit_ch
        self.r_gain = self.sreg(self.qubit_ch, "gain") # get gain register for qubit_ch    
        
        self.f_res=self.freq2reg(cfg.device.readout.frequency) # conver f_res to dac register value
        self.readout_length=self.us2cycles(cfg.device.readout.readout_length)
        
        # copy over parameters for the acquire method
        self.cfg.adc_lengths = [self.readout_length]*2
        self.cfg.adc_freqs = [cfg.device.readout.frequency]*2
        self.cfg.reps = cfg.expt.reps
        self.cfg.rounds = cfg.expt.rounds
        
        self.sigma_test = self.us2cycles(cfg.expt.sigma_test)
        
        # add qubit and readout pulses to respective channels
        if cfg.expt.pulse_type.lower() == "gauss" and self.sigma_test > 0:
            self.add_pulse(ch=self.qubit_ch, name="qubit", style="arb", 
                   idata=gauss(mu=self.sigma_test*16*4/2,si=self.sigma_test*16,length=4*self.sigma_test*16), 
                   qdata=0*gauss(mu=self.sigma_test*16*4/2,si=self.sigma_test*16,length=4*self.sigma_test*16))
            # self.add_pulse(ch=self.res_ch, name="qubit", style="arb", 
            #        idata=gauss(mu=self.sigma_test*16*4/2,si=self.sigma_test*16,length=4*self.sigma_test*16), 
            #        qdata=0*gauss(mu=self.sigma_test*16*4/2,si=self.sigma_test*16,length=4*self.sigma_test*16))
        elif self.sigma_test:
            self.add_pulse(ch=self.qubit_ch, name="qubit", style="const", length=self.sigma_test)
        self.add_pulse(ch=self.res_ch, name="measure", style="const", length=self.readout_length)
        
        # initialize gain
        self.safe_regwi(self.q_rp, self.r_gain, self.cfg.expt.start)
        self.sync_all(self.us2cycles(0.2))
    
    def body(self):
        cfg=AttrDict(self.cfg)
        if cfg.expt.sigma_test > 0:
            self.pulse(
                ch=self.qubit_ch, name="qubit", phase=deg2reg(0), 
                freq=self.freq2reg(cfg.device.qubit.f_ge), play=True) # qubit pulse
            # self.pulse(
            #     ch=self.res_ch, name="qubit", phase=deg2reg(0), 
            #     freq=self.freq2reg(cfg.device.qubit.f_ge), play=True) # qubit pulse
        self.sync_all(self.us2cycles(0.05)) # align channels and wait 50ns
        self.trigger_adc(adc1=1, adc2=1, adc_trig_offset=cfg.device.readout.trig_offset) # trigger measurement
        self.pulse(
            ch=self.res_ch, name="measure", freq=self.f_res,
            phase=deg2reg(cfg.device.readout.phase),
            gain=cfg.device.readout.gain, length=self.readout_length, t=0, play=True) # play readout pulse
        self.waiti(self.res_ch, self.readout_length + cfg.device.readout.trig_offset)
        self.sync_all(self.us2cycles(cfg.device.readout.relax_delay)) # wait for qubit to relax
    
    def update(self):
        self.mathi(self.q_rp, self.r_gain, self.r_gain, '+', self.cfg.expt.step) # update test gain
                      
# ====================================================== #
                      
class AmplitudeRabiExperiment(Experiment):
    """
    Amplitude Rabi Experiment
    Experimental Config:
    expt = dict(
        start: qubit gain [dac level]
        step: gain step [dac level]
        expts: number steps
        reps: number averages per expt
        rounds: number repetitions of experiment sweep
        sigma_test: gaussian sigma for pulse length [us] (default: from pi_ge in config)
        pulse_type: 'gauss' or 'const'
    )
    """

    def __init__(self, soccfg=None, path='', prefix='AmplitudeRabi', config_file=None, progress=None):
        super().__init__(soccfg=soccfg, path=path, prefix=prefix, config_file=config_file, progress=progress)

    def acquire(self, progress=False, debug=False):
        q_ind = self.cfg.expt.qubit
        for key, value in self.cfg.device.readout.items():
            if isinstance(value, list):
                self.cfg.device.readout.update({key: value[q_ind]})
        for key, value in self.cfg.device.qubit.items():
            if isinstance(value, list):
                self.cfg.device.qubit.update({key: value[q_ind]})
            elif isinstance(value, dict):
                for key2, value2 in value.items():
                    for key3, value3 in value2.items():
                        if isinstance(value3, list):
                            value2.update({key3: value3[q_ind]})                                
        
        if 'sigma_test' not in self.cfg.expt:
            self.cfg.expt.sigma_test = self.cfg.device.qubit.pulses.pi_ge.sigma
        
        amprabi = AmplitudeRabiProgram(soccfg=self.soccfg, cfg=self.cfg)
        adc_ch = self.cfg.hw.soc.adcs.readout.ch[self.cfg.device.readout.adc]
        
        xpts, avgi, avgq = amprabi.acquire(self.im[self.cfg.aliases.soc], threshold=None, load_pulses=True, progress=progress, debug=debug)

        shots_i = amprabi.di_buf[adc_ch].reshape((self.cfg.expt.expts, self.cfg.expt.reps)) / amprabi.readout_length
        shots_i = np.average(shots_i, axis=1)
        print(len(shots_i), self.cfg.expt.expts)
        shots_q = amprabi.dq_buf[adc_ch] / amprabi.readout_length
        print(np.std(shots_i), np.std(shots_q))
        
        avgi = avgi[adc_ch][0]
        avgq = avgq[adc_ch][0]
        amps = np.abs(avgi+1j*avgq) # Calculating the magnitude
        phases = np.angle(avgi+1j*avgq) # Calculating the phase        
        
        # data={'avgi':avgi, 'avgq':avgq, 'amps':amps, 'phases':phases}
        data={'xpts': xpts, 'avgi':avgi, 'avgq':avgq, 'amps':amps, 'phases':phases}
        self.data=data
        return data

    def analyze(self, data=None, fit=True, **kwargs):
        if data is None:
            data=self.data
        
        if fit:
            # fitparams=[amp, freq (non-angular), phase (deg), decay time, amp offset, decay time offset]
            # Remove the first and last point from fit in case weird edge measurements
            p_avgi = dsfit.fitdecaysin(data['xpts'][1:-1], data["avgi"][1:-1], fitparams=None, showfit=False)
            p_avgq = dsfit.fitdecaysin(data['xpts'][1:-1], data["avgq"][1:-1], fitparams=None, showfit=False)
            # adding this due to extra parameter in decaysin that is not in fitdecaysin
            p_avgi = np.append(p_avgi, data['xpts'][0])
            p_avgq = np.append(p_avgq, data['xpts'][0])
            data['fit_avgi'] = p_avgi   
            data['fit_avgq'] = p_avgq
        return data

    def display(self, data=None, fit=True, **kwargs):
        if data is None:
            data=self.data 
        plt.figure(figsize=(10,8))
        plt.subplot(211, title="Amplitude Rabi", ylabel="I [adc level]")
        plt.plot(data["xpts"], data["avgi"],'o-')
        if fit:
            plt.plot(data["xpts"], dsfit.decaysin(data["fit_avgi"], data["xpts"]))
            pi_gain = 1/data['fit_avgi'][1]/2
            print(f'Pi gain from avgi data [dac units]: {int(pi_gain)}')
            print(f'Pi/2 gain from avgi data [dac units]: {int(pi_gain/2)}')
            plt.axvline(pi_gain, color='0.2', linestyle='--')
            plt.axvline(pi_gain/2, color='0.2', linestyle='--')
        plt.subplot(212, xlabel="Gain [dac units]", ylabel="Q [adc levels]")
        plt.plot(data["xpts"], data["avgq"],'o-')
        if fit:
            plt.plot(data["xpts"], dsfit.decaysin(data["fit_avgq"], data["xpts"]))
            pi_gain = 1/data['fit_avgq'][1]/2
            print(f'Pi gain from avgq data [dac units]: {int(pi_gain)}')
            print(f'Pi/2 gain from avgq data [dac units]: {int(pi_gain/2)}')
            plt.axvline(pi_gain, color='0.2', linestyle='--')
            plt.axvline(pi_gain/2, color='0.2', linestyle='--')
        plt.tight_layout()
        plt.show()
    
    def save_data(self, data=None):
        print(f'Saving {self.fname}')
        super().save_data(data=data)

# ====================================================== #
                      
class AmplitudeRabiChevronExperiment(Experiment):
    """
    Amplitude Rabi Experiment
    Experimental Config:
    expt = dict(
        start_f: start qubit frequency (MHz), 
        step_f: frequency step (MHz), 
        expts_f: number of experiments in frequency,
        start_gain: qubit gain [dac level]
        step_gain: gain step [dac level]
        expts_gain: number steps
        reps: number averages per expt
        rounds: number repetitions of experiment sweep
        sigma_test: gaussian sigma for pulse length [us] (default: from pi_ge in config)
        pulse_type: 'gauss' or 'const'
    )
    """

    def __init__(self, soccfg=None, path='', prefix='AmplitudeRabiChevron', config_file=None, progress=None):
        super().__init__(soccfg=soccfg, path=path, prefix=prefix, config_file=config_file, progress=progress)

    def acquire(self, progress=False, debug=False):
        q_ind = self.cfg.expt.qubit
        for key, value in self.cfg.device.readout.items():
            if isinstance(value, list):
                self.cfg.device.readout.update({key: value[q_ind]})
        for key, value in self.cfg.device.qubit.items():
            if isinstance(value, list):
                self.cfg.device.qubit.update({key: value[q_ind]})
            elif isinstance(value, dict):
                for key2, value2 in value.items():
                    for key3, value3 in value2.items():
                        if isinstance(value3, list):
                            value2.update({key3: value3[q_ind]})                                
        
        if 'sigma_test' not in self.cfg.expt:
            self.cfg.expt.sigma_test = self.cfg.device.qubit.pulses.pi_ge.sigma

        freqpts = self.cfg.expt["start_f"] + self.cfg.expt["step_f"]*np.arange(self.cfg.expt["expts_f"])
        data={"xpts":[], "freqpts":[], "avgi":[], "avgq":[], "amps":[], "phases":[]}
        adc_ch = self.cfg.hw.soc.adcs.readout.ch[self.cfg.device.readout.adc]

        self.cfg.expt.start = self.cfg.expt.start_gain
        self.cfg.expt.step = self.cfg.expt.step_gain
        self.cfg.expt.expts = self.cfg.expt.expts_gain
        for freq in tqdm(freqpts):
            self.cfg.device.qubit.f_ge = freq
            amprabi = AmplitudeRabiProgram(soccfg=self.soccfg, cfg=self.cfg)
        
            xpts, avgi, avgq = amprabi.acquire(self.im[self.cfg.aliases.soc], threshold=None, load_pulses=True, progress=False, debug=debug)
        
            avgi = avgi[adc_ch][0]
            avgq = avgq[adc_ch][0]
            amps = np.abs(avgi+1j*avgq) # Calculating the magnitude
            phases = np.angle(avgi+1j*avgq) # Calculating the phase        

            data["avgi"].append(avgi)
            data["avgq"].append(avgq)
            data["amps"].append(amps)
            data["phases"].append(phases)
        
        data['xpts'] = xpts
        data['freqpts'] = freqpts
        for k, a in data.items():
            data[k] = np.array(a)
        self.data=data
        return data

    def analyze(self, data=None, fit=True, **kwargs):
        if data is None:
            data=self.data
        pass

    def display(self, data=None, fit=True, **kwargs):
        if data is None:
            data=self.data 
        
        x_sweep = data['xpts']
        y_sweep = data['freqpts']
        avgi = data['avgi']
        avgq = data['avgq']

        plt.figure(figsize=(10,8))
        plt.subplot(211, title="Amplitude Rabi", ylabel="Frequency [MHz]")
        plt.imshow(
            np.flip(avgi, 0),
            cmap='viridis',
            extent=[x_sweep[0], x_sweep[-1], y_sweep[0], y_sweep[-1]],
            aspect='auto')
        plt.colorbar(label='I [ADC level]')
        plt.clim(vmin=None, vmax=None)
        # plt.axvline(1684.92, color='k')
        # plt.axvline(1684.85, color='r')

        plt.subplot(212, xlabel="Gain [dac units]", ylabel="Frequency [MHz]")
        plt.imshow(
            np.flip(avgq, 0),
            cmap='viridis',
            extent=[x_sweep[0], x_sweep[-1], y_sweep[0], y_sweep[-1]],
            aspect='auto')
        plt.colorbar(label='Q [ADC level]')
        plt.clim(vmin=None, vmax=None)
        
        if fit: pass

        plt.tight_layout()
        plt.show()
        
    def save_data(self, data=None):
        print(f'Saving {self.fname}')
        super().save_data(data=data)