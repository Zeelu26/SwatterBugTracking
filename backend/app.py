import os
import uuid
import base64
from flask import Flask, request, jsonify, redirect, session, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
from functools import wraps
from supabase_client import supabase
import resend

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.join(BASE_DIR, '..', 'frontend')

app = Flask(__name__, static_folder=FRONTEND_DIR, static_url_path='')
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'super-secret-demo-key')

resend.api_key = os.environ.get('RESEND_API_KEY', '')
ADMIN_EMAIL = os.environ.get('ADMIN_EMAIL', 'Zeelpatel9262@gmail.com')
SUPABASE_URL = os.environ.get('SUPABASE_URL', '')

ROLE_HIERARCHY = {'admin': 3, 'developer': 2, 'user': 1}


def seed_admin():
    email = 'zeelpatel9262@gmail.com'
    existing = supabase.table('users').select('id').eq('email', email).execute()
    if not existing.data or len(existing.data) == 0:
        supabase.table('users').insert({
            'name': 'Zeel Patel',
            'email': email,
            'password': generate_password_hash('Zeel7821', method='pbkdf2:sha256'),
            'role': 'admin',
            'is_active': True,
            'email_verified': True
        }).execute()
        print("Super admin seeded: zeelpatel9262@gmail.com")
    else:
        supabase.table('users').update({'role': 'admin', 'email_verified': True}).eq('email', email).execute()

seed_admin()


def send_email(to, subject, html):
    try:
        if not resend.api_key or resend.api_key.startswith('re_YOUR'):
            print(f"[EMAIL SKIPPED] To: {to} | Subject: {subject}")
            return
        resend.Emails.send({
            "from": "Swatter <onboarding@resend.dev>",
            "to": [to],
            "subject": subject,
            "html": html
        })
        print(f"[EMAIL SENT] To: {to}")
    except Exception as e:
        print(f"[EMAIL ERROR] {e}")


def get_base_url():
    host = request.host_url.rstrip('/')
    return host


# ── AUTH DECORATORS ──────────────────────────────────────────
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect('/login')
        return f(*args, **kwargs)
    return decorated

def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if 'user_id' not in session:
                return redirect('/login')
            if session.get('role') not in roles:
                return jsonify({'error': 'Insufficient permissions'}), 403
            return f(*args, **kwargs)
        return decorated
    return decorator

def api_role_required(*roles):
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if 'user_id' not in session:
                return jsonify({'error': 'Unauthorized'}), 401
            if session.get('role') not in roles:
                return jsonify({'error': 'Insufficient permissions'}), 403
            return f(*args, **kwargs)
        return decorated
    return decorator


# ── PAGE ROUTES ──────────────────────────────────────────────
@app.route('/')
def index():
    if 'user_id' in session:
        if session.get('role') in ('admin', 'developer'):
            return redirect('/admin')
        return redirect('/dashboard')
    return redirect('/login')

@app.route('/login')
def page_login():
    if 'user_id' in session:
        return redirect('/')
    return send_from_directory(FRONTEND_DIR, 'login.html')

@app.route('/register')
def page_register():
    if 'user_id' in session:
        return redirect('/')
    return send_from_directory(FRONTEND_DIR, 'register.html')

@app.route('/dashboard')
@login_required
def page_dashboard():
    return send_from_directory(FRONTEND_DIR, 'dashboard_user.html')

@app.route('/admin')
@role_required('admin', 'developer')
def page_admin():
    return send_from_directory(FRONTEND_DIR, 'admin.html')

@app.route('/reviews')
def page_reviews():
    return send_from_directory(FRONTEND_DIR, 'reviews.html')

@app.route('/verify/<token>')
def verify_email(token):
    result = supabase.table('users').select('id').eq('verify_token', token).execute()
    if not result.data:
        return '<h2 style="font-family:sans-serif;text-align:center;margin-top:100px;color:#ef4444;">Invalid or expired verification link.</h2>'
    supabase.table('users').update({'email_verified': True, 'verify_token': None}).eq('verify_token', token).execute()
    return '<h2 style="font-family:sans-serif;text-align:center;margin-top:100px;color:#22c55e;">Email verified! You can now <a href="/login" style="color:#FFBE32;">sign in</a>.</h2>'

@app.route('/css/<path:f>')
def serve_css(f):
    return send_from_directory(os.path.join(FRONTEND_DIR, 'css'), f)

@app.route('/js/<path:f>')
def serve_js(f):
    return send_from_directory(os.path.join(FRONTEND_DIR, 'js'), f)


