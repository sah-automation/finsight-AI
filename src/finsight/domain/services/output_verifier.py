from .output_gate import (
    OutputGate as OutputVerifier,
)
from .output_gate import (
    OutputVerificationResult,
    verify_output,
)

__all__ = ['OutputVerificationResult', 'OutputVerifier', 'verify_output']
# Make OutputGate available under OutputVerificationService too
OutputVerificationService = OutputVerifier
# add OutputGate alias

__all__.append('OutputGate')
__all__.append('OutputVerificationService')
