from francis_forge.spec import CapabilitySpec


def test_forge_spec() -> None:
    spec = CapabilitySpec(name='x', description='y')
    assert spec.name == 'x'
