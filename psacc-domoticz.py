#!/usr/bin/env python3
"""
@author: Tatroxitum
"""
# psacc-domoticz
# Copyright (C) 2025 Tatroxitum
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
#
VERSION = "v0.1.1"
################################################################################
# SCRIPT DEPENDENCIES
################################################################################


try:
    import argparse
    import base64
    import json
    import logging
    import os
    import re
    import requests
    import sys
    import time
    from datetime import datetime, timezone, timedelta
    from logging.handlers import RotatingFileHandler
    from urllib.parse import urlencode
    import urllib3
    from colorama import Fore, Style
    
except ImportError as exc:
    print(
        "Error: failed to import python required module : " + str(exc),
        file=sys.stderr,
    )
    sys.exit(2)

################################################################################
# Output Class in charge of managing all script output to file or console
################################################################################
class Output:
    def __init__(self, logs_folder=None, debug=False):
        self.__debug = debug
        self.__logger = logging.getLogger()
        self.__print_buffer = ""
        logs_folder = (
            os.path.dirname(os.path.realpath(__file__))
            if logs_folder is None
            else logs_folder
        )
        logfile = logs_folder + "/psacc-domoticz.log"

        # By default log to console
        self.print = self.__print_to_console

        # In standard mode log to a file
        if self.__debug is False:
            # Check if we can create logfile
            try:
                open(logfile, "a+").close()
            except Exception as e:
                raise RuntimeError('"%s" %s' % (logfile, e,))

            # Set the logfile format
            file_handler = RotatingFileHandler(logfile, "a", 1000000, 1)
            formatter = logging.Formatter("%(asctime)s : %(message)s")
            file_handler.setFormatter(formatter)
            self.__logger.setLevel(logging.INFO)
            self.__logger.addHandler(file_handler)
            self.print = self.__print_to_logfile

    def __print_to_console(self, string="", st=None, end=None):
        if st:
            st = st.upper()
            st = st.replace("OK", Fore.GREEN + "OK")
            st = st.replace("WW", Fore.YELLOW + "WW")
            st = st.replace("EE", Fore.RED + "EE")
            st = "[" + st + Style.RESET_ALL + "] "

        if end is not None:
            st = st + " " if st else ""
            print(st + "%-75s" % (string,), end="", flush=True)
            self.__print_buffer = self.__print_buffer + string
        elif self.__print_buffer:
            st = st if st else "[--] "
            print(st + string.rstrip())
            self.__print_buffer = ""
        else:
            st = st if st else "[--]"
            print(("{:75s}" + st).format(string.rstrip()))
            self.__print_buffer = ""

    def __print_to_logfile(self, string="", st=None, end=None):
        if end is not None:
            self.__print_buffer = self.__print_buffer + string
        else:
            st = st if st else "--"
            self.__logger.info(
                "%s : %s %s",
                st.upper().lstrip(),
                self.__print_buffer.lstrip().rstrip(),
                string.lstrip().rstrip()
            )
            self.__print_buffer = ""


def document_initialised(driver):
    return driver.execute_script("return true;")

################################################################################
# Configuration Class to parse and load config.json
################################################################################
class Configuration:
    def __init__(self, super_print=None, debug=False):
        self.__debug = debug

        # Supersede local print function if provided as an argument
        self.print = super_print if super_print else self.print

    def load_configuration_file(self, configuration_file):
        self.print(
            "Loading configuration file : " + configuration_file, end=""
        )  
        try:
            with open(configuration_file) as conf_file:
                content = json.load(conf_file)
        except json.JSONDecodeError as e:
            raise RuntimeError("json format error : " + str(e))
        except Exception:
            raise
        else:
            self.print(st="OK")
            return content


    def print(self, string="", st=None, end=None):  
        st = "[" + st + "] " if st else ""
        if end is None:
            print(st + string)
        else:
            print(st + string + " ", end="", flush="True")


################################################################################
# Object that retrieve the historical data from psacc server
################################################################################
class PSACCCrawler:
    
    def __init__(self, config_dict, super_print=None, debug=False):
        self.__debug = debug

        # Supersede local print function if provided as an argument
        self.print = super_print if super_print else self.print

        install_dir = os.path.dirname(os.path.realpath(__file__))
        self.configuration = {
            # Mandatory config values
            "psacc_server": None,
            "VIN": None,
            "domoticz_server": None,
            "domoticz_idx_odometer": None,
            "domoticz_idx_electric_odometer": None,
            "domoticz_idx_hybrid_odometer": None,
            "domoticz_idx_battery": None,
            "domoticz_idx_battery_autonomy": None,
            "domoticz_idx_fuel": None,
            "domoticz_idx_fuel_autonomy": None,
            "domoticz_idx_air_temperature": None,
            "domoticz_idx_update_date": None,
            "domoticz_idx_charging_status": None,
            "domoticz_login": None,
            "domoticz_password": None,
            "timeout": "30",
        }

        # Intialisation des variables contenant les données de psacc
        self.vehicleinfo = None
        self.vehicletrips = None

        self.print("Start loading psacc-domoticz configuration")
        try:
            self._load_configuration_items(config_dict)
            self.print("End loading psacc-domoticz configuration", end="")
            self.print(st="ok")
        except Exception:
            raise
        else:
            if self.__debug:
                self.print(st="ok")


    # Load configuration items
    def _load_configuration_items(self, config_dict):
        for param in list((self.configuration).keys()):
            if param not in config_dict:
                if self.configuration[param] is not None:
                    if self.__debug:
                        self.print(
                            '    "'
                            + param
                            + '" = "'
                            + str(self.configuration[param])
                            + '"',
                            end="",
                        )
                        self.print(
                            "param is not found in config file, using default value",
                            "WW",
                        )
                else:
                    self.print('    "' + param + '"', end="")
                    raise RuntimeError(
                        "param is missing in configuration file"
                    )
            else:
                self.configuration[param] = config_dict[param]
                if self.__debug:
                    self.print(st="OK")


    def get_vehicleinfo(self, fromcache=True):
        if self.__debug:
            self.print("get vehicle info data from psacc", end="")
            self.print(st="")
        ###### get json file from psacc server #####
        myurl=self.configuration["psacc_server"]+"/get_vehicleinfo/"+self.configuration["VIN"]
        if fromcache==True:
            req = requests.get(myurl,params="from_cache=1") #get from cache to avoid too much requests
        else:
            req = requests.get(myurl)
            
        if self.__debug:
            print(u'  '.join((u'GET-> ',myurl,' : ',str(req.status_code))).encode('utf-8'))

        if req.status_code==200 : # Réponse HTTP 200 : OK
            self.vehicleinfo = req.json()
            if self.__debug:
                self.print("json : " + str(self.vehicleinfo), end="")
                self.print(st="ok")
            return self.vehicleinfo
            
        else:
            self.print(st="EE")
        
        return False
      

    def get_vehicletrips(self):
        if self.__debug:
            self.print("get vehicle trips data from psacc", end="")
            self.print(st="")
        myurl = self.configuration["psacc_server"]+"/vehicles/trips"
        req = requests.get(myurl) 
        if self.__debug:
            print(u'  '.join((u'GET-> ',myurl,' : ',str(req.status_code))).encode('utf-8'))

        if req.status_code==200 : # Réponse HTTP 200 : OK
            self.vehicletrips = req.json()
            if self.__debug:
                self.print("json : " + str(req.json()), end="")
                self.print(st="ok")
            return self.vehicletrips
            
        else:
            self.print(st="EE")
        
        return False


    def force_vehicle_update(self):
        self.print("Force vehicule update", end="")
        
        myurl=self.configuration["psacc_server"]+"/wakeup/"+self.configuration["VIN"]
        req = requests.get(myurl)
        if self.__debug:
            print(u'  '.join((u'GET-> ',myurl,' : ',str(req.status_code))).encode('utf-8'))

        if req.status_code==200 : # Réponse HTTP 200 : OK
            if self.__debug:
                self.print("json : " + str(req.json()), end="")
                self.print(st="")
            if req.json()==True:
                return True
                

        self.print(st="EE")
        return False


