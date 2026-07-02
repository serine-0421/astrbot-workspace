import httpx, json, pprint, datetime, statistics
headers={'Authorization':'Bearer mKtQmqlyBVChC0sQHPQxIaZubebQZvuSqSfxzW7_5MDbzCuyKw8','Accept':'application/json'}
url='https://api.pandascore.co/lol/matches/upcoming?filter[league.name]=msi&per_page=20'
r=httpx.get(url, headers=headers, timeout=30)
print('status', r.status_code)
obj = r.json()
if isinstance(obj, dict):
    obj = obj.get('data', [])
print('count', len(obj))
for m in obj[:12]:
    print({'id': m.get('id'), 'scheduled_at': m.get('scheduled_at'), 'begin_at': m.get('begin_at'), 'status': m.get('status'), 'name': m.get('name'), 'stage': m.get('serie',{}).get('name'), 'league': m.get('league',{}).get('name')})
