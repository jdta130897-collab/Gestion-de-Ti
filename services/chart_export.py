from xml.sax.saxutils import escape


def chart_data(summary, chart):
    c = summary['channels']
    if chart == 'time':
        return 'Tiempo total en servidor por canal', 'Segundos', ['Voz', 'Manual'], [
            ('Promedio', [c[k]['mean_s'] for k in ('voice','manual')]),
            ('Mediana', [c[k]['median_s'] for k in ('voice','manual')]),
            ('Percentil 90', [c[k]['p90_s'] for k in ('voice','manual')])]
    if chart == 'volume':
        return 'Resultados de los intentos', 'Intentos', ['Voz','Manual'], [(label,[c[k][field] for k in ('voice','manual')]) for label,field in [('Exitosos','success'),('Fallidos','failed'),('Abandonados','abandoned'),('Pendientes','pending')]]
    if chart == 'success':
        return 'Tasa de éxito (éxitos / [éxitos+fallos])', 'Porcentaje', ['Voz','Manual'], [('Éxito',[c[k]['success_rate'] for k in ('voice','manual')])]
    if chart == 'phases':
        return 'Preparación frente a procesamiento en servidor', 'Segundos', ['Voz','Manual'], [(label,[c[k][field] for k in ('voice','manual')]) for label,field in [('Preparación / grabación','preparation_s'),('Procesamiento y guardado','processing_s')]]
    if chart == 'trend':
        return 'Solicitudes medidas por día (Lima UTC-5)', 'Exitosos', [r['day'] for r in summary['daily']], [(label,[r[k] for r in summary['daily']]) for label,k in [('Voz','voice'),('Manual','manual')]]
    if chart == 'priority':
        return 'Prioridad de las solicitudes (operativa)', 'Solicitudes', ['Baja','Media','Alta','Crítica'], [('Cantidad',[summary['priority'][k] for k in ('low','medium','high','critical')])]
    return 'Estado de las solicitudes (operativa)', 'Solicitudes', ['Abiertos','En progreso','Resueltos','Cerrados'], [('Cantidad',[summary['status'][k] for k in ('open','in_progress','resolved','closed')])]


def make_svg(summary, chart):
    title, unit, labels, series = chart_data(summary, chart)
    width = max(1920, len(labels)*200)
    colors = ['#5b8def','#f5c518','#3dbe7a','#ff8fa8']
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="1080" viewBox="0 0 {width} 1080" role="img" aria-label="{escape(title)}">',
             '<rect width="100%" height="100%" fill="white"/>',
             f'<text x="100" y="90" font-family="Arial,sans-serif" font-size="42" font-weight="bold" fill="#1c2440">{escape(title)}</text>',
             f'<text x="100" y="140" font-family="Arial,sans-serif" font-size="24" fill="#667089">{escape(summary["scope"])} · {escape(unit)} · Exportación vectorial</text>']
    values = [v for _,vs in series for v in vs if v is not None]
    maximum = max(values+[1])*1.15
    plot_width, plot_height = width-220, 650
    for step in range(6):
        y = 850-step*plot_height/5
        value = maximum*step/5
        parts += [f'<line x1="120" y1="{y}" x2="{width-100}" y2="{y}" stroke="#e6eaf2"/>', f'<text x="105" y="{y+8}" text-anchor="end" font-family="Arial" font-size="22" fill="#667089">{value:.1f}</text>']
    if labels:
        group = plot_width/len(labels)
        bar_width = min(100, group*.7/max(len(series),1))
        for index,label in enumerate(labels):
            center = 120+group*(index+.5)
            parts.append(f'<text x="{center}" y="895" text-anchor="middle" font-family="Arial" font-size="24" fill="#1c2440">{escape(label)}</text>')
            for j,(_,vs) in enumerate(series):
                value = vs[index]
                x = center+(j-len(series)/2)*bar_width
                if value is not None:
                    height = value/maximum*plot_height
                    parts.append(f'<rect x="{x}" y="{850-height}" width="{bar_width-6}" height="{height}" rx="7" fill="{colors[j%len(colors)]}"/>')
                else:
                    parts.append(f'<text x="{x+bar_width/2}" y="820" text-anchor="middle" font-family="Arial" font-size="19" fill="#667089">Sin datos</text>')
    else:
        parts.append('<text x="200" y="480" font-family="Arial" font-size="36" fill="#667089">Sin mediciones en el período seleccionado.</text>')
    for j,(name,_) in enumerate(series):
        x = 120+j*380
        parts.append(f'<rect x="{x}" y="950" width="25" height="25" rx="5" fill="{colors[j%len(colors)]}"/><text x="{x+36}" y="971" font-family="Arial" font-size="23" fill="#1c2440">{escape(name)}</text>')
    parts.append(f'<text x="120" y="1030" font-family="Arial" font-size="20" fill="#667089">{escape(summary["sample_note"])} Comparación observacional. Actualizado: {escape(summary["updated_at"])}</text></svg>')
    return ''.join(parts)
