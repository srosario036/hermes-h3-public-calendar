"""Standalone H3 report only: Cloud Logging -> paired Telegram. Never broker,
VM startup, strategies or inference. Credentials remain in memory.
"""
import argparse,base64,contextlib,hashlib,json,os,re,shutil,subprocess,sys,time,urllib.error,urllib.parse,urllib.request,uuid
from pathlib import Path
from datetime import datetime,timedelta,timezone
from zoneinfo import ZoneInfo
from serial_codec import recover
MADRID=ZoneInfo('Europe/Madrid');NY=ZoneInfo('America/New_York')
class SafeError(Exception):pass
class NoRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,*args,**kwargs):return None

def evidence(path,text):
 if os.environ.get('H3_HOSTED_RUNNER')!='1':path.write_text(text,encoding='utf-8')

def stamp(s):
 d=datetime.fromisoformat(s.replace('Z','+00:00'))
 if d.tzinfo is None:raise SafeError('missing_timezone')
 return d

def request(url,headers=None,payload=None):
 try:
  req=urllib.request.Request(url,headers={'Content-Type':'application/json',**(headers or {})},data=None if payload is None else json.dumps(payload,allow_nan=False).encode(),method='GET' if payload is None else 'POST')
  with urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect).open(req,timeout=25) as response:return json.load(response)
 except urllib.error.HTTPError as e:raise SafeError('HTTP_'+str(e.code)+'_'+urllib.parse.urlsplit(url).hostname) from None
 except Exception:raise SafeError('network_outcome_unknown') from None

def access_token(mode,cfg):
 if mode=='gcloud':
  r=subprocess.run([shutil.which('gcloud'),'auth','print-access-token'],capture_output=True,text=True,timeout=40)
  if r.returncode or not r.stdout.strip():raise SafeError('local_auth_unavailable')
  return r.stdout.strip()
 # Optional free hosted runner, only after explicit federation authorization.
 if os.environ.get('GITHUB_REPOSITORY')!=cfg['authorized_repository'] or os.environ.get('GITHUB_REF')!='refs/heads/main':raise SafeError('unauthorized_hosted_context')
 audience=cfg['wif_audience']
 oidc=request(os.environ['ACTIONS_ID_TOKEN_REQUEST_URL']+'&audience='+urllib.parse.quote(audience,safe=''),{'Authorization':'Bearer '+os.environ['ACTIONS_ID_TOKEN_REQUEST_TOKEN']})['value']
 exchanged=request('https://sts.googleapis.com/v1/token',payload={'audience':audience,'grantType':'urn:ietf:params:oauth:grant-type:token-exchange','requestedTokenType':'urn:ietf:params:oauth:token-type:access_token','scope':'https://www.googleapis.com/auth/cloud-platform','subjectTokenType':'urn:ietf:params:oauth:token-type:jwt','subjectToken':oidc})['access_token']
 return request('https://iamcredentials.googleapis.com/v1/projects/-/serviceAccounts/'+cfg['report_service_account']+':generateAccessToken',{'Authorization':'Bearer '+exchanged,'Content-Type':'application/json'},{'scope':['https://www.googleapis.com/auth/cloud-platform'],'lifetime':'900s'})['accessToken']

class Google:
 def __init__(self,token,cfg):self.headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'};self.cfg=cfg
 def logs(self,filter_text,limit=4000):
  out=[];page=None
  for _ in range(4):
   body={'resourceNames':['projects/'+self.cfg['project']],'filter':filter_text,'pageSize':min(limit-len(out),1000),'orderBy':'timestamp desc'}
   if page:body['pageToken']=page
   data=request('https://logging.googleapis.com/v2/entries:list',self.headers,body);out+=data.get('entries',[]);page=data.get('nextPageToken')
   if not page:return out
   if len(out)>=limit:raise SafeError('log_pagination_incomplete')
  raise SafeError('log_pagination_incomplete')
 def event(self,value):
  return request('https://logging.googleapis.com/v2/entries:write',self.headers,{'entries':[{'logName':'projects/'+self.cfg['project']+'/logs/h3-telegram-delivery','resource':{'type':'global'},'jsonPayload':value}],'partialSuccess':False})
 def vm(self):return request('https://compute.googleapis.com/compute/v1/projects/'+self.cfg['project']+'/zones/'+self.cfg['zone']+'/instances/'+self.cfg['vm'],self.headers)
 def telegram_credentials(self):
  values=[]
  for name in [self.cfg['telegram_token_secret_name'],self.cfg['telegram_chat_secret_name']]:
   data=request('https://secretmanager.googleapis.com/v1/projects/'+self.cfg['project']+'/secrets/'+name+'/versions/latest:access',self.headers)
   values.append(base64.b64decode(data['payload']['data']).decode().strip())
  token,recipient=values
  if not recipient.isdigit() or not re.fullmatch(r'\d+:[A-Za-z0-9_-]+',token):raise SafeError('invalid_H3_bot_configuration')
  identity=request('https://api.telegram.org/bot'+token+'/getMe')
  if not identity.get('ok') or identity.get('result',{}).get('username','').lower()!=self.cfg['bot_username'].lower():raise SafeError('H3_bot_identity_mismatch')
  chat=request('https://api.telegram.org/bot'+token+'/getChat',payload={'chat_id':recipient})
  if not chat.get('ok') or chat.get('result',{}).get('type')!='private' or str(chat['result'].get('id'))!=recipient:raise SafeError('H3_private_recipient_mismatch')
  return token,recipient