# ── AUTH API ─────────────────────────────────────────────────
@app.route('/api/register', methods=['POST'])
def api_register():
    d = request.get_json() or {}
    name = d.get('name', '').strip()
    email = d.get('email', '').strip().lower()
    pw = d.get('password', '')
    if not name or not email or not pw:
        return jsonify({'error': 'All fields required'}), 400
    if len(name) < 2:
        return jsonify({'error': 'Name must be at least 2 characters'}), 400
    if '@' not in email or '.' not in email or email.index('@') > email.rindex('.'):
        return jsonify({'error': 'Please enter a valid email address'}), 400
    if len(pw) < 8:
        return jsonify({'error': 'Password must be at least 8 characters'}), 400
    existing = supabase.table('users').select('id').eq('email', email).execute()
    if existing.data and len(existing.data) > 0:
        return jsonify({'error': 'Email already registered'}), 409
    result = supabase.table('users').insert({
        'name': name,
        'email': email,
        'password': generate_password_hash(pw, method='pbkdf2:sha256'),
        'role': 'user',
        'is_active': True,
        'email_verified': True
    }).execute()
    user = result.data[0]
    session['user_id'] = user['id']
    session['role'] = user['role']
    session['name'] = user['name']
    session['email'] = user['email']
    return jsonify({'id': user['id'], 'name': user['name'], 'role': user['role']}), 201

@app.route('/api/login', methods=['POST'])
def api_login():
    d = request.get_json() or {}
    email = d.get('email', '').strip().lower()
    pw = d.get('password', '')
    if not email or not pw:
        return jsonify({'error': 'Email and password are required'}), 400
    if '@' not in email or '.' not in email:
        return jsonify({'error': 'Please enter a valid email address'}), 400
    if len(pw) < 8:
        return jsonify({'error': 'Password must be at least 8 characters'}), 400
    result = supabase.table('users').select('*').eq('email', email).execute()
    if not result.data or len(result.data) == 0:
        return jsonify({'error': 'Invalid email or password'}), 401
    user = result.data[0]
    if not user.get('is_active', True):
        return jsonify({'error': 'Account has been deactivated'}), 403
    if not check_password_hash(user['password'], pw):
        return jsonify({'error': 'Invalid email or password'}), 401
    session['user_id'] = user['id']
    session['role'] = user['role']
    session['name'] = user['name']
    session['email'] = user['email']
    return jsonify({'id': user['id'], 'name': user['name'], 'role': user['role']})

@app.route('/api/resend-verification', methods=['POST'])
def api_resend_verification():
    d = request.get_json() or {}
    email = d.get('email', '').strip().lower()
    if not email:
        return jsonify({'error': 'Email required'}), 400
    result = supabase.table('users').select('id, name, email_verified, verify_token').eq('email', email).execute()
    if not result.data:
        return jsonify({'message': 'If that email exists, a verification link has been sent.'}), 200
    user = result.data[0]
    if user.get('email_verified'):
        return jsonify({'message': 'Email is already verified.'}), 200
    token = user.get('verify_token') or str(uuid.uuid4())
    if not user.get('verify_token'):
        supabase.table('users').update({'verify_token': token}).eq('id', user['id']).execute()
    verify_url = f"{get_base_url()}/verify/{token}"
    send_email(email, 'Verify your Swatter account', f'<h3>Hi {user["name"]}!</h3><p>Click below to verify:</p><p><a href="{verify_url}" style="background:#FFBE32;color:#0f0f1e;padding:12px 24px;border-radius:8px;text-decoration:none;font-weight:bold;">Verify Email</a></p>')
    return jsonify({'message': 'Verification email sent! Check your inbox.'}), 200

@app.route('/api/logout', methods=['POST'])
def api_logout():
    session.clear()
    return jsonify({'message': 'Logged out successfully'})

@app.route('/api/me')
def api_me():
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    return jsonify({'id': session['user_id'], 'name': session['name'], 'role': session['role'], 'email': session.get('email', '')})


