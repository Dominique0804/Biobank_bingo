import os, random, secrets, io, json, sqlite3, threading
from flask import Flask, render_template, request, jsonify, session, send_file
from flask_socketio import SocketIO, join_room, emit
import qrcode

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', secrets.token_hex(32))
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax', SESSION_COOKIE_SECURE=os.environ.get('RENDER') == 'true')
socketio = SocketIO(app, cors_allowed_origins=None, async_mode='threading')
TERMS = [
 ('Metadata','Information describing a sample, such as the date and place it was collected.'),
 ('Informed consent','Permission given after someone understands how their sample and information may be used.'),
 ('−80 °C freezer','A very cold freezer commonly used to preserve biological samples for long periods.'),
 ('Saliva','A fluid from the mouth that can be collected as a biological sample.'),
 ('Unique ID','A code that helps distinguish one sample from another.'),
 ('Ethics approval','Review and permission from a committee that protects research participants.'),
 ('DNA','The molecule that carries genetic instructions in living organisms.'),
 ('Backup power','A second electricity source that protects stored samples during an outage.'),
 ('Tissue','A group of cells collected from a body for study or storage.'),
 ('Withdrawal','When a participant chooses to stop taking part in research, subject to the consent terms.'),
 ('Privacy code','A code used in place of a person’s name to help protect their identity.'),
 ('Research','A systematic investigation to answer questions and generate knowledge.'),
 ('Liquid nitrogen','An extremely cold liquid sometimes used to preserve samples.'),
 ('Donor','A person who provides a biological sample.'),
 ('POPIA','South Africa’s Protection of Personal Information Act.'),
 ('Access committee','A group that reviews requests to use stored samples or associated data.'),
]
# SQLite persists sessions across restarts when DB_PATH is on a Render persistent disk.
DB_PATH = os.environ.get('DB_PATH', os.path.join(os.path.dirname(__file__), 'bingo.sqlite3'))
os.makedirs(os.path.dirname(os.path.abspath(DB_PATH)), exist_ok=True)
lock = threading.RLock()
with sqlite3.connect(DB_PATH) as conn:
    conn.execute('CREATE TABLE IF NOT EXISTS games (code TEXT PRIMARY KEY, payload TEXT NOT NULL)')

def load_game(code):
    with lock, sqlite3.connect(DB_PATH) as conn:
        row = conn.execute('SELECT payload FROM games WHERE code=?', (code,)).fetchone()
    return json.loads(row[0]) if row else None

def save_game(g):
    with lock, sqlite3.connect(DB_PATH) as conn:
        conn.execute('INSERT OR REPLACE INTO games(code,payload) VALUES (?,?)', (g['code'], json.dumps(g)))


def public_game(g):
    return {'code':g['code'], 'called':g['called'], 'last':g['called'][-1] if g['called'] else None,
            'players':len(g['players']), 'winners':g['winners'], 'finished':g['finished']}

def get_game(code):
    return load_game((code or '').strip().upper())

def is_host(g):
    return session.get('host_token_'+g['code']) == g['host_token']

def player_id(g):
    pid = session.get('player_'+g['code'])
    return pid if pid in g['players'] else None

def winning_lines(marked):
    lines = [[r*4+c for c in range(4)] for r in range(4)]
    lines += [[r*4+c for r in range(4)] for c in range(4)]
    lines += [[i*5 for i in range(4)], [3+i*3 for i in range(4)]]
    return [line for line in lines if all(i in marked for i in line)]

@app.get('/health')
def health(): return jsonify(status='ok')

@app.route('/')
def index(): return render_template('index.html')

@app.post('/api/create')
def create():
    code = ''.join(random.choices('ABCDEFGHJKLMNPQRSTUVWXYZ23456789', k=6))
    while get_game(code): code = ''.join(random.choices('ABCDEFGHJKLMNPQRSTUVWXYZ23456789', k=6))
    token = secrets.token_urlsafe(24)
    g = {'code':code,'host_token':token,'called':[],'players':{},'winners':[], 'finished':False}
    save_game(g)
    session['host_token_'+code] = token
    return jsonify(code=code, host_url='/host/'+code, join_url='/game/'+code)

@app.route('/host/<code>')
def host(code):
    g=get_game(code)
    if not g: return 'Game not found',404
    if not is_host(g): return 'Host access denied. Open the host link in the browser where you created the game.',403
    return render_template('host.html', code=g['code'], terms=TERMS)

@app.route('/game/<code>')
def game(code):
    g=get_game(code)
    if not g: return 'Game not found',404
    return render_template('game.html',code=g['code'])

