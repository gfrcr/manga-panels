"""Erros conhecidos do manga_panels — mensagem acionavel, nao stack trace."""
from __future__ import annotations


class MangaPanelsError(Exception):
    """Base pra falhas esperadas (o CLI captura e imprime a mensagem)."""


class EmptyArchive(MangaPanelsError):
    """Arquivo sem nenhuma imagem."""


class BadArchive(MangaPanelsError):
    """Arquivo corrompido ou imagem invalida dentro dele."""


class MissingDependency(MangaPanelsError):
    """Extra opcional ([ml]/cbr) ou binario do sistema ausente."""
