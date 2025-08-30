# psacc-domoticz

Under development version, use at your own risk !!

Special thanks to flobz for is excellent work in integration of stellantis cars


installation : 
install flobz psacc server : https://github.com/flobz/psa_car_controller

git clone https://github.com/Tatroxitum/psacc-domoticz.git
give the rights to exectue : chmod +x psacc-domoticz.py

rename config.json.example to config.json

    "psacc_server": the IP address and port of the previously installed psacc server
    "VIN": Your car VIN
    "domoticz_server": the IP address and port of Domoticz
	
	For all these parameters, leave as it is if not used. Otherwise, put the idx of the virtual sensor in domoticz you have created
    "domoticz_idx_odometer":
    "domoticz_idx_battery":
    "domoticz_idx_battery_autonomy":
    "domoticz_idx_fuel": 
    "domoticz_idx_fuel_autonomy": 
    "domoticz_login": 
    "domoticz_password": 