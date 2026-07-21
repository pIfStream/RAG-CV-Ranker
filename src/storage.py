import re
import shutil
from pathlib import Path
from typing import Optional


def name_to_slug(name: str) -> str:
    """Converte un nome ruolo in uno slug per filesystem (es. 'Data Analyst' → 'data-analyst')."""
    slug = name.lower().strip()
    slug = re.sub(r'[^\w\s-]', '', slug)       # rimuove caratteri speciali
    slug = re.sub(r'[\s_]+', '-', slug)         # spazi e underscore → trattino
    slug = re.sub(r'-+', '-', slug)             # rimuove doppi trattini
    slug = slug.strip('-')
    return slug


class FileStorage:
    """Gestisce il salvataggio e la lettura di file su disco.

    I file sono organizzati per ruolo usando lo slug del nome:
        role_references/
            data-analyst/
                abc123.pdf
                def456.pdf
            software-engineer/
                ghi789.pdf
    """

    def __init__(self, base_path: str = "role_references"):
        self.base_path = Path(base_path)
        self.base_path.mkdir(exist_ok=True)

    def _role_dir(self, role_slug: str) -> Path:
        """Restituisce il path della directory per un ruolo."""
        return self.base_path / role_slug

    def save(self, role_slug: str, filename: str, content: bytes) -> str:
        """Salva un file nella directory del ruolo. Restituisce il path assoluto."""
        dir_path = self._role_dir(role_slug)
        dir_path.mkdir(parents=True, exist_ok=True)

        file_path = dir_path / filename
        file_path.write_bytes(content)
        return str(file_path)

    def read(self, file_path: str) -> Optional[bytes]:
        """Legge un file. Restituisce None se non esiste."""
        p = Path(file_path)
        return p.read_bytes() if p.exists() else None

    def delete(self, file_path: str) -> bool:
        """Elimina un singolo file. Restituisce True se rimosso."""
        p = Path(file_path)
        if p.exists():
            p.unlink()
            return True
        return False

    def delete_role_dir(self, role_slug: str) -> bool:
        """Elimina tutta la directory di un ruolo e il suo contenuto."""
        dir_path = self._role_dir(role_slug)
        if dir_path.exists():
            shutil.rmtree(dir_path)
            return True
        return False

    def rename_role_dir(self, old_slug: str, new_slug: str) -> bool:
        """Rinomina la directory di un ruolo (quando il nome viene cambiato)."""
        old_path = self._role_dir(old_slug)
        new_path = self._role_dir(new_slug)

        if not old_path.exists():
            return False
        if old_path == new_path:
            return True

        # Se la nuova directory esiste già, merge dei contenuti
        if new_path.exists():
            for item in old_path.iterdir():
                dest = new_path / item.name
                if not dest.exists():
                    shutil.move(str(item), str(dest))
                else:
                    # Se esiste già, sovrascrive
                    dest.unlink()
                    shutil.move(str(item), str(dest))
            shutil.rmtree(old_path)
        else:
            shutil.move(str(old_path), str(new_path))

        return True

    def get_role_dir(self, role_slug: str) -> Optional[str]:
        """Restituisce il path della directory di un ruolo, o None."""
        dir_path = self._role_dir(role_slug)
        return str(dir_path) if dir_path.exists() else None

    def list_files(self, role_slug: str) -> list[str]:
        """Restituisce la lista dei file nella directory di un ruolo."""
        dir_path = self._role_dir(role_slug)
        if not dir_path.exists():
            return []
        return sorted(str(p) for p in dir_path.iterdir() if p.is_file())
