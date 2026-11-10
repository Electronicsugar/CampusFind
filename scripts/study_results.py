"""Offline, allowlisted observation validation; never reads application data."""
import argparse
import csv
import json
import math
import re
import statistics
from pathlib import Path

FIELDS = ('session_code task_id device_class input_method completion_status assistance_level '
          'duration_seconds timing_method recoverable_error_count critical_error_count '
          'ai_uncertainty_understood claim_process_understood approval_receipt_understood '
          'returned_understood difficulty_rating observer_notes_redacted').split()
ENUMS = dict(task_id={f'U{i:02}' for i in range(1,10)},
             device_class={'mobile','tablet','desktop'}, input_method={'keyboard','touch','mouse','screen_reader','mixed'},
             completion_status={'independent','assisted','failed','not_attempted'},
             assistance_level={'none','minor_hint','substantial'}, timing_method={'measured','estimated','not_recorded'})
BOOLS = ('ai_uncertainty_understood','claim_process_understood','approval_receipt_understood','returned_understood')


def summarize(path):
    errors=[]; valid=[]; seen=set(); missing=0
    with Path(path).open(encoding='utf-8-sig',newline='') as stream:
        reader=csv.DictReader(stream)
        if reader.fieldnames!=FIELDS:
            return {'errors':['Header must match the documented allowlist and order; extra/private fields are forbidden.'], 'valid_records':0}
        for line,row in enumerate(reader,2):
            issues=[]; missing+=sum(row.get(f) in (None,'') for f in FIELDS)
            if None in row or any(v is None for v in row.values()):issues.append('wrong column count')
            if not re.fullmatch(r'S[0-9]{3,6}',row.get('session_code') or ''):issues.append('invalid pseudonymous session code')
            for f,choices in ENUMS.items():
                if row.get(f) not in choices:issues.append('invalid '+f)
            pair=(row.get('session_code'),row.get('task_id'))
            if pair in seen:issues.append('duplicate session/task; use a new session code for a repeat')
            seen.add(pair)
            for f in BOOLS:
                if row.get(f) not in ('yes','no',''):issues.append('invalid '+f)
            for f in ('recoverable_error_count','critical_error_count'):
                if not re.fullmatch(r'[0-9]+',row.get(f) or ''):issues.append('invalid '+f)
            duration=None
            if row.get('duration_seconds'):
                try:
                    duration=float(row['duration_seconds'])
                    if not math.isfinite(duration) or duration<0:raise ValueError()
                except ValueError:issues.append('invalid duration_seconds')
            if (row.get('timing_method')=='not_recorded') != (row.get('duration_seconds')==''):issues.append('timing method/duration conflict')
            if row.get('difficulty_rating') not in ('','1','2','3','4','5'):issues.append('invalid difficulty_rating')
            status=row.get('completion_status'); help_=row.get('assistance_level')
            if (status=='independent' and help_!='none') or (status=='assisted' and help_=='none'):issues.append('completion/assistance conflict')
            if status=='not_attempted' and (help_!='none' or row.get('duration_seconds') or any(row.get(f) not in ('0','') for f in ('recoverable_error_count','critical_error_count'))):issues.append('not_attempted must have no timing/errors/assistance')
            # A coded note avoids accidentally copying evidence or identifiers.
            if row.get('observer_notes_redacted') not in ('','navigation','crop','validation','uncertainty','claim','recovery','accessibility','other'):issues.append('notes must use a documented code; no free text or personal data')
            if issues:errors.append({'line':line,'issues':issues})
            else:valid.append((row,duration))
    tasks={}
    for task in sorted({r['task_id'] for r,_ in valid}):
        rows=[(r,d) for r,d in valid if r['task_id']==task]; attempted=[(r,d) for r,d in rows if r['completion_status']!='not_attempted']; n=len(attempted)
        counts={s:sum(r['completion_status']==s for r,_ in rows) for s in ('independent','assisted','failed','not_attempted')}
        durations=[d for _,d in attempted if d is not None]
        tasks[task]={'valid_records':len(rows),'attempts':n,**counts,
                     'independent_rate':counts['independent']/n if n else None,'failure_rate':counts['failed']/n if n else None,
                     'timed_attempts':len(durations),'estimated_timings':sum(r['timing_method']=='estimated' for r,_ in attempted),
                     'duration_seconds':{'median':statistics.median(durations),'min':min(durations),'max':max(durations)} if durations else None,
                     'recoverable_errors':sum(int(r['recoverable_error_count']) for r,_ in attempted),
                     'critical_errors':sum(int(r['critical_error_count']) for r,_ in attempted),
                     'comprehension':{f:{v:sum(r[f]==v for r,_ in attempted) for v in ('yes','no','')} for f in BOOLS}}
    return {'valid_records':len(valid),'sessions':len({r['session_code'] for r,_ in valid}), 'invalid_records':len(errors),
            'missing_cells':missing,'errors':errors,'tasks':tasks,'note':'Counts describe valid observations only; empty comprehension key means not assessed. No accuracy inference.'}


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('csv',type=Path);args=parser.parse_args()
    try:result=summarize(args.csv)
    except (OSError,UnicodeError,csv.Error):parser.exit(2,'Cannot read observation CSV. Check format and access.\n')
    print(json.dumps(result,indent=2,sort_keys=True));return int(bool(result['errors']))


if __name__=='__main__':raise SystemExit(main())
