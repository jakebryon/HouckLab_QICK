#%%
import WorkingProjects.Tantalum_fluxonium_escher.Client_modules.PythonDrivers.LS370 as lk
import pyvisa
import time
import numpy as np
import os

rm = pyvisa.ResourceManager()
LS370_connection = rm.open_resource('GPIB0::12::INSTR')
lakeshore = lk.Lakeshore370(LS370_connection)


foldername = r'Z:\TantalumFluxonium\Data\2024_04_12_BF2_cooldown_9\WTF\CalibrateThermometer'
filename_temp = foldername + '\\' + time.strftime('%Y.%m.%d_%H.%M.%S_', time.localtime()) + 'temp.csv'
filename_res = foldername + '\\' + time.strftime('%Y.%m.%d_%H.%M.%S_', time.localtime()) + 'res.csv'

NUM_PTS = 15 # Number of points at each temperature


temps_list = [8, 10, 15, 20, 30, 40, 50, 60]
#temps_list = [10, 15]
temps_meas_list = []
res_meas_list = []

for temp in temps_list:
    lakeshore.set_temp(temp)
    print('Current temperature: %.5f K' % float(lakeshore.get_temp(7)))
    time.sleep(60)

    for i in range(NUM_PTS):
        print('Current temperature: %.5f K' % float(lakeshore.get_temp(7)))
        temps_meas_list.append(float(lakeshore.get_temp(7)))
        print('Current resistance: %.1f Ohm' % float(lakeshore.get_resistance(8)))
        res_meas_list.append(float(lakeshore.get_resistance(8)))
        os.makedirs(os.path.dirname(filename_temp), exist_ok=True) # Create necessary directories if the file path does not exist
        np.savetxt(filename_temp, np.array(temps_meas_list), delimiter = ',', fmt='%.5f')
        np.savetxt(filename_res, np.array(res_meas_list), delimiter=',', fmt='%.5f')
        time.sleep(60)

#%%
#
lakeshore.set_temp(0)