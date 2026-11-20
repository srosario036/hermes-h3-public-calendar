"""PUBLIC standalone collector for five official BLS series, not all macro.
Only standard library and the already public collect_bls.Table are used.
No private H3 imports, credentials, trading data or order capability.
"""
import argparse,calendar,concurrent.futures,hashlib,json,os,re,urllib.request
from datetime import datetime,timedelta,timezone
from pathlib import Path
from zoneinfo import ZoneInfo
from html.parser import HTMLParser
from collect_bls import NoRedirect,digest

class SeriesTable(HTMLParser):
    """Independent row state per nested table; never reuse a closed row."""
    def __init__(self,html):
        super().__init__(convert_charrefs=True);self.stack=[];self.tables=[];self.text=[];self.feed(html)
    def handle_starttag(self,tag,attrs):
        if tag=='table':self.stack.append({'rows':[],'row':None,'cell':None})
        elif self.stack and tag=='tr':self.stack[-1]['row']=[]
        elif self.stack and tag in {'td','th'}:self.stack[-1]['cell']=[]
    def handle_data(self,data):
        self.text.append(data)
        if self.stack and self.stack[-1]['cell'] is not None:self.stack[-1]['cell'].append(data)
    def handle_endtag(self,tag):
        if not self.stack:return
        state=self.stack[-1]
        if tag in {'td','th'} and state['cell'] is not None:
            if state['row'] is not None:state['row'].append(' '.join(' '.join(state['cell']).split()))
            state['cell']=None
        elif tag=='tr' and state['row'] is not None:
            state['rows'].append(state['row']);state['row']=None
        elif tag=='table':self.tables.append(self.stack.pop()['rows'])

NY=ZoneInfo('America/New_York')
SERIES={'CPI':('cpi','Consumer Price Index'),'PPI':('ppi','Producer Price Index'),
 'Employment':('empsit','Employment Situation'),'JOLTS':('jolts','Job Openings and Labor Turnover Survey'),
 'ECI':('eci','Employment Cost Index')}
TIMEZONE_BASIS={'timezone':'America/New_York','official_convention_source':'https://www.bls.gov/schedule/2026/11_sched_list.htm',
 'method':'BLS official calendar Eastern Time convention independently reviewed20Nov2026; series pages contain clock times without their own timezone marker. DST follows IANA rules, not fixed UTC offset.'}

def parse(html,name):
    table=SeriesTable(html);text=' '.join(' '.join(table.text).split())
    if '</html>' not in html.lower() or 'Schedule of Releases for the '+SERIES[name][1] not in text:raise ValueError('series_identity_or_truncation')
    candidates=[t for t in table.tables if t and t[0]==['Reference Month','Release Date','Release Time']]
    if len(candidates)!=1:raise ValueError('series_table_schema')
    months={v.lower():i for i in range(1,13) for v in [calendar.month_name[i],calendar.month_abbr[i]]};months['sept']=9
    events=[];seen=set();periods=[]
    for row in candidates[0][1:]:
        if len(row)!=3 or not all(row):raise ValueError('series_row')
        match=re.fullmatch(r'([A-Za-z]+)\.?\s+(\d{1,2}),\s*(\d{4})',row[1])
        if not match or match[1].lower() not in months:raise ValueError('release_date')
        day=datetime(int(match[3]),months[match[1].lower()],int(match[2])).date()
        clock=datetime.strptime(row[2],'%I:%M %p').time()
        at=datetime.combine(day,clock,tzinfo=NY)
        if name=='ECI':
            period=re.fullmatch(r'(First|Second|Third|Fourth) Quarter (\d{4})',row[0])
            if not period:raise ValueError('quarter_reference_period')
            periods.append(int(period[2])*4+['First','Second','Third','Fourth'].index(period[1]))
        else:
            reference=datetime.strptime(row[0],'%B %Y');periods.append(reference.year*12+reference.month)
        if at.isoformat() in seen:raise ValueError('duplicate_release_date')
        seen.add(at.isoformat());events.append({'at':at.isoformat(),'name':SERIES[name][1],'reference_period':row[0]})
    # Count is a schema sanity check, not proof that unrelated publications exist.
    if len(events)<(4 if name=='ECI' else 6):raise ValueError('series_schema_incomplete')
    if events!=sorted(events,key=lambda e:e['at']):raise ValueError('series_not_chronological')
    if any(b-a!=1 for a,b in zip(periods,periods[1:])):raise ValueError('reference_period_gap_or_duplicate')
    return events