# ── BUGS API ────────────────────────────────────────────────
@app.route('/api/bugs', methods=['GET'])
def api_bugs_get():
    rid = request.args.get('reporter_id')
    st = request.args.get('status')
    pr = request.args.get('priority')
    aid = request.args.get('assignee_id')
    query = supabase.table('bugs').select('*, reporter:users!reporter_id(name, email), assignee:users!assignee_id(name, email)')
    if rid: query = query.eq('reporter_id', rid)
    if st: query = query.eq('status', st)
    if pr: query = query.eq('priority', pr)
    if aid: query = query.eq('assignee_id', aid)
    result = query.order('created_at', desc=True).execute()
    bugs = []
    for b in result.data:
        bugs.append({
            'id': b['id'], 'title': b['title'], 'priority': b['priority'], 'status': b['status'],
            'photo_url': b.get('photo_url'),
            'reporter_name': b['reporter']['name'] if b.get('reporter') else None,
            'assignee_name': b['assignee']['name'] if b.get('assignee') else None,
            'assignee_id': b.get('assignee_id'),
            'created_at': b.get('created_at', ''), 'updated_at': b.get('updated_at', '')
        })
    return jsonify(bugs)

@app.route('/api/bugs', methods=['POST'])
def api_bugs_post():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    d = request.get_json() or {}
    title = d.get('title', '').strip()
    desc = d.get('description', '').strip()
    priority = d.get('priority', 'medium').lower()
    photo_data = d.get('photo')
    if not title:
        return jsonify({'error': 'Title required'}), 400
    if priority not in ('critical', 'high', 'medium', 'low'): priority = 'medium'
    photo_url = None
    if photo_data:
        try:
            header, encoded = photo_data.split(',', 1)
            ext = 'png' if 'png' in header else 'jpg'
            filename = f"{uuid.uuid4()}.{ext}"
            file_bytes = base64.b64decode(encoded)
            content_type = 'image/png' if ext == 'png' else 'image/jpeg'
            supabase.storage.from_('bug-photos').upload(filename, file_bytes, {"content-type": content_type})
            photo_url = f"{SUPABASE_URL}/storage/v1/object/public/bug-photos/{filename}"
        except Exception as e:
            print(f"[PHOTO ERROR] {e}")
    result = supabase.table('bugs').insert({
        'title': title, 'description': desc, 'priority': priority, 'status': 'open',
        'reporter_id': session['user_id'], 'photo_url': photo_url    }).execute()
    bug = result.data[0]
    supabase.table('activity_log').insert({
        'bug_id': bug['id'], 'user_id': session['user_id'], 'action': 'created',
        'details': f'Bug #{bug["id"]} created with priority {priority}'
    }).execute()
    send_email(ADMIN_EMAIL, f'[Swatter] New Bug #{bug["id"]}: {title}',
        f'<h3>New Bug Report</h3><p><b>{title}</b></p><p>Priority: {priority}</p><p>By: {session["name"]}</p>')
    return jsonify({'id': bug['id'], 'title': bug['title'], 'status': bug['status']}), 201

@app.route('/api/bugs/<int:bid>', methods=['GET'])
def api_bug_get(bid):
    result = supabase.table('bugs').select('*, reporter:users!reporter_id(name, email), assignee:users!assignee_id(name, email)').eq('id', bid).execute()
    if not result.data:
        return jsonify({'error': 'Not found'}), 404
    bug = result.data[0]
    comments_result = supabase.table('comments').select('*, author:users!author_id(name)').eq('bug_id', bid).order('created_at', desc=False).execute()
    comments = [{'id': c['id'], 'text': c['text'], 'is_resolution': c['is_resolution'],
        'author_name': c['author']['name'] if c.get('author') else 'Unknown', 'created_at': c.get('created_at', '')} for c in comments_result.data]
    activity_result = supabase.table('activity_log').select('*, user:users!user_id(name)').eq('bug_id', bid).order('created_at', desc=False).execute()
    activity = [{'id': a['id'], 'action': a['action'], 'details': a['details'],
        'user_name': a['user']['name'] if a.get('user') else 'System', 'created_at': a.get('created_at', '')} for a in activity_result.data]
    return jsonify({
        'id': bug['id'], 'title': bug['title'], 'description': bug['description'],
        'priority': bug['priority'], 'status': bug['status'],
        'photo_url': bug.get('photo_url'),
        'reporter_name': bug['reporter']['name'] if bug.get('reporter') else None,
        'assignee_name': bug['assignee']['name'] if bug.get('assignee') else None,
        'assignee_id': bug.get('assignee_id'), 'created_at': bug.get('created_at', ''),
        'rating': bug.get('rating'),
        'rating_feedback': bug.get('rating_feedback'),
        'comments': comments, 'activity': activity
    })

