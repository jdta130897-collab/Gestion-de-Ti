"""Copia al CDN únicamente recursos aprobados de la interfaz, nunca audios/datos."""
from pathlib import Path
from shutil import copy2

STATIC_EXTENSIONS = {'.css', '.js', '.svg', '.png', '.jpg', '.jpeg', '.webp',
                     '.ico', '.woff', '.woff2', '.ttf', '.otf'}


def build_static(root=None):
    root = Path(root or Path(__file__).resolve().parents[1]).resolve()
    source = root / 'views/static'
    target = root / 'public/static'
    if (source.is_symlink() or target.is_symlink()
            or not source.resolve().is_relative_to(root)
            or not target.resolve().is_relative_to(root)):
        raise RuntimeError('No se admiten enlaces simbólicos en los recursos públicos.')
    target.mkdir(parents=True, exist_ok=True)
    approved = {}
    for file in source.rglob('*'):
        if file.is_symlink():
            raise RuntimeError('No se admiten enlaces simbólicos en los recursos públicos.')
        if file.is_file() and file.suffix.lower() in STATIC_EXTENSIONS:
            approved[file.relative_to(source)] = file
    # Limpia solo la salida generada. Los archivos originales se conservan.
    for file in target.rglob('*'):
        if file.is_symlink() or not file.resolve().is_relative_to(root):
            raise RuntimeError('Ruta pública fuera del proyecto.')
        if file.is_file() and file.relative_to(target) not in approved:
            file.unlink()
    for relative, file in approved.items():
        destination = target / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        copy2(file, destination)
    print(f'Recursos públicos preparados: {len(approved)} archivos de interfaz; sin audios ni datos.')
    return sorted(str(path) for path in approved)


if __name__ == '__main__':
    build_static()
