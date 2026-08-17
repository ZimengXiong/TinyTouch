import csv, html, io, json, os, re, sqlite3
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse
DB=os.environ.get('DB_PATH','/data/tinytouch.db'); EMAIL=re.compile(r'^[^\s@]+@[^\s@]+\.[^\s@]+$'); ORIGIN='https://alpacaengineer.ing'
PST=timezone(timedelta(hours=-8))
def init():
  with sqlite3.connect(DB) as c:
    c.execute('CREATE TABLE IF NOT EXISTS interest (email TEXT PRIMARY KEY, created_at TEXT NOT NULL)')
    columns={row[1] for row in c.execute('PRAGMA table_info(interest)')}
    for name in ('ip','user_agent','referrer','signup_type'):
      if name not in columns:c.execute(f'ALTER TABLE interest ADD COLUMN {name} TEXT')
class API(BaseHTTPRequestHandler):
  def send(self,status=200,payload=b'{"ok":true}'):
    self.send_response(status);self.send_header('Content-Type','application/json');self.send_header('Access-Control-Allow-Origin',ORIGIN);self.send_header('Access-Control-Allow-Methods','POST, OPTIONS');self.send_header('Access-Control-Allow-Headers','Content-Type');self.end_headers();self.wfile.write(payload)
  def do_OPTIONS(self):self.send(204,b'')
  def do_GET(self):
    if self.path=='/health':return self.send()
    if self.path.startswith('/export.csv'):
      query=parse_qs(urlparse(self.path).query)
      try:
        if 'start' not in query: raise ValueError
        start=max(0,int(query['start'][0])); end=max(start,int(query.get('end',[str(start)])[0]))
      except (TypeError,ValueError): start=end=None
      with sqlite3.connect(DB) as c:
        sql='SELECT email,created_at,signup_type,ip,user_agent,referrer FROM interest ORDER BY created_at DESC'
        rows=c.execute(sql if start is None else sql+' LIMIT ? OFFSET ?',(end-start+1,start) if start is not None else ()).fetchall()
      output=io.StringIO(); writer=csv.writer(output,lineterminator='\n')
      writer.writerow(['Email','Joined (PST)','Request','IP','Device / Browser','Referrer'])
      for email,created,signup_type,ip,user_agent,referrer in rows:
        writer.writerow([email,datetime.fromisoformat(created).astimezone(PST).strftime('%Y-%m-%d %H:%M:%S PST'),signup_type or 'waitlist',ip or '',user_agent or '',referrer or 'direct'])
      filename='tinytouch-signups.csv' if start is None else f'tinytouch-signups-{start+1}-to-{end+1}.csv'
      encoded=output.getvalue().encode();self.send_response(200);self.send_header('Content-Type','text/csv; charset=utf-8');self.send_header('Content-Disposition',f'attachment; filename="{filename}"');self.send_header('Content-Length',str(len(encoded)));self.end_headers();self.wfile.write(encoded);return
    if self.path=='/':
      with sqlite3.connect(DB) as c:
        total=c.execute('SELECT count(*) FROM interest').fetchone()[0]
        rows=c.execute('SELECT email,created_at,ip,user_agent,referrer,signup_type FROM interest ORDER BY created_at DESC').fetchall()
        signup_times=c.execute('SELECT created_at FROM interest ORDER BY created_at').fetchall()
      now_pst=datetime.now(timezone.utc).astimezone(PST).date()
      today=sum(datetime.fromisoformat(created).astimezone(PST).date()==now_pst for _,created,*_ in rows)
      body=''.join(f'<tr><td class="pick"><input class="signup-pick" type="checkbox" data-index="{index}" aria-label="Select {html.escape(email)}"></td><td>{html.escape(email)}</td><td>{html.escape(datetime.fromisoformat(created).astimezone(PST).strftime("%b %-d, %Y, %-I:%M %p PST"))}</td><td>{html.escape(signup_type or "waitlist")}</td><td>{html.escape(ip or "—")}</td><td title="{html.escape(user_agent or "")}">{html.escape((user_agent or "—")[:70])}</td><td>{html.escape(referrer or "direct")}</td></tr>' for index,(email,created,ip,user_agent,referrer,signup_type) in enumerate(rows)) or '<tr><td colspan="7">No signups yet.</td></tr>'
      hourly={}
      for (created,) in signup_times:
        local=datetime.fromisoformat(created).astimezone(PST)
        key=local.replace(minute=0,second=0,microsecond=0)
        hourly[key]=hourly.get(key,0)+1
      running=[]
      if hourly:
        cursor=min(hourly)
        end_hour=max(hourly)
        while cursor<=end_hour:
          running.append((cursor.strftime('%Y-%m-%d %H:00'),hourly.get(cursor,0)))
          cursor+=timedelta(hours=1)
      width,height,pad=760,220,36
      if running:
        maximum=max(amount for _,amount in running)
        points=[]; ticks=[]
        for index,(hour,amount) in enumerate(running):
          x=pad+(width-pad*2)*(index/max(1,len(running)-1)); y=height-pad-(height-pad*2)*(amount/max(1,maximum))
          points.append(f'{x:.1f},{y:.1f}')
          # Every hourly bucket gets its own 24-hour PST tick label.
          ticks.append(f'<path class="tick" d="M{x:.1f} {height-pad}v5"/><text x="{x:.1f}" y="{height-pad+18}" text-anchor="end" transform="rotate(-45 {x:.1f} {height-pad+18})">{hour[-5:-3]}</text>')
        path=' '.join(points); start,end=running[0][0],running[-1][0]
        chart=f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="Signups per hour"><path class="grid" d="M{pad} {height-pad}H{width-pad}M{pad} {pad}H{width-pad}"/><polyline points="{path}"/>{"".join(ticks)}<text x="{width-pad}" y="{pad+10}" text-anchor="end">{maximum}</text><text x="{pad-4}" y="{height-pad}" text-anchor="end">0</text><text x="{width/2}" y="{height-3}" text-anchor="middle" class="axis">Hour (PST, 24-hour)</text><text x="7" y="{height/2}" transform="rotate(-90 7 {height/2})" text-anchor="middle" class="axis">Signups per hour</text></svg>'
      else: chart='<div class="empty">No signup data yet.</div>'
      page=f'''<!doctype html><title>TinyTouch admin</title><style>body{{margin:0;background:#0a0a0a;color:#fff;font:16px Arial;padding:48px;max-width:900px}}.heading{{display:flex;align-items:center;justify-content:space-between;margin:0 0 36px}}h1{{font-size:2rem;margin:0}}.export{{color:#fff;border:1px solid #555;padding:9px 12px;text-decoration:none;font-size:.8rem}}.export:hover{{border-color:#fff}}.stats{{display:flex;gap:16px;margin-bottom:28px}}.stat,.chart{{background:#171717;padding:22px}}.stat{{min-width:150px}}.number{{display:block;font-size:2rem;margin-bottom:6px}}.chart{{margin-bottom:42px}}h2{{font-size:.85rem;font-weight:400;color:#aaa;margin:0 0 20px;text-transform:uppercase;letter-spacing:.08em}}svg{{width:100%;height:auto;overflow:visible}}polyline{{fill:none;stroke:#fff;stroke-width:2}}.grid,.tick{{stroke:#353535;stroke-width:1}}text{{fill:#888;font-size:11px}}.axis{{fill:#aaa}}table{{width:100%;border-collapse:collapse;font-size:.83rem}}td{{padding:13px 10px;border-bottom:1px solid #292929;vertical-align:top;max-width:220px;overflow-wrap:anywhere}}td:nth-child(2){{color:#999}}@media(max-width:600px){{body{{padding:24px}}.heading{{margin-bottom:28px}}.stats{{gap:8px;flex-wrap:wrap}}.stat{{min-width:0;flex:1;padding:16px}}.table-wrap{{overflow-x:auto}}}}</style><div class="heading"><h1>TinyTouch</h1><a class="export" href="/export.csv">Export CSV</a></div><section class="stats"><div class="stat"><span class="number">{total}</span>total signups</div><div class="stat"><span class="number">{today}</span>today (PST)</div></section><section class="chart"><h2>Signups per hour</h2>{chart}</section><div class="table-wrap"><table><thead><tr><td>Email</td><td>Joined (PST)</td><td>Request</td><td>IP</td><td>Device / browser</td><td>Referrer</td></tr></thead><tbody>{body}</tbody></table></div>'''
      page+='''<script>(function(){const boxes=[...document.querySelectorAll('.signup-pick')],heading=document.querySelector('.heading');if(!boxes.length)return;heading.insertAdjacentHTML('beforeend','<a class="export" id="range-export" hidden>Export selected range</a>');const link=document.querySelector('#range-export');let last=null;function refresh(){const selected=boxes.filter(box=>box.checked);if(!selected.length){link.hidden=true;return}const first=selected[0].dataset.index,lastSelected=selected[selected.length-1].dataset.index;link.hidden=false;link.href='/export.csv?start='+first+'&end='+lastSelected;link.textContent='Export selected range, '+selected.length+' signup'+(selected.length===1?'':'s')}boxes.forEach((box,index)=>box.addEventListener('click',event=>{if(event.shiftKey&&last!==null){const from=Math.min(last,index),to=Math.max(last,index);for(let i=from;i<=to;i++)boxes[i].checked=box.checked}last=index;refresh()}));})();</script>'''
      encoded=page.encode();self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8');self.send_header('Content-Length',str(len(encoded)));self.end_headers();self.wfile.write(encoded);return
    self.send(404,b'{"error":"not found"}')
  def do_POST(self):
    if self.path!='/interest':return self.send(404,b'{"error":"not found"}')
    try:
      payload=json.loads(self.rfile.read(int(self.headers.get('Content-Length',0))))
      email=payload.get('email','').strip().lower()
      signup_type='express' if payload.get('type')=='express' else 'waitlist'
    except:email='';signup_type='waitlist'
    if not EMAIL.match(email):return self.send(400,b'{"error":"Enter a valid email address."}')
    ip=(self.headers.get('CF-Connecting-IP') or self.headers.get('X-Forwarded-For','').split(',')[0] or self.client_address[0])[:64]
    user_agent=self.headers.get('User-Agent','')[:512]
    referrer=self.headers.get('Referer','')[:2048]
    with sqlite3.connect(DB) as c:c.execute('INSERT INTO interest (email,created_at,ip,user_agent,referrer,signup_type) VALUES (?,?,?,?,?,?) ON CONFLICT(email) DO UPDATE SET signup_type=excluded.signup_type WHERE excluded.signup_type="express"',(email,datetime.now(timezone.utc).isoformat(),ip,user_agent,referrer,signup_type))
    self.send(201)
  def log_message(self,*_):pass
if __name__=='__main__':init();ThreadingHTTPServer(('0.0.0.0',8080),API).serve_forever()
