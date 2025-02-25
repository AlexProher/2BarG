import sys

from kivymd.uix.behaviors.toggle_behavior import MDToggleButton
from kivymd.uix.taptargetview import MDTapTargetView

import tabs_old

import numpy as np
import pandas as pd

from kivymd.app import MDApp
from kivymd.uix.button import MDRaisedButton, MDTextButton
from kivymd.uix.menu import MDDropdownMenu
from kivymd.uix.floatlayout import MDFloatLayout
from kivymd.uix.tab import MDTabsBase
from kivymd.uix.dialog import MDDialog
from kivymd.uix.chip import MDChip
from kivymd.uix.behaviors import HoverBehavior

from kivy.animation import Animation
from kivy.metrics import dp
from kivy.lang import Builder
from kivy.uix.image import Image

from easygui import diropenbox, fileopenbox, filesavebox

from kivy.core.window import Window
import os
import shutil

from matplotlib import pyplot as plt
from matplotlib.widgets import Cursor

import scipy.signal
from scipy.signal import find_peaks
from scipy import integrate

import plotly.graph_objects as go
from plotly.subplots import make_subplots

import csv

"""
    WELCOME!
    
    This is the main code of main:
        This is where all the magic happens. 
        The code written here (main_old.py) uses all other files as the following suggests:
        
            ->  tabs_old.py             The GUI in main uses Kivy & Kivymd, which are based on KV language. 
                                    "tabs_old.py" is a KV file that contains the design structure of main's GUI.
                                    
            ->  bancrofts_data.txt  Data file; is used in the dispersion correction calculation.
            
            ->  k_type.txt          Data file used for the calibration of a K type Thermocouple. 
                                    This is used only if thermal analysis is enabled.
                                    
            ->  defaults.TwoBarG        As the name implies, this is where all the settings & parameters of main   
                                    are saved.
    
    The first few classes are created solely for the GUI functioning, please ignore them as they 
    do not make any importance to the analysis algorithms.
    
    The two classes that should concern you, dear reader, are BarG and SignalProcessing. 
    
    BarG is the bridge between the actual GUI and the signal processing mechanisms: 
        every button that is pressed goes through BarG.
    
    SignalProcessing is as the name implies, responsible for the actual calculations made from the signals:
        Signal Cropping, auto correlation, dispersion correction, IR claibration and the actual calculations of 
        the physical properties that are of interst to us (stress, strain, forces, etc..).
     
    Have a blast!
    
    // Gregory Tzvi Gershanik, creator of main.
    
"""


class InfoTab(MDFloatLayout, MDTabsBase):
    pass


class ParametersTab(MDFloatLayout, MDTabsBase):
    pass


class SettingsTab(MDFloatLayout, MDTabsBase):
    pass


class MyChip(MDChip):
    icon_check_color = (0, 0, 0, 1)
    text_color = (0, 0, 0, 0.5)
    _no_ripple_effect = True

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def set_chip_bg_color(self, instance_chip, active_value: int):
        '''
            Will be called every time the chip is activated/deactivated.
            Sets the background color of the chip.
        '''

        self.md_bg_color = (
            (0, 0, 0, 0.4)
            if active_value
            else (
                self.theme_cls.bg_darkest
                if self.theme_cls.theme_style == "Light"
                else (
                    self.theme_cls.bg_light
                    if not self.disabled
                    else self.theme_cls.disabled_hint_text_color
                )
            )
        )

    def set_chip_text_color(self, instance_chip, active_value: int):
        Animation(
            color=(0, 0, 0, 1) if active_value else (0, 0, 0, 0.5), d=0.2
        ).start(self.ids.label)


class MyToggleButton(MDRaisedButton, MDToggleButton):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.background_down = "#607262"
        self.md_bg_color = (0.95, 0.88, 0.82, 1)
        self.background_normal = "#f4e3d1"


class HoverTextButton(HoverBehavior, MDTextButton):
    pass


