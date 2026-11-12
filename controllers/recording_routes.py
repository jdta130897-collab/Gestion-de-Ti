"""Cada descarga comprueba sesión y propietario; el código no sustituye la autorización."""
from io import BytesIO
from flask import Blueprint,session,jsonify,send_file,render_template
from config.database import Database
from utils.permissions import is_super_admin

recordings_bp=Blueprint('recordings',__name__)


def scope():
    return ('1=1',[]) if is_super_admin() else ('r.user_id=%s',[session['user_id']])


def listing():
    condition,params=scope()
    return Database().execute_query('''SELECT r.id,r.attempt_id,r.ticket_id,r.software_version,r.byte_size,r.sha256,
        r.outcome,r.created_at,r.error_code,p.code AS participant_code
        FROM voice_recordings r JOIN research_participants p ON p.id=r.participant_id
        WHERE '''+condition+' ORDER BY r.created_at DESC LIMIT 200',params)


@recordings_bp.get('/recordings')
def index():
    return render_template('recordings.html',recordings=listing())


@recordings_bp.get('/api/recordings')
def records():
    return jsonify(items=listing())


@recordings_bp.get('/recordings/<recording_id>/audio')
def download(recording_id):
    condition,params=scope()
    rows=Database().execute_query('SELECT r.audio_data,r.mime_type,r.sha256 FROM voice_recordings r WHERE r.id=%s AND '+condition,[recording_id,*params])
    if not rows:return jsonify(error='Grabación no disponible.'),404
    row=rows[0]
    extension={'audio/webm':'webm','audio/wav':'wav','audio/mpeg':'mp3'}[row['mime_type']]
    response=send_file(BytesIO(bytes(row['audio_data'])),mimetype=row['mime_type'],
        download_name=recording_id+'.'+extension,as_attachment=True,conditional=True,etag=row['sha256'],max_age=0)
    response.headers['Cache-Control']='private, no-store, max-age=0'
    response.headers['X-Content-Type-Options']='nosniff'
    return response


@recordings_bp.post('/recordings/<recording_id>/delete')
def delete(recording_id):
    condition,params=scope()
    rows=Database().execute_query('SELECT r.id FROM voice_recordings r WHERE r.id=%s AND '+condition,[recording_id,*params])
    if not rows:return jsonify(error='Grabación no disponible.'),404
    Database().execute_update('DELETE FROM voice_recordings WHERE id=%s',(recording_id,))
    from flask import redirect,url_for
    return redirect(url_for('recordings.index'))


@recordings_bp.after_request
def private_cache(response):
    response.headers['Cache-Control']='private, no-store, max-age=0'
    return response