@app.route('/api/bugs/<int:bid>/status', methods=['PATCH'])
@api_role_required('admin', 'developer')
def api_bug_status(bid):
    d = request.get_json() or {}
    new_status = d.get('status', '').lower()
    if new_status not in ('open', 'in-progress', 'resolved', 'closed'):
        return jsonify({'error': 'Invalid status'}), 400
    bug_check = supabase.table('bugs').select('id, status, reporter_id').eq('id', bid).execute()
    if not bug_check.data:
        return jsonify({'error': 'Bug not found'}), 404
    old_status = bug_check.data[0]['status']
    supabase.table('bugs').update({'status': new_status, 'updated_at': 'now()'}).eq('id', bid).execute()
    supabase.table('activity_log').insert({'bug_id': bid, 'user_id': session['user_id'], 'action': 'status_changed', 'details': f'{old_status} → {new_status}'}).execute()
    reporter = supabase.table('users').select('email, name').eq('id', bug_check.data[0]['reporter_id']).execute()
    if reporter.data:
        send_email(reporter.data[0]['email'], f'[Swatter] Bug #{bid} → {new_status}',
            f'<p>Hi {reporter.data[0]["name"]}, Bug <b>#{bid}</b> is now <b>{new_status}</b>.</p>')
    return jsonify({'message': f'Status updated to {new_status}'})

@app.route('/api/bugs/<int:bid>/assign', methods=['PATCH'])
@api_role_required('admin', 'developer')
def api_bug_assign(bid):
    d = request.get_json() or {}
    assignee_id = d.get('assignee_id')
    if assignee_id:
        user_check = supabase.table('users').select('id, name, email').eq('id', assignee_id).execute()
        if not user_check.data:
            return jsonify({'error': 'User not found'}), 404
        assignee = user_check.data[0]
    supabase.table('bugs').update({'assignee_id': assignee_id, 'updated_at': 'now()'}).eq('id', bid).execute()
    if assignee_id:
        supabase.table('activity_log').insert({'bug_id': bid, 'user_id': session['user_id'], 'action': 'assigned', 'details': f'Assigned to {assignee["name"]}'}).execute()
        bug_info = supabase.table('bugs').select('title').eq('id', bid).execute()
        send_email(assignee['email'], f'[Swatter] Bug #{bid} assigned to you',
            f'<p>Hi {assignee["name"]}, <b>Bug #{bid}: {bug_info.data[0]["title"] if bug_info.data else ""}</b> was assigned to you.</p>')
    return jsonify({'message': 'Bug assigned'})

@app.route('/api/bugs/<int:bid>', methods=['DELETE'])
@api_role_required('admin')
def api_bug_delete(bid):
    bug_check = supabase.table('bugs').select('id, photo_url').eq('id', bid).execute()
    if not bug_check.data:
        return jsonify({'error': 'Bug not found'}), 404
    photo = bug_check.data[0].get('photo_url')
    if photo:
        try:
            filename = photo.split('/')[-1]
            supabase.storage.from_('bug-photos').remove([filename])
        except: pass
    supabase.table('bugs').delete().eq('id', bid).execute()
    return jsonify({'message': 'Bug deleted'})


# ── COMMENTS API ─────────────────────────────────────────────
@app.route('/api/bugs/<int:bid>/comments', methods=['POST'])
def api_comment(bid):
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    d = request.get_json() or {}
    text = d.get('text', '').strip()
    is_res = bool(d.get('is_resolution', False))
    if not text:
        return jsonify({'error': 'Text required'}), 400
    bug_check = supabase.table('bugs').select('id, status, reporter_id').eq('id', bid).execute()
    if not bug_check.data:
        return jsonify({'error': 'Bug not found'}), 404
    if is_res and session.get('role') not in ('admin', 'developer'):
        return jsonify({'error': 'Only staff can mark resolutions'}), 403
    result = supabase.table('comments').insert({'bug_id': bid, 'author_id': session['user_id'], 'text': text, 'is_resolution': is_res}).execute()
    action = 'resolved' if is_res else 'commented'
    supabase.table('activity_log').insert({'bug_id': bid, 'user_id': session['user_id'], 'action': action, 'details': text[:100]}).execute()
    if is_res:
        supabase.table('bugs').update({'status': 'resolved', 'updated_at': 'now()'}).eq('id', bid).execute()
        reporter = supabase.table('users').select('email, name').eq('id', bug_check.data[0]['reporter_id']).execute()
        if reporter.data:
            send_email(reporter.data[0]['email'], f'[Swatter] Bug #{bid} resolved!',
                f'<p>Hi {reporter.data[0]["name"]}, Bug <b>#{bid}</b> has been resolved by {session["name"]}.</p><p><b>Resolution:</b> {text}</p>')
    return jsonify({'id': result.data[0]['id'], 'text': result.data[0]['text']}), 201


