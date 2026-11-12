(() => {
    const root = document.getElementById('analytics-workspace');
    if (!root) return;
    const form = document.getElementById('analytics-filters'), charts = {};
    let busy=false, filters=new URLSearchParams(), latest=null;
    const colors=['#5b8def','#f5c518','#3dbe7a','#ff8fa8'];
    const num = (value,suffix='') => value==null ? 'Sin datos' : new Intl.NumberFormat('es-PE',{maximumFractionDigits:2}).format(value)+suffix;
    const write = (id,text) => document.getElementById(id).textContent=text;
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
        for(const channel of channels) write('sample-'+channel,data.channels[channel].success+' registros exitosos medidos');
        write('metric-gain',num(data.reduction_pct,' %'));write('metric-count',data.measured_success);
        write('metric-unmeasured',data.unmeasured+' reportes sin medición');
        write('analytics-note',data.sample_note+(data.reduction_pct==null ? '' : data.reduction_pct>0 ? ' La voz fue más rápida en esta muestra.' : data.reduction_pct<0 ? ' El registro manual fue más rápido en esta muestra.' : ' Ambos canales tienen el mismo promedio.'));
        write('analytics-methodology',data.methodology);
        write('analytics-updated',data.scope+' · Actualización cada 5 s · '+new Date(data.updated_at).toLocaleTimeString('es-PE'));
        const tbody=document.getElementById('analytics-comparison');tbody.replaceChildren();
        for(const [label,field,suffix] of [['Intentos','attempts',''],['Éxitos medidos','success',''],['Fallidos','failed',''],['Abandonados','abandoned',''],['Pendientes','pending',''],['Tasa de éxito','success_rate',' %'],['Mediana','median_s',' s'],['Percentil 90','p90_s',' s'],['Desviación estándar','std_s',' s'],['Mínimo','min_s',' s'],['Máximo','max_s',' s']]) {
            const row=document.createElement('tr');
            for(const text of [label,...channels.map(k=>num(data.channels[k][field],suffix))]) {const cell=document.createElement('td');cell.textContent=text;row.appendChild(cell);}tbody.appendChild(row);
        }
        const labels=['Voz','Manual'];
        chart('time','analytics-time','bar',labels,[['Promedio','mean_s'],['Mediana','median_s'],['P90','p90_s']].map(([label,field])=>({label,data:channels.map(k=>data.channels[k][field])})),'Tiempo de creación','Segundos');
        chart('volume','analytics-volume','bar',labels,[['Exitosos','success'],['Fallidos','failed'],['Abandonados','abandoned'],['Pendientes','pending']].map(([label,field])=>({label,data:channels.map(k=>data.channels[k][field])})),'Intentos y resultados','Intentos');
        chart('success','analytics-success','bar',labels,[{label:'Tasa de éxito',data:channels.map(k=>data.channels[k].success_rate)}],'Tasa de éxito','%');
        chart('phases','analytics-phases','bar',labels,[['Preparación / grabación','preparation_s'],['Procesamiento y guardado','processing_s']].map(([label,field])=>({label,data:channels.map(k=>data.channels[k][field])})),'Fases de creación','Segundos');
        chart('trend','analytics-trend','line',data.daily.map(r=>r.day),channels.map((k,i)=>({label:labels[i],data:data.daily.map(r=>r[k])})),'Evolución de registros','Exitosos');
        chart('priority','priorityChart','bar',['Baja','Media','Alta','Crítica'],[{label:'Reportes',data:['low','medium','high','critical'].map(k=>data.priority[k]),backgroundColor:colors}],'Prioridades','Solicitudes');
        chart('status','statusChart','doughnut',['Abiertos','En progreso','Resueltos','Cerrados'],[{label:'Reportes',data:['open','in_progress','resolved','closed'].map(k=>data.status[k]),backgroundColor:colors}],'Estados');
        document.querySelectorAll('[data-live-ticket]').forEach(el => {
            const values={total:data.tickets_total,open:data.status.open+data.status.in_progress,resolved:data.status.resolved+data.status.closed,progress:data.status.in_progress,critical:data.priority.critical};
            if(el.dataset.liveTicket in values) el.textContent=values[el.dataset.liveTicket];
        });
    }
    function links() {
        document.getElementById('analytics-csv').href='/reports/analytics.csv?'+filters;
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
        const config={type:source.config.type,data:JSON.parse(JSON.stringify(source.data)),options:{responsive:false,devicePixelRatio:1,animation:false,layout:{padding:{top:80,left:80,right:80,bottom:140}},plugins:{title:{display:true,text:source.options.plugins.title.text,font:{size:48},color:'#1c2440'},subtitle:{display:true,text:latest.scope+' · '+latest.updated_at,font:{size:26},padding:20},legend:{labels:{font:{size:30},color:'#1c2440'}}}},plugins:[{id:'white-export',beforeDraw(chart){const ctx=chart.ctx;ctx.save();ctx.globalCompositeOperation='destination-over';ctx.fillStyle='#fff';ctx.fillRect(0,0,chart.width,chart.height);ctx.restore();},afterDraw(chart){const ctx=chart.ctx;ctx.save();ctx.font='26px Arial';ctx.fillStyle='#667089';ctx.fillText('Muestra: '+latest.channels.voice.success+' registros por voz y '+latest.channels.manual.success+' manuales. '+latest.sample_note,80,chart.height-75);ctx.fillText('Comparación observacional. Fechas en horario de Lima. Los tiempos incluyen pausas y procesamiento.',80,chart.height-35);ctx.restore();}}]};
        if(config.type!=='doughnut')config.options.scales={x:{ticks:{font:{size:28},color:'#1c2440'}},y:{beginAtZero:true,ticks:{font:{size:28},color:'#1c2440'}}};
        const exported=new Chart(canvas,config);const link=document.createElement('a');link.download='comparativa-'+button.dataset.downloadPng+'-4K.png';link.href=canvas.toDataURL('image/png');link.click();exported.destroy();
    }));
    refresh();setInterval(refresh,5000);document.addEventListener('visibilitychange',refresh);window.addEventListener('ti-data-changed',refresh);
    document.querySelectorAll('.theme-toggle').forEach(button=>button.addEventListener('click',()=>{if(latest)render(latest);}));
})();
