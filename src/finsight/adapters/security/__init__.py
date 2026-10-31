"""Security adapters."""

from __future__ import annotations

from .virus_scanner import VirusScanner

# Backwards-friendly aliases.
VirusScannerAdapter = VirusScanner
AwsVirusScanner = VirusScanner
AWSVirusScanner = VirusScanner
ClamAVScanner = VirusScanner
ClamAvScanner = VirusScanner
MalwareScanner = VirusScanner
SecurityScanner = VirusScanner
Scanner = VirusScanner
DefaultVirusScanner = VirusScanner
VirusScanAdapter = VirusScanner

__all__ = [
    'AWSVirusScanner',
    'AwsVirusScanner',
    'ClamAVScanner',
    'ClamAvScanner',
    'DefaultVirusScanner',
    'MalwareScanner',
    'Scanner',
    'SecurityScanner',
    'VirusScanAdapter',
    'VirusScanner',
    'VirusScannerAdapter',
]
