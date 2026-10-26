"""Persisted provenance and computed display status are separate concerns."""
from app.application.templateLibrary.packs.lifecycleContracts import MemberStatus


async def member_status(scope, member):
    if member.source_template_uid is None:
        return MemberStatus(member.template_uid, 'authored')
    source = await scope.members.get_by_uid(member.source_template_uid)
    if member.creation_kind == 'member_copy':
        return MemberStatus(member.template_uid, 'member copy' if source else 'source deleted')
    pack = await scope.packs.get_by_uid(member.pack_uid)
    source_pack = await scope.packs.get_by_uid(pack.source_pack_uid) if pack and pack.source_pack_uid else None
    if source_pack is None:
        return MemberStatus(member.template_uid, 'source deleted')
    if source is None:
        return MemberStatus(member.template_uid, 'held by use')
    if source.pack_uid != source_pack.pack_uid:
        return MemberStatus(member.template_uid, 'provenance mismatch',
                            ('source member belongs to a different pack',))
    return MemberStatus(member.template_uid, 'pack copy')
