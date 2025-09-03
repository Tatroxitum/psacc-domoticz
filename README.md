# psacc-domoticz

First release.

Special thanks to flobz (https://github.com/flobz/psa_car_controller) for is excellent work in integration of API of Stellantis vehicles

This python scripts gets data from the psa_car_controller developped by flobz and update in domoticz the corresponding devices.
All the domoticz devices are virtual devices that you have to create manually

Installation : 
Prerequisites : 
- Install flobz psacc server : https://github.com/flobz/psa_car_controller

Installation of psacc-domoticz : 
- git clone https://github.com/Tatroxitum/psacc-domoticz.git
- give the rights to execute : chmod +x psacc-domoticz.py
- rename config.json.example to config.json

    "psacc_server": the IP address and port of the previously installed psacc server, example : http://192.168.1.1:5000
    "VIN": Your vehicle VIN
    "domoticz_server": the IP address and port of Domoticz, example : http://192.168.1.2:5000
	"domoticz_login": your domoticz login, you can leave it as it is if you are on a trusted network
    "domoticz_password": your domoticz password, you can leave it as it is if you are on a trusted network
	
	For all these parameters, leave as it is if not used. Otherwise, put the idx of the virtual sensor in domoticz you have created
	For each, please create a virtual sensor with the corresponding parameters :
    "domoticz_idx_odometer": Odometer of the vehicle :
							"Counter", once created set it to "custom" to have the "km" axis
    "domoticz_idx_electric_odometer": Odometer of the vehicle when only electric mode is used in a trip (from the time you have installed the psacc server)
							"Counter", once created set it to "custom" to have the "km" axis
    "domoticz_idx_hybrid_odometer": Odometer of the vehicle when hybrid mode is used in a trip (from the time you have installed the psacc server)
							"Counter", once created set it to "custom" to have the "km" axis
    "domoticz_idx_battery": Current battery percentage of the vehicle
							"Percentage"
    "domoticz_idx_battery_autonomy": Current battery autonomy of the vehicle
							"custom sensor", axis label : "km"
    "domoticz_idx_fuel": Current fuel percentage of the vehicle
							"Percentage"
    "domoticz_idx_fuel_autonomy": Current fuel autonomy of the vehicle
							"Custom sensor", axis label : "km"
    "domoticz_idx_air_temperature": Current air temperature from the vehicle
							"Temperature"
    "domoticz_idx_update_date": last update date
							"Text"
    "domoticz_idx_charging_status": button indicating the charging state. If you click on it no action will be done and it will refresh itself after the script is executed
							"Switch", type "on/off", "X10"
	
	Note : if psacc server is set in miles you can replace the above "km" axis by "miles" ; its only a string without impact.
	
To execute periodicaly, add this line to your crontab
*/10 *   * * *   pi      python3 /YOUR_INSTALLATION_PATH/psacc-domoticz/psacc-domoticz.py --run
(/10 for every 10 minutes of the hour)


Tested environments : 
Domoticz 2024.4 
Domoticz 2025.1 

Once the devices are created in domoticz, you can add a floorplan to have a dedicated overview

For example :
![Image](https://github.com/user-attachments/assets/add5f8cb-dbf0-4bbe-878e-a0e931211853)

