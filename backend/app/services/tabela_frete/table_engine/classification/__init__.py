"""Classificação de colunas, linhas e seções."""

from .column_classifier import ColumnClassifier, classify_columns

__all__ = [
    "ColumnClassifier",
    "classify_columns",
]
