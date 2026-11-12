"""Publica los recursos de Flask en el CDN de Vercel conservando sus URLs."""
from pathlib import Path
from shutil import copytree

root = Path(__file__).resolve().parents[1]
copytree(root / 'views/static', root / 'public/static', dirs_exist_ok=True)
print('Recursos estáticos preparados para Vercel.')
