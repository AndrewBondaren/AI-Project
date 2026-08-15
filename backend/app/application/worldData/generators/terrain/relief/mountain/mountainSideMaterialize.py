"""Materialize mountain sides from side_recipe (R33)."""

from __future__ import annotations

from app.application.worldData.generators.terrain.relief.pick.kindRoll import kind_roll
from app.application.worldData.generators.terrain.relief.log.log import relief_info
from app.dataModel.terrain.relief.enums import MountainSideRecipeMode, ReliefContext, ReliefSideKind
from app.dataModel.terrain.relief.mountainSideRecipe import MountainSideRecipe
from app.dataModel.terrain.relief.specs import ReliefSideSpec


def materialize_kinds(
    *,
    n: int,
    recipe: MountainSideRecipe | None,
    world_seed: str,
    template_uid: str,
    mountain_id: str,
) -> list[ReliefSideKind]:
    mode = recipe.detect_mode() if recipe else MountainSideRecipeMode.EMPTY
    if mode == MountainSideRecipeMode.FIXED:
        assert recipe is not None and recipe.default_side_kind is not None
        kinds = [recipe.default_side_kind] * n
    elif mode == MountainSideRecipeMode.PATTERN:
        assert recipe is not None and recipe.side_kinds
        pattern = list(recipe.side_kinds)
        kinds = [pattern[i % len(pattern)] for i in range(n)]
    elif mode == MountainSideRecipeMode.WEIGHTS:
        assert recipe is not None
        kinds = [
            kind_roll(
                world_seed=world_seed,
                context=ReliefContext.MOUNTAIN.value,
                template_uid=template_uid,
                site_id=mountain_id,
                slope_weight=float(recipe.slope_weight),  # type: ignore[arg-type]
                sheer_weight=float(recipe.sheer_weight),  # type: ignore[arg-type]
                side_index=i,
            )
            for i in range(n)
        ]
    else:
        # Mode D — empty recipe on a live mountain template
        sw = MountainSideRecipe.EMPTY_SLOPE_WEIGHT
        hw = MountainSideRecipe.EMPTY_SHEER_WEIGHT
        kinds = [
            kind_roll(
                world_seed=world_seed,
                context=ReliefContext.MOUNTAIN.value,
                template_uid=template_uid,
                site_id=mountain_id,
                slope_weight=sw,
                sheer_weight=hw,
                side_index=i,
            )
            for i in range(n)
        ]
    relief_info(
        "mountain_sides",
        template_uid=template_uid,
        recipe_mode=mode.log_label(),
        N=n,
        kinds=",".join(k.value for k in kinds),
    )
    return kinds


def resolve_sides_with_declare(
    *,
    n: int,
    recipe: MountainSideRecipe | None,
    world_seed: str,
    template_uid: str,
    mountain_id: str,
    declare_sides: list[ReliefSideSpec],
) -> list[ReliefSideSpec]:
    """Non-empty declare wins; empty → materialize from recipe (R33)."""
    if declare_sides:
        relief_info(
            "mountain_sides",
            template_uid=template_uid,
            recipe_mode="declare",
            override="declare",
            N=len(declare_sides),
            kinds=",".join(s.kind.value for s in declare_sides),
        )
        return list(declare_sides)

    kinds = materialize_kinds(
        n=n,
        recipe=recipe,
        world_seed=world_seed,
        template_uid=template_uid,
        mountain_id=mountain_id,
    )
    return [ReliefSideSpec(kind=k) for k in kinds]