def fetch(name):
    page,_=SERIES[name];url='https://www.bls.gov/schedule/news_release/'+page+'.htm'
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect)
    with opener.open(urllib.request.Request(url,headers={'User-Agent':'Public-official-calendar-integrity/1.0','Accept':'text/html'}),timeout=25) as response:
        raw=response.read(2_000_001);status=response.status;final=response.geturl();published=response.headers.get('Last-Modified')
    if status!=200 or final!=url or len(raw)>2_000_000:raise ValueError('source_response')
    events=parse(raw.decode('utf-8'),name);received=datetime.now(timezone.utc)
    return raw,{'source':url,'http_status':200,'acquired_at':received.isoformat(),
      'valid_until':(received+timedelta(hours=6)).isoformat(),'provider_Last_Modified_header':published,
      'provider_publication_at':None,'raw_sha256':hashlib.sha256(raw).hexdigest(),'events':events}

def validate(document,now):
    try:
        if document['schema']!='official-critical-bls-v1' or digest(document['content'])!=document['content_sha256']:raise ValueError('snapshot_integrity')
        body=document['content'];day=now.astimezone(NY).date();checked=[];until=[];today=[]
        if set(body['series'])!=set(SERIES) or body['timezone_basis']!=TIMEZONE_BASIS:raise ValueError('source_scope')
        for name,(page,title) in SERIES.items():
            item=body['series'][name];acquired=datetime.fromisoformat(item['acquired_at']);expiry=datetime.fromisoformat(item['valid_until'])
            if acquired.tzinfo is None or expiry.tzinfo is None or not acquired<=now<expiry<=acquired+timedelta(hours=6):raise ValueError('source_expired_future_or_excessive')
            if item['source']!='https://www.bls.gov/schedule/news_release/'+page+'.htm' or item['http_status']!=200:raise ValueError('source_origin')
            events=item['events'];dates=[]
            if len(events)<(4 if name=='ECI' else 6):raise ValueError('series_schema')
            for event in events:
                at=datetime.fromisoformat(event['at'])
                if at.tzinfo is None or at.utcoffset()!=at.astimezone(NY).utcoffset() or event['name']!=title or not event['reference_period']:raise ValueError('event_schema')
                dates.append(at.astimezone(NY).date())
                if dates[-1]==day:today.append(event)
            # Series pages are rolling release schedules and can begin with the
            # next future release (observed JOLTS starts1Dec on20Nov). Requiring
            # an old row would create a false outage. Bound how far the next
            # listed release may lie, retain complete reference-period sequence,
            # and never imply coverage of unscheduled announcements.
            if day>max(dates) or min(dates)>day+timedelta(days=120 if name=='ECI' else 62):raise ValueError('current_day_outside_published_schedule')
            checked.append(acquired);until.append(expiry)
        return {'listed_critical_BLS_series_verified':True,'events_today':today,'acquired_at':min(checked).isoformat(),
          'valid_until':min(until).isoformat(),'absence_scope':'Published schedules of these five series only; not unscheduled releases or other publishers',
          'all_macro_coverage_GO':False,'trading_authorized':False}
    except (ValueError,KeyError,TypeError,AttributeError):return {'listed_critical_BLS_series_verified':False,'events_today':[],'all_macro_coverage_GO':False,'trading_authorized':False}

def collect(out):
    out=Path(out);out.mkdir(parents=True,exist_ok=True);raws={};series={};failures={}
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
        futures={name:pool.submit(fetch,name) for name in SERIES}
        for name,future in futures.items():
            try:raws[name],series[name]=future.result()
            except Exception as error:failures[name]={'error_type':type(error).__name__,'http_status':getattr(error,'code',None)}
    now=datetime.now(timezone.utc);attempt={'at':now.isoformat(),'failures':failures,'all_macro_coverage_GO':False}
    if not failures:
        body={'series':series,'timezone_basis':TIMEZONE_BASIS}
        document={'schema':'official-critical-bls-v1','content':body,'content_sha256':digest(body),
          'collector_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'run_id':os.environ.get('GITHUB_RUN_ID'),
          'scope':'CPI/PPI/Employment/JOLTS/ECI only; not all BLS, Fed, BEA, Census, DOL or private-publisher events','publisher_signature':False}
        assessment=validate(document,now)
        if assessment['listed_critical_BLS_series_verified']:
            rawdir=out/'critical-sources';rawdir.mkdir(exist_ok=True)
            for name,raw in raws.items():(rawdir/(name+'.html')).write_bytes(raw)
            temporary=out/'critical-bls-latest.tmp';temporary.write_text(json.dumps(document,indent=2),encoding='utf-8');temporary.replace(out/'critical-bls-latest.json')
            attempt.update(status='verified_listed_series_only',assessment=assessment)
        else:attempt.update(status='coverage_unknown',reason='parsed_data_outside_valid_scope',latest_not_refreshed=True)
    else:attempt.update(status='coverage_unknown',latest_not_refreshed=True)
    (out/'critical-bls-last-attempt.json').write_text(json.dumps(attempt,indent=2),encoding='utf-8')
    print(json.dumps(attempt));return attempt.get('status')=='verified_listed_series_only'

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--out',default='site');args=parser.parse_args()
    raise SystemExit(0 if collect(args.out) else 1)
