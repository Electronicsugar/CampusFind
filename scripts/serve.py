"""Explicit local/reverse-proxy entry point; never trusts arbitrary forwarded IPs."""
import argparse,ipaddress,logging
import uvicorn
from backend.settings import Settings


def proxy_address(value):
    return str(ipaddress.ip_address(value))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--port',type=int,default=8000);parser.add_argument('--proxy-ip',action='append',type=proxy_address,default=[])
    args=parser.parse_args();settings=Settings.from_env()
    if not 1024<=args.port<=65535:raise SystemExit('Choose an unprivileged port.')
    logging.basicConfig(level=logging.INFO,format='%(message)s')
    uvicorn.run('backend.main:app',host='127.0.0.1',port=args.port,proxy_headers=bool(args.proxy_ip),forwarded_allow_ips=','.join(args.proxy_ip),
                access_log=False,server_header=False,limit_concurrency=64,timeout_keep_alive=5)
