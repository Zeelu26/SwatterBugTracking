import os
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

ROLE_HIERARCHY = {'admin': 4, 'manager': 3, 'moderator': 2, 'user': 1}


# ── SEED SUPER ADMIN ON STARTUP ─────────────────────────────
def seed_admin():
    email = 'zeelpatel9262@gmail.com'
    existing = supabase.table('users').select('id').eq('email', email).execute()
    if not existing.data or len(existing.data) == 0:
        supabase.table('users').insert({
            'name': 'Zeel Patel',
            'email': email,
            'password': generate_password_hash('Zeel7821', method='pbkdf2:sha256'),
            'role': 'admin',
            'is_active': True
        }).execute()
        print("Super admin seeded: zeelpatel9262@gmail.com")
    else:
        supabase.table('users').update({'role': 'admin'}).eq('email', email).execute()

seed_admin()


# ── EMAIL HELPER ─────────────────────────────────────────────
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
        print(f"[EMAIL SENT] To: {to} | Subject: {subject}")
    except Exception as e:
        print(f"[EMAIL ERROR] {e}")


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
        role = session.get('role')
        if role in ('admin', 'manager', 'moderator'):
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
@role_required('admin', 'manager', 'moderator')
def page_admin():
    return send_from_directory(FRONTEND_DIR, 'admin.html')

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
        'is_active': True
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

@app.route('/api/logout', methods=['POST'])
def api_logout():
    session.clear()
    return jsonify({'message': 'Logged out successfully'})

@app.route('/api/me')
def api_me():
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    return jsonify({
        'id': session['user_id'],
        'name': session['name'],
        'role': session['role'],
        'email': session.get('email', '')
    })