@app.get('/api/game/<code>')
def state(code):
    g=get_game(code)
    if not g:return jsonify(error='Game not found'),404
    pid=player_id(g)
    result=public_game(g)
    if pid:
        p=g['players'][pid]
        result['player']={'name':p['name'],'card':p['card'],'marked':p['marked'],'won':p['won']}
    result['host']=is_host(g)
    return jsonify(result)

@app.post('/api/game/<code>/join')
def join(code):
    g=get_game(code)
    if not g:return jsonify(error='Game not found'),404
    if g['finished']:return jsonify(error='This game has ended'),400
    pid=player_id(g)
    if pid:return jsonify(public_game(g),player=g['players'][pid])
    name=str((request.get_json(silent=True) or {}).get('name','')).strip()[:35] or 'Anonymous player'
    pid=secrets.token_urlsafe(16)
    # All players get the same 16 terms, uniquely randomized order.
    used={tuple(p['card']) for p in g['players'].values()}
    card=list(range(len(TERMS)))
    for _ in range(30):
        random.SystemRandom().shuffle(card)
        if tuple(card) not in used:break
    g['players'][pid]={'name':name,'card':card[:], 'marked':[], 'won':False}
    session['player_'+code]=pid
    save_game(g)
    socketio.emit('state',public_game(g),to=code)
    return jsonify(public_game(g),player=g['players'][pid])

@app.post('/api/game/<code>/mark')
def mark(code):
    g=get_game(code)
    if not g:return jsonify(error='Game not found'),404
    pid=player_id(g)
    if not pid:return jsonify(error='Join the game first'),403
    if g['finished']:return jsonify(error='Game has ended'),400
    data=request.get_json(silent=True) or {}
    index=data.get('index')
    p=g['players'][pid]
    if type(index) is not int or index<0 or index>=16:return jsonify(error='Invalid square'),400
    if index in p['marked']:p['marked'].remove(index)
    else:p['marked'].append(index)
    save_game(g)
    return jsonify(marked=p['marked'])

@app.post('/api/game/<code>/claim')
def claim(code):
    g=get_game(code)
    if not g:return jsonify(error='Game not found'),404
    pid=player_id(g)
    if not pid:return jsonify(error='Join the game first'),403
    p=g['players'][pid]
    valid=[line for line in winning_lines(p['marked']) if all(p['card'][i] in g['called'] for i in line)]
    if not valid:return jsonify(ok=False,message='Not yet! You need a complete line of correctly called terms.')
    if g['finished']:return jsonify(error='Game has ended'),400
    if not p['won']:
        p['won']=True
        g['winners'].append({'name':p['name'],'kind':'Full card' if len(p['marked'])==16 and all(t in g['called'] for t in p['card']) else 'Line'})
        save_game(g)
        socketio.emit('state',public_game(g),to=code)
    return jsonify(ok=True,message='BINGO! Your winning line is verified.')

@app.post('/api/game/<code>/call')
def call(code):
    g=get_game(code)
    if not g:return jsonify(error='Game not found'),404
    if not is_host(g):return jsonify(error='Host only'),403
    if g['finished']:return jsonify(error='Game has ended'),400
    data=request.get_json(silent=True) or {}
    index=data.get('index')
    if type(index) is not int or index not in range(16):return jsonify(error='Invalid clue'),400
    if index in g['called']:return jsonify(error='Already called'),400
    g['called'].append(index)
    save_game(g)
    socketio.emit('state',public_game(g),to=code)
    return jsonify(public_game(g))

@app.post('/api/game/<code>/finish')
def finish(code):
    g=get_game(code)
    if not g:return jsonify(error='Game not found'),404
    if not is_host(g):return jsonify(error='Host only'),403
    g['finished']=True
    save_game(g)
    socketio.emit('state',public_game(g),to=code)
    return jsonify(public_game(g))

@app.get('/qr/<code>.png')
def qr(code):
    g=get_game(code)
    if not g:return 'Game not found',404
    # PUBLIC_BASE_URL recommended behind reverse proxy, to avoid wrong QR links.
    base=os.environ.get('PUBLIC_BASE_URL',request.url_root.rstrip('/')).rstrip('/')
    url=base+'/game/'+g['code']
    img=qrcode.make(url)
    buf=io.BytesIO();img.save(buf,format='PNG');buf.seek(0)
    return send_file(buf,mimetype='image/png')

@socketio.on('connect')
def socket_connect(auth=None): pass

@socketio.on('join_game')
def socket_join(data):
    code=(data or {}).get('code','').upper()
    g=get_game(code)
    if g:
        join_room(code)
        emit('state',public_game(g))

if __name__=='__main__':
    socketio.run(app,host='0.0.0.0',port=int(os.environ.get('PORT',5000)),debug=False,allow_unsafe_werkzeug=True)
