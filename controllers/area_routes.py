from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from services.area_service import AreaService
from utils.permissions import is_super_admin
from config.database import Database

areas_bp = Blueprint('areas', __name__)


@areas_bp.before_request
def require_super_admin():
    if not is_super_admin():
        abort(403)


@areas_bp.route('/areas', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        try:
            AreaService.save(request.form.get('name', ''), request.form.get('code', ''), request.form.get('area_id', type=int))
            flash('Área guardada correctamente.', 'success')
            return redirect(url_for('areas.index'))
        except ValueError as error:
            flash(str(error), 'danger')
    return render_template('areas/index.html', areas=AreaService.all())


@areas_bp.post('/areas/<int:area_id>/toggle')
def toggle(area_id):
    area = AreaService.get(area_id)
    if not area:
        abort(404)
    if area['code'] == 'TI':
        flash('TI debe permanecer activa para recibir los pedidos y reportes.', 'warning')
    else:
        Database().execute_update('UPDATE areas SET is_active=NOT is_active WHERE id=%s', (area_id,))
        flash('Estado del área actualizado. Se conserva su historial.', 'success')
    return redirect(url_for('areas.index'))