# ── BUGS API ────────────────────────────────────────────────
@app.route('/api/bugs', methods=['GET'])
def api_bugs_get():
    rid = request.args.get('reporter_id')
    st = request.args.get('status')
    pr = request.args.get('priority')
    cat = request.args.get('category')
    aid = request.args.get('assignee_id')
    query = supabase.table('bugs').select(
        '*, reporter:users!reporter_id(name, email), assignee:users!assignee_id(name, email)'
    )
    if rid:
        query = query.eq('reporter_id', rid)
    if st:
        query = query.eq('status', st)
    if pr:
        query = query.eq('priority', pr)
    if cat:
        query = query.eq('category', cat)
    if aid:
        query = query.eq('assignee_id', aid)
    result = query.order('created_at', desc=True).execute()
    bugs = []
    for b in result.data:
        bugs.append({
            'id': b['id'],
            'title': b['title'],
            'priority': b['priority'],
            'status': b['status'],
            'category': b.get('category', 'other'),
            'reporter_name': b['reporter']['name'] if b.get('reporter') else None,
            'reporter_email': b['reporter']['email'] if b.get('reporter') else None,
            'assignee_name': b['assignee']['name'] if b.get('assignee') else None,
            'assignee_id': b.get('assignee_id'),
            'created_at': b.get('created_at', ''),
            'updated_at': b.get('updated_at', '')
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
    category = d.get('category', 'other').lower()
    if not title:
        return jsonify({'error': 'Title required'}), 400
    if priority not in ('critical', 'high', 'medium', 'low'):
        priority = 'medium'
    if category not in ('ui', 'backend', 'database', 'api', 'security', 'other'):
        category = 'other'
    result = supabase.table('bugs').insert({
        'title': title,
        'description': desc,
        'priority': priority,
        'status': 'open',
        'category': category,
        'reporter_id': session['user_id']
    }).execute()
    bug = result.data[0]
    supabase.table('activity_log').insert({
        'bug_id': bug['id'],
        'user_id': session['user_id'],
        'action': 'created',
        'details': f'Bug #{bug["id"]} created with priority {priority}'
    }).execute()
    send_email(
        ADMIN_EMAIL,
        f'[Swatter] New Bug #{bug["id"]}: {title}',
        f'<h3>New Bug Report</h3><p><b>Title:</b> {title}</p><p><b>Priority:</b> {priority}</p><p><b>Category:</b> {category}</p><p><b>Reported by:</b> {session["name"]}</p><p><b>Description:</b> {desc or "No description"}</p>'
    )
    return jsonify({'id': bug['id'], 'title': bug['title'], 'status': bug['status']}), 201

@app.route('/api/bugs/<int:bid>', methods=['GET'])
def api_bug_get(bid):
    result = supabase.table('bugs').select(
        '*, reporter:users!reporter_id(name, email), assignee:users!assignee_id(name, email)'
    ).eq('id', bid).execute()
    if not result.data:
        return jsonify({'error': 'Not found'}), 404
    bug = result.data[0]
    comments_result = supabase.table('comments').select(
        '*, author:users!author_id(name)'
    ).eq('bug_id', bid).order('created_at', desc=False).execute()
    comments = []
    for c in comments_result.data:
        comments.append({
            'id': c['id'],
            'text': c['text'],
            'is_resolution': c['is_resolution'],
            'author_name': c['author']['name'] if c.get('author') else 'Unknown',
            'created_at': c.get('created_at', '')
        })
    activity_result = supabase.table('activity_log').select(
        '*, user:users!user_id(name)'
    ).eq('bug_id', bid).order('created_at', desc=False).execute()
    activity = []
    for a in activity_result.data:
        activity.append({
            'id': a['id'],
            'action': a['action'],
            'details': a['details'],
            'user_name': a['user']['name'] if a.get('user') else 'System',
            'created_at': a.get('created_at', '')
        })
    return jsonify({
        'id': bug['id'],
        'title': bug['title'],
        'description': bug['description'],
        'priority': bug['priority'],
        'status': bug['status'],
        'category': bug.get('category', 'other'),
        'reporter_name': bug['reporter']['name'] if bug.get('reporter') else None,
        'reporter_email': bug['reporter']['email'] if bug.get('reporter') else None,
        'assignee_name': bug['assignee']['name'] if bug.get('assignee') else None,
        'assignee_id': bug.get('assignee_id'),
        'created_at': bug.get('created_at', ''),
        'comments': comments,
        'activity': activity
    })

@app.route('/api/bugs/<int:bid>/status', methods=['PATCH'])
@api_role_required('admin', 'manager', 'moderator')
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
    supabase.table('activity_log').insert({
        'bug_id': bid,
        'user_id': session['user_id'],
        'action': 'status_changed',
        'details': f'Status changed from {old_status} to {new_status}'
    }).execute()
    reporter_result = supabase.table('users').select('email, name').eq('id', bug_check.data[0]['reporter_id']).execute()
    if reporter_result.data:
        reporter = reporter_result.data[0]
        send_email(
            reporter['email'],
            f'[Swatter] Bug #{bid} status updated to {new_status}',
            f'<h3>Bug Status Updated</h3><p>Hi {reporter["name"]},</p><p>Bug <b>#{bid}</b> has been updated to <b>{new_status}</b> by {session["name"]}.</p>'
        )
    return jsonify({'message': f'Status updated to {new_status}'})

@app.route('/api/bugs/<int:bid>/assign', methods=['PATCH'])
@api_role_required('admin', 'manager', 'moderator')
def api_bug_assign(bid):
    d = request.get_json() or {}
    assignee_id = d.get('assignee_id')
    if assignee_id:
        user_check = supabase.table('users').select('id, name, email').eq('id', assignee_id).execute()
        if not user_check.data:
            return jsonify({'error': 'User not found'}), 404
        assignee = user_check.data[0]
    supabase.table('bugs').update({
        'assignee_id': assignee_id,
        'updated_at': 'now()'
    }).eq('id', bid).execute()
    if assignee_id:
        supabase.table('activity_log').insert({
            'bug_id': bid,
            'user_id': session['user_id'],
            'action': 'assigned',
            'details': f'Assigned to {assignee["name"]}'
        }).execute()
        bug_info = supabase.table('bugs').select('title').eq('id', bid).execute()
        bug_title = bug_info.data[0]['title'] if bug_info.data else f'Bug #{bid}'
        send_email(
            assignee['email'],
            f'[Swatter] Bug #{bid} assigned to you',
            f'<h3>Bug Assigned To You</h3><p>Hi {assignee["name"]},</p><p>Bug <b>#{bid}: {bug_title}</b> has been assigned to you by {session["name"]}.</p>'
        )
    return jsonify({'message': 'Bug assigned successfully'})

@app.route('/api/bugs/<int:bid>', methods=['DELETE'])
@api_role_required('admin', 'manager')
def api_bug_delete(bid):
    bug_check = supabase.table('bugs').select('id').eq('id', bid).execute()
    if not bug_check.data:
        return jsonify({'error': 'Bug not found'}), 404
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
    if is_res and session.get('role') not in ('admin', 'manager', 'moderator'):
        return jsonify({'error': 'Only staff can mark resolutions'}), 403
    result = supabase.table('comments').insert({
        'bug_id': bid,
        'author_id': session['user_id'],
        'text': text,
        'is_resolution': is_res
    }).execute()
    action = 'resolved' if is_res else 'commented'
    supabase.table('activity_log').insert({
        'bug_id': bid,
        'user_id': session['user_id'],
        'action': action,
        'details': text[:100]
    }).execute()
    if is_res:
        supabase.table('bugs').update({'status': 'resolved', 'updated_at': 'now()'}).eq('id', bid).execute()
        reporter_result = supabase.table('users').select('email, name').eq('id', bug_check.data[0]['reporter_id']).execute()
        if reporter_result.data:
            reporter = reporter_result.data[0]
            send_email(
                reporter['email'],
                f'[Swatter] Bug #{bid} has been resolved!',
                f'<h3>Bug Resolved</h3><p>Hi {reporter["name"]},</p><p>Bug <b>#{bid}</b> has been resolved by {session["name"]}.</p><p><b>Resolution:</b> {text}</p>'
            )
    return jsonify({'id': result.data[0]['id'], 'text': result.data[0]['text']}), 201


# ── STATS API ────────────────────────────────────────────────
@app.route('/api/stats')
def api_stats():
    all_bugs = supabase.table('bugs').select('status, priority, category').execute()
    counts = {'open': 0, 'in-progress': 0, 'resolved': 0, 'closed': 0, 'total': 0}
    priority_counts = {'critical': 0, 'high': 0, 'medium': 0, 'low': 0}
    category_counts = {}
    for bug in all_bugs.data:
        counts['total'] += 1
        s = bug['status']
        if s in counts:
            counts[s] += 1
        p = bug.get('priority', 'medium')
        if p in priority_counts:
            priority_counts[p] += 1
        c = bug.get('category', 'other')
        category_counts[c] = category_counts.get(c, 0) + 1
    user_count = len(supabase.table('users').select('id').execute().data)
    return jsonify({
        **counts,
        'priorities': priority_counts,
        'categories': category_counts,
        'total_users': user_count,
        'resolution_rate': round((counts['resolved'] + counts['closed']) / max(counts['total'], 1) * 100, 1)
    })


# ── ADMIN: USER MANAGEMENT API ──────────────────────────────
@app.route('/api/admin/users', methods=['GET'])
@api_role_required('admin', 'manager', 'moderator')
def api_admin_users():
    result = supabase.table('users').select('id, name, email, role, is_active, created_at').order('created_at', desc=True).execute()
    return jsonify(result.data)

@app.route('/api/admin/users', methods=['POST'])
@api_role_required('admin', 'manager')
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
    my_level = ROLE_HIERARCHY.get(session.get('role'), 0)
    target_level = ROLE_HIERARCHY.get(new_role, 0)
    if target_level >= my_level:
        return jsonify({'error': f'Cannot create a {new_role} — that role is equal to or above yours'}), 403
    if new_role == 'admin' and session.get('role') != 'admin':
        return jsonify({'error': 'Only admins can create other admins'}), 403
    existing = supabase.table('users').select('id').eq('email', email).execute()
    if existing.data and len(existing.data) > 0:
        return jsonify({'error': 'Email already registered'}), 409
    result = supabase.table('users').insert({
        'name': name,
        'email': email,
        'password': generate_password_hash(pw, method='pbkdf2:sha256'),
        'role': new_role,
        'is_active': True
    }).execute()
    return jsonify({'id': result.data[0]['id'], 'message': f'{new_role.capitalize()} created successfully'}), 201

@app.route('/api/admin/users/<int:uid>/role', methods=['PATCH'])
@api_role_required('admin', 'manager')
def api_admin_change_role(uid):
    d = request.get_json() or {}
    new_role = d.get('role', '').lower()
    if new_role not in ROLE_HIERARCHY:
        return jsonify({'error': 'Invalid role'}), 400
    if uid == session['user_id']:
        return jsonify({'error': 'Cannot change your own role'}), 400
    target_user = supabase.table('users').select('role').eq('id', uid).execute()
    if not target_user.data:
        return jsonify({'error': 'User not found'}), 404
    my_level = ROLE_HIERARCHY.get(session.get('role'), 0)
    current_level = ROLE_HIERARCHY.get(target_user.data[0]['role'], 0)
    target_level = ROLE_HIERARCHY.get(new_role, 0)
    if current_level >= my_level:
        return jsonify({'error': 'Cannot modify a user with equal or higher role'}), 403
    if target_level >= my_level:
        return jsonify({'error': 'Cannot promote to a role equal to or above yours'}), 403
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
    if target.data[0]['role'] == 'admin':
        return jsonify({'error': 'Cannot deactivate another admin'}), 403
    new_active = not target.data[0]['is_active']
    supabase.table('users').update({'is_active': new_active}).eq('id', uid).execute()
    return jsonify({'message': f'User {"activated" if new_active else "deactivated"}'})

@app.route('/api/admin/users/<int:uid>', methods=['DELETE'])
@api_role_required('admin')
def api_admin_delete_user(uid):
    if uid == session['user_id']:
        return jsonify({'error': 'Cannot delete yourself'}), 400
    target = supabase.table('users').select('role').eq('id', uid).execute()
    if not target.data:
        return jsonify({'error': 'User not found'}), 404
    if target.data[0]['role'] == 'admin':
        return jsonify({'error': 'Cannot delete another admin'}), 403
    supabase.table('users').delete().eq('id', uid).execute()
    return jsonify({'message': 'User deleted'})

@app.route('/api/admin/staff', methods=['GET'])
@api_role_required('admin', 'manager', 'moderator')
def api_admin_staff():
    result = supabase.table('users').select('id, name, role').in_('role', ['admin', 'manager', 'moderator']).eq('is_active', True).execute()
    return jsonify(result.data)


# ── START SERVER ─────────────────────────────────────────────
if __name__ == '__main__':
    print("Swatter Server Running (Supabase + Admin) → http://localhost:5000")
    app.run(debug=True, port=5000)
