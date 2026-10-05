"""Mask flags decide which ground-truth fields become observations."""

from dealos.macro_world.generator import world_authority, world_resource_role
from dealos.macro_world.models import ObservationMask
from dealos.macro_world.observations import leak_count, observe


def test_a_hidden_field_never_appears_and_an_exposed_field_matches() -> None:
    world = world_resource_role()
    hidden = ObservationMask()
    shown = ObservationMask(expose_role=True, expose_department=True)
    concealed = observe(world, hidden, 0)
    revealed = observe(world, shown, 0)
    assert concealed[0].get("role_id") is None
    assert revealed[0].get("role_id") == "role_legal_reviewer"
    assert revealed[0].get("department_id") == "dept_legal"
    assert leak_count(world, revealed, shown) == 0
    assert leak_count(world, concealed, hidden) == 0


def test_the_same_seed_and_mask_repeat_and_authority_follows_the_rule() -> None:
    world = world_authority()
    mask = ObservationMask(expose_authority=True)
    assert observe(world, mask, 4) == observe(world, mask, 4)
    rows = {row.get("resource_id"): row.get("authority") for row in observe(world, mask, 4)}
    assert rows["Fin_R1"] == "ApproveDeal"
    assert rows["Clerk_R2"] is None
