"""Bounded connection recovery while this computer and process are running."""
import argparse,json,logging,os,subprocess,time
from pathlib import Path
from urllib.request import Request,urlopen

ROOT=Path(__file__).resolve().parents[1]
LOG=logging.getLogger('public_connection')


def ready(url,local=False):
    try:
        request=Request(url+'/health/ready',headers={'Host':'localhost'} if local else {})
        with urlopen(request,timeout=10) as response:
            return response.status==200 and json.load(response).get('status')=='ready'
    except Exception:return False


def repair():
    # No credentials in arguments, output or logs; existing private config is reused.
    try:
        result=subprocess.run(['powershell.exe','-NoProfile','-ExecutionPolicy','RemoteSigned','-File',str(ROOT/'repair-public.ps1')],cwd=ROOT,
            stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=300,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        return result.returncode==0
    except (OSError,subprocess.TimeoutExpired):return False


class Recovery:
    def __init__(self):self.failures=0;self.next_attempt=0;self.backoff=120;self.state=None;self.attempts=[]

    def tick(self,origin,check=ready,fix=repair,clock=time.monotonic):
        instant=clock()
        if check(origin):
            self.failures=0;self.backoff=120;self.next_attempt=0
            return 'online'
        self.failures+=1
        if self.failures<2:return 'confirming_failure'
        if instant<self.next_attempt:return 'backoff'
        if not check('http://127.0.0.1:8020',local=True):
            self.next_attempt=instant+120
            return 'local_backend_unavailable'
        self.attempts=[stamp for stamp in self.attempts if stamp>instant-3600]
        if len(self.attempts)>=4:
            self.next_attempt=self.attempts[0]+3600
            return 'repair_budget_exhausted'
        self.attempts.append(instant)
        # The repair script verifies success; failures use bounded exponential backoff.
        if fix():
            self.failures=0;self.backoff=120;self.next_attempt=clock()+120
            return 'reconnected'
        self.next_attempt=clock()+self.backoff;self.backoff=min(self.backoff*2,900)
        return 'reconnect_failed'


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--pointer',required=True,type=Path);args=parser.parse_args()
    expected=(ROOT/'.local/public-host-pointer.json').resolve()
    if args.pointer.resolve()!=expected:raise SystemExit('Use the current workspace public-instance pointer.')
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(message)s')
    recovery=Recovery()
    while True:
        try:
            pointer=json.loads(expected.read_text(encoding='utf-8-sig'))
            if pointer.get('origin')!='https://campusfind-alpha-nine.vercel.app':raise ValueError('Unexpected origin')
            state=recovery.tick(pointer['origin'])
        except Exception:state='configuration_unavailable'
        if state!=recovery.state:LOG.info('public_connection %s',state);recovery.state=state
        time.sleep(30)


if __name__=='__main__':main()
