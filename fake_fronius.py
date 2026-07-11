import datetime
from fastapi import FastAPI

import pysenec
import asyncio
import aiohttp

def make_timestamp():
    return datetime.datetime.now().astimezone().replace(microsecond=0).isoformat()

app = FastAPI()

#@app.on_event("startup")
#async def startup_event():
#    print("Starting up!")
#    app.aiohttp_session = aiohttp.ClientSession()

#@app.on_event("shutdown")
#async def shutdown_event():
#    print("Shutting down")
#    await app.aiohttp_session.close()

class Memorizer:
    last_update = 0
    p_load = 0
    p_grid = 0
    p_pv = 0
    p_akku = 0
    soc = 0
    system_state = "NONE"
    temp = 0
    v = 0
    a = 0
    charging_info = 0

    def need_update(self):
        rightnow = int(round(datetime.datetime.now().timestamp()))
        return rightnow-self.last_update > 9 # min 9 seconds between updates
    
    def update(self, senec):
        self.p_load = -senec.house_power # this value is null if no meter is enabled ( + generator, - consumer )
        self.p_grid = senec.grid_state_power # this value is null if no meter is enabled ( + from grid, - to grid )
        self.p_pv = senec.solar_generated_power # this value is null if inverter is not running ( + production ( default ) )
        self.p_akku = -senec.battery_state_power # this value is null if no battery is active ( - charge, + discharge )
        self.soc = senec.battery_charge_percent
        self.system_state = senec.system_state
        self.temp = senec.battery_temp
        self.v = senec.battery_voltage
        self.a = senec.battery_current
        self.charging_info = senec.charging_info
        self.last_update = int(round(datetime.datetime.now().timestamp()))

    def GetPowerFlowRealtimeData(self):
        # "disabled", "normal", "service", "charge boost",
        # "nearly depleted", "suspended", "calibrate",
        # "grid support", "deplete recovery", "non operable (voltage)",
        # "non operable (temperature)", "preheating", # "stopped (temperature)", "battery full"
        # "nearly depleted" ... "nahezu aufgebraucht"
        # "suspended" ... "Energiesparmodus"
        # "disabled" ... "deaktiviert"
        # "calibrate" ... "Kalibriermodus"
        battery_mode = "normal"
        battery_standby = False
        if self.system_state == "BATTERY FULL":
            battery_mode = "battery full"
        if self.system_state == "SAFETY CHARGE READY":
            battery_mode = "battery full"
        if self.system_state == "OFF":
            battery_mode = "disabled"
            battery_standby = True
        if self.system_state == "GRID + DISCHARGE" and self.p_grid > 100:
            battery_mode = "grid support"
        if self.system_state == "BATTERY EMPTY":
            battery_mode = "suspended"
        elif not self.charging_info and self.soc < 10.0:
             battery_mode = "nearly depleted"
        if self.system_state == "EMERGENCY CHARGE":
            battery_mode = "deplete recovery"
        rel_SelfConsumption = None
        if self.p_pv > 0:
            rel_SelfConsumption = min(100.0, max(0, abs(self.p_load*100.0 / self.p_pv)))
        rel_Autonomy = None
        if self.p_load != 0:
            rel_Autonomy = min(100.0, max(0, 1 - abs(max(0,self.p_grid) / self.p_load))*100.0)
        return {"Body":{"Data": {"Inverters": { "1": {"DT":1,
                                                       "P":self.p_pv,
                                                       "Battery_Mode" : battery_mode,
                                                       "SOC":self.soc}},
                                    "Site": {"Meter_Location":"grid",
                        "Mode":"bidirectional",
                        "BatteryStandby" : battery_standby,
                        "P_Grid":self.p_grid,
                        "P_Load":self.p_load,
                        "P_Akku":self.p_akku,
                        "P_PV":self.p_pv,
                        "rel_Autonomy":rel_Autonomy,
                        "rel_SelfConsumption":rel_SelfConsumption},
                        "Smartloads" : {
                            "Ohmpilots" : {}
                        },
                        "Version":"12"}
                        },
                "Head" : { "RequestArguments" : {}, # function doesnt take any arguments
                            "Status": {"Code":0,
                                "Reason": "",
                                "UserMessage":""}},
                "Timestamp" : make_timestamp() }
    
    def GetStorageRealtimeData(self, Scope, DeviceId):
        # for BYD Box at section Controller
        # Status value | Description 
        # 0 STANDBY
        # 1 INACTIVE
        # 2 DARKSTART
        # 3 ACTIVE
        # 4 FAULT
        # 5 UPDATING
        Status_BatteryCell = 3
        if self.charging_info:
            Status_BatteryCell = 3 # if we're charging, we're active
        elif self.system_state == "BATTERY EMPTY":
            Status_BatteryCell = 0
        elif self.system_state == "BATTERY FULL":
            Status_BatteryCell = 1
        elif self.system_state == "SAFETY CHARGE READY":
            Status_BatteryCell = 1
        elif self.system_state == "OWN CONSUMPTION":
            Status_BatteryCell = 1
        elif self.system_state == "OFF":
            Status_BatteryCell = 0
        return {"Body":{"Data":{ "Controller" : {
                "Capacity_Maximum" : 10000.0,
                "Current_DC" : self.a,
                "DesignedCapacity" : 10000.0,
                "Details" : {
                "Manufacturer" : "BYD",
                "Model" : "BYD Battery-Box Premium HV",
                "Serial" : "P030T020Z2202261449     "
                },
                "Enable" : 1,
                "StateOfCharge_Relative" : self.soc,
                "Status_BatteryCell" : Status_BatteryCell,
                "Temperature_Cell" : self.temp,
                "TimeStamp" : self.last_update,
                "Voltage_DC" : self.v
            },
            "Modules" : [] }},
                "Head":{"RequestArguments" : { "Scope" : Scope, "DeviceId" : DeviceId },
                        "Status": {"Code":0,
                                "Reason":"",
                                "UserMessage":""}},
                "Timestamp" : make_timestamp() }


memorizer = Memorizer()

@app.get("/solar_api/v1/GetPowerFlowRealtimeData.fcgi")
async def GetPowerFlowRealtimeData():#Scope: str, DeviceId: str):
    global memorizer
    if memorizer.need_update():
        host = "192.168.178.59"
        async with aiohttp.ClientSession() as session:
            senec = pysenec.Senec(host, session)
            await senec.update()
            memorizer.update(senec)
            return memorizer.GetPowerFlowRealtimeData()
    
    return memorizer.GetPowerFlowRealtimeData()

@app.get("/solar_api/v1/GetStorageRealtimeData.cgi")
async def GetStorageRealtimeData(Scope: str, DeviceId: str):
    global memorizer
    if memorizer.need_update():
        host = "192.168.178.59"
        async with aiohttp.ClientSession() as session:
            senec = pysenec.Senec(host, session)
            await senec.update()
            memorizer.update(senec)
            return memorizer.GetStorageRealtimeData(Scope, DeviceId)
    return memorizer.GetStorageRealtimeData(Scope, DeviceId)

@app.get("/solar_api/v1/GetOhmPilotRealtimeData.cgi")
async def GetOhmPilotRealtimeData(Scope: str, DeviceId: str):
    return {"Body":{"Data":{}},
            "Head":{"RequestArguments" : { "DeviceClass" : "OhmPilot",
                                            "Scope" : Scope,
                                            "DeviceId" : DeviceId },
                    "Status": {"Code":12,
                            "Reason":"DeviceId '" + str(DeviceId) + "' does not exist",
                            "UserMessage":""}},
            "Timestamp" : make_timestamp() }



