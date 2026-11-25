"""No real network or process mutations in recovery-policy tests."""
import subprocess
import os
from pathlib import Path
import pytest
from scripts.public_watchdog import Recovery,repair


def test_transient_failure_does_not_reconnect_and_online_resets_counter():
    monitor=Recovery();calls=[]
    assert monitor.tick('public',check=lambda *a,**k:False,fix=lambda:calls.append(1),clock=lambda:0)=='confirming_failure'
    assert monitor.tick('public',check=lambda *a,**k:True,clock=lambda:1)=='online'
    assert monitor.failures==0 and not calls


def test_reconnects_only_when_local_backend_ready():
    monitor=Recovery();calls=[]
    check=lambda url,**kw:kw.get('local',False)
    assert monitor.tick('public',check=check,fix=lambda:calls.append(1),clock=lambda:0)=='confirming_failure'
    assert monitor.tick('public',check=check,fix=lambda: calls.append(1) or True,clock=lambda:30)=='reconnected'
    assert calls==[1] and monitor.failures==0


def test_local_backend_failure_is_not_treated_as_a_tunnel_failure():
    monitor=Recovery();monitor.failures=1
    def forbidden():raise AssertionError('Must not rotate a tunnel for a local failure')
    assert monitor.tick('public',check=lambda *a,**k:False,fix=forbidden,clock=lambda:30)=='local_backend_unavailable'
    assert monitor.tick('public',check=lambda *a,**k:False,fix=forbidden,clock=lambda:60)=='backoff'


def test_failed_repairs_back_off_and_do_not_loop_deployments():
    monitor=Recovery();monitor.failures=1;calls=[]
    check=lambda url,**kw:kw.get('local',False)
    fix=lambda:calls.append(1) or False
    assert monitor.tick('public',check=check,fix=fix,clock=lambda:0)=='reconnect_failed'
    assert monitor.tick('public',check=check,fix=fix,clock=lambda:30)=='backoff'
    assert monitor.tick('public',check=check,fix=fix,clock=lambda:120)=='reconnect_failed'
    assert monitor.next_attempt==360 and len(calls)==2
    monitor.tick('public',check=lambda *a,**k:True,clock=lambda:121)
    assert monitor.backoff==120 and monitor.next_attempt==0


def test_repair_process_uses_fixed_script_and_suppresses_sensitive_output(monkeypatch):
    def run(args,**kwargs):
        assert args[0]=='powershell.exe' and args[-1].endswith('repair-public.ps1')
        assert kwargs['stdout']==kwargs['stderr']==subprocess.DEVNULL
        assert kwargs['timeout']==300 and 'shell' not in kwargs
        return type('Result',(),{'returncode':0})()
    monkeypatch.setattr('scripts.public_watchdog.subprocess.run',run)
    assert repair() is True


def test_repair_timeout_is_retryable(monkeypatch):
    def timeout(*args,**kwargs):raise subprocess.TimeoutExpired('redacted',300)
    monkeypatch.setattr('scripts.public_watchdog.subprocess.run',timeout)
    assert repair() is False


def test_hourly_budget_survives_successful_health_checks():
    monitor=Recovery();monitor.failures=1;monitor.attempts=[0,10,20,30]
    monitor.tick('public',check=lambda *a,**k:True,clock=lambda:40)
    monitor.failures=1
    assert monitor.tick('public',check=lambda url,**kw:kw.get('local',False),clock=lambda:100)=='repair_budget_exhausted'
    assert monitor.next_attempt==3600


@pytest.mark.skipif(os.name!='nt',reason='PowerShell process targeting is Windows-specific.')
def test_windows_process_targeting_with_mock_processes():
    root=Path(__file__).resolve().parents[1]
    result=subprocess.run(['powershell.exe','-NoProfile','-ExecutionPolicy','RemoteSigned','-File',str(root/'tests/public_watchdog.ps1')],
        cwd=root,capture_output=True,text=True,timeout=30)
    assert result.returncode==0,result.stdout+result.stderr
