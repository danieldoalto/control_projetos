"""Handler customizado de rotação de logs com compressão gzip."""

import gzip
import logging
import logging.handlers
import os
from pathlib import Path
import shutil


class CompressedRotatingFileHandler(logging.handlers.RotatingFileHandler):
    """RotatingFileHandler que compacta logs rotacionados com gzip (.gz)."""

    def __init__(
        self,
        filename: str,
        mode: str = "a",
        maxBytes: int = 0,
        backupCount: int = 0,
        encoding: str = "utf-8",
        delay: bool = False,
        errors: str = None,
        compress: bool = True,
    ) -> None:
        # Garante que o diretório pai existe antes de abrir o arquivo
        Path(filename).parent.mkdir(parents=True, exist_ok=True)
        super().__init__(
            filename=filename,
            mode=mode,
            maxBytes=maxBytes,
            backupCount=backupCount,
            encoding=encoding,
            delay=delay,
            errors=errors,
        )
        self.compress = compress

    def doRollover(self) -> None:
        """Executa a rotação dos arquivos de log e compacta com gzip se configurado."""
        if self.stream:
            self.stream.close()
            self.stream = None

        if self.backupCount > 0:
            ext = ".gz" if self.compress else ""
            
            # Remove o arquivo de backup mais antigo se exceder o limite
            oldest_file = f"{self.baseFilename}.{self.backupCount}{ext}"
            if os.path.exists(oldest_file):
                try:
                    os.remove(oldest_file)
                except OSError:
                    pass

            # Desloca backups existentes: log.N-1.gz -> log.N.gz
            for i in range(self.backupCount - 1, 0, -1):
                sfn = f"{self.baseFilename}.{i}{ext}"
                dfn = f"{self.baseFilename}.{i + 1}{ext}"
                if os.path.exists(sfn):
                    if os.path.exists(dfn):
                        try:
                            os.remove(dfn)
                        except OSError:
                            pass
                    try:
                        os.rename(sfn, dfn)
                    except OSError:
                        pass

            # Trata o arquivo recém-rotacionado (baseFilename -> baseFilename.1 [.gz])
            dfn = f"{self.baseFilename}.1{ext}"
            if os.path.exists(dfn):
                try:
                    os.remove(dfn)
                except OSError:
                    pass

            if os.path.exists(self.baseFilename):
                if self.compress:
                    # Compacta diretamente para baseFilename.1.gz
                    try:
                        with open(self.baseFilename, "rb") as f_in:
                            with gzip.open(dfn, "wb") as f_out:
                                shutil.copyfileobj(f_in, f_out)
                        os.remove(self.baseFilename)
                    except Exception:
                        # Fallback se falhar compressão: renomeia sem comprimir
                        if os.path.exists(self.baseFilename):
                            try:
                                os.rename(self.baseFilename, f"{self.baseFilename}.1")
                            except OSError:
                                pass
                else:
                    try:
                        os.rename(self.baseFilename, dfn)
                    except OSError:
                        pass

        if not self.delay:
            self.stream = self._open()

    def emit(self, record: logging.LogRecord) -> None:
        """Emite o registro de log e força flush imediato no disco."""
        super().emit(record)
        self.flush()

