"""Standalone PUBLIC calendar collector. No trading code, keys or cloud access.

    python collect_bls.py --out site
Successful HTTP200 and complete official monthly table required. Failed requests
never refresh latest.json. Timestamp/hash are evidence, not publisher signatures.
"""
import argparse,calendar,hashlib,json,re,urllib.request
from datetime import datetime,timedelta,timezone
from html.parser import HTMLParser
from pathlib import Path
from zoneinfo import ZoneInfo

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*a,**kw):return None

class Table(HTMLParser):
    def __init__(self,html):
        super().__init__(convert_charrefs=True);self.depth=0;self.in_cell=False;self.cell=[];self.row=[];self.rows=[];self.tables=[];self.text=[];self.feed(html)
    def handle_starttag(self,tag,attrs):
        if tag=='table':
            if self.depth==0:self.rows=[]
            self.depth+=1
        if tag=='tr' and self.depth:self.row=[]
        if tag in {'td','th'} and self.depth:self.in_cell=True;self.cell=[]
    def handle_data(self,data):
        self.text.append(data)
        if self.in_cell:self.cell.append(data)
    def handle_endtag(self,tag):
        if tag in {'td','th'} and self.in_cell:self.row.append(' '.join(' '.join(self.cell).split()));self.in_cell=False
        if tag=='tr' and self.depth:self.rows.append(self.row)
        if tag=='table' and self.depth:
            self.depth-=1
            if not self.depth:self.tables.append(self.rows)

HOLIDAYS={'Veterans Day','Thanksgiving Day','Christmas Day','New Year\'s Day','New Year\u2019s Day','Independence Day','Labor Day','Memorial Day','Juneteenth National Independence Day','Washington\u2019s Birthday','Martin Luther King Jr. Day','Columbus Day'}
def parse(html,year,month):
    parser=Table(html);text=' '.join(' '.join(parser.text).split())
    if calendar.month_name[month]+' '+str(year) not in text or 'All times on calendar are Eastern Time' not in text or '</html>' not in html.lower():raise ValueError('month_timezone_or_document_incomplete')
    tables=[t for t in parser.tables if t and t[0]==['Date','Time','Release']]
    if len(tables)!=1:raise ValueError('official_calendar_table_unknown')
    events=[];notices=[]
    for row in tables[0][1:]:
        if len(row)!=3:raise ValueError('calendar_row_invalid')
        date=datetime.strptime(row[0],'%A, %B %d, %Y').date()
        if (date.year,date.month)!=(year,month) or not row[2]:raise ValueError('calendar_date_or_name_invalid')
        if not row[1]:
            if row[2] not in HOLIDAYS:raise ValueError('untimed_release_unknown')
            notices.append({'date':str(date),'name':row[2]});continue
        clock=datetime.strptime(row[1],'%I:%M %p').time()
        dt=datetime.combine(date,clock,tzinfo=ZoneInfo('America/New_York'))
        events.append({'at':dt.isoformat(),'name':row[2]})
    if len(events)<5:raise ValueError('calendar_incomplete')
    return {'month':f'{year}-{month:02d}','timezone':'America/New_York','rows':events,'holiday_notices':notices}

def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
def validate(snapshot,now):
    try:
        acquired=datetime.fromisoformat(snapshot['acquired_at']);expiry=datetime.fromisoformat(snapshot['valid_until']);content=snapshot['content']
        year,month=map(int,content['month'].split('-'));url=f'https://www.bls.gov/schedule/{year}/{month:02d}_sched_list.htm'
        if snapshot['source']!=url or snapshot.get('http_status')!=200 or snapshot.get('full_month_reviewed') is not True:raise ValueError()
        if acquired.tzinfo is None or expiry.tzinfo is None or not acquired<=now<expiry<=acquired+timedelta(hours=6) or snapshot['content_sha256']!=digest(content):raise ValueError()
        day=now.astimezone(ZoneInfo('America/New_York')).date()
        if (day.year,day.month)!=(year,month) or len(content['rows'])<5:raise ValueError()
        events=[]
        for row in content['rows']:
            dt=datetime.fromisoformat(row['at'])
            if dt.tzinfo is None or (dt.year,dt.month)!=(year,month) or not row['name']:raise ValueError()
            if dt.astimezone(ZoneInfo('America/New_York')).date()==day:events.append(row)
        return {'coverage_state':'confirmed_scheduled_events' if events else 'verified_no_scheduled_events','events':events,'acquired_at':snapshot['acquired_at'],'valid_until':snapshot['valid_until']}
    except (KeyError,TypeError,ValueError):return {'coverage_state':'coverage_unknown','events':[]}

def collect(out,opener=None):
    out=Path(out);out.mkdir(parents=True,exist_ok=True);began=datetime.now(timezone.utc);day=began.astimezone(ZoneInfo('America/New_York')).date()
    url=f'https://www.bls.gov/schedule/{day.year}/{day.month:02d}_sched_list.htm'
    try:
        opener=opener or urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect)
        with opener.open(urllib.request.Request(url,headers={'User-Agent':'Public-official-calendar-integrity/1.0'}),timeout=25) as response:
            raw=response.read(2_000_001);status=response.status;final=response.geturl()
        if status!=200 or final!=url or len(raw)>2_000_000:raise ValueError('official_response_invalid')
        content=parse(raw.decode('utf-8'),day.year,day.month);received=datetime.now(timezone.utc)
        if (received.astimezone(ZoneInfo('America/New_York')).year,received.astimezone(ZoneInfo('America/New_York')).month)!=(day.year,day.month):raise ValueError('month_changed_during_fetch')
        snapshot={'schema':'official-bls-public-snapshot-v2','source':url,'http_status':200,'acquired_at':received.isoformat(),'valid_until':(received+timedelta(hours=6)).isoformat(),
          'method':'direct HTTPS official BLS complete monthly HTML, no redirects','full_month_reviewed':True,'content':content,'content_sha256':digest(content),'source_html_sha256':hashlib.sha256(raw).hexdigest(),
          'scope':'Selected national BLS scheduled releases only; not unscheduled news or constituent earnings','publisher_signature':False}
        (out/'source.html').write_bytes(raw)
        temp=out/'latest.tmp';temp.write_text(json.dumps(snapshot,indent=2),encoding='utf-8');temp.replace(out/'latest.json')
        attempt={'at':received.isoformat(),'status':'verified','source':url,'snapshot_sha256':hashlib.sha256((out/'latest.json').read_bytes()).hexdigest()}
        success=True
    except Exception as error:
        attempt={'at':datetime.now(timezone.utc).isoformat(),'status':'coverage_unknown','source':url,'error_type':type(error).__name__,'http_status':getattr(error,'code',None),'latest_not_refreshed':True};success=False
    (out/'last-attempt.json').write_text(json.dumps(attempt,indent=2),encoding='utf-8')
    return success,attempt
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args();ok,result=collect(a.out);print(json.dumps(result));raise SystemExit(0 if ok else 2)
