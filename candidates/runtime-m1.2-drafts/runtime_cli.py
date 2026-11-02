"""Control CLI. Mutations require an explicit observed revision."""
import argparse
import json
import sys
from runtime_client import Client, UnconfirmedRequest


def main():
    p = argparse.ArgumentParser(description='LEVIS M1.1 status, attach/detach and lifecycle controls')
    p.add_argument('--profile', required=True)
    p.add_argument('--client-id', default='operator-cli')
    p.add_argument('--request-id', help='Reuse with identical arguments to query a committed control receipt')
    p.add_argument('--revision', type=int)
    p.add_argument('--after', type=int, default=0)
    p.add_argument('--limit', type=int, default=100)
    p.add_argument('--payload-file',help='Explicit JSON payload file for a typed job command')
    p.add_argument('command', choices=['status', 'snapshot', 'events', 'attach', 'detach', 'pause', 'resume', 'stop','jobs','job-events','job-artifact','job-submit','job-answer','job-retry','job-cancel'])
    args = p.parse_args()
    payload = {'after': args.after, 'limit': args.limit} if args.command == 'events' else {}
    try:
        if args.payload_file:
            from pathlib import Path
            raw=Path(args.payload_file).read_bytes()
            if len(raw)>128*1024:raise ValueError('Job payload file exceeds bound')
            import runtime_protocol
            payload=runtime_protocol.decode(raw)
        elif args.command=='job-events':
            payload={'after':args.after,'limit':args.limit}
        result = Client(args.profile, args.client_id).request(args.command, args.revision, payload, args.request_id)
        print(json.dumps(result, indent=2))
        draft=result.get('draft')
        return 0 if result['status']=='OK' and (not isinstance(draft,dict) or draft.get('status','OK')=='OK') else 2
    except UnconfirmedRequest as error:
        print(f'UNCONFIRMED: {error}', file=sys.stderr)
        return 3
    except (OSError, ValueError, RuntimeError, TimeoutError) as error:
        print(f'REFUSED: {type(error).__name__}: {error}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