# ── STATS API ────────────────────────────────────────────────
@app.route('/api/bugs/<int:bid>/rate', methods=['POST'])
def api_bug_rate(bid):
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    d = request.get_json() or {}
    rating = d.get('rating', 0)
    feedback = d.get('feedback', '').strip()
    if not isinstance(rating, int) or rating < 1 or rating > 5:
        return jsonify({'error': 'Rating must be 1-5'}), 400
    bug = supabase.table('bugs').select('reporter_id, status').eq('id', bid).execute()
    if not bug.data:
        return jsonify({'error': 'Bug not found'}), 404
    if bug.data[0]['reporter_id'] != session['user_id']:
        return jsonify({'error': 'Only the reporter can rate this bug'}), 403
    if bug.data[0]['status'] not in ('resolved', 'closed'):
        return jsonify({'error': 'Can only rate resolved bugs'}), 400
    supabase.table('bugs').update({'rating': rating, 'rating_feedback': feedback}).eq('id', bid).execute()
    supabase.table('activity_log').insert({'bug_id': bid, 'user_id': session['user_id'], 'action': 'rated', 'details': f'Rated {rating}/5'}).execute()
    return jsonify({'message': 'Rating submitted!'})
@app.route('/api/stats')
def api_stats():
    all_bugs = supabase.table('bugs').select('status, priority, category').execute()
    counts = {'open': 0, 'in-progress': 0, 'resolved': 0, 'closed': 0, 'total': 0}
    priority_counts = {'critical': 0, 'high': 0, 'medium': 0, 'low': 0}
    for bug in all_bugs.data:
        counts['total'] += 1
        s = bug['status']
        if s in counts: counts[s] += 1
        p = bug.get('priority', 'medium')
        if p in priority_counts: priority_counts[p] += 1
    users = supabase.table('users').select('id, role').execute()
    role_counts = {}
    for u in users.data:
        r = u['role']
        role_counts[r] = role_counts.get(r, 0) + 1
    return jsonify({
        **counts, 'priorities': priority_counts,
        'total_users': len(users.data), 'roles': role_counts,
        'resolution_rate': round((counts['resolved'] + counts['closed']) / max(counts['total'], 1) * 100, 1)
    })


# ── ADMIN: USER MANAGEMENT ──────────────────────────────────
@app.route('/api/admin/users', methods=['GET'])
@api_role_required('admin', 'developer')
def api_admin_users():
    role_filter = request.args.get('role')
    query = supabase.table('users').select('id, name, email, role, is_active, email_verified, created_at')
    if role_filter:
        query = query.eq('role', role_filter)
    result = query.order('created_at', desc=True).execute()
    return jsonify(result.data)

@app.route('/api/admin/users', methods=['POST'])
@api_role_required('admin')
def api_admin_create_user():
    d = request.get_json() or {}
    name = d.get('name', '').strip()
    email = d.get('email', '').strip().lower()
    pw = d.get('password', '')
    new_role = d.get('role', 'user').lower()
    if not name or not email or not pw:
        return jsonify({'error': 'All fields required'}), 400
    if len(name) < 2:
        return jsonify({'error': 'Name must be at least 2 characters'}), 400
    if '@' not in email or '.' not in email or email.index('@') > email.rindex('.'):
        return jsonify({'error': 'Please enter a valid email address'}), 400
    if len(pw) < 8:
        return jsonify({'error': 'Password must be at least 8 characters'}), 400
    if new_role not in ROLE_HIERARCHY:
        return jsonify({'error': 'Invalid role'}), 400
    existing = supabase.table('users').select('id').eq('email', email).execute()
    if existing.data and len(existing.data) > 0:
        return jsonify({'error': 'Email already registered'}), 409
    result = supabase.table('users').insert({
        'name': name, 'email': email,
        'password': generate_password_hash(pw, method='pbkdf2:sha256'),
        'role': new_role, 'is_active': True, 'email_verified': True
    }).execute()
    return jsonify({'id': result.data[0]['id'], 'message': f'{new_role.capitalize()} created successfully'}), 201