################################################################################
# Object injects data into domoticz
################################################################################
class DomoticzInjector:
    def __init__(self, config_dict, super_print, debug=False):
        self.__debug = debug

        # Supersede local print function if provided as an argument
        self.print = super_print if super_print else self.print

        self.configuration = {
            # Mandatory config values
            "domoticz_idx_odometer": None,
            "domoticz_idx_electric_odometer": None,
            "domoticz_idx_hybrid_odometer": None,
            "domoticz_idx_battery": None,
            "domoticz_idx_battery_autonomy": None,
            "domoticz_idx_fuel": None,
            "domoticz_idx_fuel_autonomy": None,
            "domoticz_idx_air_temperature": None,
            "domoticz_idx_update_date": None,
            "domoticz_idx_charging_status": None,
            "domoticz_server": None,
            "domoticz_login": "",
            "domoticz_password": "",
            "timeout": "30",
            "download_folder": os.path.dirname(os.path.realpath(__file__)) + os.path.sep,
        }
        
        # Intialisation de la variable pour forcer la maj auprès de la voiture
        self.force_update = False
        
        self.print("Start Loading Domoticz configuration")
        try:
            self._load_configuration_items(config_dict)
            self.print("End loading domoticz configuration", end="")
            self.print(st="ok")
        except Exception:
            raise
        else:
            if self.__debug:
                self.print(st="ok")

        self.__http = urllib3.PoolManager(
            retries=1, timeout=int(str(self.configuration["timeout"]))
        )
       
    def open_url(self, uri, data=None):
        # Generate URL
        url_test = str(self.configuration["domoticz_server"]) + uri

        # Add Authentication Items if needed
        if self.configuration["domoticz_login"] != "":
            b64domoticz_login = base64.b64encode(
                str(self.configuration["domoticz_login"]).encode()
            )
            b64domoticz_password = base64.b64encode(
                str(self.configuration["domoticz_password"]).encode()
            )
            url_test = (
                url_test
                + "&username="
                + b64domoticz_login.decode()
                + "&password="
                + b64domoticz_password.decode()
            )

        try:
            response = self.__http.request("GET", url_test)
        except urllib3.exceptions.MaxRetryError as e:
            # HANDLE CONNECTIVITY ERROR
            raise RuntimeError("url=" + url_test + " : " + str(e))

        # HANDLE SERVER ERROR CODE
        if not response.status == 200:
            raise RuntimeError(
                "url="
                + url_test
                + " - (code = "
                + str(response.status)
                + ")\ncontent="
                + str(response.data)
            )

        try:
            j = json.loads(response.data.decode("utf-8"))
        except Exception as e:
            # Handle JSON ERROR
            raise RuntimeError("unable to parse the JSON : " + str(e))

        if j["status"].lower() != "ok":
            raise RuntimeError(
                "url="
                + url_test
                + "\nrepsonse="
                + str(response.status)
                + "\ncontent="
                + str(j)
            )

        return j

    # Load configuration items
    def _load_configuration_items(self, config_dict):
        for param in list((self.configuration).keys()):
            if param not in config_dict:
                if self.configuration[param] is not None:
                    if self.__debug:
                        self.print(
                            '    "%s" = "%s"' % (
                                param,
                                self.configuration[param],
                            ),
                            end="",
                        )
                        self.print(
                            "param is not found in config file, using default value",
                            "WW",
                        )
                else:
                    self.print('    "' + param + '"', end="")
                    raise RuntimeError(
                        "param is missing in configuration file"
                    )
            else:
                if (
                    param == "download_folder"
                    and str(config_dict[param])[-1] != os.path.sep
                ):
                    self.configuration[param] = (
                        str(config_dict[param]) + os.path.sep
                    )
                else:
                    self.configuration[param] = config_dict[param]

                if re.match(r".*(token|password).*", param, re.IGNORECASE):
                    if self.__debug:
                            self.print(
                            '    "'
                            + param
                            + '" = "'
                            + "*" * len(str(self.configuration[param]))
                            + '"',
                            end="",
                        )
                else:
                    if self.__debug:
                            self.print(
                            '    "'
                            + param
                            + '" = "'
                            + str(self.configuration[param])
                            + '"',
                            end="",
                        )

                if self.__debug:
                    self.print(st="OK")

    def sanity_check(self, debug=False):  
        self.print(
            "Check domoticz connectivity", end=""
        )  
        response = self.open_url("/json.htm?type=command&param=getversion")
        if response["status"].lower() == "ok":
            self.print(st="ok")

        if self.__debug:
            self.print(
                "Check domoticz Devices", end=""
            )  
        
        #if odometer defined
        if self.configuration["domoticz_idx_odometer"]:
            response = self.open_url(
                "/json.htm?type=command&param=getdevices&rid=" + str(self.configuration["domoticz_idx_odometer"])
            )

            if not "result" in response:
                raise RuntimeError(
                    "device "
                    + str(self.configuration["domoticz_idx_odometer"])
                    + " could not be found on domoticz server "
                    + str(self.configuration["domoticz_server"])
                )
            else:
                properly_configured = True
                dev_AddjValue = response["result"][0]["AddjValue"]
                dev_AddjValue2 = response["result"][0]["AddjValue2"]
                dev_SubType = response["result"][0]["SubType"]
                dev_Type = response["result"][0]["Type"]
                dev_SwitchTypeVal = response["result"][0]["SwitchTypeVal"]
                dev_Name = response["result"][0]["Name"]

                if self.__debug:
                    self.print(st="ok")

                # Retrieve Device Name
                if self.__debug:
                    self.print(
                        '    Device Name            : "'
                        + dev_Name
                        + '" (idx='
                        + self.configuration["domoticz_idx_odometer"]
                        + ")",
                        end="",
                    )  
                    self.print(st="ok")

                # Checking Device Type
                if self.__debug:
                    self.print(
                        '    Device Type            : "' + dev_Type + '"', end=""
                    )  
                if dev_Type == "RFXMeter":
                    if self.__debug:
                        self.print(st="ok")
                else:
                    self.print(
                        'wrong sensor type. Go to Domoticz/Hardware - Create a virtual-sensor type "Counter"',
                        st="EE",
                    )
                    properly_configured = False

                # Checking device subtype
                if self.__debug:
                    self.print(
                        '    Device SubType         : "' + dev_SubType + '"', end=""
                    )  
                if dev_SubType == "RFXMeter counter":
                    if self.__debug:
                        self.print(st="ok")
                else:
                    self.print(
                        'wrong sensor type. Go to Domoticz/Hardware - Create a virtual-sensor type "Counter"',
                        st="ee",
                    )
                    properly_configured = False

                # Checking for SwitchType
                if self.__debug:
                    self.print(
                        '    Device SwitchType      : "' + str(dev_SwitchTypeVal),
                        end="",
                    )  
                if dev_SwitchTypeVal == 3:
                    if self.__debug:
                        self.print(st="ok")
                else:
                    self.print(
                        "wrong switch type. Go to Domoticz - Select your counter - click edit - change type to custom",
                        st="ee",
                    )
                    properly_configured = False

                # Checking for Counter Divider
                if self.__debug:
                    self.print(
                        '    Device Counter Divided : "' + str(dev_AddjValue2) + '"',
                        end="",
                    )  
                if dev_AddjValue2 == 0:
                    if self.__debug:
                        self.print(st="ok")
                else:
                    self.print(
                        'wrong counter divided. Go to Domoticz - Select your counter - click edit - set "Counter Divided" to 0',
                        st="ee",
                    )
                    properly_configured = False

                # Checking Meter Offset
                if self.__debug:
                    self.print(
                        '    Device Meter Offset    : "' + str(dev_AddjValue) + '"',
                        end="",
                    )  
                if dev_AddjValue == 0:
                    if self.__debug:
                        self.print(st="ok")
                else:
                    self.print(
                        'wrong value for meter offset. Go to Domoticz - Select your counter - click edit - set "Meter Offset" to 0',
                        st="ee",
                    )
                    properly_configured = False

                if properly_configured is False:
                    raise RuntimeError(
                        "Set your device correctly and run the script again"
                    )
        
        #if electric only odometer defined
        if self.configuration["domoticz_idx_electric_odometer"]:
            response = self.open_url(
                "/json.htm?type=command&param=getdevices&rid=" + str(self.configuration["domoticz_idx_electric_odometer"])
            )

            if not "result" in response:
                raise RuntimeError(
                    "device "
                    + str(self.configuration["domoticz_idx_electric_odometer"])
                    + " could not be found on domoticz server "
                    + str(self.configuration["domoticz_server"])
                )
            else:
                properly_configured = True
                dev_AddjValue = response["result"][0]["AddjValue"]
                dev_AddjValue2 = response["result"][0]["AddjValue2"]
                dev_SubType = response["result"][0]["SubType"]
                dev_Type = response["result"][0]["Type"]
                dev_SwitchTypeVal = response["result"][0]["SwitchTypeVal"]
                dev_Name = response["result"][0]["Name"]

                if self.__debug:
                    self.print(st="ok")

                # Retrieve Device Name
                if self.__debug:
                    self.print(
                        '    Device Name            : "'
                        + dev_Name
                        + '" (idx='
                        + self.configuration["domoticz_idx_electric_odometer"]
                        + ")",
                        end="",
                    )  
                    self.print(st="ok")

                # Checking Device Type
                if self.__debug:
                    self.print(
                        '    Device Type            : "' + dev_Type + '"', end=""
                    )  
                if dev_Type == "RFXMeter":
                    if self.__debug:
                        self.print(st="ok")
                else:
                    self.print(
                        'wrong sensor type. Go to Domoticz/Hardware - Create a virtual-sensor type "Counter"',
                        st="EE",
                    )
                    properly_configured = False

                # Checking device subtype
                if self.__debug:
                    self.print(
                        '    Device SubType         : "' + dev_SubType + '"', end=""
                    )  
                if dev_SubType == "RFXMeter counter":
                    if self.__debug:
                        self.print(st="ok")
                else:
                    self.print(
                        'wrong sensor type. Go to Domoticz/Hardware - Create a virtual-sensor type "Counter"',
                        st="ee",
                    )
                    properly_configured = False

                # Checking for SwitchType
                if self.__debug:
                    self.print(
                        '    Device SwitchType      : "' + str(dev_SwitchTypeVal),
                        end="",
                    )  
                if dev_SwitchTypeVal == 3:
                    if self.__debug:
                        self.print(st="ok")
                else:
                    self.print(
                        "wrong switch type. Go to Domoticz - Select your counter - click edit - change type to custom",
                        st="ee",
                    )
                    properly_configured = False

                # Checking for Counter Divider
                if self.__debug:
                    self.print(
                        '    Device Counter Divided : "' + str(dev_AddjValue2) + '"',
                        end="",
                    )  
                if dev_AddjValue2 == 0:
                    if self.__debug:
                        self.print(st="ok")
                else:
                    self.print(
                        'wrong counter divided. Go to Domoticz - Select your counter - click edit - set "Counter Divided" to 0',
                        st="ee",
                    )
                    properly_configured = False

                # Checking Meter Offset
                if self.__debug:
                    self.print(
                        '    Device Meter Offset    : "' + str(dev_AddjValue) + '"',
                        end="",
                    )  
                if dev_AddjValue == 0:
                    if self.__debug:
                        self.print(st="ok")
                else:
                    self.print(
                        'wrong value for meter offset. Go to Domoticz - Select your counter - click edit - set "Meter Offset" to 0',
                        st="ee",
                    )
                    properly_configured = False

                if properly_configured is False:
                    raise RuntimeError(
                        "Set your device correctly and run the script again"
                    )
                    
        #if hybrid odometer defined
        if self.configuration["domoticz_idx_hybrid_odometer"]:
            response = self.open_url(
                "/json.htm?type=command&param=getdevices&rid=" + str(self.configuration["domoticz_idx_hybrid_odometer"])
            )

            if not "result" in response:
                raise RuntimeError(
                    "device "
                    + str(self.configuration["domoticz_idx_hybrid_odometer"])
                    + " could not be found on domoticz server "
                    + str(self.configuration["domoticz_server"])
                )
            else:
                properly_configured = True
                dev_AddjValue = response["result"][0]["AddjValue"]
                dev_AddjValue2 = response["result"][0]["AddjValue2"]
                dev_SubType = response["result"][0]["SubType"]
                dev_Type = response["result"][0]["Type"]
                dev_SwitchTypeVal = response["result"][0]["SwitchTypeVal"]
                dev_Name = response["result"][0]["Name"]

                if self.__debug:
                    self.print(st="ok")

                # Retrieve Device Name
                if self.__debug:
                        self.print(
                            '    Device Name            : "'
                            + dev_Name
                            + '" (idx='
                            + self.configuration["domoticz_idx_hybrid_odometer"]
                            + ")",
                            end="",
                        )  
                        self.print(st="ok")

                # Checking Device Type
                if self.__debug:
                    self.print(
                        '    Device Type            : "' + dev_Type + '"', end=""
                    )  
                if dev_Type == "RFXMeter":
                    if self.__debug:
                        self.print(st="ok")
                else:
                    self.print(
                        'wrong sensor type. Go to Domoticz/Hardware - Create a virtual-sensor type "Counter"',
                        st="EE",
                    )
                    properly_configured = False

                # Checking device subtype
                if self.__debug:
                    self.print(
                        '    Device SubType         : "' + dev_SubType + '"', end=""
                    )  
                if dev_SubType == "RFXMeter counter":
                    if self.__debug:
                        self.print(st="ok")
                else:
                    self.print(
                        'wrong sensor type. Go to Domoticz/Hardware - Create a virtual-sensor type "Counter"',
                        st="ee",
                    )
                    properly_configured = False

                # Checking for SwitchType
                if self.__debug:
                    self.print(
                        '    Device SwitchType      : "' + str(dev_SwitchTypeVal),
                        end="",
                    )  
                if dev_SwitchTypeVal == 3:
                    if self.__debug:
                        self.print(st="ok")
                else:
                    self.print(
                        "wrong switch type. Go to Domoticz - Select your counter - click edit - change type to custom",
                        st="ee",
                    )
                    properly_configured = False

                # Checking for Counter Divider
                if self.__debug:
                    self.print(
                        '    Device Counter Divided : "' + str(dev_AddjValue2) + '"',
                        end="",
                    )  
                if dev_AddjValue2 == 0:
                    if self.__debug:
                        self.print(st="ok")
                else:
                    self.print(
                        'wrong counter divided. Go to Domoticz - Select your counter - click edit - set "Counter Divided" to 0',
                        st="ee",
                    )
                    properly_configured = False

                # Checking Meter Offset
                if self.__debug:
                    self.print(
                        '    Device Meter Offset    : "' + str(dev_AddjValue) + '"',
                        end="",
                    )  
                if dev_AddjValue == 0:
                    if self.__debug:
                        self.print(st="ok")
                else:
                    self.print(
                        'wrong value for meter offset. Go to Domoticz - Select your counter - click edit - set "Meter Offset" to 0',
                        st="ee",
                    )
                    properly_configured = False

                if properly_configured is False:
                    raise RuntimeError(
                        "Set your device correctly and run the script again"
                    )

        #if battery defined
        if self.configuration["domoticz_idx_battery"]:
            response = self.open_url("/json.htm?type=command&param=getdevices&rid=" + str(self.configuration["domoticz_idx_battery"]))

            if not "result" in response:
                raise RuntimeError("device " + str(self.configuration["domoticz_idx_battery"])
                    + " could not be found on domoticz server " + str(self.configuration["domoticz_server"]))
            else:
                properly_configured = True
                dev_SubType = response["result"][0]["SubType"]
                dev_Type = response["result"][0]["Type"]
                dev_Name = response["result"][0]["Name"]
                if self.__debug:
                    self.print(st="ok")

                # Retrieve Device Name
                if self.__debug:
                    self.print('    Device Name            : "'+ dev_Name+ '" (idx='+ self.configuration["domoticz_idx_battery"]+ ")",end="",)  
                    self.print(st="ok")

                # Checking Device Type
                if self.__debug:
                    self.print('    Device Type            : "' + dev_Type + '"', end="")  
                if dev_Type == "General":
                    if self.__debug:
                        self.print(st="ok")
                else:
                    self.print('wrong sensor type. Go to Domoticz/Hardware - Create a virtual-sensor type "Percentage"',
                        st="EE",)
                    properly_configured = False

                # Checking device subtype
                if self.__debug:
                    self.print('    Device SubType         : "' + dev_SubType + '"', end="")  
                if dev_SubType == "Percentage":
                    if self.__debug:
                        self.print(st="ok")
                else:
                    self.print('wrong sensor type. Go to Domoticz/Hardware - Create a virtual-sensor type "Percentage"',
                        st="ee",)
                    properly_configured = False

                if properly_configured is False:
                    raise RuntimeError("Set your device correctly and run the script again")
        
        #if battery autonomy defined
        if self.configuration["domoticz_idx_battery_autonomy"]:
            response = self.open_url("/json.htm?type=command&param=getdevices&rid=" + str(self.configuration["domoticz_idx_battery_autonomy"]))

            if not "result" in response:
                raise RuntimeError("device " + str(self.configuration["domoticz_idx_battery_autonomy"])
                    + " could not be found on domoticz server " + str(self.configuration["domoticz_server"]))
            else:
                properly_configured = True
                dev_SubType = response["result"][0]["SubType"]
                dev_Type = response["result"][0]["Type"]
                dev_Name = response["result"][0]["Name"]
                if self.__debug:
                    self.print(st="ok")

                # Retrieve Device Name
                if self.__debug:
                    self.print('    Device Name            : "'+ dev_Name+ '" (idx='+ self.configuration["domoticz_idx_battery_autonomy"]+ ")",end="",)  
                    self.print(st="ok")

                # Checking Device Type
                if self.__debug:
                    self.print('    Device Type            : "' + dev_Type + '"', end="")  
                if dev_Type == "General":
                    if self.__debug:
                        self.print(st="ok")
                else:
                    self.print('wrong sensor type. Go to Domoticz/Hardware - Create a virtual-sensor type "Custom Sensor"',
                        st="EE",)
                    properly_configured = False

                # Checking device subtype
                if self.__debug:
                    self.print('    Device SubType         : "' + dev_SubType + '"', end="")  
                if dev_SubType == "Custom Sensor":
                    if self.__debug:
                        self.print(st="ok")
                else:
                    self.print('wrong sensor type. Go to Domoticz/Hardware - Create a virtual-sensor type "Custom Sensor"',
                        st="ee",)
                    properly_configured = False

                if properly_configured is False:
                    raise RuntimeError("Set your device correctly and run the script again")
        
        #if fuel defined
        if self.configuration["domoticz_idx_fuel"]:
            response = self.open_url("/json.htm?type=command&param=getdevices&rid=" + str(self.configuration["domoticz_idx_fuel"]))

            if not "result" in response:
                raise RuntimeError("device " + str(self.configuration["domoticz_idx_fuel"])
                    + " could not be found on domoticz server " + str(self.configuration["domoticz_server"]))
            else:
                properly_configured = True
                dev_SubType = response["result"][0]["SubType"]
                dev_Type = response["result"][0]["Type"]
                dev_Name = response["result"][0]["Name"]
                if self.__debug:
                    self.print(st="ok")

                # Retrieve Device Name
                if self.__debug:
                    self.print('    Device Name            : "'+ dev_Name+ '" (idx='+ self.configuration["domoticz_idx_fuel"]+ ")",end="",)  
                    self.print(st="ok")

                # Checking Device Type
                if self.__debug:
                    self.print('    Device Type            : "' + dev_Type + '"', end="")  
                if dev_Type == "General":
                    if self.__debug:
                        self.print(st="ok")
                else:
                    self.print('wrong sensor type. Go to Domoticz/Hardware - Create a virtual-sensor type "Percentage"',
                        st="EE",)
                    properly_configured = False

                # Checking device subtype
                if self.__debug:
                    self.print('    Device SubType         : "' + dev_SubType + '"', end="")  
                if dev_SubType == "Percentage":
                    if self.__debug:
                        self.print(st="ok")
                else:
                    self.print('wrong sensor type. Go to Domoticz/Hardware - Create a virtual-sensor type "Percentage"',
                        st="ee",)
                    properly_configured = False

                if properly_configured is False:
                    raise RuntimeError("Set your device correctly and run the script again")

        #if fuel autonomy defined
        if self.configuration["domoticz_idx_fuel_autonomy"]:
            response = self.open_url("/json.htm?type=command&param=getdevices&rid=" + str(self.configuration["domoticz_idx_fuel_autonomy"]))

            if not "result" in response:
                raise RuntimeError("device " + str(self.configuration["domoticz_idx_fuel_autonomy"])
                    + " could not be found on domoticz server " + str(self.configuration["domoticz_server"]))
            else:
                properly_configured = True
                dev_SubType = response["result"][0]["SubType"]
                dev_Type = response["result"][0]["Type"]
                dev_Name = response["result"][0]["Name"]
                if self.__debug:
                    self.print(st="ok")

                # Retrieve Device Name
                if self.__debug:
                    self.print('    Device Name            : "'+ dev_Name+ '" (idx='+ self.configuration["domoticz_idx_fuel_autonomy"]+ ")",end="",)  
                    self.print(st="ok")

                # Checking Device Type
                if self.__debug:
                    self.print('    Device Type            : "' + dev_Type + '"', end="")  
                if dev_Type == "General":
                    if self.__debug:
                        self.print(st="ok")
                else:
                    self.print('wrong sensor type. Go to Domoticz/Hardware - Create a virtual-sensor type "Custom Sensor"',
                        st="EE",)
                    properly_configured = False

                # Checking device subtype
                if self.__debug:
                    self.print('    Device SubType         : "' + dev_SubType + '"', end="")  
                if dev_SubType == "Custom Sensor":
                    if self.__debug:
                        self.print(st="ok")
                else:
                    self.print('wrong sensor type. Go to Domoticz/Hardware - Create a virtual-sensor type "Custom Sensor"',
                        st="ee",)
                    properly_configured = False

                if properly_configured is False:
                    raise RuntimeError("Set your device correctly and run the script again")
                    
        #if air temperature defined
        if self.configuration["domoticz_idx_air_temperature"]:
            response = self.open_url(
                "/json.htm?type=command&param=getdevices&rid=" + str(self.configuration["domoticz_idx_air_temperature"])
            )

            if not "result" in response:
                raise RuntimeError(
                    "device "
                    + str(self.configuration["domoticz_idx_air_temperature"])
                    + " could not be found on domoticz server "
                    + str(self.configuration["domoticz_server"])
                )
            else:
                properly_configured = True
                dev_AddjValue = response["result"][0]["AddjValue"]
                dev_AddjValue2 = response["result"][0]["AddjValue2"]
                dev_SubType = response["result"][0]["SubType"]
                dev_Type = response["result"][0]["Type"]
                dev_Name = response["result"][0]["Name"]

                if self.__debug:
                    self.print(st="ok")

                # Retrieve Device Name
                if self.__debug:
                    self.print(
                        '    Device Name            : "'
                        + dev_Name
                        + '" (idx='
                        + self.configuration["domoticz_idx_air_temperature"]
                        + ")",
                        end="",
                    )  
                    self.print(st="ok")

                # Checking Device Type
                if self.__debug:
                    self.print(
                        '    Device Type            : "' + dev_Type + '"', end=""
                    )  
                if dev_Type == "Temp":
                    if self.__debug:
                        self.print(st="ok")
                else:
                    self.print(
                        'wrong sensor type. Go to Domoticz/Hardware - Create a virtual-sensor type "Temperature"',
                        st="EE",
                    )
                    properly_configured = False

                # Checking device subtype
                if self.__debug:
                    self.print(
                        '    Device SubType         : "' + dev_SubType + '"', end=""
                    )  
                if dev_SubType == "LaCrosse TX3":
                    if self.__debug:
                        self.print(st="ok")
                else:
                    self.print(
                        'wrong sensor type. Go to Domoticz/Hardware - Create a virtual-sensor type "Temperature"',
                        st="ee",
                    )
                    properly_configured = False

                # Checking for Counter Divider
                if self.__debug:
                    self.print(
                        '    Device Counter Divided : "' + str(dev_AddjValue2) + '"',
                        end="",
                    )  
                if dev_AddjValue2 == 0:
                    if self.__debug:
                        self.print(st="ok")
                else:
                    self.print(
                        'wrong counter divided. Go to Domoticz - Select your counter - click edit - set "Counter Divided" to 0',
                        st="ee",
                    )
                    properly_configured = False

                # Checking Meter Offset
                if self.__debug:
                    self.print(
                        '    Device Meter Offset    : "' + str(dev_AddjValue) + '"',
                        end="",
                    )  
                if dev_AddjValue == 0:
                    if self.__debug:
                        self.print(st="ok")
                else:
                    self.print(
                        'wrong value for meter offset. Go to Domoticz - Select your counter - click edit - set "Meter Offset" to 0',
                        st="ee",
                    )
                    properly_configured = False

                if properly_configured is False:
                    raise RuntimeError(
                        "Set your device correctly and run the script again"
                    )
                    
        #if update date defined
        if self.configuration["domoticz_idx_update_date"]:
            response = self.open_url(
                "/json.htm?type=command&param=getdevices&rid=" + str(self.configuration["domoticz_idx_update_date"])
            )

            if not "result" in response:
                raise RuntimeError(
                    "device "
                    + str(self.configuration["domoticz_idx_update_date"])
                    + " could not be found on domoticz server "
                    + str(self.configuration["domoticz_server"])
                )
            else:
                properly_configured = True
                dev_AddjValue = response["result"][0]["AddjValue"]
                dev_AddjValue2 = response["result"][0]["AddjValue2"]
                dev_SubType = response["result"][0]["SubType"]
                dev_Type = response["result"][0]["Type"]
                dev_Name = response["result"][0]["Name"]

                if self.__debug:
                    self.print(st="ok")

                # Retrieve Device Name
                if self.__debug:
                    self.print(
                        '    Device Name            : "'
                        + dev_Name
                        + '" (idx='
                        + self.configuration["domoticz_idx_update_date"]
                        + ")",
                        end="",
                    )  
                    self.print(st="ok")

                # Checking Device Type
                if self.__debug:
                    self.print(
                        '    Device Type            : "' + dev_Type + '"', end=""
                    )  
                if dev_Type == "General":
                    if self.__debug:
                        self.print(st="ok")
                else:
                    self.print(
                        'wrong sensor type. Go to Domoticz/Hardware - Create a virtual-sensor type "Text"',
                        st="EE",
                    )
                    properly_configured = False

                # Checking device subtype
                if self.__debug:
                    self.print(
                        '    Device SubType         : "' + dev_SubType + '"', end=""
                    )  
                if dev_SubType == "Text":
                    if self.__debug:
                        self.print(st="ok")
                else:
                    self.print(
                        'wrong sensor type. Go to Domoticz/Hardware - Create a virtual-sensor type "Text"',
                        st="ee",
                    )
                    properly_configured = False

                # Checking for Counter Divider
                if self.__debug:
                    self.print(
                        '    Device Counter Divided : "' + str(dev_AddjValue2) + '"',
                        end="",
                    )  
                if dev_AddjValue2 == 0:
                    if self.__debug:
                        self.print(st="ok")
                else:
                    self.print(
                        'wrong counter divided. Go to Domoticz - Select your counter - click edit - set "Counter Divided" to 0',
                        st="ee",
                    )
                    properly_configured = False

                # Checking Meter Offset
                if self.__debug:
                    self.print(
                        '    Device Meter Offset    : "' + str(dev_AddjValue) + '"',
                        end="",
                    )  
                if dev_AddjValue == 0:
                    if self.__debug:
                        self.print(st="ok")
                else:
                    self.print(
                        'wrong value for meter offset. Go to Domoticz - Select your counter - click edit - set "Meter Offset" to 0',
                        st="ee",
                    )
                    properly_configured = False

                if properly_configured is False:
                    raise RuntimeError(
                        "Set your device correctly and run the script again"
                    )

        #if charging status defined
        if self.configuration["domoticz_idx_charging_status"]:
            response = self.open_url(
                "/json.htm?type=command&param=getdevices&rid=" + str(self.configuration["domoticz_idx_charging_status"])
            )

            if not "result" in response:
                raise RuntimeError(
                    "device "
                    + str(self.configuration["domoticz_idx_charging_status"])
                    + " could not be found on domoticz server "
                    + str(self.configuration["domoticz_server"])
                )
            else:
                properly_configured = True
                dev_SubType = response["result"][0]["SubType"]
                dev_Type = response["result"][0]["Type"]
                dev_Name = response["result"][0]["Name"]

                if self.__debug:
                    self.print(st="ok")

                # Retrieve Device Name
                if self.__debug:
                    self.print(
                        '    Device Name            : "'
                        + dev_Name
                        + '" (idx='
                        + self.configuration["domoticz_idx_charging_status"]
                        + ")",
                        end="",
                    )  
                    self.print(st="ok")

                # Checking Device Type
                if self.__debug:
                    self.print(
                        '    Device Type            : "' + dev_Type + '"', end=""
                    )  
                if dev_Type == "Lighting 1":
                    if self.__debug:
                        self.print(st="ok")
                else:
                    self.print(
                        'wrong sensor type. Go to Domoticz/Hardware - Create a virtual subtype on/off X10',
                        st="EE",
                    )
                    properly_configured = False

                # Checking device subtype
                if self.__debug:
                    self.print(
                        '    Device SubType         : "' + dev_SubType + '"', end=""
                    )  
                if dev_SubType == "X10":
                    if self.__debug:
                        self.print(st="ok")
                else:
                    self.print(
                        'wrong sensor type. Go to Domoticz/Hardware - Create a virtual switch subtype on/off X10',
                        st="ee",
                    )
                    properly_configured = False


    #Update all domoticz devices defined in config.json
    def update_devices(self, vehicleinfo_json_file, vehicletrips_jsonf_file=None):
        odometer_update_date = ""
        energy_fuel_update_date = ""
        energy_battery_update_date = ""
        
        #Update odometer or update date if defined 
        if self.configuration["domoticz_idx_odometer"] or self.configuration["domoticz_idx_update_date"]:
            date_string = vehicleinfo_json_file["timed_odometer"]["updated_at"]
            date_stringiso=datetime.fromisoformat(date_string)
            odometer_update_date=date_stringiso.astimezone(datetime.now().astimezone().tzinfo)
            
            #Update odometer if defined
            if self.configuration["domoticz_idx_odometer"]:
                mileage = int(vehicleinfo_json_file["timed_odometer"]["mileage"])
                # Generate URL
                url_args = {
                    "type": "command",
                    "param": "udevice",
                    "idx": self.configuration["domoticz_idx_odometer"],
                    "nValue":"0",
                    "svalue": str(mileage),
                }
                
                # Update Current
                url_current = "/json.htm?" + urlencode(url_args)
                if url_current:
                    if self.open_url(url_current):
                        self.print("update domoticz device odometer "+str(mileage)+" km",st="ok")
                    else:
                        self.print("update domoticz device odometer "+str(mileage)+" km",st="EE")

        #Update type of energy if defined (fuel and or electric) and/or autonomy and/or update date and/or charging status
        if (self.configuration["domoticz_idx_battery"] or
            self.configuration["domoticz_idx_fuel"] or
            self.configuration["domoticz_idx_battery_autonomy"] or
            self.configuration["domoticz_idx_fuel_autonomy"] or
            self.configuration["domoticz_idx_charging_status"] or
            self.configuration["domoticz_idx_update_date"] or
            self.configuration["domoticz_idx_electric_odometer"] or
            self.configuration["domoticz_idx_hybrid_odometer"]
            ):
                
            energy_content = vehicleinfo_json_file["energy"]
            
            for json_inner_array in energy_content:
                if json_inner_array["type"] == "Electric" and (self.configuration["domoticz_idx_battery"] or self.configuration["domoticz_idx_update_date"]):
                    
                    level = int(json_inner_array["level"])
                    
                    date_string = json_inner_array["updated_at"]
                    date_stringiso=datetime.fromisoformat(date_string)
                    energy_battery_update_date=date_stringiso.astimezone(datetime.now().astimezone().tzinfo)
                    
                    # Generate URL
                    url_args = {
                        "type": "command",
                        "param": "udevice",
                        "idx": self.configuration["domoticz_idx_battery"],
                        "nValue":"0",
                        "svalue": str(level),
                    }
                    # Update Current value
                    url_current = "/json.htm?" + urlencode(url_args)
                    if url_current:
                        if self.open_url(url_current):
                            self.print("update domoticz device battery "+str(level)+" %",st="ok")
                        else:
                            self.print("update domoticz device battery "+str(level)+" %",st="EE")
                             
                if json_inner_array["type"] == "Electric" and (self.configuration["domoticz_idx_battery_autonomy"] or self.configuration["domoticz_idx_update_date"]):
                    
                    autonomy = int(json_inner_array["autonomy"])
                    
                    date_string = json_inner_array["updated_at"]
                    date_stringiso=datetime.fromisoformat(date_string)
                    energy_fuel_update_date=date_stringiso.astimezone(datetime.now().astimezone().tzinfo)
                    
                    url_args = {
                        "type": "command",
                        "param": "udevice",
                        "idx": self.configuration["domoticz_idx_battery_autonomy"],
                        "nValue":"0",
                        "svalue": str(autonomy),
                    }
                    # Update Current value
                    url_current = "/json.htm?" + urlencode(url_args)
                    if url_current:
                        if self.open_url(url_current):
                            self.print("update domoticz device battery autonomy "+str(autonomy),st="ok")
                        else:
                            self.print("update domoticz device battery autonomy "+str(autonomy),st="EE")
                
                if json_inner_array["type"] == "Fuel" and self.configuration["domoticz_idx_fuel"]:
                    level = int(json_inner_array["level"])
                    # Generate URL
                    url_args = {
                        "type": "command",
                        "param": "udevice",
                        "idx": self.configuration["domoticz_idx_fuel"],
                        "nValue":"0",
                        "svalue": str(level),
                    }
                    # Update Current value
                    url_current = "/json.htm?" + urlencode(url_args)
                    if url_current:
                        if self.open_url(url_current):
                            self.print("update domoticz device fuel "+str(level)+" %",st="ok")
                        else:
                            self.print("update domoticz device fuel "+str(level)+" %",st="EE")
                
                if json_inner_array["type"] == "Fuel" and self.configuration["domoticz_idx_fuel_autonomy"]:
                    autonomy = int(json_inner_array["autonomy"])
                    # Generate URL
                    url_args = {
                        "type": "command",
                        "param": "udevice",
                        "idx": self.configuration["domoticz_idx_fuel_autonomy"],
                        "nValue":"0",
                        "svalue": str(autonomy),
                    }
                    # Update Current value
                    url_current = "/json.htm?" + urlencode(url_args)
                    if url_current:
                        if self.open_url(url_current):
                            self.print("update domoticz device fuel autonomy "+str(autonomy),st="ok")
                        else:
                            self.print("update domoticz device fuel autonomy "+str(autonomy),st="EE")
                
                if json_inner_array["type"] == "Electric" and self.configuration["domoticz_idx_charging_status"]:
                    #Update charging state if defined
                    charging_state = str(json_inner_array["charging"]["status"])
                    
                    #Get current domoticz status
                    # Generate URL
                    url_args = {
                        "type": "command",
                        "param": "getdevices",
                        "rid": self.configuration["domoticz_idx_charging_status"],
                    }
                        
                    # Get Current
                    url_current = "/json.htm?" + urlencode(url_args)
                    if url_current:
                        domoticz_charging_status_old = self.open_url(url_current)
                        if domoticz_charging_status_old:
                            self.print("get domoticz device charging status : "+str(domoticz_charging_status_old["result"][0]["Status"]),st="ok")
                        else:
                            self.print("get domoticz device charging status : "+str(domoticz_charging_status_old["result"][0]["Status"]),st="EE")
                    
                    current_charging_status = "Off"
                    if charging_state == "InProgress":
                        current_charging_status = "On"
                        self.force_update = True
                    
                    if domoticz_charging_status_old["result"][0]["Status"] != current_charging_status:
                        # Generate URL
                        url_args = {
                            "type": "command",
                            "param": "switchlight",
                            "idx": self.configuration["domoticz_idx_charging_status"],
                            "switchcmd":str(current_charging_status),
                        }
                            
                        # Update Current
                        url_current = "/json.htm?" + urlencode(url_args)
                        if url_current:
                            if self.open_url(url_current):
                                self.print("update domoticz device charging status : "+str(current_charging_status),st="ok")
                            else:
                                self.print("update domoticz device charging status : "+str(current_charging_status),st="EE")
        
        #Udpate date and verification of force update if charging
        if self.__debug:
            self.print("update domoticz device Odometer update date "+str(odometer_update_date),st="ok")
            self.print("update domoticz device Fuel update date "+str(energy_fuel_update_date),st="ok")
            self.print("update domoticz device Battery update date "+str(energy_battery_update_date),st="ok")
        most_recent_update_date = energy_battery_update_date
        if energy_fuel_update_date > energy_battery_update_date:
            most_recent_update_date = energy_fuel_update_date
        if most_recent_update_date < odometer_update_date: 
            most_recent_update_date = odometer_update_date
        
        if self.force_update:
            #verification of the last update date to be sure
            if (most_recent_update_date+timedelta(minutes=10)) > datetime.now(most_recent_update_date.now().astimezone().tzinfo):
                self.force_update = False
            
        #Update "update date" if defined
        if self.configuration["domoticz_idx_update_date"]:
            # Generate URL
            url_args = {
                "type": "command",
                "param": "udevice",
                "idx": self.configuration["domoticz_idx_update_date"],
                "nValue":"0",
                "svalue": str(most_recent_update_date.date()) + " " + str(most_recent_update_date.time()),
            }
                
            # Update Current
            url_current = "/json.htm?" + urlencode(url_args)
            if url_current:
                if self.open_url(url_current):
                    self.print("update domoticz device update date "+str(most_recent_update_date),st="ok")
                else:
                    self.print("update domoticz device update date "+str(most_recent_update_date),st="EE")
                        
        #Update air temperature if defined
        if self.configuration["domoticz_idx_air_temperature"]:
            temperature = int(vehicleinfo_json_file["environment"]["air"]["temp"])
            
            # Generate URL
            url_args = {
                "type": "command",
                "param": "udevice",
                "idx": self.configuration["domoticz_idx_air_temperature"],
                "nValue":"0",
                "svalue": str(temperature),
            }
            
            # Update Current
            url_current = "/json.htm?" + urlencode(url_args)
            if url_current:
                if self.open_url(url_current):
                    self.print("update domoticz device air temperature "+str(temperature)+" °C",st="ok")
                else:
                    self.print("update domoticz device air temperature "+str(temperature)+" °C",st="EE")

        #Update electric only odometer and hybrid/fuel odomoter
        if ((self.configuration["domoticz_idx_electric_odometer"] or self.configuration["domoticz_idx_hybrid_odometer"]) and 
        vehicletrips_jsonf_file
        ):
            total_electrical_distance = 0.0    
            total_hybrid_distance = 0.0    
            
            for json_inner_array in vehicletrips_jsonf_file:
                consumption_fuel_km = float(json_inner_array["consumption_fuel_km"])
                consumption_electric_km = float(json_inner_array["consumption_km"])
                distance = float(json_inner_array["distance"])
                    
                date_string=datetime.strptime(json_inner_array["start_at"], '%a, %d %b %Y %H:%M:%S %Z')
                update_dateLocal=date_string.astimezone(datetime.now().astimezone().tzinfo) #apply local timezone
                
                
                if(consumption_fuel_km==0):
                    total_electrical_distance=total_electrical_distance+distance
                else:
                    total_hybrid_distance = total_hybrid_distance + distance
                
            
            total_electrical_distance=round(total_electrical_distance,2)
            total_hybrid_distance=round(total_hybrid_distance,2)
            # Generate URL
            if self.configuration["domoticz_idx_electric_odometer"]:
                url_args = {
                    "type": "command",
                    "param": "udevice",
                    "idx": self.configuration["domoticz_idx_electric_odometer"],
                    "nValue":"0",
                    "svalue": str(total_electrical_distance),
                }
                # Update Current value
                url_current = "/json.htm?" + urlencode(url_args)
                if url_current:
                    if self.open_url(url_current):
                        self.print("update domoticz electric only odometer "+str(total_electrical_distance)+" km",st="ok")
                    else:
                        self.print("update domoticz electric only odometer "+str(total_electrical_distance)+" km",st="EE")
                        
            if self.configuration["domoticz_idx_hybrid_odometer"]:
                url_args = {
                    "type": "command",
                    "param": "udevice",
                    "idx": self.configuration["domoticz_idx_hybrid_odometer"],
                    "nValue":"0",
                    "svalue": str(total_hybrid_distance),
                }
                # Update Current value
                url_current = "/json.htm?" + urlencode(url_args)
                if url_current:
                    if self.open_url(url_current):
                        self.print("update domoticz hybrid mode odometer "+str(total_hybrid_distance)+" km",st="ok")
                    else:
                        self.print("update domoticz hybrid mode odometer "+str(total_hybrid_distance)+" km",st="EE")
                         

