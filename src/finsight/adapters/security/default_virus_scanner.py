"""Alias module for the virus scanner adapter."""

from __future__ import annotations

from .virus_scanner import VirusScanner as DefaultVirusScanner

__all__ = ['DefaultVirusScanner']
