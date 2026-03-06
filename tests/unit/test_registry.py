from francis_skills.registry import SkillRegistry


def test_registry_registers() -> None:
    reg = SkillRegistry()
    reg.register('disk', {'kind': 'probe'})
    assert reg.list() == ['disk']
