"""Read only H3 native-console summary chunks. No network, eval or execution."""
import json,base64,hashlib,codecs,re
from collections import defaultdict

def recover(entries):
 groups={};bad=0
 for entry in entries:
  text=entry.get('textPayload','')
  if '\\"' in text:
   try:text=codecs.decode(text,'unicode_escape')
   except (UnicodeError,ValueError):bad+=1;continue
  for line in text.splitlines():
   if not line.startswith('H3SUM1 '):continue
   try:
    v=json.loads(line[7:]);key=v['id'];i=v['i'];n=v['n'];part=v['d'];phase=v['phase']
    if not re.fullmatch('[0-9a-f]{64}',key) or type(i)!=int or type(n)!=int or not 0<=i<n<=200 or not isinstance(part,str) or len(part)>128:raise ValueError()
    group=groups.setdefault(key,{'n':n,'phase':phase,'parts':{},'conflict':False})
    if group['n']!=n or group['phase']!=phase or (i in group['parts'] and group['parts'][i]!=part):group['conflict']=True
    group['parts'][i]=part
   except (KeyError,TypeError,ValueError):bad+=1
 complete=[];incomplete=[]
 for key,g in groups.items():
  try:
   if g['conflict'] or len(g['parts'])!=g['n']:raise ValueError()
   raw=base64.b64decode(''.join(g['parts'][i] for i in range(g['n'])),validate=True)
   if hashlib.sha256(raw).hexdigest()!=key:raise ValueError()
   summary=json.loads(raw)
   if not re.fullmatch(r'h3-[a-z0-9-]{1,120}',summary.get('run_id','')) or summary.get('phase')!=g['phase']:raise ValueError()
   complete.append({'sha256':key,'phase':g['phase'],'chunks':g['n'],'summary':summary})
  except (KeyError,TypeError,ValueError):incomplete.append({'sha256':key,'received':len(g['parts']),'required':g['n'],'conflict':g['conflict']})
 return {'complete_messages':complete,'incomplete_messages':incomplete,'malformed_records':bad}

if __name__=='__main__':
 from pathlib import Path
 import sys
 data=recover(json.loads(Path(sys.argv[1]).read_text(encoding='utf-8-sig')))
 Path(sys.argv[2]).write_text(json.dumps(data,indent=2),encoding='utf-8')
 print(json.dumps({'complete':len(data['complete_messages']),'incomplete':len(data['incomplete_messages']),'malformed_records':data['malformed_records']}))
