import json
import os
import re

from PyQt5.QtWidgets import QWidget, QGridLayout, QPushButton, QComboBox, QLineEdit, QVBoxLayout, QLabel, QFormLayout
from PyQt5.QtCore import pyqtSignal, pyqtSlot, qInfo, qWarning

from MasterProject.Client_modules.CoreLib.socProxy import makeProxy

class AccountTabWidget(QWidget):

    ### pyQt signals

    # argument is name of account
    account_created = pyqtSignal(str)

    # argument is name of account
    account_loaded = pyqtSignal(str)

    # argument is ip_address
    rfsoc_connected = pyqtSignal(str)

    rfsoc_disconnected = pyqtSignal()

    def __init__(self, parent):
        super().__init__(parent=parent)

        # connect signals to slots
        self.account_created.connect(self.__set_account_list_dropdown)
        self.account_loaded.connect(self.__update_on_load_account)

        self.account_settings_widget = None
        self.account_settings_form_widget = None
        self.current_account = 'default'

        self.rfsoc_is_connected = False

        self.root_dir = os.getcwd()
        self.config_dir = os.path.join(self.root_dir, 'config')
        self.account_dir = os.path.join(self.config_dir, 'accounts')

        self.__intiUI()

        self.__create_account_settings_widget()
        self.__load_default_account()

    def __intiUI(self):

        account_tab_layout = QGridLayout(self)
        self.setLayout(account_tab_layout)
        # self.__create_account_settings_widget()

        spacer_widget = QWidget(self)
        account_tab_layout.addWidget(spacer_widget, 2, 0)

        # panel for connecting to rfsoc
        self.__create_rfsoc_widget()

        # panel for saving and loading accounts
        self.__create_save_load_widget()

    def __create_rfsoc_widget(self):
        # buttons to connect to the rfsoc

        account_tab_layout = self.layout()
        rfsoc_connection_widget = QWidget(self)
        account_tab_layout.addWidget(rfsoc_connection_widget, 1, 0)

        rfsoc_connection_layout = QGridLayout(rfsoc_connection_widget)

        # display current status
        self.rfsoc_status_label = QLabel(f'Current status: <span style="color: red;">not connected</span>', rfsoc_connection_widget)
        rfsoc_connection_layout.addWidget(self.rfsoc_status_label, 0, 0, 1, 2)

        # connect
        connect_to_rfsoc_button = QPushButton('Connect')
        rfsoc_connection_layout.addWidget(connect_to_rfsoc_button, 1, 0)
        connect_to_rfsoc_button.clicked.connect(self.connect_to_rfsoc)

        disconnect_from_rfsoc_button = QPushButton('Disconnect')
        rfsoc_connection_layout.addWidget(disconnect_from_rfsoc_button, 1, 1)
        disconnect_from_rfsoc_button.clicked.connect(self.__disconnect_from_rfsoc)


    def __create_save_load_widget(self):

        account_tab_layout = self.layout()

        # saving and loading accounts
        save_load_account_widget = QWidget(self)
        account_tab_layout.addWidget(save_load_account_widget, 0, 1)

        save_load_account_layout = QGridLayout(save_load_account_widget)

        # load account button
        load_account_button = QPushButton('Load account')
        save_load_account_layout.addWidget(load_account_button, 0, 0)

        self.account_drop_down = QComboBox(save_load_account_widget)
        save_load_account_layout.addWidget(self.account_drop_down, 0, 1)
        load_account_button.clicked.connect(lambda: self.__load(self.account_drop_down.currentText()))

        self.__set_account_list_dropdown()

        # save account button
        save_account_button = QPushButton('Save account')
        save_account_button.clicked.connect(self.__save)
        save_load_account_layout.addWidget(save_account_button, 1, 0)

        save_as_account_button = QPushButton('Save as new account')
        save_load_account_layout.addWidget(save_as_account_button, 2, 0)

        self.new_account_text_input = QLineEdit(f'{self.current_account} copy', save_load_account_widget)
        save_load_account_layout.addWidget(self.new_account_text_input, 2, 1)

        save_as_account_button.clicked.connect(lambda: self.__save_as(self.new_account_text_input.text()))

        # set default button
        set_default_button = QPushButton('Set current account as default')
        set_default_button.clicked.connect(self.__set_default_account)
        save_load_account_layout.addWidget(set_default_button, 3, 0)

    def __create_account_settings_widget(self):
        # widget to display account details
        self.account_settings_widget = QWidget(parent=self)

        self.current_account_label = QLabel(f'Current Account: {self.current_account}', self.account_settings_widget)

        account_details_layout = QVBoxLayout(self.account_settings_widget)

        account_details_layout.addWidget(self.current_account_label)

    def __update_account_settings_widget(self):

        self.current_account_label.setText(f'Current Account: {self.current_account}')

        account_details_layout = self.account_settings_widget.layout()

        if self.account_settings_form_widget is not None:
            account_details_layout.removeWidget(self.account_settings_form_widget)

        self.account_settings_form_widget = QWidget(parent=self.account_settings_widget)
        account_details_layout.addWidget(self.account_settings_form_widget)

        account_details_formlayout = QFormLayout(self.account_settings_form_widget)

        # dictionaries to map QLineEdit to parameter name it will change and vice versa
        self.name_to_line_edit = {}
        self.line_edit_to_name = {}

        # display account details
        for key, value in self.account_settings.items():
            if key not in ['default_account_name', 'account_name']:
                text_input = QLineEdit(f'{value}')
                text_input.setFixedWidth(200)

                self.name_to_line_edit[key] = text_input
                self.line_edit_to_name[text_input] = key
                account_details_formlayout.addRow(f'{key}:', text_input)

        account_tab_layout = self.layout()
        account_tab_layout.addWidget(self.account_settings_widget, 0, 0)



    def __load_default_account(self):
        '''
        Read default.json to find `default_account_name`, then set as the current account and load
        '''

        account_file_path = os.path.join(self.account_dir, f'default.json')

        with open(account_file_path, 'r') as f:
            default_settings = json.load(f)

        default_account_name = default_settings['default_account_name']
        self.__load(default_account_name)

    ########################################################################################################################
    #####################################  Signal functions for Account  ###################################################
    ########################################################################################################################

    @pyqtSlot(str)
    def __update_on_load_account(self):
        # update text box for save as button
        self.new_account_text_input.setText(f'{self.current_account} copy')
        # update settings display with loaded parameters
        self.__update_account_settings_widget()

    @pyqtSlot(str)
    def __set_account_list_dropdown(self):
        '''
        Search through the config/accounts directory to find all .json files representing accounts and list them in
        a drop down menu.
        :param account_drop_down: drop down menu object listing all accounts
        '''

        # clear current items
        self.account_drop_down.clear()

        # find all possible accounts
        account_file_regex = re.compile('(?P<accountName>.*).json')

        account_names = []
        for root, dirs, files in os.walk(self.account_dir):
            for file in files:
                match = account_file_regex.search(file)
                account_names.append(match.groupdict()['accountName'])

        for accountName in account_names:
            self.account_drop_down.addItem(accountName)

    def __load(self, account_name):
        self.current_account = account_name

        qInfo(f'Loading account {self.current_account}')
        account_file_path = os.path.join(self.account_dir, f'{self.current_account}.json')

        with open(account_file_path, 'r') as f:
            self.account_settings = json.load(f)

        self.account_loaded.emit(account_name)

    def __save(self):
        self.__save_as(self.current_account)

    def __save_as(self, new_account_name):

        # load settings from form into json
        if new_account_name == 'default':
            qWarning('Cannot overwrite default account')
            return

        json_data = {}

        for key, value in self.name_to_line_edit.items():
            parameter_value = value.text()
            json_data[key] = parameter_value

        json_data['account_name'] = new_account_name

        account_file_path = os.path.join(self.account_dir, f'{new_account_name}.json')

        # dump json to file
        qInfo(f'Saving to {new_account_name}')
        with open(account_file_path, 'w') as f:
            json.dump(json_data, f)

        # emit account created signal and load new account if new account is not the same as current one
        if not self.current_account == new_account_name:
            self.account_created.emit(new_account_name)
            self.__load(new_account_name)

    def __set_default_account(self):

        qInfo(f'Setting default account to {self.current_account}')

        # load default.json

        account_file_path = os.path.join(self.account_dir, 'default.json')

        # read json file
        with open(account_file_path, 'r') as f:
            json_data = json.load(f)

        # update default account name
        json_data['default_account_name'] = self.current_account

        # write json file
        with open(account_file_path, 'w') as f:
            json.dump(json_data, f)

    def connect_to_rfsoc(self):
        if self.rfsoc_is_connected:
            qWarning('RFSoC is already connected')
        else:
            ip_address = self.name_to_line_edit['ip_address'].text()
            self.rfsoc_status_label.setText(f'Current status: <span style="color: orange;">connecting to {ip_address} failed</span>')
            qInfo(f'Trying to connect to {ip_address}')
            self.rfsoc_connected.emit(ip_address)

    def __disconnect_from_rfsoc(self):
        if self.rfsoc_is_connected:
            ip_address = self.name_to_line_edit['ip_address'].text()
            self.rfsoc_status_label.setText(f'Current status: <span style="color: red;"> not connected</span>')
            qInfo(f'Disconnecting from {ip_address}')
            self.rfsoc_is_connected = False
            self.rfsoc_disconnected.emit()
        else:
            qWarning('RFSoC is already disconnected')


    @pyqtSlot(str, str)
    def rfsoc_connection_updated_handler(self, ip_address, status):
        '''
        signal handler for receiving rfsoc_connection_updated signal from main window. Used to determine if the
        connection was sucecssful or failed.
        '''
        if status == 'success':
            self.rfsoc_status_label.setText(f'Current status: <span style="color: green;">connected at {ip_address}</span>')
            qInfo(f'Connected to {ip_address}')
            self.rfsoc_is_connected = True
        elif status == 'failure':
            self.rfsoc_status_label.setText(f'Current status: <span style="color: red;">connection to {ip_address} failed</span>')
            self.rfsoc_is_connected = False