"""Gemini free-tier-only transport. No retries, paid fallback, or automatic quota reset.

Zero cost relies on the user-confirmed billing-disabled project. The API does not
provide a per-request dollar ceiling. Requests and raw outcomes are persisted.
"""
import base64
import json
import math
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from ..checkpoint import atomic_json, object_hash, read_json


class BudgetExceeded(RuntimeError):
    pass


class ConfigurationError(ValueError):
    pass


def validate_config(config):
    required = {'endpoint','api_key_env','worker_model','aggregator_model','max_completion_tokens',
                'max_input_tokens','input_usd_per_million','output_usd_per_million','budget_usd',
                'timeout_seconds','image_detail','bootstrap_seed','bootstrap_replicates',
                'billing_disabled_confirmed','minimum_request_interval_seconds'}
    if set(config)!=required:
        raise ConfigurationError('configuration keys must match the supplied real-vision example')
    if not all(isinstance(config[k],str) and config[k] and not config[k].startswith('SET_') for k in
               ('endpoint','api_key_env','worker_model','aggregator_model')):
        raise ConfigurationError('choose endpoint, credential environment variable, and both model IDs')
    from urllib.parse import urlparse
    url=urlparse(config['endpoint'])
    if url.scheme!='https' or url.username or url.password or url.query or url.fragment:
        raise ConfigurationError('use an HTTPS endpoint without credentials or query parameters')
    for key in ('max_completion_tokens','max_input_tokens','bootstrap_replicates'):
        if type(config[key]) is not int or config[key]<1:
            raise ConfigurationError(key+' must be a positive integer')
    if config['endpoint'] != 'https://generativelanguage.googleapis.com/v1beta/openai/chat/completions':
        raise ConfigurationError('only the verified Gemini endpoint is allowed')
    if any(config[k] != 'gemini-3.8-flash' for k in ('worker_model','aggregator_model')):
        raise ConfigurationError('only the verified Gemini Flash model is allowed; no fallback')
    if config['billing_disabled_confirmed'] is not True:
        raise ConfigurationError('a billing-disabled free-tier project must be confirmed')
    if any(type(config[k]) not in (int,float) or config[k]!=0 for k in ('input_usd_per_million','output_usd_per_million','budget_usd')):
        raise ConfigurationError('this experiment requires an exact zero-dollar cap and free-tier rates')
    for key in ('timeout_seconds','minimum_request_interval_seconds'):
        if type(config[key]) not in (int,float) or not math.isfinite(config[key]) or config[key]<=0:
            raise ConfigurationError(key+' must be a positive finite number')
    if config['image_detail'] not in ('low','high','auto'):
        raise ConfigurationError('invalid image detail')
    # Use a conservative rate covering BOTH selected models; provider rates must be checked before running.
    return config


class HTTPTransport:
    """Real network boundary; test transports are injected only by unit tests."""
    def __init__(self,config):
        self.config=config
        self.key=os.environ.get(config['api_key_env'])
        key_file=Path.home()/'.config/provenance-pilot/gemini-api-key'
        if not self.key and key_file.is_file():
            self.key=key_file.read_text().strip()
        if not self.key:
            raise ConfigurationError('credential environment variable is not configured')

    def __call__(self,body):
        request=urllib.request.Request(self.config['endpoint'], data=json.dumps(body).encode(),
            headers={'Authorization':'Bearer '+self.key,'Content-Type':'application/json'},method='POST')
        # Do not follow redirects carrying credentials to an unexpected endpoint.
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self,*args,**kwargs):
                return None
        try:
            with urllib.request.build_opener(NoRedirect).open(request,timeout=self.config['timeout_seconds']) as response:
                return {'http_status':response.status,'body':response.read().decode('utf-8')}
        except urllib.error.HTTPError as exc:
            return {'http_status':exc.code,'body':exc.read().decode('utf-8',errors='replace')}


