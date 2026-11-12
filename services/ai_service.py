import numpy as np
from datetime import datetime
import os
import pickle
import random  # Para simulación

class AIService:
    """Servicio de IA para predicciones en el sistema."""
    _instance = None
    _model = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(AIService, cls).__new__(cls)
            # Cargar modelo pre-entrenado si existe
            model_path = os.path.join(os.path.dirname(__file__), '../models/ai/prediction_model.pkl')
            if os.path.exists(model_path):
                try:
                    with open(model_path, 'rb') as f:
                        cls._model = pickle.load(f)
                except:
                    cls._model = None
            else:
                # Si no hay modelo, utilizaremos un enfoque basado en reglas
                cls._model = None
        return cls._instance
    
    def predict_asset_failure(self, asset_data):
        """
        Predice si un activo podría fallar en base a sus características.
        
        Args:
            asset_data: Dict con características del activo
            
        Returns:
            Dict con predicción y probabilidad
        """
        try:
            # Si no hay modelo ML, usar enfoque basado en reglas
            if self._model is None:
                return self._rule_based_prediction(asset_data)
            
            # Preparar datos para el modelo
            features = self._prepare_features(asset_data)
            
            # Hacer predicción con modelo ML
            prediction = self._model.predict([features])[0]
            probability = max(self._model.predict_proba([features])[0])
            
            return {
                "prediction": "failure" if prediction == 1 else "ok",
                "probability": float(probability),
                "message": "Predicción exitosa"
            }
        except Exception as e:
            # En caso de error, volver al enfoque basado en reglas
            return self._rule_based_prediction(asset_data)
    
    def _rule_based_prediction(self, asset_data):
        """
        Enfoque basado en reglas para predecir fallos cuando no hay modelo ML.
        """
        try:
            risk_score = 0.0
            risk_factors = []
            
            # Calcular edad del activo en días
            if 'purchase_date' in asset_data:
                try:
                    if isinstance(asset_data['purchase_date'], str):
                        purchase_date = datetime.strptime(asset_data['purchase_date'], '%Y-%m-%d')
                    else:
                        purchase_date = asset_data['purchase_date']
                    
                    age_days = (datetime.now() - purchase_date).days
                    
                    # Activos más viejos tienen mayor riesgo
                    if age_days > 1825:  # > 5 años
                        risk_score += 0.4
                        risk_factors.append("Activo con más de 5 años de antigüedad")
                    elif age_days > 1095:  # > 3 años
                        risk_score += 0.2
                        risk_factors.append("Activo con más de 3 años de antigüedad")
                except:
                    pass
            
            # Considerar tipo de activo
            asset_type = asset_data.get('type', '').lower()
            if asset_type == 'hardware':
                risk_score += 0.1
            
            # Considerar uso de CPU si está disponible
            if 'avg_cpu' in asset_data:
                cpu_usage = asset_data.get('avg_cpu', 0)
                if cpu_usage > 90:
                    risk_score += 0.3
                    risk_factors.append("Uso de CPU superior al 90%")
                elif cpu_usage > 75:
                    risk_score += 0.1
                    risk_factors.append("Uso de CPU elevado")
            
            # Considerar uso de memoria si está disponible
            if 'avg_memory' in asset_data:
                memory_usage = asset_data.get('avg_memory', 0)
                if memory_usage > 90:
                    risk_score += 0.3
                    risk_factors.append("Uso de memoria superior al 90%")
                elif memory_usage > 75:
                    risk_score += 0.1
                    risk_factors.append("Uso de memoria elevado")
            
            # Considerar temperatura si está disponible
            if 'avg_temperature' in asset_data:
                temperature = asset_data.get('avg_temperature', 25)
                if temperature > 75:
                    risk_score += 0.4
                    risk_factors.append("Temperatura crítica")
                elif temperature > 60:
                    risk_score += 0.2
                    risk_factors.append("Temperatura elevada")
            
            # Añadir un factor aleatorio para simular predicciones más realistas
            random_factor = random.uniform(-0.1, 0.1)
            risk_score += random_factor
            
            # Limitar riesgo entre 0 y 1
            risk_score = max(0, min(1, risk_score))
            
            # Determinar predicción final
            prediction = "failure" if risk_score > 0.6 else "ok"
            
            return {
                "prediction": prediction,
                "probability": float(risk_score),
                "message": "Predicción basada en reglas",
                "risk_factors": risk_factors
            }
        except Exception as e:
            return {
                "prediction": "unknown",
                "probability": 0.0,
                "message": f"Error en la predicción: {str(e)}"
            }
    
    def _prepare_features(self, asset_data):
        """Prepara las características del activo para el modelo ML."""
        # Vectorización simple de características
        features = []
        
        # Edad del activo en días
        if 'purchase_date' in asset_data:
            try:
                if isinstance(asset_data['purchase_date'], str):
                    purchase_date = datetime.strptime(asset_data['purchase_date'], '%Y-%m-%d')
                else:
                    purchase_date = asset_data['purchase_date']
                age_days = (datetime.now() - purchase_date).days
                features.append(age_days / 1825)  # Normalizar a 5 años
            except:
                features.append(0)
        else:
            features.append(0)
        
        # Tipo de activo (one-hot encoding simplificado)
        asset_type_map = {'hardware': 1, 'software': 0, 'network': 2, 'other': 3}
        asset_type = asset_data.get('type', 'other').lower()
        type_feature = asset_type_map.get(asset_type, 3) / 3  # Normalizar
        features.append(type_feature)
        
        # Uso de CPU
        features.append(asset_data.get('avg_cpu', 0) / 100)
        
        # Uso de memoria
        features.append(asset_data.get('avg_memory', 0) / 100)
        
        # Temperatura
        features.append((asset_data.get('avg_temperature', 25) - 20) / 80)  # Normalizar en rango aproximado
        
        # Incidentes previos (si está disponible)
        features.append(min(asset_data.get('previous_incidents', 0) / 10, 1))
        
        return features
    
    def train_model(self, training_data):
        """
        Entrena un nuevo modelo con datos proporcionados.
        
        Args:
            training_data: Lista de diccionarios con datos de entrenamiento
            
        Returns:
            Dict con resultado del entrenamiento
        """
        try:
            if not training_data or len(training_data) < 10:
                return {
                    "status": "error", 
                    "message": "Se requieren al menos 10 muestras para entrenar el modelo"
                }
            
            # Preparar datos de entrenamiento
            X = []  # Características
            y = []  # Etiquetas (1: fallo, 0: ok)
            
            for item in training_data:
                # Validar datos de entrenamiento
                if 'asset_data' not in item or 'failed' not in item:
                    continue
                
                # Extraer características
                features = self._prepare_features(item['asset_data'])
                X.append(features)
                
                # Extraer etiqueta
                y.append(1 if item['failed'] else 0)
            
            if not X or not y:
                return {
                    "status": "error", 
                    "message": "No se pudieron procesar los datos de entrenamiento"
                }
            
            # Importar biblioteca para entrenamiento
            try:
                from sklearn.ensemble import RandomForestClassifier
            except ImportError:
                return {
                    "status": "error", 
                    "message": "Biblioteca scikit-learn no disponible"
                }
            
            # Entrenar modelo
            self._model = RandomForestClassifier(n_estimators=100, random_state=42)
            self._model.fit(X, y)
            
            # Guardar modelo
            model_dir = os.path.join(os.path.dirname(__file__), '../models/ai')
            os.makedirs(model_dir, exist_ok=True)
            model_path = os.path.join(model_dir, 'prediction_model.pkl')
            
            with open(model_path, 'wb') as f:
                pickle.dump(self._model, f)
            
            return {
                "status": "success", 
                "message": "Modelo entrenado correctamente",
                "samples": len(X)
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    def simulate_training_data(self, num_samples=100):
        """
        Genera datos de entrenamiento simulados para el modelo.
        Útil para crear un modelo inicial sin datos reales.
        
        Args:
            num_samples: Número de muestras a generar
            
        Returns:
            Lista de datos de entrenamiento simulados
        """
        training_data = []
        for _ in range(num_samples):
            # Generar datos aleatorios para un activo ficticio
            age_years = random.uniform(0, 8)  # Edad entre 0 y 8 años
            asset_type = random.choice(['hardware', 'software', 'network', 'other'])
            cpu_usage = random.uniform(10, 95)
            memory_usage = random.uniform(10, 95)
            temperature = random.uniform(20, 85)
            previous_incidents = random.randint(0, 10)
            
            # Crear registro de activo
            asset_data = {
                'purchase_date': (datetime.now() - timedelta(days=int(age_years*365))).strftime('%Y-%m-%d'),
                'type': asset_type,
                'avg_cpu': cpu_usage,
                'avg_memory': memory_usage,
                'avg_temperature': temperature,
                'previous_incidents': previous_incidents
            }
            
            # Determinar si falló (reglas simples)
            failed = False
            if age_years > 5 and temperature > 70:
                failed = True
            elif age_years > 3 and cpu_usage > 85 and memory_usage > 85:
                failed = True
            elif temperature > 80:
                failed = True
            elif age_years > 6 and previous_incidents > 5:
                failed = True
            elif random.random() < 0.05:  # 5% de fallos aleatorios
                failed = True
            
            # Añadir ruido a los datos
            if random.random() < 0.1:  # 10% de datos con ruido
                failed = not failed
            
            training_data.append({
                'asset_data': asset_data,
                'failed': failed
            })
        
        return training_data