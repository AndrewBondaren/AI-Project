"""Library-pack FS surface — plan library-packs-model.md step 3.

``manifest`` — typed ``pack.manifest.json`` loading and validation;
``defaults`` — the explicit declared default sources (TZ §6, no wildcard
scans); ``uidMap`` — the explicit old→new UID migration artifact;
``legacyPack`` — the world-owned ``legacy`` pack that receives bodies from
manifest-less bundle sections; ``packCatalog`` — manifest → catalog rows /
insert-missing attach.
"""
