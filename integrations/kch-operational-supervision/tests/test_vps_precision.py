"""Deterministic regression fixtures, not measurements of a live VPS."""
import importlib.util
from pathlib import Path
import unittest

spec=importlib.util.spec_from_file_location('vps_precision',Path(__file__).resolve().parents[1]/'runtime/kch_ops/vps.py')
vps=importlib.util.module_from_spec(spec)
spec.loader.exec_module(vps)

class PrecisionTests(unittest.TestCase):
    def sample(self,scope='NOT_REQUESTED'):
        return {'monotonic':0,'cpu':[0]*8,'memory':{},'load_average':[0,0,0],
                'processes':{},'errors':[],'pressure':{},'process_scope':scope}

    def compare(self,b,a):
        return vps.compare(b,a,ticks_per_second=100,page_size=4096,cpu_count=4)

    def test_unrequested_process_counts_are_unavailable(self):
        b=self.sample();a={**b,'monotonic':1,'cpu':[0,0,0,100,0,0,0,0]}
        r=self.compare(b,a)
        for k in ('process_count_observed','zombie_count','uninterruptible_count'):
            self.assertIsNone(r[k])

    def test_requested_empty_inventory_is_zero(self):
        b=self.sample('UID_ALLOWLIST');a={**b,'monotonic':1,'cpu':[0,0,0,100,0,0,0,0]}
        r=self.compare(b,a)
        self.assertEqual(r['process_count_observed'],0)
        self.assertEqual(r['zombie_count'],0)

    def test_exact_window_pressure_distinct_from_utilization(self):
        b=self.sample();b['pressure']={'cpu':{'some':{'total':1000000}}}
        a={**b,'monotonic':2,'cpu':[10,0,0,90,0,0,0,0],
           'pressure':{'cpu':{'some':{'total':2000000,'avg10':60}}}}
        r=self.compare(b,a)
        self.assertEqual(r['cpu_busy_percent'],10)
        self.assertEqual(r['pressure_sample_window']['cpu']['some']['percent_of_wall_interval'],50)
        self.assertEqual(r['pressure']['cpu']['some']['avg10'],60)
        self.assertNotIn('full',r['pressure_sample_window']['cpu'])

    def test_missing_is_not_zero(self):
        r=vps.pressure_window(self.sample(),self.sample(),1)
        self.assertEqual(r['cpu']['some']['state'],'UNAVAILABLE')
        self.assertIsNone(r['cpu']['some']['percent_of_wall_interval'])

    def test_reset_preserved(self):
        b=self.sample();b['pressure']={'cpu':{'some':{'total':4}}}
        a={**b,'pressure':{'cpu':{'some':{'total':3}}}}
        self.assertEqual(vps.pressure_window(b,a,1)['cpu']['some']['state'],'COUNTER_RESET')

    def test_invalid_counter_values_not_invented(self):
        for value in (None,'unknown',float('nan'),float('inf'),True):
            b=self.sample();b['pressure']={'cpu':{'some':{'total':0}}}
            a={**b,'pressure':{'cpu':{'some':{'total':value}}}}
            self.assertEqual(vps.pressure_window(b,a,1)['cpu']['some']['state'],'UNAVAILABLE')

    def test_mem_io_full_and_some(self):
        b=self.sample();a=self.sample()
        for resource in ('memory','io'):
            b['pressure'][resource]={'some':{'total':0},'full':{'total':0}}
            a['pressure'][resource]={'some':{'total':100000},'full':{'total':50000}}
        r=vps.pressure_window(b,a,1)
        self.assertEqual(r['memory']['some']['percent_of_wall_interval'],10)
        self.assertEqual(r['io']['full']['percent_of_wall_interval'],5)

    def test_nan_interval_rejected(self):
        b=self.sample();a={**b,'monotonic':float('nan'),'cpu':[1]*8}
        with self.assertRaises(ValueError):self.compare(b,a)

    def test_direct_pressure_invalid_intervals_rejected(self):
        for interval in (0,-1,float('nan'),float('inf'),True):
            with self.assertRaises(ValueError):vps.pressure_window(self.sample(),self.sample(),interval)

if __name__=='__main__':unittest.main()
