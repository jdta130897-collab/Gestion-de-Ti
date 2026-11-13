(() => {
    const root = document.getElementById('analytics-workspace');
    if (!root) return;
    const form = document.getElementById('analytics-filters'), charts = {};
    let busy=false, filters=new URLSearchParams(), latest=null;
    const colors=['#5b8def','#f5c518','#3dbe7a','#ff8fa8'];
    const num = (value,suffix='') => value==null ? 'Sin datos' : new Intl.NumberFormat('es-PE',{maximumFractionDigits:2}).format(value)+suffix;
    const write = (id,text) => { const el = document.getElementById(id); if (el) el.textContent = text; };
    function chart(key,id,type,labels,datasets,title,unit='') {
        const ink=getComputedStyle(document.body).color;
        const data={labels,datasets:datasets.map((d,i) => ({label:d.label,data:d.data,backgroundColor:d.backgroundColor || colors[i%colors.length],borderColor:colors[i%colors.length],borderRadius:6,borderWidth:type==='line'?2:0,tension:.25}))};
        const options={responsive:true,maintainAspectRatio:false,animation:false,plugins:{title:{display:false,text:title},legend:{display:type!=='doughnut'&&datasets.length>1,labels:{color:ink}}}};
        if(type!=='doughnut') options.scales={x:{ticks:{color:ink},grid:{display:false}},y:{beginAtZero:true,title:{display:!!unit,text:unit,color:ink},ticks:{color:ink},grid:{color:'#94a3b833'}}};
        if(charts[key]) {charts[key].data=data;charts[key].options=options;charts[key].update();}
        else charts[key]=new Chart(document.getElementById(id),{type,data,options});
    }
    function render(data) {
        const channels=['voice','manual'];
        write('metric-voice',num(data.channels.voice.mean_s,' s')); write('metric-manual',num(data.channels.manual.mean_s,' s'));
        for(const channel of channels) write('sample-'+channel,data.channels[channel].success+' éxitos medidos (servidor)');
        write('metric-gain',num(data.reduction_pct,' %'));write('metric-count',data.measured_success);
        write('metric-unmeasured',data.unmeasured+' tickets operativos sin medición');
        write('analytics-note',data.sample_note+(data.reduction_pct==null ? '' : data.reduction_pct>0 ? ' La voz fue más rápida en el servidor en esta muestra.' : data.reduction_pct<0 ? ' El registro manual fue más rápido en el servidor en esta muestra.' : ' Ambos canales tienen el mismo promedio.'));
        write('analytics-methodology',data.methodology);
        write('analytics-updated',data.scope+' · Actualización cada 5 s · '+new Date(data.updated_at).toLocaleTimeString('es-PE'));

        if (data.scope_comparison) {
            const act = data.scope_comparison.active;
            const per = data.scope_comparison.personal;
            write('analytics-scope-summary',
                `Vista activa: ${act.scope_label} (${act.tickets_total} tickets operativos, ${act.measured_success}/${act.attempts_total} intentos exitosos) · `
                + `Tus datos personales propios: ${per.tickets_total} tickets creados (${per.tickets_open} activos), ${per.measured_success}/${per.attempts_total} intentos exitosos.`
            );
        }
        if (data.denominators) {
            const d = data.denominators;
            write('analytics-denominators',
                `Denominadores: Tasa de éxito = ${d.success_rate.formula} (Voz N=${d.success_rate.voice_denominator}, Manual N=${d.success_rate.manual_denominator}) | `
                + `Finalización = ${d.completion_rate.formula} (Voz N=${d.completion_rate.voice_denominator}, Manual N=${d.completion_rate.manual_denominator}) | `
                + `Tiempos servidor N=(Voz ${d.server_timings.voice_n}, Manual ${d.server_timings.manual_n}) | `
                + `Confirmación visible navegador N=(Voz ${d.browser_timings.voice_n}, Manual ${d.browser_timings.manual_n}).`
            );
        }
        if (data.operational) {
            const op = data.operational;
            write('analytics-operational-summary',
                `Total tickets visibles: ${op.tickets_total} (${op.measured_tickets} con medición experimental, ${op.unmeasured} sin medición) · `
                + `Creados por ti: ${op.created_by_me} · Asignados a ti: ${op.assigned_to_me} · Sin asignar activos: ${op.unassigned_open}.`
            );
        }

        const tbody=document.getElementById('analytics-comparison');tbody.replaceChildren();
        const rowsSpec = [
            ['Intentos totales (éxitos+fallos+aband.+pend.)','attempts',''],
            ['Éxitos medidos (en tiempos)','success',''],
            ['Fallidos (incl. procesamiento vencido)','failed',''],
            ['Fallidos por timeout de procesamiento (>10 min)','stale_processing_failed',''],
            ['Abandonados (explícito, reinicio o >2 h)','abandoned',''],
            ['Pendientes activos (iniciado/procesando)','pending',''],
            ['Tasa de éxito (éxitos / [éxitos+fallos])','success_rate',' %'],
            ['Tasa de finalización (éxitos / intentos totales)','completion_rate',' %'],
            ['Preparación promedio incl. pausas (servidor)','preparation_s',' s'],
            ['Pausas promedio detectadas en cliente','paused_s',' s'],
            ['Procesamiento promedio en servidor','processing_s',' s'],
            ['Total servidor promedio (hasta commit BD)','mean_s',' s'],
            ['Mediana servidor','median_s',' s'],
            ['Percentil 90 servidor','p90_s',' s'],
            ['Desviación estándar servidor','std_s',' s'],
            ['Mínimo servidor','min_s',' s'],
            ['Máximo servidor','max_s',' s'],
            ['Confirmados visualmente en navegador','browser_confirmed',''],
            ['Recuperados tras respuesta perdida','browser_recovered',''],
            ['Total percibido promedio en navegador','browser_mean_s',' s'],
            ['Ida y vuelta HTTP promedio en navegador','browser_roundtrip_s',' s'],
        ];
        for(const [label,field,suffix] of rowsSpec) {
            const row=document.createElement('tr');
            for(const text of [label,...channels.map(k=>num(data.channels[k][field],suffix))]) {const cell=document.createElement('td');cell.textContent=text;row.appendChild(cell);}tbody.appendChild(row);
        }
        const labels=['Voz','Manual'];
        chart('time','analytics-time','bar',labels,[['Promedio','mean_s'],['Mediana','median_s'],['P90','p90_s']].map(([label,field])=>({label,data:channels.map(k=>data.channels[k][field])})),'Tiempo total en servidor','Segundos');
        chart('volume','analytics-volume','bar',labels,[['Exitosos','success'],['Fallidos','failed'],['Abandonados','abandoned'],['Pendientes','pending']].map(([label,field])=>({label,data:channels.map(k=>data.channels[k][field])})),'Intentos y resultados','Intentos');
        chart('success','analytics-success','bar',labels,[{label:'Tasa de éxito',data:channels.map(k=>data.channels[k].success_rate)}],'Tasa de éxito','%');
        chart('phases','analytics-phases','bar',labels,[['Preparación / grabación','preparation_s'],['Procesamiento y guardado','processing_s']].map(([label,field])=>({label,data:channels.map(k=>data.channels[k][field])})),'Fases en servidor','Segundos');
        chart('trend','analytics-trend','line',data.daily.map(r=>r.day),channels.map((k,i)=>({label:labels[i],data:data.daily.map(r=>r[k])})),'Evolución diaria (Lima UTC-5)','Exitosos');
        chart('priority','priorityChart','bar',['Baja','Media','Alta','Crítica'],[{label:'Reportes',data:['low','medium','high','critical'].map(k=>data.priority[k]),backgroundColor:colors}],'Prioridades (operativa)','Solicitudes');
        chart('status','statusChart','doughnut',['Abiertos','En progreso','Resueltos','Cerrados'],[{label:'Reportes',data:['open','in_progress','resolved','closed'].map(k=>data.status[k]),backgroundColor:colors}],'Estados (operativa)');
        document.querySelectorAll('[data-live-ticket]').forEach(el => {
            const values={total:data.tickets_total,open:data.status.open+data.status.in_progress,resolved:data.status.resolved+data.status.closed,progress:data.status.in_progress,critical:data.priority.critical};
            if(el.dataset.liveTicket in values) el.textContent=values[el.dataset.liveTicket];
        });
    }
    function links() {
        document.getElementById('analytics-csv').href='/reports/analytics.csv?'+filters;
        const bundleEl = document.getElementById('analytics-bundle');
        if (bundleEl) bundleEl.href='/reports/analytics-bundle.json?'+filters;
        document.getElementById('analytics-report').href='/reports/analytics?'+filters;
        document.getElementById('analytics-html').href='/reports/analytics?download=1&'+filters;
        document.querySelectorAll('[data-download-svg]').forEach(a=>a.href='/reports/chart.svg?chart='+a.dataset.downloadSvg+'&'+filters);
    }
    async function refresh() {
        if(busy||document.hidden)return;busy=true;
        const requested = filters.toString();
        try {
            const response=await fetch('/api/analytics?'+filters,{cache:'no-store'});
            if(response.redirected)throw new Error('La sesión terminó. Vuelve a ingresar.');
            const data=await response.json();if(!response.ok)throw new Error(data.error||'No se pudieron cargar las estadísticas.');
            if (requested !== filters.toString()) return;
            latest=data;render(data);links();
        } catch(error) {write('analytics-updated',error.message+' · Reintentando automáticamente.');}
        finally {busy=false;if(requested!==filters.toString())refresh();}
    }
    form.addEventListener('submit',event=>{event.preventDefault();filters=new URLSearchParams(new FormData(form));refresh();});
    form.addEventListener('reset',()=>{filters=new URLSearchParams();refresh();});
    document.querySelectorAll('[data-download-png]').forEach(button=>button.addEventListener('click',()=>{
        const source=charts[button.dataset.downloadPng];if(!source||!latest)return;
        const canvas=document.createElement('canvas');canvas.width=3840;canvas.height=2160;
        const config={type:source.config.type,data:JSON.parse(JSON.stringify(source.data)),options:{responsive:false,devicePixelRatio:1,animation:false,layout:{padding:{top:80,left:80,right:80,bottom:140}},plugins:{title:{display:true,text:source.options.plugins.title.text,font:{size:48},color:'#1c2440'},subtitle:{display:true,text:latest.scope+' · '+latest.updated_at,font:{size:26},padding:20},legend:{labels:{font:{size:30},color:'#1c2440'}}}},plugins:[{id:'white-export',beforeDraw(chart){const ctx=chart.ctx;ctx.save();ctx.globalCompositeOperation='destination-over';ctx.fillStyle='#fff';ctx.fillRect(0,0,chart.width,chart.height);ctx.restore();},afterDraw(chart){const ctx=chart.ctx;ctx.save();ctx.font='26px Arial';ctx.fillStyle='#667089';ctx.fillText('Muestra: '+latest.channels.voice.success+' éxitos por voz y '+latest.channels.manual.success+' manuales. '+latest.sample_note,80,chart.height-75);ctx.fillText('Comparación observacional. Horario Lima (UTC-5) sobre UTC. Duración en servidor hasta commit BD.',80,chart.height-35);ctx.restore();}}]};
        if(config.type!=='doughnut')config.options.scales={x:{ticks:{font:{size:28},color:'#1c2440'}},y:{beginAtZero:true,ticks:{font:{size:28},color:'#1c2440'}}};
        const exported=new Chart(canvas,config);const link=document.createElement('a');link.download='comparativa-'+button.dataset.downloadPng+'-4K.png';link.href=canvas.toDataURL('image/png');link.click();exported.destroy();
    }));
    refresh();setInterval(refresh,5000);document.addEventListener('visibilitychange',refresh);window.addEventListener('ti-data-changed',refresh);
    document.querySelectorAll('.theme-toggle').forEach(button=>button.addEventListener('click',()=>{if(latest)render(latest);}));
})();
