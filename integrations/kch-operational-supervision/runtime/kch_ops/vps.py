"""Read-only Linux sampling. No process arguments, environments, signals or restarts.

This module is self-contained so the SSH adapter can transport the exact source
without installing a daemon or package on the observed VPS.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import sys
import time
from datetime import datetime, timezone


def read(path):
    return Path(path).read_text(encoding='utf-8', errors='replace')


def parse_stat(text):
    # comm can contain spaces and parentheses: split after its final closing ')'.
    first, last = text.index('('), text.rindex(')')
    fields = text[last + 2:].split()
    return {'pid': int(text[:first].strip()), 'comm': text[first+1:last],
            'state': fields[0], 'ppid': int(fields[1]),
            'cpu_ticks': int(fields[11]) + int(fields[12]),
            'start_ticks': int(fields[19]), 'rss_pages': int(fields[21])}


def snapshot(proc='/proc', *, allowed_uids=None, max_processes=5000):
    """An explicit UID allowlist is required to inspect process metadata."""
    root = Path(proc)
    if allowed_uids is not None and (not allowed_uids or any(type(x) is not int or x < 0 for x in allowed_uids)):
        raise ValueError('NONEMPTY_UID_ALLOWLIST_REQUIRED')
    cpu = [int(x) for x in read(root/'stat').splitlines()[0].split()[1:9]]
    if len(cpu) != 8:
        raise ValueError('CPU_STAT_INCOMPLETE')
    memory = {}
    for line in read(root/'meminfo').splitlines():
        key, value = line.split(':', 1)
        memory[key] = int(value.split()[0]) * 1024
    processes, errors = {}, []
    total_pids = 0
    if allowed_uids is not None:
        for directory in root.iterdir():
            if not directory.name.isdigit():
                continue
            total_pids += 1
            if total_pids > max_processes:
                errors.append('PROCESS_ENUMERATION_LIMIT')
                break
            try:
                # Ownership check precedes reading process content.
                if directory.stat().st_uid not in allowed_uids:
                    continue
                item = parse_stat(read(directory/'stat'))
                processes[str(item['pid'])] = item
            except FileNotFoundError:
                errors.append('PROCESS_EXIT_DURING_SAMPLE')
            except PermissionError:
                errors.append('PROCESS_PERMISSION_DENIED')
            except (OSError, ValueError, IndexError):
                errors.append('PROCESS_STAT_UNAVAILABLE')
    pressure = {}
    for resource in ('cpu', 'memory', 'io'):
        try:
            pressure[resource] = {}
            for line in read(root/'pressure'/resource).splitlines():
                fields = line.split()
                pressure[resource][fields[0]] = {key:float(value) for key,value in (f.split('=') for f in fields[1:])}
        except (OSError, ValueError):
            pressure[resource] = None
    return {'monotonic':time.monotonic(), 'cpu':cpu, 'memory':memory,
            'load_average':[float(x) for x in read(root/'loadavg').split()[:3]],
            'processes':processes, 'pressure':pressure, 'errors':errors,
            'process_scope':'UID_ALLOWLIST' if allowed_uids is not None else 'NOT_REQUESTED'}


def compare(before, after, *, ticks_per_second, page_size, cpu_count):
    elapsed = after['monotonic'] - before['monotonic']
    if elapsed <= 0 or min(ticks_per_second, page_size, cpu_count) <= 0:
        raise ValueError('INVALID_MEASUREMENT_INTERVAL')
    delta = [b-a for a,b in zip(before['cpu'], after['cpu'])]
    if len(delta) != 8 or any(x < 0 for x in delta) or sum(delta) <= 0:
        raise ValueError('CPU_COUNTER_RESET_OR_UNOBSERVED')
    total = sum(delta)
    rows = []
    for pid, current in after['processes'].items():
        previous = before['processes'].get(pid)
        cpu = None
        if previous and current['start_ticks'] == previous['start_ticks']:
            consumed = current['cpu_ticks'] - previous['cpu_ticks']
            if consumed >= 0:
                cpu = 100 * consumed / ticks_per_second / elapsed
        state = current['state']
        activity = ('ZOMBIE_OBSERVED' if state == 'Z' else
                    'UNINTERRUPTIBLE_WAIT_OBSERVED' if state == 'D' else
                    'IDENTITY_OR_BASELINE_UNAVAILABLE' if cpu is None else
                    'CPU_ACTIVITY_OBSERVED' if cpu > 0 else 'NO_CPU_DELTA_IN_WINDOW')
        rows.append({**current, 'cpu_percent_one_core':cpu,
                     'rss_bytes':max(0,current['rss_pages']) * page_size,
                     'activity':activity, 'useful_progress':'NOT_ESTABLISHED_BY_PROCESS_COUNTERS',
                     'orphan_status':'NOT_INFERRED_FROM_PPID'})
    rows.sort(key=lambda x: (x['state'] in ('Z','D'),x['cpu_percent_one_core'] or 0,x['rss_bytes']), reverse=True)
    memory = after['memory']
    available = memory.get('MemAvailable')
    return {'interval_seconds':elapsed,
            'cpu_busy_percent':100*(total-delta[3]-delta[4]-delta[7])/total,
            'cpu_iowait_percent':100*delta[4]/total, 'cpu_steal_percent':100*delta[7]/total,
            'cpu_count':cpu_count, 'load_average':after['load_average'],
            'memory_total_bytes':memory.get('MemTotal'), 'memory_available_bytes':available,
            'swap_used_bytes':memory.get('SwapTotal',0)-memory.get('SwapFree',0),
            'pressure':after['pressure'], 'process_count_observed':len(rows),
            'zombie_count':sum(x['state']=='Z' for x in rows),
            'uninterruptible_count':sum(x['state']=='D' for x in rows),
            'processes':rows, 'process_scope':after['process_scope'],
            'errors':before['errors']+after['errors']}


def collect(request):
    if sys.platform != 'linux':
        raise RuntimeError('LINUX_PROC_REQUIRED')
    interval = request.get('interval_seconds', 2)
    if type(interval) not in (int,float) or not 0.25 <= interval <= 10:
        raise ValueError('INTERVAL_OUT_OF_BOUNDS')
    uids = request.get('allowed_uids')
    services = request.get('services', [])
    if len(services)>20 or any(not isinstance(x,str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.@:-]{0,127}',x) for x in services):
        raise ValueError('INVALID_SERVICE_ALLOWLIST')
    before = snapshot(allowed_uids=uids)
    time.sleep(interval)
    after = snapshot(allowed_uids=uids)
    report = compare(before,after,ticks_per_second=os.sysconf('SC_CLK_TCK'),
                     page_size=os.sysconf('SC_PAGE_SIZE'),cpu_count=os.cpu_count() or 1)
    disk = shutil.disk_usage('/')
    inode = os.statvfs('/')
    report.update(schema='kch.vps-observation.v0.1.0', timestamp_utc=datetime.now(timezone.utc).isoformat(),
                  hostname=socket.gethostname(), disk_root={'total_bytes':disk.total,'free_bytes':disk.free,
                  'inodes_total':inode.f_files,'inodes_free':inode.f_favail},
                  services=[], process_rows_omitted=max(0,len(report['processes'])-100))
    report['processes'] = report['processes'][:100]
    for name in services:
        try:
            check = subprocess.run(['systemctl','is-active','--',name],capture_output=True,text=True,timeout=3)
            report['services'].append({'name':name,'exit_code':check.returncode,'activity':check.stdout.strip()[:100],
                                       'application_health':'NOT_VERIFIED_BY_SYSTEMD_ACTIVITY'})
        except (OSError, subprocess.TimeoutExpired) as error:
            report['services'].append({'name':name,'activity':'UNAVAILABLE','error':type(error).__name__})
    report['gate'] = 'OBSERVED_WITH_LIMITS' if report['errors'] else 'OBSERVED'
    report['meaning'] = 'Reachability and sampled resource use are not proof of useful work or application health.'
    report['mutations_performed'] = False
    return report


def ssh_command(profile):
    host,user = profile['host'],profile['user']
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9.:-]{0,252}',host) or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_-]{0,63}',user):
        raise ValueError('INVALID_SSH_TARGET')
    port = profile.get('port',22)
    if type(port) is not int or not 1 <= port <= 65535:
        raise ValueError('INVALID_SSH_PORT')
    if not profile.get('authorization_ref'):
        raise ValueError('EXACT_HOST_AUTHORIZATION_REQUIRED')
    expiry = datetime.fromisoformat(profile['expires_at_utc'].replace('Z','+00:00'))
    if expiry.tzinfo is None or datetime.now(timezone.utc)>=expiry:
        raise ValueError('SSH_LEASE_EXPIRED_OR_UNBOUND')
    key = Path(profile['identity_file']).resolve(strict=True)
    if not key.is_file():
        raise ValueError('IDENTITY_FILE_REQUIRED')
    return ['ssh','-T','-o','BatchMode=yes','-o','IdentitiesOnly=yes','-o','StrictHostKeyChecking=yes',
            '-o','ClearAllForwardings=yes','-o','ConnectTimeout=8','-o','ConnectionAttempts=1',
            '-i',str(key),'-p',str(port),f'{user}@{host}','python3','-B','-']


def diagnose_ssh(profile, request):
    timeout = profile.get('timeout_seconds',85)
    if type(timeout) not in (int,float) or not 5 <= timeout <= 85:
        raise ValueError('SSH_TIMEOUT_OUT_OF_BOUNDS')
    command = ssh_command(profile)
    source = Path(__file__).read_text(encoding='utf-8')
    payload = 'import json\n_KCH_REQUEST=json.loads('+repr(json.dumps(request,allow_nan=False))+')\n'+source
    # __future__ must be the first non-docstring statement in a Python program.
    payload = payload.replace('from __future__ import annotations\n','')
    started = time.monotonic()
    receipt = {'schema':'kch.vps-ssh-receipt.v0.1.0','host':profile['host'],
               'source_sha256':hashlib.sha256(source.encode()).hexdigest(),
               'authorization_ref':profile['authorization_ref'],
               'timestamp_utc':datetime.now(timezone.utc).isoformat(),'remote_mutations':False}
    try:
        result = subprocess.run(command,input=payload,text=True,encoding='utf-8',capture_output=True,timeout=timeout)
    except subprocess.TimeoutExpired as error:
        stderr = error.stderr or ''
        if isinstance(stderr,bytes): stderr=stderr.decode('utf-8',errors='replace')
        receipt.update(gate='SSH_DEADLINE_EXCEEDED',exit_code=None,
                       elapsed_seconds=time.monotonic()-started,timeout_seconds=timeout,
                       local_client_terminated=True,remote_process_exit='UNVERIFIED',
                       error=stderr[-3000:],observation=None)
        return receipt
    receipt.update(exit_code=result.returncode,elapsed_seconds=time.monotonic()-started)
    if result.returncode:
        receipt.update(gate='ACCESS_OR_EXECUTION_FAILED',error=result.stderr[-3000:])
    else:
        try:
            observation=json.loads(result.stdout)
            if not isinstance(observation,dict) or observation.get('schema')!='kch.vps-observation.v0.1.0':
                raise ValueError('REMOTE_OBSERVATION_SCHEMA_MISMATCH')
        except (ValueError,TypeError):
            receipt.update(gate='REMOTE_OUTPUT_INVALID',observation=None,
                           stdout_sha256=hashlib.sha256(result.stdout.encode()).hexdigest())
        else:
            receipt.update(gate='REMOTE_OBSERVATION_RECEIVED',observation=observation)
    return receipt


if __name__ == '__main__':
    print(json.dumps(collect(globals().get('_KCH_REQUEST',{})),allow_nan=False))
