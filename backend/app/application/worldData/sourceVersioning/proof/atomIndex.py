"""Enumerate exact atoms of a proof already admitted as canonical by the caller."""

from app.dataModel.sourceVersioning.sourceCaptureUsage import SourceCaptureUsage
from app.dataModel.sourceVersioning.sourceDependencies import SourceDependencySet
from app.dataModel.sourceVersioning.sourceDurableProof import SourceDurableProof


class SourceProofAtomIndex:
    def enumerate(self, proof: SourceDurableProof) -> tuple[SourceCaptureUsage, ...]:
        atoms: list[SourceCaptureUsage] = []
        for use in proof.uses:
            for source in use.dependencies.objects:
                atoms.append(SourceCaptureUsage(capture=use.capture,
                    dependencies=SourceDependencySet(objects=(source,), collections=())))
            for source in use.dependencies.collections:
                atoms.append(SourceCaptureUsage(capture=use.capture,
                    dependencies=SourceDependencySet(objects=(), collections=(source,))))
        return tuple(atoms)