class BarG(MDApp):

    def __init__(self, **kwargs):
        super().__init__()
        # of experiment: Compression or Tension (1 or -1 respectively).
        # Most experiments are Compression experiments, so the default will be 1.
        # This variable will change when pressing on the Compression (C) or Tension (T) buttons in the program.

        self.owd = os.getcwd()  # Original working directory
        self.poisson_ratio = 0.33
        self.mode = "compression"
        self.specimen_mode = "regular"
        self.num_of_experiments = 0
        self.bar_num = 2

        # Get the current (original) directory for os operations.  This string will be valuable when using
        # the "Change Path Folder" button. Used in set_path_input(self, path) functions.
        self.two_bar_g_path = os.getcwd()

        #   define default path input
        self.path_input = ""

        #   This function will create a matrix called "parameters",
        #   as well as define some needed variables.
        self.set_data()

        #   In the Parameters Menu, there is a dropdown bar to choose an experiment.
        #   This new list (experiment_menu_items) will contain the experiments.
        if not self.thermal_analysis:
            self.experiment_menu_items = [{"text": f"No Experiments Loaded",
                                        "viewclass": "OneLineListItem", "height": dp(54)}]
        else:
            self.experiment_menu_items = []

        #   sp (see "Signal Processing" class) will be used for... signal processing.
        self.sp = SignalProcessing()
        #   Cropping mode is set to automatic as default:
        self.sp_mode = "Automatic"
        self.auto_open_report = True

        #   Defines the spacing, prominence and Curve Smoothing values used in the signal processing algorithms.
        self.spacing = 60
        self.prominence_percent = 0.5
        self.smooth_value = 71
        self.about_dfl = "The Mechanics and Physics of high rate deformation and fracture is the central and historical research theme" \
                         " of the Dynamic Fracture Laboratory (DFL). The DFL was started within the Materials Mechanics Center in 1994" \
                         " by D. Rittel, to address specific issues in dynamic fracture mechanics and stress wave physics through a" \
                         " combined experimental-numerical approach." \
                         "\n\n" \
                         "Since then, the Dynamic Fracture Laboratory has been actively developing new tools and techniques to address" \
                         " these issues, while expanding its activity to other related and exciting new domains, such as soft matter" \
                         " mechanics and dental biomechanics, or dental engineering. Throughout our research, we never lose sight of" \
                         " the governing physics of the processes that we characterize and model."

        self.guide = """1. Using the "Set Path Folder" button, choose the folder you stored your experiment files at. The files should be numbered.
        2. Fill in the experiment's parameters on the left. Make sure to press Enter each time you enter a new value. 
        3. Choose your experiment mode (compression / tension) and your cropping mode (automatic or manual). 
        4. Choose which experiment to analyse using the "Choose Experiment button", or analyse all of them.
        """

    def set_data(self):
        """
            A simple function that groups all needed values to the "parameters" matrix and creates
            some variables that is needed for the control of the program.
        """
        data = self.txt_to_array("../ProgramFiles/defaults.TwoBarG", True)
        spec_diam = data[0]
        spec_length = data[1]
        bar_diameter = data[2]
        young_modulus = data[3]
        first_gage = data[4]
        second_gage = data[5]
        sound_velocity = data[6]
        gage_factor = data[7]
        bridge_tension = data[8]
        self.path_input = data[9]
        lod = data[10]
        if data[11] == "True":
            self.thermal_analysis = True
        if data[11] == "False":
            self.thermal_analysis = False

        self.parameters = [["Specimen Diameter", spec_diam],
                           ["Specimen Length", spec_length],
                           ["Bar Diameter", bar_diameter],
                           ["Young's Modulus", young_modulus],
                           ["First Gauge", first_gage],
                           ["Second Gauge", second_gage],
                           ["Sound Velocity", sound_velocity],
                           ["Gauge Factor", gage_factor],
                           ["Bridge Tension", bridge_tension],
                           ["Path", self.path_input],
                           ["Light or Dark", lod],
                           ["Thermal Analysis", self.thermal_analysis]]

        #   lod = Light Or Dark
        if lod == "Dark":
            self.light_or_dark = (0.2, 0.2, 0.2, 1)
            self.theme_cls.theme_style = "Dark"

        else:
            self.light_or_dark = (0.98, 0.976, 0.957, 1)

    def build(self):
        """
            This functions builds the actual GUI, and most of it is graphic configuration of themes, buttons and screens.
        """
        # Set color themes and colors:

        self.theme_cls.primary_palette = "Red"
        self.theme_cls.material_style = "M3"
        self.theme_cls.primary_hue = "A100"
        self.main_color = "#607262"
        self.pink = "#e5b9b0"
        self.beige = "#f4e3d1"
        self.white = "#faf9f4"

        self.text_font = "GOTHIC"

        self.icon = "2BarG_emblem.ico"

        Window.bind(on_request_close=self.on_request_close)

        return Builder.load_string(tabs_old.Tabs)

    def on_start(self):

        # Add the different Tabs
        self.root.ids.tabs.add_widget(InfoTab(title="INFO"))
        self.root.ids.tabs.add_widget(ParametersTab(title="PARAMETERS"))
        self.root.ids.tabs.add_widget(SettingsTab(title="SETTINGS"))

        # Make the startup tab the Main Tab
        self.root.ids.tabs.switch_tab("PARAMETERS", search_by="title")

        # Define the experiments menu items (in Signal Processing tab)

        self.experiments_menu = MDDropdownMenu(caller=self.root.ids.tabs.get_slides()[1].ids.experiment_chooser,
                                               items=self.experiment_menu_items,
                                               width_mult=3)

        if self.light_or_dark == (0.2, 0.2, 0.2, 1):
            self.root.ids.tabs.get_slides()[2].ids.dark_mode.active = True

        if self.thermal_analysis:
            self.root.ids.tabs.get_slides()[2].ids.thermal_analysis.active = True

        self.set_path_input(self.path_input)

    def on_tab_switch(self, instance_tabs, instance_tab, instance_tab_label, tab_text):
        instance_tab.ids.label = instance_tab_label

    def set_path_input(self, path):
        """
            This functions uses the chosen (or default) path given to the main program to do the following:
            The path folder chosen shall be one with raw experiment data in 'WFT' files,
            if this condition is not satisfied then this function will do nothing (can also mean that this function
            has already ran in the given path).
            If it is satisfied, then this function will convert the WFT files into FLT files using WFT2FLT.EXE
            and sort everything into experiments, divided by folders (EXP #1, EXP #2 ..)
            After everything is sorted, this function will create
            a dropdown menu of experiments in the Signal Processing menu, for further usage.
        """

        if self.thermal_analysis:
            #   If thermal analysis is desired, use the corresponding function for setting the path input.
            self.set_path_input_thermal(path)
        else:
            if path != "" and os.path.isdir(path):
                os.chdir(path)  # Run cmd through the given path.
                files = os.listdir(path)  # make a list of file names from the path directory

                '''
                    The following loop will check if the data files are in WFT format.
                    If so, a conversion to FLT file type will be made using the WFT2FLT.EXE program.   
                '''

                apply_WFT2FLT = False
                for file in files:
                    file_name, file_type = os.path.splitext(file)
                    file_type = file_type[1:]

                    if file_type == "WFT":
                        apply_WFT2FLT = True
                        break

                if "Exp #1" not in files:
                    # If there is at least one experiment folder then the
                    # WFT2FLT program has already been executed before,
                    # and there is no need to run it again.
                    # This condition can save startup time.

                    os.chdir(self.two_bar_g_path)  # Run cmd from this program's (main) path.

                    if apply_WFT2FLT:
                        WFT_exists = 1
                        WFT2FLT_path = shutil.copy("../ProgramFiles/WFT2FLTN.EXE", path)  # Copy the WFT2FLT program into the given path.
                        WFT2FLT_command_path = WFT2FLT_path + " -dir=."  # This is the full command that is used in the cmd.

                        os.chdir(path)  # Run cmd through the given path.
                        os.system(WFT2FLT_command_path)  # Run the WFT2FLT program using cmd.
                        os.remove(WFT2FLT_path)  # Remove the WFT2FLT.EXE file from the path.

                        files = os.listdir(path)
                        os.makedirs(path + '/' + "Original WFT Files")
                        for file in files:
                            file_name, file_type = os.path.splitext(file)
                            file_type = file_type[1:]
                            if file_type == "WFT":
                                shutil.move(path + "/" + file, path + '/' + "Original WFT Files")

                    else:
                        WFT_exists = 0

                    os.chdir(path)  # Run cmd through the given path.

                    files = os.listdir(path)
                    num_of_experiments = int((len(files) - WFT_exists) / 2)

                    #   Check if there is already an existing report in the path folder.
                    #   if so, don't include it in the experiments count.
                    for file in files:
                        file_name, file_type = os.path.splitext(file)
                        file_type = file_type[1:]
                        if file_type == "html":
                            num_of_experiments -= 1


                    experiments = []
                    exp_num = 0

                    while True:
                        # This loop creates the new directories based on the file types and divides the files
                        # into their newly created directory. It also renames them accordingly (incid, trans).
                        file = files[0]
                        file_name, file_type = os.path.splitext(files[0])
                        file_type = file_type[1:]

                        if file_type != "":

                            exp_num += 1
                            os.makedirs(path + '/' + "Exp #" + str(exp_num))

                            self.file_type = file_type

                            #   Name of the folder the file should be moved into:
                            directory = path + '/' + "Exp #" + str(exp_num) + '/' + file_type

                            if not os.path.isdir(directory):
                                # create the folder if it doesn't exist:
                                os.makedirs(directory)

                            #   Move the experiment files to the folder:
                            shutil.move(path + '/' + files[0], path + '/' + "Exp #" + str(exp_num) + '/' + file_type)
                            old_path = path + '/' + "Exp #" + str(exp_num) + '/' + file_type + '/' + files[0]
                            new_path = path + '/' + "Exp #" + str(exp_num) + '/' + file_type + '/' + "incid." + file_type
                            os.rename(old_path, new_path)
                            experiments.append(["Exp #" + str(exp_num), new_path])

                            shutil.move(path + '/' + files[1], path + '/' + "Exp #" + str(exp_num) + '/' + file_type)
                            old_path = path + '/' + "Exp #" + str(exp_num) + '/' + file_type + '/' + files[1]
                            new_path = path + '/' + "Exp #" + str(exp_num) + '/' + file_type + '/' + "trans." + file_type
                            os.rename(old_path, new_path)
                            experiments.append(["Exp #" + str(exp_num), new_path])

                            files = os.listdir(path)

                        else:
                            #   if the current file is a folder, remove it from the files list.
                            files.remove(file)

                        #   Search for remaining experiment files.
                        #   If there are no remaining experiment files,
                        #   the process is complete and the 'While' loop can be exited.
                        found_exp_files = False
                        for file in files:
                            file_name, file_type = os.path.splitext(file)
                            file_type = file_type[1:]

                            if file_type != "":
                                found_exp_files = True
                                break

                        if not found_exp_files:
                            break

                else:
                    # If there are already experiment directories, arranging has already been done.
                    # Thus, there are as many directories as experiments.

                    files = os.listdir(path + "/Exp #1")
                    for file in files:
                        #   The name of the folder inside the first experiment
                        #   will be the name of the file type that is used.
                        file_name, file_type = os.path.splitext(file)
                        file_type = file_type[1:]
                        if file_type == '':
                            self.file_type = file_name
                            break

                    exp_count = 0
                    files = os.listdir(path)
                    for file in files:
                        file_name, file_type = os.path.splitext(file)
                        file_type = file_type[1:]
                        if "Exp" == file.split(" ")[0]:
                            exp_count += 1

                    num_of_experiments = exp_count

                    for file in files:
                        file_name, file_type = os.path.splitext(file)
                        file_type = file_type[1:]
                        if file_type == "html":
                            num_of_experiments -= 1

                if num_of_experiments != 0:
                    # If the number of experiments is 0 (aka there are no experiments loaded),
                    # there is no reason to reconfigure the Drop - Down Choose Experiment menu.
                    # Configure the "Choose Experiment" button's menu items.
                    self.num_of_experiments = num_of_experiments
                    self.experiment_menu_items = [{
                        "text": f"Experiment {i + 1}",
                        "viewclass": "OneLineListItem", "height": dp(54),
                        "on_release": lambda x=i + 1: self.use_experiment(x),
                    } for i in range(num_of_experiments)]

                    # Configure the menu itself.
                    self.experiments_menu = MDDropdownMenu(caller=self.root.ids.tabs.get_slides()[1].ids.experiment_chooser,
                                                           items=self.experiment_menu_items,
                                                           pos_hint={"center_x": .5, "center_y": .5},
                                                           width_mult=2.1)

                elif num_of_experiments == 0:
                    self.experiment_menu_items = [{"icon": "flask",
                                                   "text": "No Experiments Loaded",
                                                   "viewclass": "OneLineListItem",
                                                   "height": dp(54)}]

                    # Configure the menu itself.
                    self.experiments_menu = MDDropdownMenu(caller=self.root.ids.tabs.get_slides()[1].ids.experiment_chooser,
                                                           items=self.experiment_menu_items,
                                                           pos_hint={"center_x": .5, "center_y": .5},
                                                           width_mult=2.1)

                #   Configure the needed parameters in the SignalProcessing class.
                self.sp.configure_parameters(self.parameters,
                                             self.path_input,
                                             self.poisson_ratio,
                                             self.prominence_percent,
                                             self.auto_open_report,
                                             self.smooth_value)

            else:
                #   if no path folder is selected, the list of experiments should be empty.
                self.experiment_menu_items = [{"icon": "flask",
                                               "text": "No Experiments Loaded",
                                               "viewclass": "OneLineListItem", "height": dp(54),
                                               "height": dp(54)}]

    def set_path_input_thermal(self, path):
        """
        Sets the path and converts WFT files to FLT if they exist.
        Since in Thermal Analysis the user manually chosses which file is which,
        no further file arranging is needed.
        """
        if path != "" and os.path.isdir(path):
            os.chdir(path)  # Run cmd through the given path.
            files = os.listdir(path)  # make a list of file names from the path directory

            '''
                The following loop will check if the data files are in WFT format.
                If so, a conversion to FLT file type will be made using the WFT2FLT.EXE program.   
            '''
            apply_WFT2FLT = False
            for file in files:
                file_name, file_type = os.path.splitext(file)
                file_type = file_type[1:]

                if file_type == "WFT":
                    apply_WFT2FLT = True
                    break

            if "Exp #1" not in files:
                # If there is at least one experiment folder then the WFT2FLT program has already been executed before,
                # and there is no need to run it again. This condition can save startup time.

                os.chdir(self.two_bar_g_path)  # Run cmd from this program's (main) path.

                if apply_WFT2FLT:
                    WFT_exists = 1
                    WFT2FLT_path = shutil.copy("../ProgramFiles/WFT2FLTN.EXE", path)  # Copy the WFT2FLT program into the given path.
                    WFT2FLT_command_path = WFT2FLT_path + " -dir=."  # This is the full command that is used in the cmd.

                    os.chdir(path)  # Run cmd through the given path.
                    os.system(WFT2FLT_command_path)  # Run the WFT2FLT program using cmd.
                    os.remove(WFT2FLT_path)  # Remove the WFT2FLT.EXE file from the path.

                    files = os.listdir(path)
                    os.makedirs(path + '/' + "Original WFT Files")
                    for file in files:
                        file_name, file_type = os.path.splitext(file)
                        file_type = file_type[1:]
                        if file_type == "WFT":
                            shutil.move(path + "/" + file, path + '/' + "Original WFT Files")

                if file_type != "WFT":
                    self.file_type = file_type
                else:
                    self.file_type = "FLT"

    def change_path_input(self):
        # This functions uses easygui's directory chooser and sets the given path into the program.
        #   changes the path input to a new path given by user's input text
        #   opens the file browser
        try:
            path = diropenbox()

            if path != "":

                os.chdir(path)  # Run cmd through the given path.
                files = os.listdir(path)  # make a list of file names from the path directory

                #   These are the only file types accepted by main
                valid_file_types = ["WFT", "FLT", "txt", "xlsx", "csv"]

                #   Search for files that are not acceptable:
                invalid_folder = False
                for file in files:

                    #   Folder MUST be empty of irrelevant files for proper analysis of data.

                    file_name, file_type = os.path.splitext(file)
                    file_type = file_type[1:]

                    if file_type not in valid_file_types:
                        invalid_folder = True

                if not invalid_folder or "Exp #1" in files:
                    self.path_input = path
                    self.set_path_input(path)
                    self.parameters[9][1] = self.path_input

                else:
                    self.error_message()

        except:
            pass

    def select_data_file(self, signal):
        """
        In Thermal Analysis, the user chooses which file is which.
        'signa;' can be INCID, TRANS, IR EXP, IR CAL or TC CAL.
        This function will use the selected file and rename it accordingly
        """
        os.chdir(self.path_input)  # Run cmd through the given path.
        if self.path_input != "":
            file = fileopenbox()
            new_path = self.path_input + '/' + signal + "." + self.file_type

            os.rename(file, new_path)

    def update_parameters(self, data_type, index, instance):
        #   Update the parameter of given text field.
        #   "instance" is the text field itself from the Parameters tab.
        if instance.text != '' and instance.text != " ":
            if data_type == "experiment" or data_type == "specimen":
                if index == 3:
                    #   Index 3 is Young Modulus, which is given in Giga - Pascals:
                    self.parameters[index][1] = float(instance.text) * (10**9)
                else:
                    self.parameters[index][1] = float(instance.text)

            if data_type == "spacing":
                self.spacing = int(round(float(instance.text)))

            if data_type == "prominence":
                self.prominence_percent = int(round(float(instance.text))) / 100


        boo = True
        for i in range(len(self.parameters)-1):
            if self.parameters[i][1] != 42:
                boo = False
                break

        if boo:
            text = """The answer you were looking for is the answer for the ultimate question of LIFE, the UNIVERSE and 
                EVERYTHING. """
            self.boo_dialog = MDDialog(title='42',
                                       text=text,
                                       size_hint=(0.2, 1))
            self.boo_dialog.open()

    def set_parameters_as_default(self, obj):
        # Saves the current parameters (experiment_data, specimen_data ..) in the defaults file.

        self.change_defaults_txt(self.parameters, "../ProgramFiles/defaults.TwoBarG", self.owd)
        self.root.ids.tabs.get_slides()[1].ids.spec_diam.helper_text = "Default value: {}".format(self.parameters[0][1])
        self.root.ids.tabs.get_slides()[1].ids.spec_length.helper_text = "Default value: {}".format(self.parameters[1][1])
        self.root.ids.tabs.get_slides()[1].ids.bar_diameter.helper_text = "Default value: {}".format(self.parameters[2][1])
        self.root.ids.tabs.get_slides()[1].ids.young_modulus.helper_text = "Default value: {}".format(self.parameters[3][1]/1e9)
        self.root.ids.tabs.get_slides()[1].ids.first_gage.helper_text = "Default value: {}".format(self.parameters[4][1])
        self.root.ids.tabs.get_slides()[1].ids.second_gage.helper_text = "Default value: {}".format(self.parameters[5][1])
        self.root.ids.tabs.get_slides()[1].ids.sound_velocity.helper_text = "Default value: {}".format(self.parameters[6][1])
        self.root.ids.tabs.get_slides()[1].ids.gage_factor.helper_text = "Default value: {}".format(self.parameters[7][1])
        self.root.ids.tabs.get_slides()[1].ids.bridge_tension.helper_text = "Default value: {}".format(self.parameters[8][1])

    def save_parameters_file(self, obj):
        # Saves the current parameters (experiment_data, specimen_data ..) in the defaults file.
        fname = filesavebox(default='2BarG_Parameter_Preset.twobarg')
        if fname is not None:

            if not os.path.exists(fname):
                f = open(fname, "x")
            else:
                f = open(fname, 'r+')

            f.truncate(0)
            s = ""
            for x in self.parameters:
                s += str(x[1]) + "\n"
            s += "\n"  # For some reason, there is a problem without a new line at the end of the defaults file.
            f.write(s)
            f.close()

    def load_parameters_file(self):
        file = fileopenbox()
        try:
            data = self.txt_to_array(file)
            if data != -1:
                for i in range(len(self.parameters)):
                    self.parameters[i][1] = data[i]
        except:
            pass

    def use_experiment(self, exp_num):
        # When an experiment is choosen, new buttons will appear, this function defines them.

        instance_text = "Experiment " + str(exp_num)
        if self.experiment_menu_items != [{"text": f"No Experiments Loaded"}]:
            # Note that if this expression is False, then no experiments were loaded,
            # thus there is no experiment to choose. In that case, this function does nothing.

            # Dismiss the dropdown menu.
            self.experiments_menu.dismiss()

            #   Start analysis process:
            self.call_sp_analyze(exp_num, "edit")

    def call_sp_analyze(self, exp_num, purpose):
        """
            Calls Signal Processing's "analyze" function after
            loading the files and checking they are valid for use.

            purpose:        Analyze one experiment or all of them.
            returns nothing.
        """
        #   Get current smooth value from slider on settings tab:
        self.smooth_value = self.root.ids.tabs.get_slides()[2].ids.smooth_slider.value

        try:
            # load the experiment files and check if they are valid for further analysis:
            valid_files = self.sp.load_experiments(exp_num, self.path_input,  self.mode,
                                                   self.specimen_mode, self.file_type, self.thermal_analysis)

            if valid_files:
                print("Loaded files are valid. \nConfiguring parameters...")
                try:
                    self.sp.configure_parameters(self.parameters, self.path_input, self.poisson_ratio,
                                                 self.prominence_percent, self.auto_open_report, self.smooth_value)
                except:
                    print("Parameter configuration FAILED.")
                    self.error_message()

                #   Analyze experiment files:
                valid = self.sp.analyze(purpose, exp_num, self.sp_mode, self.parameters, self.spacing, self.bar_num)

                if not valid:
                    print("Analysis Failed")
                    self.error_message()

            else:
                print("Loaded files are not valid.")
                self.error_message()

        except Exception as e:
            print("Something went wrong, please observe the following error:")
            print(e)
            self.error_message()

    def show_data(self, obj):
        #   opens a dialog with the current parameters

        #   dialog_text = "\nDefault Path = " + self.path_input

        dialog_text = "\n"
        dialog_text += str(self.parameters[0][0]) + " = " + str(self.parameters[0][1] * 1e3) + " [mm]" + "\n"
        dialog_text += str(self.parameters[1][0]) + " = " + str(self.parameters[1][1] * 1e3) + " [mm]" + "\n"
        dialog_text += str(self.parameters[2][0]) + " = " + str(self.parameters[2][1] * 1e3) + " [mm]" + "\n"
        dialog_text += str(self.parameters[3][0]) + " = " + str(self.parameters[3][1] * 1e-9) + " [GPa]" + "\n"
        dialog_text += str(self.parameters[4][0]) + " = " + str(self.parameters[4][1]) + " [m]" + "\n"
        dialog_text += str(self.parameters[5][0]) + " = " + str(self.parameters[5][1]) + " [m]" + "\n"
        dialog_text += str(self.parameters[6][0]) + " = " + str(self.parameters[6][1]) + " [m/s]" + "\n"
        dialog_text += str(self.parameters[7][0]) + " = " + str(self.parameters[7][1]) + "\n"
        dialog_text += str(self.parameters[8][0]) + " = " + str(self.parameters[8][1]) + " [V]" + "\n\n"

        self.tap_target_view = MDTapTargetView(
            widget=self.root.ids.tabs.get_slides()[1].ids.show_parameters,
            title_text="Current Parameters",
            title_text_size="30sp",
            description_text=dialog_text,
            description_text_size="18sp",
            outer_circle_color=(0.898, 0.725, 0.69),
            title_text_color=(0.376, 0.447, 0.38, 1),
            description_text_color=(0.376, 0.447, 0.38, 1),
            widget_position="right",
            outer_radius=dp(290),
            cancelable=True,
        )

        self.tap_target_start()

    def tap_target_start(self):
        if self.tap_target_view.state == "close":
            self.tap_target_view.start()
        else:
            self.tap_target_view.stop()

    def close_dialog(self, obj):
        #   closes the parameter dialog
        self.dialog.dismiss()

    def analyse_all_experiments(self):
        self.sp.configure_parameters(self.parameters, self.path_input, self.poisson_ratio, self.prominence_percent,
                                     self.auto_open_report, self.smooth_value)
        if self.num_of_experiments > 1:
            errors = []

            for i in range(self.num_of_experiments):

                try:
                    self.sp.load_experiments(i + 1, self.path_input, self.mode, self.specimen_mode, self.file_type, self.thermal_analysis)
                    valid = self.sp.analyze("all", i + 1, self.sp_mode, self.parameters, self.spacing, self.bar_num)
                    if not valid:
                        errors.append(i + 1)
                except Exception as e:
                    errors.append(i + 1)
                    print(e)
            if len(errors) != 0:
                # open a dialog if some experiments were corrupt.
                text = "There seem to be some problems with the following experiments: \n" \
                       + (" " * (26 // len(errors))) + str(errors).strip('[]') + "\n" \
                                                                                 "Please make sure that: \n\n" \
                                                                                 "¤   Your file type is supported\n" \
                                                                                 "¤   The correct mode is selected \n" \
                                                                                 "¤   All parameters are valid\n"

                dialog = MDDialog(title="Some experiments didn't make it.",
                                  text=text,
                                  size_hint=(0.26, 1),
                                  radius=[20, 7, 20, 7])
                dialog.open()

        else:
            self.call_sp_analyze(1, "edit")

    def error_message(self, text=""):
        """
        Opens the "Something went wrong" popup.
        """
        if text == "":
            text = "Please make sure that: \n\n" \
               "¤   Path folder is empty of \n" \
               "      irrelevant files.\n" \
               "¤   Your file type is supported\n" \
               "¤   The correct mode is selected \n" \
               "¤   All parameters are valid\n" \
               "¤   Curve smoothing is \n" \
               "      appropriate\n" \


        dialog = MDDialog(title='Something went wrong.',
                          text=text,
                          size_hint=(0.3, 1),
                          radius=[20, 7, 20, 7])
        dialog.open()

    def txt_to_array(self, fileName, startup=False):
        fileObj = open(fileName, "r")  # opens the file in read mode
        words = fileObj.read().splitlines()  # puts the file into an array
        fileObj.close()
        succus = True
        for i in range(len(words)):
            try:
                words[i] = float(words[i])

            except Exception as e: print(e)

        if succus:
            return words
        else:
            return -1

    def change_defaults_txt(self, data, filename, owd):
        os.chdir(owd)
        if not os.path.exists(owd+"/"+filename):
            f = open(filename, "x")
        else:
            f = open(filename, 'r+')

        f.truncate(0)
        s = ""
        for x in data:
            s += str(x[1]) + "\n"
        s += "\n"       # For some reason, there is a problem without a new line at the end of the defaults file.
        f.write(s)
        f.close()

    def change_auto_open_report(self):
        if not self.auto_open_report:
            self.auto_open_report = True
        else:
            self.auto_open_report = False

    def change_bar_num(self):
        if self.bar_num == 1:
            self.bar_num = 2
        else:
            self.bar_num = 1

    def change_thermal_analysis(self):
        active = self.root.ids.tabs.get_slides()[2].ids.thermal_analysis.active

        if active:
            self.thermal_analysis = True
            #   Replace the "Analyze." button's function to directly analyze the only experiment that's loaded.
            #   (in Thermal Analysis only one experiment is loaded at a time).
            self.root.ids.tabs.get_slides()[1].ids.experiment_chooser.on_release = lambda: self.use_experiment(1)

            #   Make the Thermal Analysis buttons visible & active:
            self.root.ids.tabs.get_slides()[1].ids.INCID.disabled = False
            self.root.ids.tabs.get_slides()[1].ids.INCID.opacity = 1
            self.root.ids.tabs.get_slides()[1].ids.TRANS.disabled = False
            self.root.ids.tabs.get_slides()[1].ids.TRANS.opacity = 1
            self.root.ids.tabs.get_slides()[1].ids.IR_EXP.disabled = False
            self.root.ids.tabs.get_slides()[1].ids.IR_EXP.opacity = 1
            self.root.ids.tabs.get_slides()[1].ids.IR_CAL.disabled = False
            self.root.ids.tabs.get_slides()[1].ids.IR_CAL.opacity = 1
            self.root.ids.tabs.get_slides()[1].ids.TC_CAL.disabled = False
            self.root.ids.tabs.get_slides()[1].ids.TC_CAL.opacity = 1

        else:
            self.thermal_analysis = False
            self.root.ids.tabs.get_slides()[1].ids.experiment_chooser.on_release = lambda: self.experiments_menu.open()

            #   Make the Thermal Analysis buttons invisible & deactivated:
            self.root.ids.tabs.get_slides()[1].ids.INCID.disabled = True
            self.root.ids.tabs.get_slides()[1].ids.INCID.opacity = 0
            self.root.ids.tabs.get_slides()[1].ids.TRANS.disabled = True
            self.root.ids.tabs.get_slides()[1].ids.TRANS.opacity = 0
            self.root.ids.tabs.get_slides()[1].ids.IR_EXP.disabled = True
            self.root.ids.tabs.get_slides()[1].ids.IR_EXP.opacity = 0
            self.root.ids.tabs.get_slides()[1].ids.IR_CAL.disabled = True
            self.root.ids.tabs.get_slides()[1].ids.IR_CAL.opacity = 0
            self.root.ids.tabs.get_slides()[1].ids.TC_CAL.disabled = True
            self.root.ids.tabs.get_slides()[1].ids.TC_CAL.opacity = 0

        self.parameters[11][1] = self.thermal_analysis
        self.change_defaults_txt(self.parameters, "../ProgramFiles/defaults.TwoBarG", self.owd)

    def change_theme(self):
        active = self.root.ids.tabs.get_slides()[2].ids.dark_mode.active
        if active:
            self.theme_cls.theme_style = "Dark"
            self.light_or_dark = (0.2, 0.2, 0.2, 1)
            tab_list = self.root.ids.tabs.get_slides()
            tab_list[0].add_widget(Image(source="images/2BarG_white.png", pos_hint={"center_x": 0.5, "center_y": 0.8}))

            self.parameters[10][1] = "Dark"

        else:
            self.theme_cls.theme_style = "Light"
            self.light_or_dark = (0.98, 0.976, 0.957, 1)
            tab_list = self.root.ids.tabs.get_slides()
            tab_list[0].add_widget(Image(source="images/2BarG_emblem.png", pos_hint={"center_x": 0.5, "center_y": 0.8}))

            self.parameters[10][1] = "Light"

        for i in range(3):
            tab_list[i].md_bg_color = self.light_or_dark

        self.change_defaults_txt(self.parameters, "../ProgramFiles/defaults.TwoBarG", self.owd)

    def on_request_close(self, *args):
        os.chdir(self.owd + "/Reports")
        files = os.listdir(self.owd + "/Reports")

        for file in files:
            file_name, file_type = os.path.splitext(file)
            file_type = file_type[1:]

            if file_type == "html":
                os.remove(file)

        self.stop()

    def removes_marks_all_chips(self, selected_instance_chip):
        for instance_chip in self.ids.chip_box.children:
            if instance_chip != selected_instance_chip:
                instance_chip.active = False

    def open_curve_smoothing_dialog(self):
        dialog_text = """
            A filter (smoothing) is applied on 
            a separate copy of the raw signals.
            This is done to filter out experiment
            noises and get a better estimate
            of the signal's peaks. 
            
            The "Curve Smoothing" parameter 
            is the "window length" when 
            applying a Savitzky-Golay filter 
            upon the raw signals. 
            
            As a rule of thumb:
            the higher the window length,
            the smoother the signal. 
             
            """

        self.curve_smoothing_tap_target = MDTapTargetView(
            widget=self.root.ids.tabs.get_slides()[2].ids.curve_smooth_info,
            title_text="       Curve Smoothing",
            title_text_size="30sp",
            description_text=dialog_text,
            description_text_size="18sp",
            title_text_color=(0.376, 0.447, 0.38, 1),
            description_text_color=(0.376, 0.447, 0.38, 1),
            widget_position="top",
            target_radius=dp(0),
            outer_radius=dp(0),
            cancelable=True,
        )

        self.curve_smoothing_tap_target_start()

    def curve_smoothing_tap_target_start(self):
        if self.curve_smoothing_tap_target.state == "close":
            self.curve_smoothing_tap_target.start()
        else:
            self.curve_smoothing_tap_target.stop()


class SignalProcessing:

    def __init__(self):
        self.path_input = ""
        self.mode = "compression"
        self.exp_num = 1
        self.damp_f = 10 ** (-3)  # New variable to be used in the future (future...future......future...)

        self.vcc_incid = []
        self.vcc_trans = []

        self.time_incid = []
        self.volt_incid = []

        self.time_trans = []
        self.volt_trans = []

        self.time_reflected = []
        self.vcc_reflected = []

        self.og_time_incid = []
        self.og_vcc_incid = []
        self.og_time_trans = []
        self.og_vcc_trans = []

    def configure_parameters(self, parameters, path_input, poisson_ratio, prominence_percent, auto_open_report, smooth_value):
        """
            Configures all given parameters into the Signal Processing Class
        """
        self.path_input = path_input
        self.poisson_ratio = poisson_ratio

        self.spec_diam = float(parameters[0][1])
        self.specimen_length = float(parameters[1][1])
        self.bar_diameter = float(parameters[2][1])
        self.young_modulus = float(parameters[3][1])
        self.first_gage = float(parameters[4][1])
        self.second_gage = float(parameters[5][1])
        self.sound_velocity = float(parameters[6][1])
        self.gage_factor = float(parameters[7][1])
        self.bridge_tension = float(parameters[8][1])

        self.prominence_percent = prominence_percent
        self.auto_open_report = auto_open_report
        self.smooth_value = smooth_value

        print("Parameter configuration CMPLT.")

    def load_experiments(self, exp_num, path_input, mode, specimen_mode, file_type, thermal_analysis):
        """
            This function takes data from the loaded experiment and
            makes it into two voltage and two time vectors:
            incident & transmitted.

            It keeps an "og" version - an original version of the vectors
             to be untouched by any processing that follows.
        """
        self.vcc_incid = []
        self.vcc_trans = []

        self.time_incid = []
        self.volt_incid = []

        self.time_trans = []
        self.volt_trans = []

        self.time_reflected = []
        self.vcc_reflected = []

        self.og_time_incid = []
        self.og_vcc_incid = []
        self.og_time_trans = []
        self.og_vcc_trans = []

        self.mode = mode
        self.specimen_mode = specimen_mode
        self.thermal_analysis = thermal_analysis
        if thermal_analysis:

            self.time_IR_EXP = []
            self.volt_IR_EXP = []
            self.time_IR_CAL = []
            self.volt_IR_CAL = []
            self.time_TC_CAL = []
            self.volt_TC_CAL = []

        os.chdir(path_input)  # Run cmd through the given path.

        if file_type == "csv" or file_type == "xlsx" or file_type == "txt" or file_type == "FLT":
            valid_files = True
        else:
            valid_files = False

        if valid_files:
            self.exp_num = exp_num

            exp_path_incid = path_input + "/Exp #" + str(self.exp_num) + "/" + file_type + "/incid." + file_type
            exp_path_trans = path_input + "/Exp #" + str(self.exp_num) + "/" + file_type + "/trans." + file_type

            if thermal_analysis:
                exp_path_incid = path_input + "/incid." + file_type
                exp_path_trans = path_input + "/trans." + file_type
                exp_path_IR_EXP = path_input + "/IR_EXP." + file_type
                exp_path_IR_CAL = path_input + "/IR_CAL." + file_type
                exp_path_TC_CAL = path_input + "/TC_CAL." + file_type

            if file_type == "FLT" or file_type == "txt":
                #   Incident
                vector_file = open(exp_path_incid)
                vector_incid = np.loadtxt(vector_file,
                                    delimiter='\t',
                                    skiprows=2)
                vector_file.close()

                # Transmitted
                vector_file = open(exp_path_trans)
                vector_trans = np.loadtxt(vector_file,
                                    delimiter='\t',
                                    skiprows=2)
                vector_file.close()

                if thermal_analysis:
                    #   IR EXP
                    vector_file = open(exp_path_IR_EXP)
                    vector_IR_EXP = np.loadtxt(vector_file,
                                              delimiter='\t',
                                              skiprows=2)
                    vector_file.close()

                    # IR CAL
                    vector_file = open(exp_path_IR_CAL)
                    vector_IR_CAL = np.loadtxt(vector_file,
                                              delimiter='\t',
                                              skiprows=2)
                    vector_file.close()

                    # TC CAL
                    vector_file = open(exp_path_TC_CAL)
                    vector_TC_CAL = np.loadtxt(vector_file,
                                               delimiter='\t',
                                               skiprows=2)
                    vector_file.close()

            elif file_type == "csv":
                vector_file = open(exp_path_incid)
                vector_csv = csv.reader(vector_file)
                vector_incid = []

                for row in vector_csv:
                    vector_incid.append(row)
                vector_file.close()

                vector_file = open(exp_path_trans)
                vector_csv = csv.reader(vector_file)
                vector_trans = []
                for row in vector_csv:
                    vector_trans.append(row)

                if thermal_analysis:
                    vector_file = open(exp_path_IR_EXP)
                    vector_csv = csv.reader(vector_file)
                    vector_IR_EXP = []

                    for row in vector_csv:
                        vector_IR_EXP.append(row)
                    vector_file.close()

                    vector_file = open(exp_path_IR_CAL)
                    vector_csv = csv.reader(vector_file)
                    vector_IR_CAL = []
                    for row in vector_csv:
                        vector_IR_CAL.append(row)

                    vector_file = open(exp_path_TC_CAL)
                    vector_csv = csv.reader(vector_file)
                    vector_TC_CAL = []
                    for row in vector_csv:
                        vector_TC_CAL.append(row)

            elif file_type == "xlsx":
                vector_file = pd.read_excel(exp_path_incid)
                vector_incid = vector_file.values

                vector_file = pd.read_excel(exp_path_trans)
                vector_trans = vector_file.values

                if thermal_analysis:
                    vector_file = pd.read_excel(exp_path_IR_EXP)
                    vector_IR_EXP = vector_file.values

                    vector_file = pd.read_excel(exp_path_IR_CAL)
                    vector_IR_CAL = vector_file.values

                    vector_file = pd.read_excel(exp_path_TC_CAL)
                    vector_TC_CAL = vector_file.values
            else:
                vector = []

            for i in range(len(vector_incid)):
                try:
                    self.volt_incid.append(float(vector_incid[i][0]))
                    self.time_incid.append(float(vector_incid[i][1]))

                    self.volt_trans.append(float(vector_trans[i][0]))
                    self.time_trans.append(float(vector_trans[i][1]))

                    if thermal_analysis:
                        self.volt_IR_EXP.append(float(vector_IR_EXP[i][0]))
                        self.time_IR_EXP.append(float(vector_IR_EXP[i][1]))
                except:
                    continue
            if thermal_analysis:
                for i in range(len(vector_IR_CAL)):
                    try:
                        self.volt_IR_CAL.append(float(vector_IR_CAL[i][0]))
                        self.time_IR_CAL.append(float(vector_IR_CAL[i][1]))
                        self.volt_TC_CAL.append(float(vector_TC_CAL[i][0]))
                        self.time_TC_CAL.append(float(vector_TC_CAL[i][1]))
                    except:
                        continue

            # zeroing will make the two voltage vectors start from zero. See self.zeroing() for full explanation.
            self.zeroing()

            self.vcc_incid = [value for value in self.volt_incid]
            self.vcc_trans = [value for value in self.volt_trans]

            # Extract Time Per Point from the data.
            self.tpp = self.time_incid[1] - self.time_incid[0]

            # og = original. the following are defined as the original signals taken directly from the FLT files.
            # Saving them is necessary for resetting the signal cropping.
            self.og_time_incid = self.time_incid.copy()
            self.og_vcc_incid = self.vcc_incid.copy()
            self.og_time_trans = self.time_trans.copy()
            self.og_vcc_trans = self.vcc_trans.copy()

        return valid_files

    def analyze(self, purpose, exp_num, sp_mode, parameters, spacing, bar_num):
        """
            This function is the main function that calls all the
            processing and calculations done on the experiment files.

        purpose: Analyze one given experiment or all of the experiments
        sp_mode: Signal Proceesing mode: Manual / Automatic cropping
        return: True is analysis and report production was succusful, False otherwise.
        """
        self.spacing = spacing
        self.parameters = parameters
        if sp_mode == "Manual":
            """
                Manual cropping analysis
            """
            text = """Please Select 3 points: 
                   1) Incident's start, 2) Incident's end,  3) Reflected's start.
                    To delete the last selected point, press backspace. 
                    Once you are finished, please close this window."""

            x = self.manual_crop(self.og_time_incid, self.og_vcc_incid, text, "Incident")
            if x is None:
                #   If cropping process has been stopped by user or by program error, do nothing.
                return

            before_crop, after_crop, reflected_crop = float(x[0]), float(x[1]), float(x[2])

            text = """Please Select the Transmitted's starting point.
                    To delete the last selected point, press backspace.
                    Once you are finished, please close this window."""

            x = self.manual_crop(self.og_time_trans, self.og_vcc_trans, text, "Transmitted")
            if x is None:
                #   If cropping process has been stopped by user or by program error, do nothing.
                return

            #   we are only interested in the X point value (Time) for the signal cutting:
            transmitted_crop = float(x[0])

            self.crop_signal("before", before_crop, None)
            self.crop_signal("after", before_crop, after_crop)
            self.crop_signal("reflected", before_crop, after_crop, reflected_crop)
            self.crop_signal("transmitted", before_crop, after_crop, 0, transmitted_crop)

            if purpose == "edit":
                #   analyze only one given experiment
                self.dispertion_correction()
                #self.cross_correlate_signals()
                valid = self.final_calculation()
                if valid:
                    self.plotly_report(exp_num, parameters, bar_num)
                    return True
                else:
                    return False

            elif purpose == "all":
                # Analyze all experiments
                self.dispertion_correction()
                valid = self.final_calculation()
                if valid:
                    return True
                else:
                    return False

        elif sp_mode == "Automatic":
            """
                Automatic cropping analysis
            """
            print("Automatic Cropping Initialized...")
            if purpose == "edit":
                #   Analyze only one given experiment
                self.auto_crop()
                self.dispertion_correction()
                self.cross_correlate_signals()
                print("Initializing Final calculation...")
                valid = self.final_calculation()
                if valid:
                    print("Final calculation CMPLT; creating final report.")
                    self.plotly_report(exp_num, parameters, bar_num)
                    return True

                else:
                    return False

            elif purpose == "all":
                #   analyze all experiments
                self.auto_crop()
                self.dispertion_correction()
                self.cross_correlate_signals()

                valid = self.final_calculation()
                if valid:
                    self.plotly_report(exp_num, parameters, bar_num)
                    return True
                else:
                    return False

    def zeroing(self):
        """
                Not all experiments are born perfect, and some might be entirely offset.
                Thus, we can take the first value of each vector and move the entire
                vector upwards or downwards by that value
                (in an ideal experiment the first value will be 0).
        """

        zeroer = self.volt_incid[0]
        for i in range(len(self.volt_incid)):
            self.volt_incid[i] -= zeroer

        zeroer = self.volt_trans[0]
        for i in range(len(self.volt_trans)):
            self.volt_trans[i] -= zeroer

        if self.thermal_analysis:
            zeroer = self.volt_IR_EXP[0]
            for i in range(len(self.volt_IR_EXP)):
                self.volt_IR_EXP[i] -= zeroer

    def crop_signal(self, mode, before_crop, after_crop, reflected_crop=0.0, transmitted_crop=0.0):
        """
                This function crops the signal, first crop is from the left and second is from the right.
                In the second crop the function will return the time difference between
                the crops for further automatic cropping.

        """

        if mode == "before":
            for i in range(len(self.time_incid)):
                if self.time_incid[i] >= before_crop:

                    self.time_incid = self.time_incid[i:]
                    self.vcc_incid = self.vcc_incid[i:]

                    self.time_trans = self.time_trans[i:]
                    self.vcc_trans = self.vcc_trans[i:]

                    for j in range(len(self.time_incid)):
                        self.time_incid[j] -= before_crop
                        self.time_trans[j] -= before_crop

                    break

        elif mode == "after":
            for i in range(len(self.time_incid)):
                if self.time_incid[i] >= after_crop:
                    self.time_incid = self.time_incid[:i]
                    self.vcc_incid = self.vcc_incid[:i]

                    break
            align = self.time_incid[0]
            for j in range(len(self.time_incid)):
                self.time_incid[j] -= align

        elif mode == "reflected":
            time_period = after_crop

            for i in range(len(self.og_time_incid)):
                if self.og_time_incid[i] >= reflected_crop:
                    reflected_crop_idx = i
                    break

            tpp = self.og_time_incid[1] - self.og_time_incid[0]
            time_period = round(time_period / tpp)
            self.time_reflected = self.og_time_incid[reflected_crop_idx:reflected_crop_idx + time_period].copy()
            self.vcc_reflected = self.og_vcc_incid[reflected_crop_idx:reflected_crop_idx + time_period].copy()

            align = self.time_reflected[0]
            for j in range(len(self.time_reflected)):
                self.time_reflected[j] -= align

        elif mode == "transmitted":
            time_period = after_crop

            for i in range(len(self.time_trans)):
                if self.time_trans[i] >= transmitted_crop:
                    transmitted_crop_idx = i
                    break

            tpp = self.og_time_incid[1] - self.og_time_incid[0]
            time_period = round(time_period / tpp)

            self.time_trans = self.time_trans[transmitted_crop_idx:transmitted_crop_idx + time_period]
            self.vcc_trans = self.vcc_trans[transmitted_crop_idx:transmitted_crop_idx + time_period]

            align = self.time_trans[0]
            for j in range(len(self.time_trans)):
                self.time_trans[j] -= align

    def manual_crop(self, time_ax, voltage, text, wave):
        """
        Manual graph cropping using GInput

        time_ax: the signals' time axis
        voltage: the signals' voltage
        text: The text the appears in the figure once opened
        wave: wave type: either "Incident", "Transmitted" or "Reflected".
        :return: time coordinate(s) of the user's cropping.

        Note:               "GInput" is a real troublemaker when used in a GUI (at least in this one),
                            which is why at failure the program will quit entirely.
        """

        fig, ax = plt.subplots()

        ax.plot(time_ax, voltage)
        ax.grid()
        plt.title(text)

        plt.xlabel("Time")
        plt.ylabel("Amplitude (V)")
        plt.legend(wave)

        cursor = Cursor(ax, horizOn=True, vertOn=True, useblit=True, color='b', linewidth=1)

        try:
            # Get the selected coordinates from the graph:
            if wave == "Incident":
                cropping_coordinates = plt.ginput(n=3, show_clicks=True)

            else:
                cropping_coordinates = plt.ginput(n=1, show_clicks=True)

            plt.show()
            x, y = zip(*cropping_coordinates)
            # we are only interested in the X point values (Time) for the signal cutting:
            return x

        except:
            #   If selection hasn't been made (interrupted), exit the program.
            #   Ginput is a dinosaur. It's bad for use and crushes instantly inside a GUI.
            exit()

        print("Manual Cropping CMPLT.")

    def auto_crop(self):
        """
            Automatic cropping of the signals through peak detection.

            First we will create an array with the signals in absolute values.
            Then, using SciPy's function "find_peaks()" we will find the peaks of the graph.
            According to the first peak in the incident signal, we will crop the incident wave,
            According to the second peak in the incident signal, we will crop the reflected wave.

            This function manipulates existing signals and doesn't return anything.
        """

        #   For better peak-finding results, we will use smoothed signals, using the Savitzky - Golay filter:
        sav_incid = scipy.signal.savgol_filter(self.vcc_incid, self.smooth_value, 3)

        #   A softer smoothing is applied on the transmitted signal since it is more sensitive than the incident signal:
        sav_trans = scipy.signal.savgol_filter(self.vcc_trans, self.smooth_value - 50, 3)

        print("\t...detecting signal peaks with Sav - Gol filter with " + str(self.smooth_value) + " window length (Curve Smoothing).")

        #   Create absolute valued signals:
        abs_incid = np.absolute(sav_incid)
        abs_trans = np.absolute(sav_trans)

        max_incid = max(sav_incid)

        prominence = max_incid * self.prominence_percent

        #   Find the peaks in the Incident signal and take only the time stamps
        peaks_incid, _ = find_peaks(abs_incid, prominence=prominence)

        #   There should be at least 4 peaks in the signal,
        #   if less than 4 have been found -> lower the prominence by one percent of its original value.
        while len(peaks_incid) < 4:
            prominence -= max_incid / 200
            peaks_incid, _ = find_peaks(abs_incid, prominence=prominence)

        #   For an estimated prominence, we will take half of the maximum value:
        max_trans = max(sav_trans)
        prominence = max_trans * self.prominence_percent

        #   Find the peaks in the Transmitted signal and take only the time stamps
        peaks_trans, _ = find_peaks(abs_trans, prominence=prominence)

        while len(peaks_trans) < 4:
            prominence -= max_trans / 200
            peaks_trans, _ = find_peaks(abs_trans, prominence=prominence)

        print("\t...Peaks detected in both signals. ")
        #   The mode changes sign in some calculation, so a constant of 1 or -1 will be useful.
        if self.mode == "compression":
            K = 1

        else:
            K = -1

        #   The following will look for the point where the wave changes its sign from both sides,
        #   Obtaining these points is crucial for determining where to crop the signal to export the different waves.

        #   For incident wave:
        incid_before_idx = peaks_incid[0]
        while K * self.og_vcc_incid[incid_before_idx] < 0:
            incid_before_idx -= 1

        incid_after_idx = peaks_incid[0]
        while K * self.og_vcc_incid[incid_after_idx] < 0:
            incid_after_idx += 1

        #   "spacing" is the number of points to take before or after the peak in the signal.
        spacing = self.spacing

        self.vcc_incid = self.og_vcc_incid[incid_before_idx - spacing: incid_after_idx + 2 * spacing]
        self.time_incid = self.og_time_incid[incid_before_idx - spacing: incid_after_idx + 2 * spacing]

        #   We want all three waves to be of the same vector size, so we will use the total time of the incident wave,
        #   and only find where the other two waves begin.
        signal_time = incid_after_idx - incid_before_idx

        #   For reflected wave:
        before_idx = peaks_incid[1]
        while K * self.og_vcc_incid[before_idx] > 0:
            before_idx -= 1

        #   Total cropping time
        after_idx = before_idx + signal_time
        reflected_idx = before_idx
        self.vcc_reflected = self.og_vcc_incid[before_idx - spacing: after_idx + 2 * spacing]
        self.time_reflected = self.og_time_incid[before_idx - spacing: after_idx + 2 * spacing]

        #   For transmitted wave:
        before_idx = peaks_trans[0]
        while K * self.og_vcc_trans[before_idx] < 0:
            before_idx -= 1

        #   Total cropping time
        after_idx = before_idx + signal_time

        '''
                uncomment the following to display where the cropping occurs.

        plt.clf()
        plt.plot(self.og_time_incid, self.og_vcc_incid)
        plt.plot(self.og_time_trans, self.og_vcc_trans)
        plt.axvline(x=self.time_trans[incid_before_idx - spacing], linewidth=2, color='r')
        plt.axvline(x=self.time_trans[before_idx - spacing], linewidth=2, color='k')
        plt.axvline(x=self.time_trans[reflected_idx - spacing], linewidth=2, color='b')
        plt.legend(["Incident", "Transmitted"])
        plt.show()
        '''

        self.vcc_trans = self.og_vcc_trans[before_idx - spacing: after_idx + 2 * spacing]
        self.time_trans = self.og_time_trans[before_idx - spacing: after_idx + 2 * spacing]

        #   Fix all cropped signals to the beginning (t = 0)
        n = len(self.time_incid)
        zeroer = self.time_incid[0]
        for i in range(n):
            self.time_incid[i] -= zeroer

        n = len(self.time_reflected)
        zeroer = self.time_reflected[0]
        for i in range(n):
            self.time_reflected[i] -= zeroer

        n = len(self.time_trans)
        zeroer = self.time_trans[0]
        for i in range(n):
            self.time_trans[i] -= zeroer

        if self.thermal_analysis:
            #   Use a copy of IR_EXP
            time_IR_EXP = self.time_IR_EXP.copy()

            #   The time difference that needs to be cut out from the IR signal.
            dt = self.first_gage / self.sound_velocity + self.og_time_incid[incid_before_idx] - self.og_time_incid[self.spacing]
            cropping_idx = 0
            for i in range(len(time_IR_EXP)):
                if time_IR_EXP[i] >= dt:
                    cropping_idx = i
                    break

            time_IR_EXP = time_IR_EXP[cropping_idx:]
            self.volt_IR_EXP = self.volt_IR_EXP[cropping_idx:]

            n = len(time_IR_EXP)
            zeroer = time_IR_EXP[0]
            for i in range(n):
                time_IR_EXP[i] -= zeroer
            self.time_IR_EXP = time_IR_EXP

        print("Automatic Cropping CMPLT.")

    def dispertion_correction(self):
        print("Dispersion Correction Initialized...")
        #   Perform FFT on all signals:
        fft_incid = np.fft.fft(self.vcc_incid, axis=0)
        fft_trans = np.fft.fft(self.vcc_trans, axis=0)
        fft_reflected = np.fft.fft(self.vcc_reflected, axis=0)

        n = len(fft_incid)  # length of signals
        bar_radius = self.bar_diameter / 2

        frequencies = np.zeros(n)
        change_in_frequency = 1 / n / self.tpp

        #   harmonic series
        for i in range(n):
            frequencies[i] = change_in_frequency * (i + 1)

        sound_velocity = self.sound_velocity
        self.ratios = self.bancroft_interpolation()

        pi = np.pi

        first_gage = self.first_gage
        second_gage = self.second_gage

        #   Velocities will be filled with the interpolated velocities.
        velocities = np.zeros(n)

        #   Incident, Reflected & Transmitted phases respectively
        i_phase = []
        r_phase = []
        t_phase = []

        ratios = self.ratios
        print("\t...obtaining Fourier components")
        for i in range(n // 2):
            #   Calculating (by interpolation) the phase velocity of each Fourier component.
            velocities[i] = self.phase_velocity_calculation(frequencies[i], bar_radius, sound_velocity, ratios)

            '''
                        Note that the first is positive (+) and the following two are negative (-). 
                        This is because the incident
                        wave is the one prior to the impact, so we move it forward in time,
                        and the transmitted and reflected occur after the impact, 
                        therefore are needed to move backwards in time.
            '''

            #   Calculate phase changes:
            i_phase.append(2 * pi * frequencies[i] * first_gage * ((1 / sound_velocity) - (1 / velocities[i])))
            r_phase.append(-2 * pi * frequencies[i] * first_gage * ((1 / sound_velocity) - (1 / velocities[i])))
            t_phase.append(-2 * pi * frequencies[i] * second_gage * ((1 / sound_velocity) - (1 / velocities[i])))

        '''
                        The following deals with Aliasing of the Fourier Transform analytically.
        '''

        i_phase.append(0)
        r_phase.append(0)
        t_phase.append(0)

        for i in range(n):
            i_phase.append(- i_phase[n // 2 - i])
            r_phase.append(- r_phase[n // 2 - i])
            t_phase.append(- t_phase[n // 2 - i])

        fti = []
        ftr = []
        ftt = []

        #   Add the phase change to each Fourier component.
        #   '1j = sqrt(-1)'
        for i in range(min(len(fft_reflected), len(r_phase))):
            fti.append(np.exp(1j * i_phase[i]) * fft_incid[i])
            ftr.append(np.exp(1j * r_phase[i]) * fft_reflected[i])
            ftt.append(np.exp(1j * t_phase[i]) * fft_trans[i])

        print("\t...Fourier components obtained, performing inverse Fourier transform...")
        # Inverse Fourier transform
        clean_incident = np.real(np.fft.ifft(fti, axis=0))
        clean_reflected = np.real(np.fft.ifft(ftr, axis=0))
        clean_transmitted = np.real(np.fft.ifft(ftt, axis=0))

        # Damp factor fixing
        self.fixed_incident = clean_incident * np.exp((-1) * self.damp_f * first_gage)
        self.fixed_reflected = clean_reflected * np.exp((+1) * self.damp_f * first_gage)
        self.fixed_transmitted = clean_transmitted * np.exp((+1) * self.damp_f * second_gage)

        print("Dispersion Correction CMPLT.")

    def phase_velocity_calculation(self, f1, a1, c0, h):
        # Radius - Wavelength Ratio (RWR):
        rwr = f1 * a1 / c0

        i = 0
        while rwr >= h[i][0]:
            i += 1
            if i > 25:
                break

        # Interpolation of phase velocity from Bancroft's data table:
        if i < 25:
            phase_velocity = c0 * (
                        (1 / (h[i][0] - h[i - 1][0])) * (rwr - h[i - 1][0]) * (h[i][1] - h[i - 1][1]) + h[i - 1][1])
        else:
            phase_velocity = 0.59 * c0

        return phase_velocity

    def bancroft_interpolation(self):
        """
            This function uses Bancroft's Data to calculate the different wave velocities.
            Please read the manual "Signal Cleaning" for a full understanding of this function.
            The specific number 26 is simply the number of rows in Bancroft's data table.
        """
        p_r = self.poisson_ratio  # The bar's Poisson's ratio NEEDS TO BE ADDED
        os.chdir(os.path.dirname(os.path.abspath(__file__)))
        bancrofts_data = np.loadtxt("../ProgramFiles/bancrofts_data.txt")

        rwr = np.zeros(26)  # Radius - Wavelength Ratio (RWR)
        phase_velocities = np.zeros(26)

        # The following interpolates poisson's ratio according to its value.
        # "column" is the needed column from Bancroft's data table (based on Poisson's ratio's value).

        if 0.2 <= p_r <= 0.25:
            interpolated_p_r = (p_r - 0.2) / (0.25 - 0.2)
            column = 0

        elif 0.25 <= p_r <= 0.30:
            interpolated_p_r = (p_r - 0.25) / (0.30 - 0.25)
            column = 1

        elif 0.3 <= p_r <= 0.35:
            interpolated_p_r = (p_r - 0.3) / (0.35 - 0.3)
            column = 2

        else:
            column = 3
            print('nu out of program range')

        if column != 3:
            for j in range(26):
                rwr[j] = bancrofts_data[j][4] / 2
                phase_velocities[j] = bancrofts_data[j][column] + (
                            bancrofts_data[j][column + 1] - bancrofts_data[j][column]) * interpolated_p_r

        ratios = np.zeros((26, 2))  # previously named 'hh'

        rwr = rwr[0:25]
        rwr = rwr[:]

        phase_velocities = phase_velocities[0:25]
        phase_velocities = phase_velocities[:]

        for i in range(25):
            ratios[i][0] = rwr[i]
            ratios[i][1] = phase_velocities[i]

        return ratios

    def cross_correlate_signals(self):
        print("Signal cross - corelation Initialized...")
        """
            This function uses Cross - Correlation to fix the given signals on each other.
            The "time_2" vector is the time vector that corresponds to the given "signal_2".

            The function only manipulates existing signals and returns nothing.

            signal_1 = incident
            signal_2 = transmitted
            signal_3 = reflected
        """

        def autocorrelate(a, b):
            """
                SciPy's correlation is not starting at a time difference of 0, it starts at a negative time difference,
                closes to 0, and then goes positive. For this reason, we need to take the last half of the correlation
                result, and that should be the auto - correlation we are looking for.

            :param a: First signal to correlate to
            :param b: Second signal to be correlated to the first
            :return: fixed auto - correlated signal
            """
            result = scipy.signal.correlate(a, b, mode='full')
            return result[result.size // 2:]

        abs_signal_1 = []
        abs_signal_2 = []
        abs_signal_3 = []

        time_1 = self.time_incid
        time_2 = self.time_trans
        time_3 = self.time_reflected

        signal_1 = scipy.signal.savgol_filter(self.fixed_incident, self.smooth_value, 3)
        signal_2 = scipy.signal.savgol_filter(self.fixed_transmitted, self.smooth_value, 3)
        signal_3 = scipy.signal.savgol_filter(self.fixed_reflected, self.smooth_value, 3)

        for value in signal_1:
            abs_signal_1.append(abs(value))

        for value in signal_2:
            abs_signal_2.append(abs(value))

        for value in signal_3:
            abs_signal_3.append(abs(value))

        '''
        #   Auto - Correlated Signal (acs) of the Incident signal and the Transmitted signal:
        acs = autocorrelate(abs_signal_1, abs_signal_2)

        #   Get the position of the maximum value in the Auto - Correlated Signal:
        correlated_position = np.argmax(acs)
        correlated_time = time_2[correlated_position]

        if correlated_position != 0:
            #   Align signal_2 to signal_1 according to the ACS result:
            time_1 = time_1[:-correlated_position]
            time_2 = time_2[correlated_position:]

            signal_1 = self.fixed_incident[:-correlated_position]
            signal_2 = self.fixed_transmitted[correlated_position:]

        for i in range(len(time_2)):
            time_2[i] -= correlated_time
        
        '''

        #   Auto - Correlate signal (acs) of the Incident signal and the Reflected signal:
        acs = autocorrelate(abs_signal_3, abs_signal_1)

        #   Get the position of the maximum value in the Auto - Correlated Signal:
        correlated_position = np.argmax(acs)
        correlated_time = time_3[correlated_position]

        if correlated_position != 0:
            #   Align signal_2 to signal_1 according to the ACS result:
            time_1 = time_1[:-correlated_position]
            time_2 = time_2[:-correlated_position]
            time_3 = time_3[correlated_position:]

            signal_1 = self.fixed_incident[:-correlated_position]
            signal_2 = self.fixed_transmitted[:-correlated_position]
            signal_3 = self.fixed_reflected[correlated_position:]

            for i in range(len(time_3)):
                time_2[i] -= correlated_time
                time_3[i] -= correlated_time

            self.fixed_incident = signal_1
            self.fixed_transmitted = signal_2
            self.fixed_reflected = signal_3

        self.time_incid = time_1
        self.time_trans = time_2
        self.time_reflected = time_3
        print("Cross - Correlation CMPLT.")

    def mean_of_signal(self, signal):
        """
            Calculate the mean value of the signal.
            (analytically this should be the value of the step).

        :param signal:  Some step signal of data.
        :return: the mean value of the peak.
        """

        #   Take absolute value of signal:
        abs_signal = np.absolute(signal)

        #   Smooth the signal to find peak:
        smooth_signal = scipy.signal.savgol_filter(abs_signal, 51, 3)

        # find peak value of the signal:
        peak_value = max(abs_signal)

        if self.mode == "compression":
            k = 1
        else:
            k = -1

        #   Find the first peak of the signal, with a prominence of half the peak's value:
        peaks, _ = find_peaks(smooth_signal, prominence=peak_value * self.prominence_percent)
        if len(peaks) == 0:
            return -1
        peak = peaks[0]
        #   Start at peak and go backwards to find where the peak ends:
        idx = peak
        while idx > 0:
            if k * signal[idx] <= 0:
                break
            idx -= 1
        before_peak = idx

        #   Start at peak and forward to find where the peak ends:
        idx = peak
        while 0 < idx < len(signal):
            if k * signal[idx] <= 0:
                break
            idx += 1
        after_peak = idx

        # Crop the signal with some spacing
        cropped_signal = abs_signal[before_peak + self.spacing:after_peak - self.spacing]

        #   Take mean value of cropped signal:
        mean_value = np.mean(cropped_signal)

        #   Return the mean value:
        return mean_value

    def final_calculation(self):
        e_incid = []
        e_reflected = []
        e_trans = []
        striker_velocity = []
        v_in = []
        v_out = []
        F_in = []
        F_out = []
        eng_stress = []
        eng_strain_rate = []

        incid_strain = []
        trans_strain = []

        bar_surface = np.pi * (self.bar_diameter ** 2) / 4  # [m^2]
        specimen_surface = np.pi * (self.spec_diam ** 2) / 4  # [m^2]

        time = []

        for i in range(len(self.fixed_incident)):
            """
                Some physical properties (in vectors):
            """
            time.append((i + 1) * self.tpp)

            #   Strains
            e_incid.append((4 * self.fixed_incident[i]) / (self.gage_factor * self.bridge_tension))  # [strain]
            e_reflected.append((4 * self.fixed_reflected[i]) / (self.gage_factor * self.bridge_tension))  # [strain]
            e_trans.append((4 * self.fixed_transmitted[i]) / (self.gage_factor * self.bridge_tension))  # [strain]

            incid_strain.append((4 * self.og_vcc_incid[i]) / (self.gage_factor * self.bridge_tension))
            trans_strain.append((4 * self.og_vcc_trans[i]) / (self.gage_factor * self.bridge_tension))

            #   Velocities
            striker_velocity.append(-2 * e_incid[i] * self.sound_velocity)

            v_in.append((-1) * self.sound_velocity * (e_incid[i] - e_reflected[i]))
            v_out.append((-1) * self.sound_velocity * e_trans[i])

            #   Forces
            F_in.append((-1) * self.young_modulus * bar_surface * (e_incid[i] + e_reflected[i]))
            F_out.append((-1) * self.young_modulus * bar_surface * e_trans[i])

            #   Engineering Stress
            eng_stress.append(abs(F_out[i] / specimen_surface) / (10 ** 6))  # MPa
            eng_strain_rate.append((2 * self.sound_velocity / self.specimen_length) * e_reflected[i])

        #   Displacements
        u_in = integrate.cumtrapz(v_in, time)
        u_out = integrate.cumtrapz(v_out, time)
        eng_strain = integrate.cumtrapz(eng_strain_rate, time)
        idx = 0

        for strain in eng_strain:
            if strain >= 1:
                break
            idx += 1

        if idx == 0:
            idx = len(eng_strain)

        eng_strain = abs(eng_strain[:idx])
        eng_stress = eng_stress[:idx]

        #   Calculate the average (mean) striker velocity:
        self.mean_striker_velocity = self.mean_of_signal(striker_velocity[:idx])

        if self.mean_striker_velocity == -1:
            return False

        #   Make all vectors the same length:
        self.F_in = F_in[:idx]
        self.F_out = F_out[:idx]
        self.u_in = u_in[:idx]
        self.u_out = u_out[:idx]
        self.v_in = v_in[:idx]
        self.v_out = v_out[:idx]
        self.incid_strain = incid_strain[:idx]
        self.trans_strain = trans_strain[:idx]
        self.fixed_incident = self.fixed_incident[:idx]
        self.fixed_reflected = self.fixed_reflected[:idx]
        self.fixed_transmitted = self.fixed_transmitted[:idx]
        self.time = time[:idx]

        n = len(self.og_vcc_incid) - 1
        self.og_vcc_incid = self.og_vcc_incid[:n]
        self.og_time_incid = self.og_time_incid[:n]
        self.og_vcc_trans = self.og_vcc_trans[:n]
        self.og_time_trans = self.og_time_trans[:n]

        strain = []
        for value in eng_strain:
            strain.append(abs(value))

        surf_spec_inst = []
        true_stress = []
        true_strain = []

        #   True stress // strain calculation:
        if self.mode == "compression":
            K = -1
        else:
            K = 1

        for i in range(idx):
            surf_spec_inst.append(abs(specimen_surface / (1 + K*strain[i])))
            true_stress.append(abs(eng_stress[i] * (1 + K*strain[i])))
            true_strain.append(abs(np.log(1 + K*strain[i])))

        self.true_stress_strain = [true_strain, true_stress]
        self.eng_stress_strain = [eng_strain, eng_stress]

        self.mean_strain_rate = self.mean_of_signal(eng_strain_rate[:-1])

        if self.thermal_analysis:
            self.IR_calibration()

            print("beta_int calculation starting...")
            #   beta_int calculation:
            rho = 8000  # [kg / m^3]
            Cp = 500

            """
                The plastic strain is the strain after the elastic region. 
                A cropping should be done to obtain this area.
            """

            length = len(true_stress)
            from scipy.stats import linregress

            #   Find sigma_y (yield point):
            """
                To find sigma_y we perform a linear regression repeatedly, 
                each iteration enlarging the size of the vector upon which 
                the regression os performed. When the value of r^2 > 0.9
                we can assume we found the elastic zone (since it is linear). 
                
                Once r^2 > 0.9 is reached we start searching for our cropping point:
                this is where we leave the elastic zone and the curve starts to become
                less inclined. Once we enter the r^2 < 0.9 zone we can approximate that 
                this is where the plastic zone begins. 
            """
            crop_idx = 0
            point_searching_activated = False
            for i in range(10, length):

                _, _, r, _, _ = linregress(true_strain[0:i], true_stress[0:i])

                if 0.9 < r**2 and not point_searching_activated:
                    point_searching_activated = True

                if r**2 < 0.9 and point_searching_activated:
                    crop_idx = i
                    print("\t...Yield point found")
                    break

            plastic_stress = true_stress[crop_idx:]
            plastic_strain = true_strain[crop_idx:]

            """
                uncomment to see (graphically) the actual cropping with respect
                to the original stress - strain curve.
                 
                plt.figure()
                plt.plot(true_strain, true_stress)
                plt.plot(plastic_strain, plastic_stress)
                plt.show()
            """

            #   Make the strain start at zero:
            de = plastic_strain[0]
            self.plastic_strain = [X - de for X in plastic_strain]
            self.plastic_stress = plastic_stress
            self.IR_temperature = self.IR_temperature[crop_idx:]
            self.plastic_time = self.time[crop_idx:]
            dt = self.time[0]
            self.plastic_time = [X - dt for X in self.plastic_time]

            beta_int = []
            Wp = []
            for i in range(len(plastic_stress)):
                Wp_i = scipy.integrate.trapz(plastic_stress[0:i], plastic_strain[0:i])
                Wp.append(Wp_i)
                beta_int.append(rho * Cp * self.IR_temperature[i] / Wp_i / 10**6)   # [Stress is in MPa thus / 10^6]

            self.beta_int = beta_int
            self.Wp = Wp
            slope, intercept, _, _, _ = linregress(Wp, self.IR_temperature[0:len(plastic_stress)])
            self.LR_T_Wp = [intercept + slope*X for X in Wp]
            self.LR_T_Wp_intercept = intercept
            self.LR_T_Wp_slope = slope
            print("beta_int calculation CMPLT.")

        return True

    def IR_calibration(self):
        print("IR Calibration Initialized...")
        Num_Test = 1    # number of calibration tests done.
        Num_pnt = 5000  # number of recorded points - for better code performance.
        Cp = 500        # heat capacity for beta [J/(kg*C)]
        rho = 8000      # density for beta [kg/m^3]
        HCT_sort = sorted(self.volt_IR_CAL, reverse=True)

        #   correct signal to zero by first 4 maximas and minimas
        HCT_delta_correct = np.mean(HCT_sort[0:3]) + np.mean(HCT_sort[-4:-1])
        """
            After zeroing the HCT signal previously, the positive and negative
            values are almost symmetric. the total voltage for the HCT is the
            differenc: (+ voltage) - (- voltage), but since they are almost equal
            it's possible just to multiply the positive values by 2 and have the
            required difference (delta) in the voltage, this timr just regarding
            to zero. Hence HCT is multiplied by 2 at the end.
        """

        HCT = [2 * (X - HCT_delta_correct / 2) for X in self.volt_IR_CAL]
        #   Take HCT's upper envelope:
        df = pd.DataFrame(data={"y": HCT}, index=self.time_IR_CAL)

        windowsize = 20
        df["y_upperEnv"] = df["y"].rolling(window=windowsize).max().shift(int(-windowsize / 2))
        df["y_lowerEnv"] = df["y"].rolling(window=windowsize).min().shift(int(-windowsize / 2))

        from math import isnan
        HCT_envelope = df["y_upperEnv"].values.tolist()
        for i in range(len(HCT_envelope)):
            if not isnan(HCT_envelope[i]):
                HCT_envelope = HCT_envelope[i:]
                self.volt_TC_CAL= self.volt_TC_CAL[i:]
                self.time_IR_CAL = self.time_IR_CAL[i:]
                self.time_TC_CAL = self.time_TC_CAL[i:]
                break

        for i in range(len(HCT_envelope)):
            if not isnan(HCT_envelope[len(HCT_envelope) - i - 1]):
                HCT_envelope = HCT_envelope[:-i]
                self.volt_TC_CAL = self.volt_TC_CAL[:-i]
                self.time_IR_CAL = self.time_IR_CAL[:-i]
                self.time_TC_CAL = self.time_TC_CAL[:-i]
                break

        """
            The following automatically crops the unwanted ~ constant 
            beginning of the HCT's envelope.
        """
        #   Take derivative
        HCT_envelope_diff = np.diff(HCT_envelope)
        time_diff = self.time_IR_CAL[1] - self.time_IR_CAL[0]

        for i in range(len(HCT_envelope)):
            HCT_envelope_derivative = HCT_envelope_diff[i] / time_diff

            #   If the derivative is negative enough, crop the signal.
            if HCT_envelope_derivative < -0.5:

                #   Crop the signals according to the found crop index
                HCT_envelope = HCT_envelope[i:]
                HCT_time = self.time_IR_CAL[i:]

                TC = self.volt_TC_CAL[i:]
                TC_time = self.time_TC_CAL[i:]

                HCT_time = [t - self.time_IR_CAL[0] for t in HCT_time]
                TC_time = [t - self.time_TC_CAL[0] for t in TC_time]

                print("\t...Cropping Complete")
                break

        #   Calculate a double exponential fit for the TC - HCT graph:
        #   y(x) = a * exp(b * x) + c + exp(d * x)
        def double_exponential_fit(x, a, b, c, d):
            return a * np.exp(b * x) + c * np.exp(d * x)

        P0 = (150, 0.04, -130, -0.2)
        coeff, _ = scipy.optimize.curve_fit(double_exponential_fit, HCT_envelope, TC, p0=P0, maxfev=5000)
        c1 = coeff[0]
        c2 = coeff[1]
        c3 = coeff[2]
        c4 = coeff[3]
        print("\t...Curve Fitting 1 CMPLT")
        #   Calculate R^2 of the fit:
        def_HCT = [double_exponential_fit(X, c1, c2, c3, c4) for X in HCT_envelope]

        #residuals = TC - def_HCT
        #R_squared = sum((residuals ** 2) / def_HCT)

        Volt2Temp = self.k_temp(TC)
        print("\t...K Temp Configured (Volt2Temp)")
        coeff, _ = scipy.optimize.curve_fit(double_exponential_fit, HCT_envelope, Volt2Temp, p0=P0, maxfev=5000)
        d1 = coeff[0]
        d2 = coeff[1]
        d3 = coeff[2]
        d4 = coeff[3]

        print("\t...Curve Fitting 2 CMPLT with function (Volt -> Temperature):")
        print("\t\tT(v)" + str(d1) + " * exp {" + str(d2) + " * v} + " + str(d3) + " * exp {" + str(d4) + " * v}")

        #   Calculate R^2 of the fit:
        #def_HCT = [double_exponential_fit(X, c1, c2, c3, c4) for X in HCT_envelope]
        #residuals = TC - def_HCT
        #self.temp_R_squared = sum((residuals ** 2) / def_HCT)

        IR_temperature = [double_exponential_fit(X, d1, d2, d3, d4) for X in self.volt_IR_EXP]
        zero_IR_temperature = np.mean(IR_temperature[1:50])
        self.IR_temperature = [T - zero_IR_temperature for T in IR_temperature]
        print("IR Calibration CMPLT.")

    def k_temp(self, v):
        """
        K = Type of Thermocouple
        """

        vector_file = open("../ProgramFiles/k_type.txt")
        k_type = np.loadtxt(vector_file, delimiter='\t')
        vector_file.close()
        temp = []
        volt = []
        for i in range(len(k_type)):
            try:
                temp.append(float(k_type[i][0]))
                volt.append(float(k_type[i][1]))

            except:
                continue
        #   VOLTS CONVERTED TO mVOLT
        v = [X * 1000 for X in v]
        size_v = len(v)

        #   for T type thermocouple converts volts in temperature w/r to zero junction
        #   correction for ambient temperature

        tamb = 22
        vamb = 0.879

        inf = -400
        sup = +400

        from scipy.interpolate import interp1d

        def interp(ys, mul):
            # linear extrapolation for last (mul - 1) points
            ys = list(ys)
            ys.append(2 * ys[-1] - ys[-2])
            # make interpolation function
            xs = np.arange(len(ys))
            fn = interp1d(xs, ys, kind="cubic")
            # call it on desired data points
            new_xs = np.arange(len(ys) - 1, step=1. / mul)
            return fn(new_xs)

        intt = interp(temp, 5)
        intv = interp(volt, 5)

        temp = intt
        volt = intv
        v = [X + vamb for X in v]
        t_resu = []
        for i in range(size_v):
            diff_volt = [abs(v[i] - X) for X in volt]
            min_diff_volt = min(diff_volt)
            index = diff_volt.index(min_diff_volt)
            if volt[index] >= v[i]:
                del_v = volt[index] - volt[index - 1]
                del_t = temp[index] - temp[index - 1]
                t_resu.append(temp[index - 1] + (del_t / del_v) * (v[i] - volt[index - 1]))
            else:
                del_v = volt[index + 1] - volt[index]
                del_t = temp[index + 1] - temp[index]
                t_resu.append(temp[index] + (del_t / del_v) * (v[i] - volt[index]))
        return t_resu

    def plotly_report(self, exp_num, parameters, bar_num):
        """
                This function creates the final report that opens once an experiment was chosen.
        :param exp_num:         number (index) of current experiment
        :param specimen_data:   specimen's parameters filled by user
        :param experiment_data: experiment's parameters filled by user
        :return:                nothing, open up a report of the analyzed data.
        """
        micro_sec = [t*1e6 for t in self.time]
        if self.thermal_analysis:
            os.makedirs(self.path_input + "\Analysis Results")
            micro_sec_IR = [t*1e6 for t in self.time_IR_EXP]
            if bar_num == 1:
                if self.specimen_mode == "regular":
                    vectors = [self.og_vcc_incid, self.og_time_incid]
                    df = np.transpose(np.array(vectors))
                    filepath = self.path_input + "/Exp #" + str(exp_num) + '/Raw Signal.csv'
                    np.savetxt(filepath, df, delimiter=',', header='Incident [V], time [s]',
                               fmt='%s')

                    vectors = [self.fixed_incident,
                               self.fixed_reflected,
                               self.time]
                    df = np.transpose(np.array(vectors))
                    filepath = self.path_input + "/Exp #" + str(exp_num) + '/Corrected Signals.csv'
                    np.savetxt(filepath, df, delimiter=',',
                               header='Incident [V], Reflected [V], time [s]',
                               fmt='%s')

                    vectors = [self.u_in, self.time]
                    df = np.transpose(np.array(vectors))
                    filepath = self.path_input + "/Exp #" + str(exp_num) + '/Displacement.csv'
                    np.savetxt(filepath, df, delimiter=',', header='u_in [m], time [s]', fmt='%s')

                    vectors = [self.true_stress_strain[0], self.true_stress_strain[1]]
                    df = np.transpose(np.array(vectors))
                    filepath = self.path_input + "/Exp #" + str(exp_num) + '/Stress-Strain True.csv'
                    np.savetxt(filepath, df, delimiter=',', header='Strain, Stress', fmt='%s')

                    vectors = [self.eng_stress_strain[0], self.eng_stress_strain[1]]
                    df = np.transpose(np.array(vectors))
                    filepath = self.path_input + "/Exp #" + str(exp_num) + '/Stress-Strain Engineering.csv'
                    np.savetxt(filepath, df, delimiter=',', header='Strain, Stress', fmt='%s')

                    vectors = [self.F_in, self.time]
                    df = np.transpose(np.array(vectors))
                    filepath = self.path_input + "/Exp #" + str(exp_num) + '/Force.csv'
                    np.savetxt(filepath, df, delimiter=',', header='F_in [N], time [s]', fmt='%s')

                    vectors = [self.v_in, self.time]
                    df = np.transpose(np.array(vectors))
                    filepath = self.path_input + "/Exp #" + str(exp_num) + '/Velocity.csv'
                    np.savetxt(filepath, df, delimiter=',', header='v_in [m/s], time [s]', fmt='%s')

                    fig = go.FigureWidget(
                        [
                            go.Scatter(name=r'$Incident$', y=self.og_vcc_incid, x=self.og_time_incid,
                                       mode=r'lines', visible=False),

                            go.Scatter(name=r'$Incident$', y=self.fixed_incident, x=micro_sec,
                                       mode='lines', visible=False),
                            go.Scatter(name=r'$Reflected$', y=self.fixed_reflected, x=micro_sec,
                                       mode='lines', visible=False),

                            go.Scatter(name=r'$U_{in}$', y=self.u_in, x=micro_sec,
                                       mode='lines', visible=False),

                            go.Scatter(name=r'$\sigma_{Engineering}$', y=self.eng_stress_strain[1],
                                       x=self.eng_stress_strain[0], mode='lines'),
                            go.Scatter(name=r'$True$', y=self.true_stress_strain[1],
                                       x=self.true_stress_strain[0], mode='lines'),

                            go.Scatter(name=r'$F_{in}$', y=self.F_in, x=micro_sec,
                                       mode='lines', visible=False),

                            go.Scatter(name=r'$V_{in}$', y=self.v_in, x=micro_sec,
                                       mode='lines', visible=False)

                        ]
                    )

                    fig.update_layout(title_x=0.4, template='none',
                                      font=dict(family="Gravitas One", size=22),
                                      legend=dict(yanchor='top', xanchor='right', y=0.99, x=0.99),
                                      updatemenus=[go.layout.Updatemenu(
                                          active=3,
                                          buttons=list(
                                              [dict(label='Raw Signal',
                                                    method='update',
                                                    args=[{'visible': [True] + [False] * 7},
                                                          {'title': 'Raw Signals',
                                                           'xaxis': {'title': r'$Time [μs]$'},
                                                           'yaxis': {'title': r'$Amplitude [V]$'},
                                                           'showlegend': True}]),

                                               dict(label='Corrected Signals',
                                                    method='update',
                                                    args=[{'visible': [False] + [True] * 2 + [False] * 5},
                                                          {'title': r'$Corrected Signals$',
                                                           'xaxis': {'title': r'$Time [μs]$'},
                                                           'yaxis': {'title': r'$Amplitude [V]$'},
                                                           'showlegend': True}]),

                                               dict(label='Displacement',
                                                    method='update',
                                                    args=[{'visible': [False] * 3 + [True] + [False] * 4},
                                                          {'title': r'$Displacement$',
                                                           'xaxis': {'title': r'$Time [μs]$'},
                                                           'yaxis': {'title': r'$Displacement [m]$'},
                                                           'showlegend': True}]),

                                               dict(label='Stress - Strain',
                                                    method='update',
                                                    args=[{'visible': [False] * 4 + [True] * 2 + [False] * 2},
                                                          {'title': r'$Stress - Strain$',
                                                           'xaxis': {'title': r'$\epsilon [strain]$'},
                                                           'yaxis': {'title': r'$Stress [MPa]$'},
                                                           'showlegend': True}]),

                                               dict(label='Force',
                                                    method='update',
                                                    args=[{'visible': [False] * 6 + [True] + [False]},
                                                          {'title': r'$Forces$',
                                                           'xaxis': {'title': r'$Time [μs]$'},
                                                           'yaxis': {'title': r'$Force [N]$'},
                                                           'showlegend': True}]),

                                               dict(label='Velocity',
                                                    method='update',
                                                    args=[{'visible': [False] * 7 + [True]},
                                                          {'title': r'$Velocity$',
                                                           'xaxis': {'title': r'$Time [μs]$'},
                                                           'yaxis': {'title': r'$Velocity [m/s]$'},
                                                           'showlegend': True}]

                                                    ),
                                               ]),
                                          x=0.9, y=1.1
                                      )
                                      ])

                if self.specimen_mode == "shear":
                    vectors = [self.incid_strain, self.time]
                    df = np.transpose(np.array(vectors))
                    filepath = self.path_input + "/Exp #" + str(exp_num) + '/Bar Strain.csv'
                    np.savetxt(filepath, df, delimiter=',',
                               header='incident strain, time [s]',
                               fmt='%s')

                    vectors = [self.og_vcc_incid, self.og_time_incid]
                    df = np.transpose(np.array(vectors))
                    filepath = self.path_input + "/Exp #" + str(exp_num) + '/Raw Signal.csv'
                    np.savetxt(filepath, df, delimiter=',', header='Incident [V], time [s]',
                               fmt='%s')

                    vectors = [self.fixed_incident,
                               self.fixed_reflected,
                               self.time]

                    df = np.transpose(np.array(vectors))
                    filepath = self.path_input + "/Exp #" + str(exp_num) + '/Corrected Signals.csv'
                    np.savetxt(filepath, df, delimiter=',',
                               header='Incident [V], Reflected [V], time [s]',
                               fmt='%s')

                    vectors = [self.u_in, self.time]
                    df = np.transpose(np.array(vectors))
                    filepath = self.path_input + "/Exp #" + str(exp_num) + '/Displacement.csv'
                    np.savetxt(filepath, df, delimiter=',', header='u_in [m], time [s]', fmt='%s')

                    vectors = [self.F_in, self.time]
                    df = np.transpose(np.array(vectors))
                    filepath = self.path_input + "/Exp #" + str(exp_num) + '/Forces.csv'
                    np.savetxt(filepath, df, delimiter=',', header='F_in [N], time [s]', fmt='%s')

                    vectors = [self.v_in, self.time]
                    df = np.transpose(np.array(vectors))
                    filepath = self.path_input + "/Exp #" + str(exp_num) + '/Velocity.csv'
                    np.savetxt(filepath, df, delimiter=',', header='v_in [m/s], time [s]', fmt='%s')

                    fig = go.FigureWidget(
                        [
                            go.Scatter(name=r'$Incident$', y=self.og_vcc_incid, x=self.og_time_incid,
                                       mode='lines', visible=False),

                            go.Scatter(name=r'$Incident$', y=self.fixed_incident, x=micro_sec,
                                       mode='lines', visible=False),
                            go.Scatter(name=r'$Reflected$', y=self.fixed_reflected, x=micro_sec,
                                       mode='lines', visible=False),

                            go.Scatter(name=r'$U_{in}$', y=self.u_in, x=micro_sec,
                                       mode='lines', visible=False),

                            go.Scatter(name=r'$F_{in}$', y=self.F_in, x=micro_sec,
                                       mode='lines', visible=True),

                            go.Scatter(name=r'$V_{in}$', y=self.v_in, x=micro_sec,
                                       mode='lines', visible=False),

                        ]
                    )

                    fig.update_layout(title_x=0.5, template='none',
                                      font=dict(family="Gravitas One", size=22),
                                      legend=dict(yanchor='top', xanchor='right', y=0.99, x=0.99),
                                      updatemenus=[go.layout.Updatemenu(
                                          active=3,
                                          buttons=list(
                                              [dict(label='Raw Signal',
                                                    method='update',
                                                    args=[{'visible': [True] + [False] * 5},
                                                          {'title': r'$Raw Signals$',
                                                           'xaxis': {'title': r'$Time [μs]$'},
                                                           'yaxis': {'title': r'$Amplitude [V]$'},
                                                           'showlegend': True}]),

                                               dict(label='Corrected Signals',
                                                    method='update',
                                                    args=[{'visible': [False] + [True] * 2 + [False] * 3},
                                                          {'title': r'$Corrected Signals$',
                                                           'xaxis': {'title': r'$Time [μs]$'},
                                                           'yaxis': {'title': r'$Amplitude [V]$'},
                                                           'showlegend': True}]),

                                               dict(label='Displacement',
                                                    method='update',
                                                    args=[{'visible': [False] * 3 + [True] + [False] * 2},
                                                          {'title': r'$Displacement$',
                                                           'xaxis': {'title': r'$Time [μs]$'},
                                                           'yaxis': {'title': r'$Displacement [m]$'},
                                                           'showlegend': True}]),

                                               dict(label='Forces',
                                                    method='update',
                                                    args=[{'visible': [False] * 4 + [True] + [False]},
                                                          {'title': r'$Force$',
                                                           'xaxis': {'title': r'$Time [μs]$'},
                                                           'yaxis': {'title': r'$Force [N]$'},
                                                           'showlegend': True}]),

                                               dict(label='Velocities',
                                                    method='update',
                                                    args=[{'visible': [False] * 5 + [True]},
                                                          {'title': r'$Velocity$',
                                                           'xaxis': {'title': r'$Time [μs]$'},
                                                           'yaxis': {'title': r'$Velocity [m/s]$'},
                                                           'showlegend': True}]

                                                    ),
                                               ]),
                                          x=0.9, y=1.1
                                      )
                                      ])

                fig.add_annotation(dict(font=dict(color='red', size=16),
                                        font_family="Garamound",
                                        x=1,
                                        y=0.1,
                                        showarrow=False,
                                        text="Average Strain Rate: " + str(int(self.mean_strain_rate)) + " [1/s]",
                                        textangle=0,
                                        xanchor='left',
                                        xref="paper",
                                        yref="paper"))

                fig.add_annotation(dict(font=dict(color='black', size=16),
                                        font_family="Garamound",
                                        x=1,
                                        y=0.37,
                                        showarrow=False,
                                        font_color='blue',
                                        text="<b>Experiment Parameters:<b>                   ",
                                        textangle=0,
                                        xanchor='left',
                                        xref="paper",
                                        yref="paper"))

                fig.add_annotation(dict(font=dict(color='black', size=14),
                                        font_family="Garamound",
                                        x=1,
                                        y=0.32,
                                        showarrow=False,
                                        text="Specimen Diameter: " + str(parameters[0][1]) + " [m]",
                                        textangle=0,
                                        xanchor='left',
                                        xref="paper",
                                        yref="paper"))

                fig.add_annotation(dict(font=dict(color='black', size=14),
                                        font_family="Garamound",
                                        x=1,
                                        y=0.29,
                                        showarrow=False,
                                        text="Specimen Length: " + str(parameters[1][1]) + " [m]",
                                        textangle=0,
                                        xanchor='left',
                                        xref="paper",
                                        yref="paper"))

                fig.add_annotation(dict(font=dict(color='black', size=14),
                                        font_family="Garamound",
                                        x=1,
                                        y=0.26,
                                        showarrow=False,
                                        text="Bar Diameter: " + str(parameters[2][1]) + " [m]",
                                        textangle=0,
                                        xanchor='left',
                                        xref="paper",
                                        yref="paper"))

                fig.add_annotation(dict(font=dict(color='black', size=14),
                                        font_family="Garamound",
                                        x=1,
                                        y=0.23,
                                        showarrow=False,
                                        text="Young's Modulus: " + str(parameters[3][1] / (10 ** 9)) + " [GPa]",
                                        textangle=0,
                                        xanchor='left',
                                        xref="paper",
                                        yref="paper"))

                fig.add_annotation(dict(font=dict(color='black', size=14),
                                        font_family="Garamound",
                                        x=1,
                                        y=0.2,
                                        showarrow=False,
                                        text="Sound Velocity in Bar: " + str(parameters[6][1]) + " [m/s]",
                                        textangle=0,
                                        xanchor='left',
                                        xref="paper",
                                        yref="paper"))

                fig.add_annotation(dict(font=dict(color='black', size=14),
                                        font_family="Garamound",
                                        x=1,
                                        y=0.17,
                                        showarrow=False,
                                        text="Bridge Tension: " + str(parameters[8][1]) + " [V]",
                                        textangle=0,
                                        xanchor='left',
                                        xref="paper",
                                        yref="paper"))

                fig.add_annotation(dict(font=dict(color='black', size=14),
                                        font_family="Garamound",
                                        x=1,
                                        y=0.14,
                                        showarrow=False,
                                        text="Striker Velocity: " + str("%.2f" % self.mean_striker_velocity) + " [m/s]",
                                        textangle=0,
                                        xanchor='left',
                                        xref="paper",
                                        yref="paper"))

                fig.add_annotation(dict(font=dict(color='black', size=18),
                                        font_family="Garamound",
                                        x=1,
                                        y=0.6,
                                        showarrow=False,
                                        text="<b>Experiment no. " + str(exp_num) + "<b>",
                                        textangle=0,
                                        xanchor='left',
                                        xref="paper",
                                        yref="paper"))

                fig.add_annotation(dict(font=dict(color='black', size=14),
                                        font_family="Garamound",
                                        x=1,
                                        y=0.56,
                                        showarrow=False,
                                        text="Specimen type: " + str(self.specimen_mode),
                                        textangle=0,
                                        xanchor='left',
                                        xref="paper",
                                        yref="paper"))

                fig.add_annotation(dict(font=dict(color='black', size=14),
                                        font_family="Garamound",
                                        x=1,
                                        y=0.54,
                                        showarrow=False,
                                        text="Experiment mode: " + str(self.mode),
                                        textangle=0,
                                        xanchor='left',
                                        xref="paper",
                                        yref="paper"))

                fig.add_annotation(dict(font=dict(color='black', size=20),
                                        font_family="Garamound",
                                        x=1,
                                        y=0.8,
                                        showarrow=False,
                                        text="main Analysis Report",
                                        textangle=0,
                                        xanchor='left',
                                        xref="paper",
                                        yref="paper"))

                fig.update_layout(margin=dict(r=250))
                fig.write_html(self.path_input + "\Exp " + str(exp_num) + '.html',
                               auto_open=self.auto_open_report,
                               include_mathjax='cdn')

            if bar_num == 2:
                if self.specimen_mode == "regular":
                    vectors = [self.og_vcc_incid, self.og_vcc_trans, self.og_time_incid]
                    df = np.transpose(np.array(vectors))
                    filepath = self.path_input + "/Analysis Results" + '/Raw Signals.csv'
                    np.savetxt(filepath, df, delimiter=',', header='Incident [V], Transmitted [V], time [s]',
                               fmt='%s')

                    vectors = [self.fixed_incident,
                               self.fixed_reflected,
                               self.fixed_transmitted,
                               self.time]
                    df = np.transpose(np.array(vectors))
                    filepath = self.path_input + "/Analysis Results" + '/Corrected Signals.csv'
                    np.savetxt(filepath, df, delimiter=',',
                               header='Incident [V], Reflected [V], Transmitted [V], time [s]',
                               fmt='%s')

                    vectors = [self.u_in, self.u_out, self.time]
                    df = np.transpose(np.array(vectors))
                    filepath = self.path_input + "/Analysis Results" + '/Displacements.csv'
                    np.savetxt(filepath, df, delimiter=',', header='u_in [m], u_out [m], time [s]', fmt='%s')

                    vectors = [self.true_stress_strain[0], self.true_stress_strain[1]]
                    df = np.transpose(np.array(vectors))
                    filepath = self.path_input + "/Analysis Results" + '/Stress-Strain True.csv'
                    np.savetxt(filepath, df, delimiter=',', header='Strain, Stress', fmt='%s')

                    vectors = [self.eng_stress_strain[0], self.eng_stress_strain[1]]
                    df = np.transpose(np.array(vectors))
                    filepath = self.path_input + "/Analysis Results" + '/Stress-Strain Engineering.csv'
                    np.savetxt(filepath, df, delimiter=',', header='Strain, Stress', fmt='%s')

                    vectors = [self.F_in, self.F_out, self.time]
                    df = np.transpose(np.array(vectors))
                    filepath = self.path_input + "/Analysis Results" + '/Forces.csv'
                    np.savetxt(filepath, df, delimiter=',', header='F_in [N], F_out [N], time [s]', fmt='%s')

                    vectors = [self.v_in, self.v_out, self.time]
                    df = np.transpose(np.array(vectors))
                    filepath = self.path_input + "/Analysis Results" + '/Velocities.csv'
                    np.savetxt(filepath, df, delimiter=',', header='v_in [m/s], v_out [m/s], time [s]', fmt='%s')

                    vectors = [self.plastic_strain, self.plastic_stress, self.IR_temperature, self.plastic_time]
                    df = np.transpose(np.array(vectors))
                    filepath = self.path_input + "/Analysis Results" + '/Plastic Strain and Temperature.csv'
                    np.savetxt(filepath, df, delimiter=',', header='strain, stress [GPa], Temperature [K], time[s]', fmt='%s')

                    vectors = [self.plastic_strain, self.plastic_stress, self.beta_int]
                    df = np.transpose(np.array(vectors))
                    filepath = self.path_input + "/Analysis Results" + '/Plastic Stress - Strain - beta_int.csv'
                    np.savetxt(filepath, df, delimiter=',', header='strain , stress [GPa], beta_int',
                               fmt='%s')

                    fig = make_subplots(specs=[[{"secondary_y": True}]])
                    fig.add_trace(go.Scatter(name=r'$Incident$', y=self.og_vcc_incid, x=self.og_time_incid,
                                       mode='lines', visible=False), secondary_y=False)
                    fig.add_trace(go.Scatter(name=r'$Transmitted$', y=self.og_vcc_trans, x=self.og_time_trans,
                                       mode='lines', visible=False), secondary_y=False)

                    fig.add_trace(go.Scatter(name=r'$Incident$', y=self.fixed_incident, x=micro_sec,
                                       mode='lines', visible=False), secondary_y=False)
                    fig.add_trace(go.Scatter(name=r'$Transmitted$', y=self.fixed_transmitted, x=micro_sec,
                                       mode='lines', visible=False), secondary_y=False)
                    fig.add_trace(go.Scatter(name=r'$Reflected$', y=self.fixed_reflected, x=micro_sec,
                                       mode='lines', visible=False), secondary_y=False)
                    fig.add_trace(go.Scatter(name=r'$IR$', y=self.volt_IR_EXP[:len(micro_sec)], x=micro_sec,
                                       mode='lines', visible=False), secondary_y=True)

                    fig.add_trace(go.Scatter(name=r'$U_{in}$', y=self.u_in, x=micro_sec,
                                       mode='lines', visible=False), secondary_y=False)
                    fig.add_trace(go.Scatter(name=r'$U_{out}$', y=self.u_out, x=micro_sec,
                                       mode='lines', visible=False), secondary_y=False)

                    fig.add_trace(go.Scatter(name=r'$\sigma$', y=self.plastic_stress, x=self.plastic_strain,
                                             mode='lines'), secondary_y=False)
                    fig.add_trace(go.Scatter(name=r'$IR$', y=self.IR_temperature, x=self.plastic_strain,
                                             mode='lines', visible=False), secondary_y=True)

                    fig.add_trace(go.Scatter(name='$F_{in}$', y=self.F_in, x=micro_sec,
                                       mode='lines', visible=False), secondary_y=False)
                    fig.add_trace(go.Scatter(name=r'$F_{out}$', y=self.F_out, x=micro_sec,
                                       mode='lines', visible=False), secondary_y=False)

                    fig.add_trace(go.Scatter(name=r'$V_{in}$', y=self.v_in, x=micro_sec,
                                       mode='lines', visible=False), secondary_y=False)
                    fig.add_trace(go.Scatter(name=r'$V_{out}$', y=self.v_out, x=micro_sec,
                                       mode='lines', visible=False), secondary_y=False)

                    fig.add_trace(go.Scatter(name=r'$\epsilon_{plastic}$', y=self.plastic_strain, x=micro_sec,
                                             mode='lines', visible=False), secondary_y=False)
                    fig.add_trace(go.Scatter(name=r'$IR$', y=self.IR_temperature, x=micro_sec,
                                             mode='lines', visible=False), secondary_y=True)

                    fig.add_trace(go.Scatter(name=r'$\beta_{int}$', y=self.beta_int, x=self.plastic_strain,
                                             mode='lines', visible=False), secondary_y=False)

                    fig.add_trace(go.Scatter(name=r'$\Delta T = \beta_{int} \cdot W_p \textrm{ (Experiment)}$', y=self.IR_temperature, x=self.Wp,
                                             mode='lines', visible=False), secondary_y=False)

                    LR_name =  r"$\Delta T = " + str(self.LR_T_Wp_slope)[:5] + "W_p " + " + " \
                               + str(self.LR_T_Wp_intercept)[:5] + r"\textrm{ (Linear Regression) ____ }$"
                    fig.add_trace(go.Scatter(name=LR_name, y=self.LR_T_Wp, x=self.Wp, line=dict(dash='dash'),
                                             mode='lines', visible=False), secondary_y=False)

                    fig.update_layout(title_x=0.45, template='none',
                                      font=dict(family="Times New Roman", size=25),
                                      legend=dict(yanchor='top', xanchor='right', y=1.2, x=1,
                                                  font=dict(size=30)),
                                      margin=dict(l=200, r=250, t=200, b=250),
                                      updatemenus=[go.layout.Updatemenu(
                                          active=3,
                                          buttons=list(
                                              [dict(label='Raw Signals',
                                                    method='update',
                                                    args=[{'visible': [True] * 2 + [False] * 17},
                                                          {'title': 'Raw Signals',
                                                           'xaxis': {'title': 'Time [μs]'},
                                                           'yaxis': {'title': 'Amplitude [V]'},
                                                           "yaxis2.visible": False,
                                                           'showlegend': True}]),

                                               dict(label='Corrected Signals',
                                                    method='update',
                                                    args=[{'visible': [False] * 2 + [True] * 4 + [False] * 13},
                                                          {'title': r'Corrected Signals',
                                                           'xaxis': {'title': 'Time [μs]'},
                                                           'yaxis': {'title': 'Amplitude [V]'},
                                                           'yaxis2': {'title': 'Amplitude [V]',
                                                                      'color': 'Red',
                                                                      'zeroline': False,
                                                                      'mirror': True,
                                                                      'anchor': 'free',
                                                                      'overlaying': 'y',
                                                                      'side': 'right',
                                                                      'position': 1},
                                                           'showlegend': True}]),

                                               dict(label='Displacements',
                                                    method='update',
                                                    args=[{'visible': [False] * 6 + [True] * 2 + [False] * 11},
                                                          {'title': 'Displacements',
                                                           'xaxis': {'title': 'Time [μs]'},
                                                           'yaxis': {'title': 'Displacement [m]'},
                                                           "yaxis2.visible": False,
                                                           'showlegend': True}]),

                                               dict(label='Stress - Strain',
                                                    method='update',
                                                    args=[{'visible': [False] * 8 + [True] * 2 + [False] * 9},
                                                          {'title': 'True Stress and Temperature vs. True Plastic Strain',
                                                           'xaxis': {'title': 'Plastic Strain'},
                                                           'yaxis': {'title': 'Stress [MPa]',
                                                                     'zeroline': False,
                                                                     'mirror': True},

                                                           'yaxis2': {'title': r'${\Delta} T [Celsius]$',
                                                                      'color': 'Orange',
                                                                      'zeroline': False,
                                                                      'mirror': True,
                                                                      'anchor': 'free',
                                                                      'overlaying': 'y',
                                                                      'side': 'right',
                                                                      'position': 1},
                                                                      'showlegend': True}]),

                                               dict(label='Forces',
                                                    method='update',
                                                    args=[{'visible': [False] * 10 + [True] * 2 + [False] * 7},
                                                          {'title': 'Forces',
                                                           'xaxis': {'title': 'Time [μs]'},
                                                           'yaxis': {'title': 'Force [N]'},
                                                           "yaxis2.visible": False,
                                                           'showlegend': True}]),

                                               dict(label='Velocities',
                                                    method='update',
                                                    args=[{'visible': [False] * 12 + [True] * 2 + [False] * 5},
                                                          {'title': 'Velocities',
                                                           'xaxis': {'title': 'Time [μs]'},
                                                           'yaxis': {'title': 'Velocity [m/s]'},
                                                           "yaxis2.visible": False,
                                                           'showlegend': True}]),

                                               dict(label='Plastic Strain & Temperature',
                                                    method='update',
                                                    args=[{'visible': [False] * 14 + [True] * 2 + [False] * 3},
                                                          {'title': 'Temperature, Strain vs Time',
                                                           'xaxis': {'title': 'Time [μs]'},
                                                           'yaxis': {'title': 'Plastic Strain'},
                                                           'yaxis2': {'title': r'${\Delta} T [Celsius]$ ',
                                                                      'color': 'Orange',
                                                                      'zeroline': False,
                                                                      'mirror': True,
                                                                      'anchor': 'free',
                                                                      'overlaying': 'y',
                                                                      'side': 'right',
                                                                      'position': 1},
                                                           'showlegend': True}]),

                                               dict(label='beta_int',
                                                    method='update',
                                                    args=[{'visible': [False] * 16 + [True] + [False] * 2},
                                                          {'title': 'Energy Ratio',
                                                           'xaxis': {'title': 'True Plastic Strain'},
                                                           'yaxis': {'title': r'$\beta_{int}$'},
                                                           "yaxis2.visible": False,
                                                           'showlegend': False}]),

                                               dict(label='Temperature - Plastic Work',
                                                    method='update',
                                                    args=[{'visible': [False] * 17 + [True] * 2},
                                                          {'title': 'Energy Ratio',
                                                           'xaxis': {'title': 'Plastic Work [J]'},
                                                           'yaxis': {'title': r'${\Delta} T [Celsius]$'},
                                                           "yaxis2.visible": False,
                                                           'showlegend': True}]),
                                               ]),
                                          x=0.125, y=1.2
                                      )
                                      ])

                if self.specimen_mode == "shear":
                    vectors = [self.incid_strain, self.trans_strain, self.time]
                    df = np.transpose(np.array(vectors))
                    filepath = self.path_input + "/Analysis Results" + '/Bar Strains.csv'
                    np.savetxt(filepath, df, delimiter=',',
                               header='incident strain, transmitted strain, time [s]',
                               fmt='%s')

                    vectors = [self.og_vcc_incid, self.og_vcc_trans, self.og_time_incid]
                    df = np.transpose(np.array(vectors))
                    filepath = self.path_input + "/Analysis Results" + '/Raw Signals.csv'
                    np.savetxt(filepath, df, delimiter=',', header='Incident [V], Transmitted [V], time [s]',
                               fmt='%s')

                    vectors = [self.fixed_incident,
                               self.fixed_reflected,
                               self.fixed_transmitted,
                               self.time]
                    df = np.transpose(np.array(vectors))
                    filepath = self.path_input + "/Analysis Results" + '/Corrected Signals.csv'
                    np.savetxt(filepath, df, delimiter=',',
                               header='Incident [V], Reflected [V], Transmitted [V], time [s]',
                               fmt='%s')

                    vectors = [self.u_in, self.u_out, self.time]
                    df = np.transpose(np.array(vectors))
                    filepath = self.path_input + "/Analysis Results" + '/Displacements.csv'
                    np.savetxt(filepath, df, delimiter=',', header='u_in [m], u_out [m], time [s]', fmt='%s')

                    vectors = [self.F_in, self.F_out, self.time]
                    df = np.transpose(np.array(vectors))
                    filepath = self.path_input + "/Analysis Results" + '/Forces.csv'
                    np.savetxt(filepath, df, delimiter=',', header='F_in [N], F_out [N], time [s]', fmt='%s')

                    vectors = [self.v_in, self.v_out, self.time]
                    df = np.transpose(np.array(vectors))
                    filepath = self.path_input + "/Analysis Results" + '/Velocities.csv'
                    np.savetxt(filepath, df, delimiter=',', header='v_in [m/s], v_out [m/s], time [s]', fmt='%s')

                    fig = go.FigureWidget(
                        [
                            go.Scatter(name=r'$Incident$', y=self.og_vcc_incid, x=self.og_time_incid,
                                       mode='lines', visible=False),
                            go.Scatter(name=r'$Transmitted$', y=self.og_vcc_trans, x=self.og_time_trans,
                                       mode='lines', visible=False),

                            go.Scatter(name=r'$Incident$', y=self.fixed_incident, x=micro_sec,
                                       mode='lines', visible=False),
                            go.Scatter(name=r'$Transmitted$', y=self.fixed_transmitted, x=micro_sec,
                                       mode='lines', visible=False),
                            go.Scatter(name=r'$Reflected$', y=self.fixed_reflected, x=micro_sec,
                                       mode='lines', visible=False),
                            go.Scatter(name=r'$IR_{EXP}$', y=self.volt_IR_EXP, x=micro_sec,
                                       mode='lines', visible=False),

                            go.Scatter(name=r'$U_{in}$', y=self.u_in, x=micro_sec,
                                       mode='lines', visible=False),
                            go.Scatter(name=r'$U_{out}$', y=self.u_out, x=micro_sec,
                                       mode='lines', visible=False),

                            go.Scatter(name=r'$F_{in}$', y=self.F_in, x=micro_sec,
                                       mode='lines', visible=True),
                            go.Scatter(name=r'$F_{out}$', y=self.F_out, x=micro_sec,
                                       mode='lines', visible=True),

                            go.Scatter(name=r'$V_{in}$', y=self.v_in, x=micro_sec,
                                       mode='lines', visible=False),
                            go.Scatter(name=r'$V_{out}$', y=self.v_out, x=micro_sec,
                                       mode='lines', visible=False),

                        ]
                    )

                    fig.update_layout(title_x=0.5, template='none',
                                      font=dict(family="Gravitas One", size=22),
                                      legend=dict(yanchor='top', xanchor='right', y=0.99, x=0.99, itemsizing='trace'),
                                      updatemenus=[go.layout.Updatemenu(
                                          active=3,
                                          buttons=list(
                                              [dict(label='Raw Signals',
                                                    method='update',
                                                    args=[{'visible': [True]*2 + [False] * 10},
                                                          {'title': r'$Raw Signals$',
                                                           'xaxis': {'title': r'$Time [μs]$'},
                                                           'yaxis': {'title': r'$Amplitude [V]$'},
                                                           'showlegend': True}]),

                                               dict(label='Corrected Signals',
                                                    method='update',
                                                    args=[{'visible': [False] * 2 + [True] * 4 + [False] * 6},
                                                          {'title': r'$Corrected Signals$',
                                                           'xaxis': {'title': r'$Time [μs]$'},
                                                           'yaxis': {'title': r'$Amplitude [V]$'},
                                                           'showlegend': True}]),

                                               dict(label='Displacement',
                                                    method='update',
                                                    args=[{'visible': [False] * 6 + [True] * 2 + [False] * 4},
                                                          {'title': r'$Displacements$',
                                                           'xaxis': {'title': r'$Time [μs]$'},
                                                           'yaxis': {'title': r'$Displacement [m]$'},
                                                           'showlegend': True}]),

                                               dict(label='Forces',
                                                    method='update',
                                                    args=[{'visible': [False] * 8 + [True] * 2 + [False] * 2},
                                                          {'title': r'$Forces$',
                                                           'xaxis': {'title': r'$Time [μs]$'},
                                                           'yaxis': {'title': r'$Force [N]$'},
                                                           'showlegend': True}]),

                                               dict(label='Velocities',
                                                    method='update',
                                                    args=[{'visible': [False] * 10 + [True] * 2},
                                                          {'title': r'$Velocities$',
                                                           'xaxis': {'title': r'$Time [μs]$'},
                                                           'yaxis': {'title': r'$Velocity [m/s]$'},
                                                           'showlegend': True}]

                                                    ),
                                               ]),
                                          x=0.9, y=1.1
                                      )
                                      ])

                fig.update_layout(margin=dict(r=250))
                fig.write_html(self.path_input + "/Analysis Results" + '.html',
                               auto_open=self.auto_open_report,
                               include_mathjax='cdn')
                f_path = self.path_input + "\Analysis Results" + "\Parameters.txt"
        else:
            if bar_num == 1:
                if self.specimen_mode == "regular":

                    vectors = [self.og_vcc_incid, self.og_time_incid]
                    df = np.transpose(np.array(vectors))
                    filepath = self.path_input + "/Exp #" + str(exp_num) + '/Raw Signal.csv'
                    np.savetxt(filepath, df, delimiter=',', header='Incident [V], time [s]',
                               fmt='%s')

                    vectors = [self.fixed_incident,
                               self.fixed_reflected,
                               self.time]
                    df = np.transpose(np.array(vectors))
                    filepath = self.path_input + "/Exp #" + str(exp_num) + '/Corrected Signals.csv'
                    np.savetxt(filepath, df, delimiter=',',
                               header='Incident [V], Reflected [V], time [s]',
                               fmt='%s')

                    vectors = [self.u_in, self.time]
                    df = np.transpose(np.array(vectors))
                    filepath = self.path_input + "/Exp #" + str(exp_num) + '/Displacement.csv'
                    np.savetxt(filepath, df, delimiter=',', header='u_in [m], time [s]', fmt='%s')

                    vectors = [self.true_stress_strain[0], self.true_stress_strain[1]]
                    df = np.transpose(np.array(vectors))
                    filepath = self.path_input + "/Exp #" + str(exp_num) + '/Stress-Strain True.csv'
                    np.savetxt(filepath, df, delimiter=',', header='Strain, Stress', fmt='%s')

                    vectors = [self.eng_stress_strain[0], self.eng_stress_strain[1]]
                    df = np.transpose(np.array(vectors))
                    filepath = self.path_input + "/Exp #" + str(exp_num) + '/Stress-Strain Engineering.csv'
                    np.savetxt(filepath, df, delimiter=',', header='Strain, Stress', fmt='%s')

                    vectors = [self.F_in, self.time]
                    df = np.transpose(np.array(vectors))
                    filepath = self.path_input + "/Exp #" + str(exp_num) + '/Force.csv'
                    np.savetxt(filepath, df, delimiter=',', header='F_in [N], time [s]', fmt='%s')

                    vectors = [self.v_in, self.time]
                    df = np.transpose(np.array(vectors))
                    filepath = self.path_input + "/Exp #" + str(exp_num) + '/Velocity.csv'
                    np.savetxt(filepath, df, delimiter=',', header='v_in [m/s], time [s]', fmt='%s')

                    fig = go.FigureWidget(
                        [
                            go.Scatter(name=r'$Incident$', y=self.og_vcc_incid, x=self.og_time_incid,
                                       mode=r'lines', visible=False),

                            go.Scatter(name=r'$Incident$', y=self.fixed_incident, x=micro_sec,
                                       mode='lines', visible=False),
                            go.Scatter(name=r'$Reflected$', y=self.fixed_reflected, x=micro_sec,
                                       mode='lines', visible=False),

                            go.Scatter(name=r'$U_{in}$', y=self.u_in, x=micro_sec,
                                       mode='lines', visible=False),

                            go.Scatter(name=r'$\sigma_{Engineering}$', y=self.eng_stress_strain[1],
                                       x=self.eng_stress_strain[0], mode='lines'),
                            go.Scatter(name=r'$True$', y=self.true_stress_strain[1],
                                       x=self.true_stress_strain[0], mode='lines'),

                            go.Scatter(name=r'$F_{in}$', y=self.F_in, x=micro_sec,
                                       mode='lines', visible=False),

                            go.Scatter(name=r'$V_{in}$', y=self.v_in, x=micro_sec,
                                       mode='lines', visible=False)

                        ]
                    )

                    fig.update_layout(title_x=0.4, template='none',
                                      font=dict(family="Gravitas One", size=22),
                                      legend=dict(yanchor='top', xanchor='right', y=0.99, x=0.99),
                                      updatemenus=[go.layout.Updatemenu(
                                          active=3,
                                          buttons=list(
                                              [dict(label='Raw Signal',
                                                    method='update',
                                                    args=[{'visible': [True] + [False] * 7},
                                                          {'title': 'Raw Signals',
                                                           'xaxis': {'title': r'$Time [μs]$'},
                                                           'yaxis': {'title': r'$Amplitude [V]$'},
                                                           'showlegend': True}]),

                                               dict(label='Corrected Signals',
                                                    method='update',
                                                    args=[{'visible': [False] + [True] * 2 + [False] * 5},
                                                          {'title': r'$Corrected Signals$',
                                                           'xaxis': {'title': r'$Time [μs]$'},
                                                           'yaxis': {'title': r'$Amplitude [V]$'},
                                                           'showlegend': True}]),

                                               dict(label='Displacement',
                                                    method='update',
                                                    args=[{'visible': [False] * 3 + [True] + [False] * 4},
                                                          {'title': r'$Displacement$',
                                                           'xaxis': {'title': r'$Time [μs]$'},
                                                           'yaxis': {'title': r'$Displacement [m]$'},
                                                           'showlegend': True}]),

                                               dict(label='Stress - Strain',
                                                    method='update',
                                                    args=[{'visible': [False] * 4 + [True] * 2 + [False] * 2},
                                                          {'title': r'$Stress - Strain$',
                                                           'xaxis': {'title': r'$\epsilon [strain]$'},
                                                           'yaxis': {'title': r'$Stress [MPa]$'},
                                                           'showlegend': True}]),

                                               dict(label='Force',
                                                    method='update',
                                                    args=[{'visible': [False] * 6 + [True] + [False] },
                                                          {'title': r'$Forces$',
                                                           'xaxis': {'title': r'$Time [μs]$'},
                                                           'yaxis': {'title': r'$Force [N]$'},
                                                           'showlegend': True}]),

                                               dict(label='Velocity',
                                                    method='update',
                                                    args=[{'visible': [False] * 7 + [True]},
                                                          {'title': r'$Velocity$',
                                                           'xaxis': {'title': r'$Time [μs]$'},
                                                           'yaxis': {'title': r'$Velocity [m/s]$'},
                                                           'showlegend': True}]

                                                    ),
                                               ]),
                                          x=0.9, y=1.1
                                      )
                                      ])

                if self.specimen_mode == "shear":

                    vectors = [self.incid_strain, self.time]
                    df = np.transpose(np.array(vectors))
                    filepath = self.path_input + "/Exp #" + str(exp_num) + '/Bar Strain.csv'
                    np.savetxt(filepath, df, delimiter=',',
                               header='incident strain, time [s]',
                               fmt='%s')

                    vectors = [self.og_vcc_incid, self.og_time_incid]
                    df = np.transpose(np.array(vectors))
                    filepath = self.path_input + "/Exp #" + str(exp_num) + '/Raw Signal.csv'
                    np.savetxt(filepath, df, delimiter=',', header='Incident [V], time [s]',
                               fmt='%s')

                    vectors = [self.fixed_incident,
                               self.fixed_reflected,
                               self.time]

                    df = np.transpose(np.array(vectors))
                    filepath = self.path_input + "/Exp #" + str(exp_num) + '/Corrected Signals.csv'
                    np.savetxt(filepath, df, delimiter=',',
                               header='Incident [V], Reflected [V], time [s]',
                               fmt='%s')

                    vectors = [self.u_in, self.time]
                    df = np.transpose(np.array(vectors))
                    filepath = self.path_input + "/Exp #" + str(exp_num) + '/Displacement.csv'
                    np.savetxt(filepath, df, delimiter=',', header='u_in [m], time [s]', fmt='%s')

                    vectors = [self.F_in, self.time]
                    df = np.transpose(np.array(vectors))
                    filepath = self.path_input + "/Exp #" + str(exp_num) + '/Forces.csv'
                    np.savetxt(filepath, df, delimiter=',', header='F_in [N], time [s]', fmt='%s')

                    vectors = [self.v_in, self.time]
                    df = np.transpose(np.array(vectors))
                    filepath = self.path_input + "/Exp #" + str(exp_num) + '/Velocity.csv'
                    np.savetxt(filepath, df, delimiter=',', header='v_in [m/s], time [s]', fmt='%s')

                    fig = go.FigureWidget(
                        [
                            go.Scatter(name=r'$Incident$', y=self.og_vcc_incid, x=self.og_time_incid,
                                       mode='lines', visible=False),

                            go.Scatter(name=r'$Incident$', y=self.fixed_incident, x=micro_sec,
                                       mode='lines', visible=False),
                            go.Scatter(name=r'$Reflected$', y=self.fixed_reflected, x=micro_sec,
                                       mode='lines', visible=False),

                            go.Scatter(name=r'$U_{in}$', y=self.u_in, x=micro_sec,
                                       mode='lines', visible=False),

                            go.Scatter(name=r'$F_{in}$', y=self.F_in, x=micro_sec,
                                       mode='lines', visible=True),

                            go.Scatter(name=r'$V_{in}$', y=self.v_in, x=micro_sec,
                                       mode='lines', visible=False),

                        ]
                    )

                    fig.update_layout(title_x=0.5, template='none',
                                      font=dict(family="Gravitas One", size=22),
                                      legend=dict(yanchor='top', xanchor='right', y=0.99, x=0.99),
                                      updatemenus=[go.layout.Updatemenu(
                                          active=3,
                                          buttons=list(
                                              [dict(label='Raw Signal',
                                                    method='update',
                                                    args=[{'visible': [True] + [False] * 5},
                                                          {'title': r'$Raw Signals$',
                                                           'xaxis': {'title': r'$Time [μs]$'},
                                                           'yaxis': {'title': r'$Amplitude [V]$'},
                                                           'showlegend': True}]),

                                               dict(label='Corrected Signals',
                                                    method='update',
                                                    args=[{'visible': [False] + [True] * 2 + [False] * 3},
                                                          {'title': r'$Corrected Signals$',
                                                           'xaxis': {'title': r'$Time [μs]$'},
                                                           'yaxis': {'title': r'$Amplitude [V]$'},
                                                           'showlegend': True}]),

                                               dict(label='Displacement',
                                                    method='update',
                                                    args=[{'visible': [False] * 3 + [True] + [False] * 2},
                                                          {'title': r'$Displacement$',
                                                           'xaxis': {'title': r'$Time [μs]$'},
                                                           'yaxis': {'title': r'$Displacement [m]$'},
                                                           'showlegend': True}]),

                                               dict(label='Forces',
                                                    method='update',
                                                    args=[{'visible': [False] * 4 + [True] + [False]},
                                                          {'title': r'$Force$',
                                                           'xaxis': {'title': r'$Time [μs]$'},
                                                           'yaxis': {'title': r'$Force [N]$'},
                                                           'showlegend': True}]),

                                               dict(label='Velocities',
                                                    method='update',
                                                    args=[{'visible': [False] * 5 + [True]},
                                                          {'title': r'$Velocity$',
                                                           'xaxis': {'title': r'$Time [μs]$'},
                                                           'yaxis': {'title': r'$Velocity [m/s]$'},
                                                           'showlegend': True}]

                                                    ),
                                               ]),
                                          x=0.9, y=1.1
                                      )
                                      ])

                fig.add_annotation(dict(font=dict(color='red', size=16),
                                        font_family="Garamound",
                                        x=1,
                                        y=0.1,
                                        showarrow=False,
                                        text="Average Strain Rate: " + str(int(self.mean_strain_rate)) + " [1/s]",
                                        textangle=0,
                                        xanchor='left',
                                        xref="paper",
                                        yref="paper"))

                fig.add_annotation(dict(font=dict(color='black', size=16),
                                        font_family="Garamound",
                                        x=1,
                                        y=0.37,
                                        showarrow=False,
                                        font_color='blue',
                                        text="<b>Experiment Parameters:<b>                   ",
                                        textangle=0,
                                        xanchor='left',
                                        xref="paper",
                                        yref="paper"))

                fig.add_annotation(dict(font=dict(color='black', size=14),
                                        font_family="Garamound",
                                        x=1,
                                        y=0.32,
                                        showarrow=False,
                                        text="Specimen Diameter: " + str(parameters[0][1]) + " [m]",
                                        textangle=0,
                                        xanchor='left',
                                        xref="paper",
                                        yref="paper"))

                fig.add_annotation(dict(font=dict(color='black', size=14),
                                        font_family="Garamound",
                                        x=1,
                                        y=0.29,
                                        showarrow=False,
                                        text="Specimen Length: " + str(parameters[1][1]) + " [m]",
                                        textangle=0,
                                        xanchor='left',
                                        xref="paper",
                                        yref="paper"))

                fig.add_annotation(dict(font=dict(color='black', size=14),
                                        font_family="Garamound",
                                        x=1,
                                        y=0.26,
                                        showarrow=False,
                                        text="Bar Diameter: " + str(parameters[2][1]) + " [m]",
                                        textangle=0,
                                        xanchor='left',
                                        xref="paper",
                                        yref="paper"))

                fig.add_annotation(dict(font=dict(color='black', size=14),
                                        font_family="Garamound",
                                        x=1,
                                        y=0.23,
                                        showarrow=False,
                                        text="Young's Modulus: " + str(parameters[3][1] / (10 ** 9)) + " [GPa]",
                                        textangle=0,
                                        xanchor='left',
                                        xref="paper",
                                        yref="paper"))

                fig.add_annotation(dict(font=dict(color='black', size=14),
                                        font_family="Garamound",
                                        x=1,
                                        y=0.2,
                                        showarrow=False,
                                        text="Sound Velocity in Bar: " + str(parameters[6][1]) + " [m/s]",
                                        textangle=0,
                                        xanchor='left',
                                        xref="paper",
                                        yref="paper"))

                fig.add_annotation(dict(font=dict(color='black', size=14),
                                        font_family="Garamound",
                                        x=1,
                                        y=0.17,
                                        showarrow=False,
                                        text="Bridge Tension: " + str(parameters[8][1]) + " [V]",
                                        textangle=0,
                                        xanchor='left',
                                        xref="paper",
                                        yref="paper"))

                fig.add_annotation(dict(font=dict(color='black', size=14),
                                        font_family="Garamound",
                                        x=1,
                                        y=0.14,
                                        showarrow=False,
                                        text="Striker Velocity: " + str("%.2f" % self.mean_striker_velocity) + " [m/s]",
                                        textangle=0,
                                        xanchor='left',
                                        xref="paper",
                                        yref="paper"))

                fig.add_annotation(dict(font=dict(color='black', size=18),
                                        font_family="Garamound",
                                        x=1,
                                        y=0.6,
                                        showarrow=False,
                                        text="<b>Experiment no. " + str(exp_num) + "<b>",
                                        textangle=0,
                                        xanchor='left',
                                        xref="paper",
                                        yref="paper"))

                fig.add_annotation(dict(font=dict(color='black', size=14),
                                        font_family="Garamound",
                                        x=1,
                                        y=0.56,
                                        showarrow=False,
                                        text="Specimen type: " + str(self.specimen_mode),
                                        textangle=0,
                                        xanchor='left',
                                        xref="paper",
                                        yref="paper"))

                fig.add_annotation(dict(font=dict(color='black', size=14),
                                        font_family="Garamound",
                                        x=1,
                                        y=0.54,
                                        showarrow=False,
                                        text="Experiment mode: " + str(self.mode),
                                        textangle=0,
                                        xanchor='left',
                                        xref="paper",
                                        yref="paper"))

                fig.add_annotation(dict(font=dict(color='black', size=20),
                                        font_family="Garamound",
                                        x=1,
                                        y=0.8,
                                        showarrow=False,
                                        text="main Analysis Report",
                                        textangle=0,
                                        xanchor='left',
                                        xref="paper",
                                        yref="paper"))

                fig.update_layout(margin=dict(r=250))
                fig.write_html(self.path_input + "\Exp " + str(exp_num) + '.html',
                               auto_open=self.auto_open_report,
                               include_mathjax='cdn')

            if bar_num == 2:
                if self.specimen_mode == "regular":

                    vectors = [self.og_vcc_incid, self.og_vcc_trans, self.og_time_incid]
                    df = np.transpose(np.array(vectors))
                    filepath = self.path_input + "/Exp #" + str(exp_num) + '/Raw Signals.csv'
                    np.savetxt(filepath, df, delimiter=',', header='Incident [V], Transmitted [V], time [s]',
                               fmt='%s')

                    vectors = [self.fixed_incident,
                               self.fixed_reflected,
                               self.fixed_transmitted,
                               self.time]
                    df = np.transpose(np.array(vectors))
                    filepath = self.path_input + "/Exp #" + str(exp_num) + '/Corrected Signals.csv'
                    np.savetxt(filepath, df, delimiter=',',
                               header='Incident [V], Reflected [V], Transmitted [V], time [s]',
                               fmt='%s')

                    vectors = [self.u_in, self.u_out, self.time]
                    df = np.transpose(np.array(vectors))
                    filepath = self.path_input + "/Exp #" + str(exp_num) + '/Displacements.csv'
                    np.savetxt(filepath, df, delimiter=',', header='u_in [m], u_out [m], time [s]', fmt='%s')

                    vectors = [self.true_stress_strain[0], self.true_stress_strain[1]]
                    df = np.transpose(np.array(vectors))
                    filepath = self.path_input + "/Exp #" + str(exp_num) + '/Stress-Strain True.csv'
                    np.savetxt(filepath, df, delimiter=',', header='Strain, Stress', fmt='%s')

                    vectors = [self.eng_stress_strain[0], self.eng_stress_strain[1]]
                    df = np.transpose(np.array(vectors))
                    filepath = self.path_input + "/Exp #" + str(exp_num) + '/Stress-Strain Engineering.csv'
                    np.savetxt(filepath, df, delimiter=',', header='Strain, Stress', fmt='%s')

                    vectors = [self.F_in, self.F_out, self.time]
                    df = np.transpose(np.array(vectors))
                    filepath = self.path_input + "/Exp #" + str(exp_num) + '/Forces.csv'
                    np.savetxt(filepath, df, delimiter=',', header='F_in [N], F_out [N], time [s]', fmt='%s')

                    vectors = [self.v_in, self.v_out, self.time]
                    df = np.transpose(np.array(vectors))
                    filepath = self.path_input + "/Exp #" + str(exp_num) + '/Velocities.csv'
                    np.savetxt(filepath, df, delimiter=',', header='v_in [m/s], v_out [m/s], time [s]', fmt='%s')

                    fig = go.FigureWidget(
                        [
                            go.Scatter(name=r'$Incident$', y=self.og_vcc_incid, x=self.og_time_incid,
                                       mode='lines', visible=False),
                            go.Scatter(name=r'$Transmitted$', y=self.og_vcc_trans, x=self.og_time_trans,
                                       mode='lines', visible=False),

                            go.Scatter(name=r'$Incident$', y=self.fixed_incident, x=micro_sec,
                                       mode='lines', visible=False),
                            go.Scatter(name=r'$Transmitted$', y=self.fixed_transmitted, x=micro_sec,
                                       mode='lines', visible=False),
                            go.Scatter(name=r'$Reflected$', y=self.fixed_reflected, x=micro_sec,
                                       mode='lines', visible=False),

                            go.Scatter(name=r'$U_{in}$', y=self.u_in, x=micro_sec,
                                       mode='lines', visible=False),
                            go.Scatter(name=r'$U_{out}$', y=self.u_out, x=micro_sec,
                                       mode='lines', visible=False),

                            go.Scatter(name=r'$\sigma_{Engineering}$', y=self.eng_stress_strain[1],
                                       x=self.eng_stress_strain[0], mode='lines'),
                            go.Scatter(name=r'$\sigma_{True}$', y=self.true_stress_strain[1],
                                       x=self.true_stress_strain[0], mode='lines'),

                            go.Scatter(name='$F_{in}$', y=self.F_in, x=micro_sec,
                                       mode='lines', visible=False),
                            go.Scatter(name=r'$F_{out}$', y=self.F_out, x=micro_sec,
                                       mode='lines', visible=False),

                            go.Scatter(name=r'$V_{in}$', y=self.v_in, x=micro_sec,
                                       mode='lines', visible=False),
                            go.Scatter(name=r'$V_{out}$', y=self.v_out, x=micro_sec,
                                       mode='lines', visible=False),

                        ]
                    )

                    fig.update_layout(title_x=0.45, template='none',
                                      font=dict(family="Gravitas One", size=22),
                                      legend=dict(yanchor='top', xanchor='right', y=0.99, x=0.95),
                                      updatemenus=[go.layout.Updatemenu(
                                          active=3,
                                          buttons=list(
                                              [dict(label='Raw Signals',
                                                    method='update',
                                                    args=[{'visible': [True, True] + [False] * 11},
                                                          {'title': r'$Raw Signals$',
                                                           'xaxis': {'title': r'$Time [μs]$'},
                                                           'yaxis': {'title': r'$Amplitude [V]$'},
                                                           'showlegend': True}]),

                                               dict(label='Corrected Signals',
                                                    method='update',
                                                    args=[{'visible': [False] * 2 + [True] * 3 + [False] * 8},
                                                          {'title': r'$Corrected Signals$',
                                                           'xaxis': {'title': r'$Time [μs]$'},
                                                           'yaxis': {'title': r'$Amplitude [V]$'},
                                                           'showlegend': True}]),

                                               dict(label='Displacements',
                                                    method='update',
                                                    args=[{'visible': [False] * 5 + [True] * 2 + [False] * 6},
                                                          {'title': r'$Displacements$',
                                                           'xaxis': {'title': r'$Time [μs]$'},
                                                           'yaxis': {'title': r'$Displacement [m]$'},
                                                           'showlegend': True}]),

                                               dict(label='Stress - Strain',
                                                    method='update',
                                                    args=[{'visible': [False] * 7 + [True] * 2 + [False] * 4},
                                                          {'title': r'$Stress - Strain$',
                                                           'xaxis': {'title': r'$\epsilon [strain]$'},
                                                           'yaxis': {'title': 'Stress [MPa]'},
                                                           'showlegend': True}]),

                                               dict(label='Forces',
                                                    method='update',
                                                    args=[{'visible': [False] * 9 + [True] * 2 + [False] * 2},
                                                          {'title': r'$Forces$',
                                                           'xaxis': {'title': r'$Time [μs]$'},
                                                           'yaxis': {'title': r'$Force [N]$'},
                                                           'showlegend': True}]),

                                               dict(label='Velocities',
                                                    method='update',
                                                    args=[{'visible': [False] * 11 + [True] * 2},
                                                          {'title': r'$Velocities$',
                                                           'xaxis': {'title': r'$Time [μs]$'},
                                                           'yaxis': {'title': r'$Velocity [m/s]$'},
                                                           'showlegend': True}]

                                                    ),
                                               ]),
                                          x=0.9, y=1.1
                                      )
                                      ])

                if self.specimen_mode == "shear":

                    vectors = [self.incid_strain, self.trans_strain, self.time]
                    df = np.transpose(np.array(vectors))
                    filepath = self.path_input + "/Exp #" + str(exp_num) + '/Bar Strains.csv'
                    np.savetxt(filepath, df, delimiter=',',
                               header='incident strain, transmitted strain, time [s]',
                               fmt='%s')

                    vectors = [self.og_vcc_incid, self.og_vcc_trans, self.og_time_incid]
                    df = np.transpose(np.array(vectors))
                    filepath = self.path_input + "/Exp #" + str(exp_num) + '/Raw Signals.csv'
                    np.savetxt(filepath, df, delimiter=',', header='Incident [V], Transmitted [V], time [s]',
                               fmt='%s')

                    vectors = [self.fixed_incident,
                               self.fixed_reflected,
                               self.fixed_transmitted,
                               self.time]
                    df = np.transpose(np.array(vectors))
                    filepath = self.path_input + "/Exp #" + str(exp_num) + '/Corrected Signals.csv'
                    np.savetxt(filepath, df, delimiter=',',
                               header='Incident [V], Reflected [V], Transmitted [V], time [s]',
                               fmt='%s')

                    vectors = [self.u_in, self.u_out, self.time]
                    df = np.transpose(np.array(vectors))
                    filepath = self.path_input + "/Exp #" + str(exp_num) + '/Displacements.csv'
                    np.savetxt(filepath, df, delimiter=',', header='u_in [m], u_out [m], time [s]', fmt='%s')

                    vectors = [self.F_in, self.F_out, self.time]
                    df = np.transpose(np.array(vectors))
                    filepath = self.path_input + "/Exp #" + str(exp_num) + '/Forces.csv'
                    np.savetxt(filepath, df, delimiter=',', header='F_in [N], F_out [N], time [s]', fmt='%s')

                    vectors = [self.v_in, self.v_out, self.time]
                    df = np.transpose(np.array(vectors))
                    filepath = self.path_input + "/Exp #" + str(exp_num) + '/Velocities.csv'
                    np.savetxt(filepath, df, delimiter=',', header='v_in [m/s], v_out [m/s], time [s]', fmt='%s')

                    fig = go.FigureWidget(
                        [
                            go.Scatter(name=r'$Incident$', y=self.og_vcc_incid, x=self.og_time_incid,
                                       mode='lines', visible=False),
                            go.Scatter(name=r'$Transmitted$', y=self.og_vcc_trans, x=self.og_time_trans,
                                       mode='lines', visible=False),

                            go.Scatter(name=r'$Incident$', y=self.fixed_incident, x=micro_sec,
                                       mode='lines', visible=False),
                            go.Scatter(name=r'$Transmitted$', y=self.fixed_transmitted, x=micro_sec,
                                       mode='lines', visible=False),
                            go.Scatter(name=r'$Reflected$', y=self.fixed_reflected, x=micro_sec,
                                       mode='lines', visible=False),

                            go.Scatter(name=r'$U_{in}$', y=self.u_in, x=micro_sec,
                                       mode='lines', visible=False),
                            go.Scatter(name=r'$U_{out}$', y=self.u_out, x=micro_sec,
                                       mode='lines', visible=False),

                            go.Scatter(name=r'$F_{in}$', y=self.F_in, x=micro_sec,
                                       mode='lines', visible=True),
                            go.Scatter(name=r'$F_{out}$', y=self.F_out, x=micro_sec,
                                       mode='lines', visible=True),

                            go.Scatter(name=r'$V_{in}$', y=self.v_in, x=micro_sec,
                                       mode='lines', visible=False),
                            go.Scatter(name=r'$V_{out}$', y=self.v_out, x=micro_sec,
                                       mode='lines', visible=False),

                        ]
                    )

                    fig.update_layout(title_x=0.5, template='none',
                                      font=dict(family="Gravitas One", size=22),
                                      legend=dict(yanchor='top', xanchor='right', y=0.99, x=0.99,itemsizing='trace'),
                                      updatemenus=[go.layout.Updatemenu(
                                          active=3,
                                          buttons=list(
                                              [dict(label='Raw Signals',
                                                    method='update',
                                                    args=[{'visible': [True, True] + [False] * 9},
                                                          {'title': r'$Raw Signals$',
                                                           'xaxis': {'title': r'$Time [μs]$'},
                                                           'yaxis': {'title': r'$Amplitude [V]$'},
                                                           'showlegend': True}]),

                                               dict(label='Corrected Signals',
                                                    method='update',
                                                    args=[{'visible': [False] * 2 + [True] * 3 + [False] * 6},
                                                          {'title': r'$Corrected Signals$',
                                                           'xaxis': {'title': r'$Time [μs]$'},
                                                           'yaxis': {'title': r'$Amplitude [V]$'},
                                                           'showlegend': True}]),

                                               dict(label='Displacement',
                                                    method='update',
                                                    args=[{'visible': [False] * 5 + [True] * 2 + [False] * 4},
                                                          {'title': r'$Displacements$',
                                                           'xaxis': {'title': r'$Time [μs]$'},
                                                           'yaxis': {'title': r'$Displacement [m]$'},
                                                           'showlegend': True}]),

                                               dict(label='Forces',
                                                    method='update',
                                                    args=[{'visible': [False] * 7 + [True] * 2 + [False] * 2},
                                                          {'title': r'$Forces$',
                                                           'xaxis': {'title': r'$Time [μs]$'},
                                                           'yaxis': {'title': r'$Force [N]$'},
                                                           'showlegend': True}]),

                                               dict(label='Velocities',
                                                    method='update',
                                                    args=[{'visible': [False] * 9 + [True] * 2},
                                                          {'title': r'$Velocities$',
                                                           'xaxis': {'title': r'$Time [μs]$'},
                                                           'yaxis': {'title': r'$Velocity [m/s]$'},
                                                           'showlegend': True}]

                                                    ),
                                               ]),
                                          x=0.9, y=1.1
                                      )
                                      ])

                fig.add_annotation(dict(font=dict(color='red', size=16),
                                        font_family="Garamound",
                                        x=1,
                                        y=0.1,
                                        showarrow=False,
                                        text="Average Strain Rate: " + str(int(self.mean_strain_rate)) + " [1/s]",
                                        textangle=0,
                                        xanchor='left',
                                        xref="paper",
                                        yref="paper"))

                fig.add_annotation(dict(font=dict(color='black', size=16),
                                        font_family="Garamound",
                                        x=1,
                                        y=0.37,
                                        showarrow=False,
                                        font_color='blue',
                                        text="<b>Experiment Parameters:<b>                   ",
                                        textangle=0,
                                        xanchor='left',
                                        xref="paper",
                                        yref="paper"))

                fig.add_annotation(dict(font=dict(color='black', size=14),
                                        font_family="Garamound",
                                        x=1,
                                        y=0.32,
                                        showarrow=False,
                                        text="Specimen Diameter: " + str(parameters[0][1]) + " [m]",
                                        textangle=0,
                                        xanchor='left',
                                        xref="paper",
                                        yref="paper"))

                fig.add_annotation(dict(font=dict(color='black', size=14),
                                        font_family="Garamound",
                                        x=1,
                                        y=0.29,
                                        showarrow=False,
                                        text="Specimen Length: " + str(parameters[1][1]) + " [m]",
                                        textangle=0,
                                        xanchor='left',
                                        xref="paper",
                                        yref="paper"))

                fig.add_annotation(dict(font=dict(color='black', size=14),
                                        font_family="Garamound",
                                        x=1,
                                        y=0.26,
                                        showarrow=False,
                                        text="Bar Diameter: " + str(parameters[2][1]) + " [m]",
                                        textangle=0,
                                        xanchor='left',
                                        xref="paper",
                                        yref="paper"))

                fig.add_annotation(dict(font=dict(color='black', size=14),
                                        font_family="Garamound",
                                        x=1,
                                        y=0.23,
                                        showarrow=False,
                                        text="Young's Modulus: " + str(parameters[3][1] / (10 ** 9)) + " [GPa]",
                                        textangle=0,
                                        xanchor='left',
                                        xref="paper",
                                        yref="paper"))

                fig.add_annotation(dict(font=dict(color='black', size=14),
                                        font_family="Garamound",
                                        x=1,
                                        y=0.2,
                                        showarrow=False,
                                        text="Sound Velocity in Bar: " + str(parameters[6][1]) + " [m/s]",
                                        textangle=0,
                                        xanchor='left',
                                        xref="paper",
                                        yref="paper"))

                fig.add_annotation(dict(font=dict(color='black', size=14),
                                        font_family="Garamound",
                                        x=1,
                                        y=0.17,
                                        showarrow=False,
                                        text="Bridge Tension: " + str(parameters[8][1]) + " [V]",
                                        textangle=0,
                                        xanchor='left',
                                        xref="paper",
                                        yref="paper"))

                fig.add_annotation(dict(font=dict(color='black', size=14),
                                        font_family="Garamound",
                                        x=1,
                                        y=0.14,
                                        showarrow=False,
                                        text="Striker Velocity: " + str("%.2f" % self.mean_striker_velocity) + " [m/s]",
                                        textangle=0,
                                        xanchor='left',
                                        xref="paper",
                                        yref="paper"))

                fig.add_annotation(dict(font=dict(color='black', size=18),
                                        font_family="Garamound",
                                        x=1,
                                        y=0.6,
                                        showarrow=False,
                                        text="<b>Experiment no. " + str(exp_num) + "<b>",
                                        textangle=0,
                                        xanchor='left',
                                        xref="paper",
                                        yref="paper"))

                fig.add_annotation(dict(font=dict(color='black', size=14),
                                        font_family="Garamound",
                                        x=1,
                                        y=0.56,
                                        showarrow=False,
                                        text="Specimen type: " + str(self.specimen_mode),
                                        textangle=0,
                                        xanchor='left',
                                        xref="paper",
                                        yref="paper"))

                fig.add_annotation(dict(font=dict(color='black', size=14),
                                        font_family="Garamound",
                                        x=1,
                                        y=0.54,
                                        showarrow=False,
                                        text="Experiment mode: " + str(self.mode),
                                        textangle=0,
                                        xanchor='left',
                                        xref="paper",
                                        yref="paper"))

                fig.add_annotation(dict(font=dict(color='black', size=20),
                                        font_family="Garamound",
                                        x=1,
                                        y=0.8,
                                        showarrow=False,
                                        text="main Analysis Report",
                                        textangle=0,
                                        xanchor='left',
                                        xref="paper",
                                        yref="paper"))

                fig.update_layout(margin=dict(r=250))
                fig.write_html(self.path_input + "\Exp " + str(exp_num) + '.html',
                               auto_open=self.auto_open_report,
                               include_mathjax='cdn')
            f_path = self.path_input + "\Exp #" + str(exp_num) + "\Parameters.txt"

        if os.path.isfile(f_path):
            os.remove(f_path)
        f = open(f_path, 'x')
        f = open(f_path, 'r+')
        f.truncate(0)
        s = ""

        s += str(parameters[0][0]) + ": " + str(parameters[0][1]) + " [m]" +"\n"
        s += str(parameters[1][0]) + ": " + str(parameters[1][1]) + " [m]" + "\n"
        s += str(parameters[2][0]) + ": " + str(parameters[2][1]) + " [m]" + "\n"
        s += str(parameters[3][0]) + ": " + str(parameters[3][1]/(10**9)) + " [GPa]" + "\n"
        s += str(parameters[4][0]) + ": " + str(parameters[4][1]) + " [m]" + "\n"
        s += str(parameters[5][0]) + ": " + str(parameters[5][1]) + " [m]" +"\n"
        s += str(parameters[6][0]) + ": " + str(parameters[6][1]) + " [m/s]" + "\n"
        s += str(parameters[7][0]) + ": " + str(parameters[7][1]) + "\n"
        s += str(parameters[8][0]) + ": " + str(parameters[8][1]) + " [V]" + "\n"
        s += "Spacing: " + str(self.spacing) + " Points" + "\n"
        s += "Prominence: " + str(self.prominence_percent * 100) + "%" + "\n"
        s += "Curve Smoothing Parameter: " + str(self.smooth_value * 100) + "\n"
        s += "Average Strain Rate: " + str(self.mean_strain_rate) + "[1/s]"
        s += "\n"  # For some reason, there is a problem without a new line at the end of the defaults file.
        f.write(s)
        f.close()


Window.size = (900, 850)
Window.icon = "/2BarG_emblem.png"
Window.title = "main"
Window.top = 100
Window.left = 500


def resize(*args):
    Window.top = Window.top
    Window.left = Window.left
    Window.size = (900, 850)
    return True


Window.bind(on_resize=resize)


#   The following will hide the CMD window when the program is running.
if sys.platform == "win32":
    import ctypes

    ctypes.windll.user32.ShowWindow(ctypes.windll.kernel32.GetConsoleWindow(), 0)

BarG().run()