def latest(entries,now):
 decoded=recover(entries);items=[]
 for m in decoded['complete_messages']:
  s=m['summary']
  if m['phase']!='lease_end' or s.get('captures',0)<=0:continue
  at=stamp(s['generated_at'])
  if at>now or now-at>timedelta(days=30):continue
  # Legacy run-id explicitly identifies its observation day. Require agreement
  # rather than silently inferring a new session from today's report date.
  match=re.search(r'(\d{8})$',s['run_id']);day=s.get('session_date')
  if day is None and match:day=datetime.strptime(match[1],'%Y%m%d').date().isoformat()
  if day is None or day!=at.astimezone(NY).date().isoformat():continue
  if s['evaluations']-s['unique_contracts']!=s['repeated_evaluations']:raise SafeError('count_integrity_failed')
  for b in ['30','60','100','150']:
   v=s['budgets'][b]
   if not 0<=v['unique_eligible']<=v['unique_affordable']<=s['unique_contracts']:raise SafeError('budget_integrity_failed')
  items.append(dict(m,session_date=day))
 if not items:raise SafeError('no_verified_final_summary_available')
 return max(items,key=lambda m:stamp(m['summary']['generated_at'])),decoded

def compose(item,vm,now,full=True):
 s=item['summary'];local=now.astimezone(MADRID)
 if s is None:
  known=datetime.fromisoformat(item['session_date']).strftime('%d/%m/%Y') if item.get('session_date') else 'NO VERIFICABLE'
  state='DETENIDO' if vm['status']=='TERMINATED' else vm['status']
  return '\n'.join(['HERMES H3 — '+local.strftime('%d/%m/%Y %H:%M Madrid'),'Última sesión conocida: '+known+'.','Estado actual H3: '+state+'.','Sin resumen íntegro disponible en la retención consultada. Resultados: NO EVALUABLE. No son datos nuevos.','Paper desactivado; LIVE bloqueado. Sin nuevas inferencias de pago.'])
 day=datetime.fromisoformat(item['session_date']).strftime('%d/%m/%Y')
 state='DETENIDO' if vm['status']=='TERMINATED' else vm['status']
 lines=['HERMES H3 — '+local.strftime('%d/%m/%Y %H:%M Madrid'),'Última sesión observada: '+day+' (observación parcial).','Estado actual H3: '+state+'.']
 delay=int((local-local.replace(hour=8,minute=0,second=0,microsecond=0)).total_seconds()//60)
 if delay>=5:lines+=['Informe diario recuperado con retraso de '+str(delay)+' min respecto a las 08:00 Madrid.']
 if item['session_date']!=local.date().isoformat():lines+=['Sin datos nuevos de hoy. Se informa el último resultado disponible.']
 if not full:return '\n'.join(lines+['El resultado consolidado ya fue informado; no se repiten sus cifras.','Paper desactivado; LIVE bloqueado. Sin nuevas inferencias de pago.'])
 lines += ['Cierre de evidencia: '+stamp(s['generated_at']).astimezone(MADRID).strftime('%d/%m %H:%M Madrid')+'.',f"Capturas {s['captures']}; contratos únicos {s['unique_contracts']}; evaluaciones {s['evaluations']}; repeticiones {s['repeated_evaluations']}.",f"Cotizaciones frescas al capturar: {s['fresh_quote_evaluations']} evaluaciones; OI aceptado: {s['oi_accepted_unique']} contratos únicos.",'Presupuestos hipotéticos USD — asequibles / elegibles:']
 for b in ['30','60','100','150']:
  v=s['budgets'][b];lines.append(f"{b}: {v['unique_affordable']} / {v['unique_eligible']}")
 lines+=['El débito operativo vigente no cambia con estas comparaciones.',('Hay coincidencias señal+contrato registradas; no son órdenes.' if any(n for values in s.get('research_signal_and_eligible_unique',{}).values() for n in values.values()) else 'Ningún contrato elegible coincide con las hipótesis evaluadas.'),'Rechazos por contrato (se solapan y pueden ocurrir solo en parte de la ventana):']
 reasons=s['unique_rejections_nonexclusive'];labels={'spread':'spread','quote_stale':'quote antigua','greeks':'griegas','oi_insufficient':'OI insuficiente','oi_absent':'OI ausente','theta_decay':'theta'}
 lines+=['; '.join(label+': '+str(reasons.get(k,0)) for k,label in labels.items())+'.','Las etiquetas de eventos agregadas incluyen registros anteriores a la corrección; no prueban bloqueo durante toda la ventana.','Self-Evaluation: '+ '; '.join(k+': '+(str(s.get('scores',{}).get(k,{}).get('score'))+'/100' if s.get('scores',{}).get(k,{}).get('score') is not None else 'NO EVALUABLE') for k in ['performance','learning','reliability'])+'; Learning histórico, sin nuevo ciclo Hermes.','Observación indicative, no OPRA. Sin rentabilidad demostrada ni P&L evaluable.','Paper desactivado; LIVE bloqueado. Ninguna inferencia de pago.']
 text='\n'.join(lines)
 if len(text)>3900:raise SafeError('message_too_long')
 return text

def ledger_filter(project):return 'logName="projects/'+project+'/logs/h3-telegram-delivery" AND timestamp>="'+(datetime.now(timezone.utc)-timedelta(days=30)).isoformat()+'"'
def already_day(events,day):return any(e.get('jsonPayload',{}).get('day')==day and e.get('jsonPayload',{}).get('state') in ['claimed','confirmed','uncertain'] for e in events)
def full_seen(events,sha):return any(e.get('jsonPayload',{}).get('source_sha256')==sha and e.get('jsonPayload',{}).get('kind')=='full' and e.get('jsonPayload',{}).get('state') in ['claimed','confirmed','uncertain'] for e in events)

def deliver(google,item,vm,now,out,send=False,recovery=False):
 day=now.astimezone(MADRID).date().isoformat();events=google.logs(ledger_filter(google.cfg['project']))
 if already_day(events,day):
  confirmed=any(e.get('jsonPayload',{}).get('day')==day and e['jsonPayload'].get('state')=='confirmed' for e in events)
  if send and not confirmed:raise SafeError('daily_delivery_unconfirmed_no_retry')
  return {'status':'already_claimed_no_duplicate','messages_sent':0,'delivery_confirmed':confirmed}
 full=item.get('summary') is not None and not full_seen(events,item['sha256']);text=compose(item,vm,now,full=full)
 out.mkdir(parents=True,exist_ok=True);evidence(out/'report-preview.txt',text)
 if not send:return {'status':'preview_only','messages_sent':0,'kind':'full' if full else 'status_only'}
 local=now.astimezone(MADRID)
 # GitHub can enqueue hours late. Keep the current-day daily key and never
 # discard an otherwise valid report merely because the 08:00 target passed.
 if not recovery and local.hour<8:return {'status':'before_daily_target','messages_sent':0}
 token,recipient=google.telegram_credentials()
 attempt=uuid.uuid4().hex;claim={'day':day,'key':'morning:'+day,'state':'claimed','kind':'full' if full else 'status_only','attempt':attempt,'at':now.isoformat(),'source_sha256':item['sha256'],'last_session':item['session_date'],'text_sha256':hashlib.sha256(text.encode()).hexdigest(),'mode':'explicit_recovery' if recovery else 'scheduled'}
 # Before-send durable claim. A single hosted concurrency group owns future
 # sends; during bootstrap there is one local locked process, never both.
 claim.update(execution_origin=os.environ.get('GITHUB_EVENT_NAME','local'),workflow_run_id=os.environ.get('GITHUB_RUN_ID'))
 google.event(claim)
 persisted=False
 for _ in range(6):
  found=google.logs(ledger_filter(google.cfg['project']))
  if any(e.get('jsonPayload',{}).get('attempt')==attempt for e in found):persisted=True;break
  time.sleep(2)
 if not persisted:raise SafeError('claim_not_verified_no_send')
 try:
  sent=request('https://api.telegram.org/bot'+token+'/sendMessage',payload={'chat_id':recipient,'text':text,'disable_web_page_preview':True})
  message=sent.get('result',{})
  if sent.get('ok') is not True or str(message.get('chat',{}).get('id'))!=recipient or message.get('text')!=text:raise SafeError('delivery_not_confirmed')
  receipt={**claim,'state':'confirmed','message_id':message['message_id'],'confirmed_at':datetime.now(timezone.utc).isoformat()}
  evidence(out/'delivery-receipt.json',json.dumps(receipt,indent=2));google.event(receipt)
  return {'status':'confirmed','messages_sent':1,'kind':claim['kind'],'source_sha256':item['sha256'],'last_session':item['session_date'],'message_id':message['message_id']}
 except Exception:
  uncertain={**claim,'state':'uncertain','no_automatic_retry':True}
  evidence(out/'delivery-uncertain.json',json.dumps(uncertain,indent=2))
  try:google.event(uncertain)
  except Exception:pass
  raise SafeError('delivery_uncertain_no_retry') from None

@contextlib.contextmanager
def lock(path):
 path.parent.mkdir(parents=True,exist_ok=True)
 with path.open('a+b') as f:
  if f.tell()==0:f.write(b'0');f.flush()
  f.seek(0)
  if os.name=='nt':
   import msvcrt;msvcrt.locking(f.fileno(),msvcrt.LK_NBLCK,1)
  else:
   import fcntl;fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
  try:yield
  finally:
   if os.name=='nt':f.seek(0);msvcrt.locking(f.fileno(),msvcrt.LK_UNLCK,1)
   else:fcntl.flock(f,fcntl.LOCK_UN)

def main():
 p=argparse.ArgumentParser();p.add_argument('--config',type=Path);p.add_argument('--output',type=Path,required=True);p.add_argument('--auth',choices=['gcloud','github'],default='gcloud');p.add_argument('--send',action='store_true');p.add_argument('--check-delivery',action='store_true');p.add_argument('--verify-bot',action='store_true');p.add_argument('--recovery-date');args=p.parse_args()
 if args.send and (args.check_delivery or args.verify_bot):raise SafeError('check_mode_cannot_send')
 now=datetime.now(timezone.utc);cfg=json.loads(args.config.read_text(encoding="utf-8-sig")) if args.config else json.loads(os.environ["H3_REPORT_CONFIG"])
 if args.recovery_date and args.recovery_date!=now.astimezone(MADRID).date().isoformat():raise SafeError('recovery_date_mismatch')
 with lock(args.output/'report.lock'):
  g=Google(access_token(args.auth,cfg),cfg)
  f='resource.type="gce_instance" AND resource.labels.instance_id="'+cfg['instance_id']+'" AND log_id("serialconsole.googleapis.com/serial_port_1_output") AND "H3SUM1" AND timestamp>="'+(now-timedelta(days=30)).isoformat()+'"'
  entries=g.logs(f)
  try:item,decoded=latest(entries,now)
  except SafeError as error:
   if str(error)!='no_verified_final_summary_available':raise
   old=g.logs(ledger_filter(cfg['project']));dates=[e.get('jsonPayload',{}).get('last_session') for e in old if e.get('jsonPayload',{}).get('state')=='confirmed'];dates=[d for d in dates if isinstance(d,str) and re.fullmatch(r'\d{4}-\d{2}-\d{2}',d)]
   item={'sha256':None,'session_date':max(dates) if dates else None,'summary':None}
  try:vm=g.vm()
  except SafeError:vm={'status':'NO VERIFICADO'}
  args.output.mkdir(parents=True,exist_ok=True)
  evidence(args.output/'latest-final-summary.json',json.dumps(item,indent=2));evidence(args.output/'vm-current.json',json.dumps({k:vm.get(k) for k in ['name','status','lastStartTimestamp','lastStopTimestamp']},indent=2))
  if args.verify_bot:
   g.telegram_credentials();result={'status':'H3_bot_identity_verified','messages_sent':0}
  elif args.check_delivery:
   events=g.logs(ledger_filter(cfg['project']));day=now.astimezone(MADRID).date().isoformat()
   confirmed=[e['jsonPayload'] for e in events if e.get('jsonPayload',{}).get('day')==day and e['jsonPayload'].get('state')=='confirmed']
   result={'status':'already_claimed_no_duplicate' if already_day(events,day) else 'not_claimed','messages_sent':0,'confirmed_attempts':len({e['attempt'] for e in confirmed}),'confirmed_message_ids':len({e['message_id'] for e in confirmed}),'sender_not_invoked':True}
   evidence(args.output/'dedupe-readonly-proof.json',json.dumps(result,indent=2))
  else:result=deliver(g,item,vm,now,args.output,send=args.send,recovery=bool(args.recovery_date))
  evidence(args.output/'last-run.json',json.dumps(result,indent=2))
  print(json.dumps({'status':result['status'],'messages_sent':result['messages_sent']}))
  if args.send and result['status'] not in ['confirmed','already_claimed_no_duplicate','before_daily_target']:raise SafeError('daily_delivery_not_completed')
if __name__=='__main__':
 try:main()
 except Exception as e:print(json.dumps({'status':'blocked','error_type':type(e).__name__,'reason':str(e) if isinstance(e,SafeError) else 'details_omitted'}));raise SystemExit(1)