def exit_on_error(psacc_obj=None, domoticz=None, string="", debug=False):
    try:
        o
    except:
        print(string)
    else:
        o.print(string, st="EE")

    try:
        o
    except:
        print("Ended with error%s" % ("" if debug else " : // re-run the program with '--debug' option",))
    else:
        o.print(
            "Ended with error%s" % ("" if debug else " : // re-run the program with '--debug' option",),
            st="EE",
        )
    sys.exit(2)


def check_new_script_version():
    o.print("Check script version is up to date", end="")
    try:
        http = urllib3.PoolManager()
        user_agent = {"user-agent": "psacc-domoticz - " + VERSION}
        r = http.request(
            "GET",
            "https://api.github.com/repos/Tatroxitum/psacc-domoticz/releases/latest",
            headers=user_agent,
        )
        j = json.loads(r.data.decode("utf-8"))
    except Exception:
        raise
    else:
        if j["tag_name"] > VERSION:
            o.print(
                'New version "'
                + j["name"]
                + '"('
                + j["tag_name"]
                + ") available. Check : https://github.com/Tatroxitum/psacc-domoticz/releases/latest",
                st="ww",
            )
        else:
            o.print(st="ok")


if __name__ == "__main__":
    # Default config value
    script_dir = os.path.dirname(os.path.realpath(__file__)) + os.path.sep
    default_logfolder = script_dir
    default_configuration_file = script_dir + "/config.json"

    # COMMAND LINE OPTIONS
    parser = argparse.ArgumentParser(
        description="Load PSACC values into domoticz"
    )
    parser.add_argument("--version", action="version", version=VERSION)
    parser.add_argument(
        "-d",
        "--debug",
        action="store_true",
        help="active graphical debug mode (only for troubleshooting)",
    )
    parser.add_argument(
        "-l",
        "--logs-folder",
        help="specify the logs location folder (" + default_logfolder + ")",
        default=default_logfolder,
        nargs=1,
    )
    parser.add_argument(
        "-c",
        "--config",
        help="specify configuration location ("
        + default_configuration_file
        + ")",
        default=default_configuration_file,
        nargs=1,
    )
    parser.add_argument(
        "-r",
        "--run",
        action="store_true",
        help="run the script",
        required=True,
    )
    args = parser.parse_args()

    # Init output
    try:
        o = Output(
            logs_folder=str(args.logs_folder).strip("[]'"), debug=args.debug
        )
    except Exception as exc:
        exit_on_error(string=str(exc), debug=args.debug)

    # Print debug message
    if args.debug:
        o.print("DEBUG MODE ACTIVATED", end="")
        o.print("only use '--debug' for troubleshooting", st="WW")

    # New version checking
    try:
        check_new_script_version()
    except Exception as exc:
        exit_on_error(string=str(exc), debug=args.debug)

    # Load configuration
    try:
        c = Configuration(debug=args.debug, super_print=o.print)
        configuration_json = c.load_configuration_file(
            str(args.config).strip("[]'")
        )
        configuration_json["logs_folder"] = str(args.logs_folder).strip("[]'")
    except Exception as exc:
        exit_on_error(string=str(exc), debug=args.debug)

    # Create objects
    try:
        psaccserver = PSACCCrawler(
            configuration_json, super_print=o.print, debug=args.debug
        )
        domoticzserver = DomoticzInjector(
            configuration_json, super_print=o.print, debug=args.debug
        )
    except Exception as exc:
        exit_on_error(string=str(exc), debug=args.debug)

    # Check requirements on domoticz
    try:
        domoticzserver.sanity_check(args.debug)
    except Exception as exc:
        exit_on_error(psaccserver, domoticzserver, str(exc), debug=args.debug)

    # Get informations from psacc server
    try:
        vehicleinfo_json = psaccserver.get_vehicleinfo()
        vehicletrips_json = psaccserver.get_vehicletrips()
    except Exception as exc:
        exit_on_error(psaccserver, domoticzserver, str(exc), debug=args.debug)
    
    # Update domoticz
    try:
        domoticzserver.update_devices(vehicleinfo_json,vehicletrips_json)
        if domoticzserver.force_update == True:
            #force vehicule update and redo
            o.print("force update is true", st="WW") 
            if psaccserver.force_vehicle_update():
                o.print("waiting for 90 seconds", st="WW") 
                time.sleep(90) #wait 90 sec for update of the server
                get_vehicleinfo_json = psaccserver.get_vehicleinfo(fromcache=False)
                domoticzserver.update_devices(vehicleinfo_json)
    
    except Exception as exc:
        exit_on_error(psaccserver, domoticzserver, str(exc), debug=args.debug)

    o.print("Finished on success")
    sys.exit(0)