class Session:
    def __init__(self,config,directory,transport=None,replay_only=False):
        self.config=validate_config(config)
        self.directory=Path(directory);self.directory.mkdir(parents=True,exist_ok=True)
        self.identity=object_hash(config)
        self.ledger_path=self.directory/'ledger.json'
        self.ledger=read_json(self.ledger_path) if self.ledger_path.exists() else {
            'config_id':self.identity,'reserved_usd':0.0,'calls':{}}
        if self.ledger['config_id']!=self.identity:
            raise ConfigurationError('cached model settings/budget do not match; use a new run directory')
        self.transport=transport
        self.replay_only=replay_only
        self.reservation=(config['max_input_tokens']*config['input_usd_per_million']+
                          config['max_completion_tokens']*config['output_usd_per_million'])/1_000_000

    def call(self,logical_id,role,messages,schema):
        body={'model':self.config['worker_model' if role=='worker' else 'aggregator_model'],
              'messages':messages,'reasoning_effort':'low','max_completion_tokens':self.config['max_completion_tokens'],
              'response_format':{'type':'json_schema','json_schema':{'name':role+'_output','strict':True,'schema':schema}}}
        key=object_hash({'logical_id':logical_id,'role':role,'body':body,'config_id':self.identity})
        cached=self.ledger['calls'].get(key)
        if cached:
            if cached['status']=='reserved':
                return {'call_id':key,'status':'failure: interrupted_request_outcome_unknown','parsed':None,
                        'raw':None,'estimated_cost_usd':None,'latency_seconds':None,'usage':None}
            path=self.directory/(key+'.json')
            entry=read_json(path)
            if object_hash(entry)!=cached['response_hash']:
                raise ConfigurationError('cached response integrity mismatch')
            return entry
        if self.ledger.get('stopped_reason'):
            raise BudgetExceeded(self.ledger['stopped_reason'])
        if self.replay_only:
            raise ConfigurationError('replay has an uncached request; refuse network access')
        if any(v.get('overrun') for v in self.ledger['calls'].values()):
            raise BudgetExceeded('reported usage exceeded configured bounds; further calls disabled')
        if self.ledger['reserved_usd']+self.reservation>self.config['budget_usd']+1e-12:
            raise BudgetExceeded('local spending reservation cap reached')
        if self.transport is None:
            self.transport=HTTPTransport(self.config)
        self.ledger['calls'][key]={'status':'reserved','reserved_usd':self.reservation}
        self.ledger['reserved_usd']+=self.reservation
        atomic_json(self.ledger_path,self.ledger)
        atomic_json(self.directory/(key+'.request.json'),{'logical_id':logical_id,'role':role,'request':body})
        delay=self.config['minimum_request_interval_seconds']-(time.time()-self.ledger.get('last_request_epoch',0))
        if delay>0:
            time.sleep(delay)
        self.ledger['last_request_epoch']=time.time()
        atomic_json(self.ledger_path,self.ledger)
        start=time.monotonic()
        entry={'call_id':key,'logical_id':logical_id,'role':role,'parsed':None,'usage':None,
               'estimated_cost_usd':None,'raw':None,'status':'failure: transport'}
        try:
            raw=self.transport(body)
            entry['raw']=raw
            if raw['http_status']!=200:
                entry['status']='failure: http_'+str(raw['http_status'])
                self.ledger['stopped_reason']='HTTP '+str(raw['http_status'])+'; no retries or fallback (429 means quota/rate exhausted)' 
            else:
                response=json.loads(raw['body'])
                entry['provider_model']=response.get('model')
                entry['provider_fingerprint']=response.get('system_fingerprint')
                entry['usage']=response.get('usage')
                choice=response['choices'][0]
                if choice['finish_reason']!='stop' or choice['message'].get('refusal'):
                    entry['status']='failure: refusal_or_incomplete_response'
                else:
                    entry['parsed']=json.loads(choice['message']['content'])
                    entry['status']='received'  # Semantic schema checks run outside the transport.
                usage=entry['usage']
                if usage and all(type(usage.get(k)) is int and usage[k]>=0 for k in ('prompt_tokens','completion_tokens')):
                    entry['estimated_cost_usd']=(usage['prompt_tokens']*self.config['input_usd_per_million']+
                        usage['completion_tokens']*self.config['output_usd_per_million'])/1_000_000
                    if usage['prompt_tokens']>self.config['max_input_tokens'] or usage['completion_tokens']>self.config['max_completion_tokens']:
                        self.ledger['calls'][key]['overrun']=True
                else:
                    entry['usage']=None
        except (OSError,ValueError,KeyError,IndexError,TypeError) as exc:
            # Never put API keys or request headers in error output.
            entry['status']='failure: '+type(exc).__name__
            self.ledger['stopped_reason']='transport or parsing failure; manual review required'
        entry['latency_seconds']=time.monotonic()-start
        atomic_json(self.directory/(key+'.json'),entry)
        self.ledger['calls'][key].update(status='complete',response_hash=object_hash(entry))
        atomic_json(self.ledger_path,self.ledger)
        return entry


def image_content(payload,modality,detail):
    if modality not in ('image/png','image/jpeg'):
        raise ValueError('vision adapter requires PNG or JPEG bytes')
    return {'type':'image_url','image_url':{'url':'data:'+modality+';base64,'+base64.b64encode(payload).decode(),
                                          'detail':detail}}
