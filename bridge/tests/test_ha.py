import json
import math
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import Mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from ha_client import HAConfigStore, HAService

class HATests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.config=HAConfigStore(Path(self.temp.name)/'ha.json')
        self.config.write({'url':'http://ha.local:8123','token':'secret-token','entities':[{'entity_id':'light.room','label':'卧室灯'},{'entity_id':'climate.room','label':'卧室空调'},{'entity_id':'sensor.temp','label':'温度'}]})
        self.service=HAService(self.config)
        self.states=[{'entity_id':'light.room','state':'on','attributes':{}},{'entity_id':'climate.room','state':'cool','attributes':{'temperature':25,'hvac_modes':['off','cool'],'min_temp':17,'max_temp':30,'target_temp_step':.5}},{'entity_id':'sensor.temp','state':'26.5','attributes':{'unit_of_measurement':'°C'}}]
        def request(config,path,body=None):
            if path=='/api/states':return self.states
            if path.startswith('/api/states/'):return next(x for x in self.states if x['entity_id']==path[len('/api/states/'):])
            return []
        self.service.request=Mock(side_effect=request);self.service.refresh();self.revision=self.config.read()['revision']
    def command(self,slot=0,action='turn_off',value=None,revision=None):
        return self.service.command({'slot':slot,'revision':self.revision if revision is None else revision,'action':action,'value':value})
    def test_secret_never_public_or_snapshot(self):
        self.assertNotIn('secret-token',json.dumps(self.config.public()))
        self.assertNotIn('secret-token',json.dumps(self.service.snapshot()))
        self.assertEqual(os.stat(self.config.path).st_mode & 0o777,0o600)
    def test_existing_secret_preserved(self):
        self.config.write({'entities':[]});self.assertEqual(self.config.read()['token'],'secret-token')
    def test_url_redirect_secret_validation(self):
        for url in ['ftp://ha.local','http://u:p@ha.local','http://ha.local/?x=1','http://ha.local/#x','http://ha.local/api','http://ha.local:xyz']:
            with self.subTest(url=url),self.assertRaises(ValueError):self.config.write({'url':url,'token':'new-secret'})
        with self.assertRaises(ValueError):self.config.write({'url':'http://other.local'})
    def test_entity_allowlist_and_duplicates(self):
        for entities in [[{'entity_id':'lock.front'}],[{'entity_id':'light.room'},{'entity_id':'light.room'}],[{'entity_id':'light.room/../../'}]]:
            with self.subTest(entities=entities),self.assertRaises(ValueError):self.config.write({'entities':entities})
    def test_light_uses_actual_service(self):
        self.command();self.assertTrue(any(c.args[1]=='/api/services/light/turn_off' and c.args[2]=={'entity_id':'light.room'} for c in self.service.request.call_args_list))
    def test_arbitrary_service_not_allowed(self):
        with self.assertRaises(ValueError):self.command(action='toggle_all')
    def test_sensor_read_only(self):
        with self.assertRaises(ValueError):self.command(slot=2)
    def test_offline_and_stale_block(self):
        self.service.cached['connected']=False
        with self.assertRaises(ValueError):self.command()
        self.service.cached.update(connected=True,updated_at_epoch=int(time.time())-31)
        with self.assertRaises(ValueError):self.command()
    def test_revision_prevents_wrong_entity(self):
        with self.assertRaises(ValueError):self.command(revision=0)
        self.config.write({'entities':[{'entity_id':'light.other'}]})
        with self.assertRaises(ValueError):self.command()
    def test_unavailable_revalidated_before_control(self):
        self.states[0]['state']='unavailable'
        with self.assertRaises(ValueError):self.command()
    def test_climate_mode_validation(self):
        self.command(slot=1,action='mode',value='cool')
        with self.assertRaises(ValueError):self.command(slot=1,action='mode',value='heat')
    def test_temperature_bounds(self):
        for value in [16,31,25.1,True,'nan','inf',None]:
            with self.subTest(value=value),self.assertRaises(ValueError):self.command(slot=1,action='temperature',value=value)
        self.command(slot=1,action='temperature',value=25.5)
    def test_boolean_slot_or_revision_rejected(self):
        with self.assertRaises(ValueError):self.command(slot=True)
        with self.assertRaises(ValueError):self.command(revision=True)
    def test_failed_refresh_does_not_erase_last_state(self):
        self.service.request.side_effect=ValueError('offline');self.service.refresh()
        self.assertFalse(self.service.snapshot()['connected']);self.assertEqual(len(self.service.snapshot()['entities']),3)
    def test_missing_entity_unavailable(self):
        self.states.pop();self.service.refresh();self.assertFalse(self.service.snapshot()['entities'][-1]['available'])
    def test_disabled_blocks_controls(self):
        self.service.enabled=lambda:False
        with self.assertRaises(ValueError):self.command()
    def test_slot_bounds(self):
        for slot in [-1,3,'0']:
            with self.subTest(slot=slot),self.assertRaises(ValueError):self.command(slot=slot)

    def test_brightness_requires_capability_and_integer(self):
        with self.assertRaises(ValueError): self.command(action='brightness',value=50)
        self.states[0]['attributes']['supported_color_modes']=['color_temp']
        self.command(action='brightness',value=70)
        self.assertTrue(any(c.args[1]=='/api/services/light/turn_on' and c.args[2].get('brightness_pct')==70 for c in self.service.request.call_args_list))
        for value in [-1,101,True,50.5,'50']:
            with self.subTest(value=value),self.assertRaises(ValueError):self.command(action='brightness',value=value)
    def test_vacuum_commands_follow_feature_flags(self):
        self.config.write({'entities':[{'entity_id':'vacuum.robot','label':'扫地机器人'}]})
        self.revision=self.config.read()['revision']
        self.states=[{'entity_id':'vacuum.robot','state':'docked','attributes':{'supported_features':8192|4|16}}]
        self.service.refresh()
        self.command(action='start');self.command(action='pause');self.command(action='return_to_base')
        with self.assertRaises(ValueError):self.command(action='stop')
        self.assertTrue(any(c.args[1]=='/api/services/vacuum/start' for c in self.service.request.call_args_list))
    def test_weather_and_vehicle_are_read_only(self):
        self.config.write({'entities':[{'entity_id':'weather.home','label':'天气'},{'entity_id':'sensor.tesla_battery_level','label':'车辆电量'}]})
        self.revision=self.config.read()['revision']
        self.states=[{'entity_id':'weather.home','state':'rainy','attributes':{'temperature':21,'humidity':85}},{'entity_id':'sensor.tesla_battery_level','state':'77','attributes':{'device_class':'battery'}}]
        self.service.refresh();self.assertEqual(self.service.snapshot()['entities'][1]['role'],'vehicle_battery')
        for slot in [0,1]:
            with self.assertRaises(ValueError):self.command(slot=slot,action='turn_on')
    def test_32_entity_limit(self):
        self.config.write({'entities':[{'entity_id':'sensor.e'+str(i)} for i in range(32)]})
        with self.assertRaises(ValueError):self.config.write({'entities':[{'entity_id':'sensor.e'+str(i)} for i in range(33)]})

    def test_fan_percentage_capability_and_range(self):
        self.config.write({'entities':[{'entity_id':'fan.purifier','label':'净化器'}]})
        self.revision=self.config.read()['revision']
        self.states=[{'entity_id':'fan.purifier','state':'off','attributes':{'supported_features':1,'percentage':66}}]
        self.service.refresh();self.command(action='percentage',value=70)
        self.assertTrue(any(c.args[1]=='/api/services/fan/set_percentage' and c.args[2].get('percentage')==70 for c in self.service.request.call_args_list))
        for value in [True,-1,101,1.5,'70']:
            with self.subTest(value=value),self.assertRaises(ValueError):self.command(action='percentage',value=value)
        self.states[0]['attributes']['supported_features']=0
        with self.assertRaises(ValueError):self.command(action='percentage',value=70)

if __name__=='__main__':unittest.main()
