from models.monitoring import Monitoring
from models.asset import Asset
from services.ai_service import AIService
from datetime import datetime, timedelta
from utils.timezone import utc_now

class MonitoringController:
    """Controlador para gestionar monitoreo de activos."""
    
    @staticmethod
    def get_monitoring_data(asset_id=None, metric_name=None, hours=24):
        """Obtiene datos de monitoreo según filtros específicos."""
        try:
            # Si se especifica activo y métrica, obtener datos específicos
            if asset_id and metric_name:
                data = Monitoring.get_asset_metrics(asset_id, metric_name, hours)
                return {"status": "success", "data": data}
            
            # Si solo se especifica activo, obtener todas las métricas de ese activo
            if asset_id:
                data = Monitoring.find_by_asset(asset_id)
                asset = Asset.find_by_id(asset_id)
                
                # Preparar datos para visualización
                metrics = {}
                for row in data:
                    metric = row['metric_name']
                    if metric not in metrics:
                        metrics[metric] = []
                    metrics[metric].append({
                        'timestamp': row['timestamp'],
                        'value': row['metric_value']
                    })
                
                return {
                    "status": "success", 
                    "data": {
                        "asset": asset,
                        "metrics": metrics
                    }
                }
            
            # Si no se especifica activo, obtener las métricas más recientes
            latest_metrics = Monitoring.get_latest_metrics(10)
            
            # Obtener promedios por métrica
            avg_cpu = Monitoring.get_average_by_metric("cpu_usage", hours)
            avg_memory = Monitoring.get_average_by_metric("memory_usage", hours)
            avg_disk = Monitoring.get_average_by_metric("disk_usage", hours)
            
            # Verificar activos con métricas anómalas
            ai_service = AIService()
            assets_at_risk = []
            
            for asset in Asset.find_all():
                # Obtener últimas métricas del activo
                asset_metrics = Monitoring.find_recent_by_asset(asset['id'], 10)
                
                if asset_metrics:
                    # Preparar datos para la predicción
                    asset_data = {
                        'id': asset['id'],
                        'name': asset['name'],
                        'type': asset['type'],
                        'purchase_date': asset['purchase_date'].strftime('%Y-%m-%d'),
                        'usage_hours': 24 * 7,  # Suponemos uso 24/7 para simplificar
                        'avg_cpu': sum(m['metric_value'] for m in asset_metrics if m['metric_name'] == 'cpu_usage') / 
                                  sum(1 for m in asset_metrics if m['metric_name'] == 'cpu_usage') if any(m['metric_name'] == 'cpu_usage' for m in asset_metrics) else 0,
                        'avg_memory': sum(m['metric_value'] for m in asset_metrics if m['metric_name'] == 'memory_usage') / 
                                     sum(1 for m in asset_metrics if m['metric_name'] == 'memory_usage') if any(m['metric_name'] == 'memory_usage' for m in asset_metrics) else 0,
                        'avg_temperature': sum(m['metric_value'] for m in asset_metrics if m['metric_name'] == 'temperature') / 
                                          sum(1 for m in asset_metrics if m['metric_name'] == 'temperature') if any(m['metric_name'] == 'temperature' for m in asset_metrics) else 25
                    }
                    
                    # Realizar predicción
                    prediction = ai_service.predict_asset_failure(asset_data)
                    
                    if prediction['prediction'] == 'failure' and prediction['probability'] > 0.6:
                        assets_at_risk.append({
                            'asset': asset,
                            'risk_probability': prediction['probability'],
                            'last_metrics': {m['metric_name']: m['metric_value'] for m in asset_metrics[:5]}
                        })
            
            # Devolver dashboard de monitoreo
            return {
                "status": "success", 
                "data": {
                    "latest_metrics": latest_metrics,
                    "averages": {
                        "cpu": avg_cpu,
                        "memory": avg_memory,
                        "disk": avg_disk
                    },
                    "assets_at_risk": assets_at_risk
                }
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    @staticmethod
    def add_metric(monitoring_data):
        """Añade una nueva métrica de monitoreo."""
        try:
            # Validar datos de monitoreo
            if not monitoring_data.get("asset_id") or not monitoring_data.get("metric_name") or "metric_value" not in monitoring_data:
                return {
                    "status": "error", 
                    "message": "Se requiere ID de activo, nombre de métrica y valor"
                }
            
            # Verificar si el activo existe
            asset = Asset.find_by_id(monitoring_data.get("asset_id"))
            if not asset:
                return {"status": "error", "message": "Activo no encontrado"}
            
            # Crear nueva métrica
            monitoring = Monitoring(
                asset_id=monitoring_data.get("asset_id"),
                metric_name=monitoring_data.get("metric_name"),
                metric_value=float(monitoring_data.get("metric_value")),
                timestamp=monitoring_data.get("timestamp", utc_now())
            )
            
            monitoring_id = monitoring.save()
            return {
                "status": "success", 
                "message": "Métrica añadida correctamente", 
                "id": monitoring_id
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    @staticmethod
    def batch_add_metrics(metrics_data):
        """Añade múltiples métricas en lote."""
        try:
            results = []
            for metric in metrics_data:
                result = MonitoringController.add_metric(metric)
                results.append(result)
            
            return {
                "status": "success", 
                "message": f"Añadidas {sum(1 for r in results if r['status'] == 'success')} de {len(results)} métricas",
                "details": results
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    @staticmethod
    def generate_report(asset_id=None, start_date=None, end_date=None, metric_name=None):
        """Genera un informe de monitoreo según filtros específicos."""
        try:
            # Configurar fechas por defecto si no se proporcionan
            if not end_date:
                end_date = utc_now()
            if not start_date:
                start_date = end_date - timedelta(days=30)  # Por defecto, último mes
            
            # Construir consulta según filtros
            params = []
            query = "SELECT m.*, a.name as asset_name, a.type as asset_type FROM monitoring_data m JOIN assets a ON m.asset_id = a.id WHERE m.timestamp BETWEEN %s AND %s"
            params.extend([start_date, end_date])
            
            if asset_id:
                query += " AND m.asset_id = %s"
                params.append(asset_id)
            
            if metric_name:
                query += " AND m.metric_name = %s"
                params.append(metric_name)
            
            query += " ORDER BY m.timestamp"
            
            # Ejecutar consulta
            db = Monitoring.db
            report_data = db.execute_query(query, params)
            
            # Agrupar datos por activo y métrica
            grouped_data = {}
            for row in report_data:
                asset_id = row['asset_id']
                asset_name = row['asset_name']
                metric = row['metric_name']
                
                if asset_id not in grouped_data:
                    grouped_data[asset_id] = {
                        'name': asset_name,
                        'type': row['asset_type'],
                        'metrics': {}
                    }
                
                if metric not in grouped_data[asset_id]['metrics']:
                    grouped_data[asset_id]['metrics'][metric] = []
                
                grouped_data[asset_id]['metrics'][metric].append({
                    'timestamp': row['timestamp'],
                    'value': row['metric_value']
                })
            
            # Calcular estadísticas
            stats = {
                'period': {
                    'start': start_date,
                    'end': end_date
                },
                'assets_count': len(grouped_data),
                'metrics_count': sum(len(data['metrics']) for data in grouped_data.values()),
                'data_points': len(report_data)
            }
            
            return {
                "status": "success", 
                "data": {
                    "stats": stats,
                    "assets": grouped_data
                }
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}