@app.route('/api/admin/users/<int:uid>/role', methods=['PATCH'])
@api_role_required('admin')
def api_admin_change_role(uid):
    d = request.get_json() or {}
    new_role = d.get('role', '').lower()
    if new_role not in ROLE_HIERARCHY:
        return jsonify({'error': 'Invalid role'}), 400
    if uid == session['user_id']:
        return jsonify({'error': 'Cannot change your own role'}), 400
    target = supabase.table('users').select('role').eq('id', uid).execute()
    if not target.data:
        return jsonify({'error': 'User not found'}), 404
    supabase.table('users').update({'role': new_role}).eq('id', uid).execute()
    return jsonify({'message': f'Role updated to {new_role}'})

@app.route('/api/admin/users/<int:uid>/toggle', methods=['PATCH'])
@api_role_required('admin')
def api_admin_toggle_user(uid):
    if uid == session['user_id']:
        return jsonify({'error': 'Cannot deactivate yourself'}), 400
    target = supabase.table('users').select('is_active, role').eq('id', uid).execute()
    if not target.data:
        return jsonify({'error': 'User not found'}), 404
    if target.data[0]['role'] == 'admin' and session.get('role') != 'admin':
        return jsonify({'error': 'Cannot deactivate an admin'}), 403
    new_active = not target.data[0]['is_active']
    supabase.table('users').update({'is_active': new_active}).eq('id', uid).execute()
    return jsonify({'message': f'User {"activated" if new_active else "deactivated"}'})

@app.route('/api/admin/users/<int:uid>', methods=['DELETE'])
@api_role_required('admin')
def api_admin_delete_user(uid):
    if uid == session['user_id']:
        return jsonify({'error': 'Cannot delete yourself'}), 400
    supabase.table('users').delete().eq('id', uid).execute()
    return jsonify({'message': 'User deleted'})

@app.route('/api/admin/staff', methods=['GET'])
@api_role_required('admin', 'developer')
def api_admin_staff():
    result = supabase.table('users').select('id, name, role').in_('role', ['admin', 'developer']).eq('is_active', True).execute()
    return jsonify(result.data)


# ── REVIEWS API ──────────────────────────────────────────────
@app.route('/api/reviews', methods=['GET'])
def api_reviews_get():
    result = supabase.table('reviews').select('*, author:users!author_id(name)').order('created_at', desc=True).execute()
    reviews = []
    for r in result.data:
        replies_result = supabase.table('review_replies').select('*, author:users!author_id(name, role)').eq('review_id', r['id']).order('created_at', desc=False).execute()
        replies = [{'id': rp['id'], 'text': rp['text'], 'author_name': rp['author']['name'] if rp.get('author') else 'Staff',
            'author_role': rp['author']['role'] if rp.get('author') else '', 'created_at': rp.get('created_at', '')} for rp in replies_result.data]
        reviews.append({
            'id': r['id'], 'rating': r['rating'], 'title': r['title'], 'body': r.get('body', ''),
            'author_name': r['author']['name'] if r.get('author') else 'Anonymous',
            'author_id': r.get('author_id'), 'created_at': r.get('created_at', ''), 'replies': replies
        })
    return jsonify(reviews)

@app.route('/api/reviews', methods=['POST'])
def api_reviews_post():
    if 'user_id' not in session:
        return jsonify({'error': 'Login required to leave a review'}), 401
    d = request.get_json() or {}
    rating = d.get('rating', 0)
    title = d.get('title', '').strip()
    body = d.get('body', '').strip()
    if not title:
        return jsonify({'error': 'Title required'}), 400
    if not isinstance(rating, int) or rating < 1 or rating > 5:
        return jsonify({'error': 'Rating must be 1-5'}), 400
    result = supabase.table('reviews').insert({'rating': rating, 'title': title, 'body': body, 'author_id': session['user_id']}).execute()
    return jsonify({'id': result.data[0]['id'], 'message': 'Review submitted!'}), 201

@app.route('/api/reviews/<int:rid>', methods=['DELETE'])
@api_role_required('admin', 'developer')
def api_review_delete(rid):
    supabase.table('reviews').delete().eq('id', rid).execute()
    return jsonify({'message': 'Review deleted'})

@app.route('/api/reviews/<int:rid>/reply', methods=['POST'])
@api_role_required('admin', 'developer')
def api_review_reply(rid):
    d = request.get_json() or {}
    text = d.get('text', '').strip()
    if not text:
        return jsonify({'error': 'Reply text required'}), 400
    result = supabase.table('review_replies').insert({'review_id': rid, 'author_id': session['user_id'], 'text': text}).execute()
    return jsonify({'id': result.data[0]['id'], 'message': 'Reply posted'}), 201


if __name__ == '__main__':
    print("Swatter V3 Running → http://localhost:5000")
    app.run(debug=True, port=5000)
