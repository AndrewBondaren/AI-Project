"""Runtime contracts of the error core (error-contracts-1 §3.9 C0-1…C0-5)."""

import unittest
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ValidationError

from app.dataModel.fields.checkedPath import CheckedPath, CheckedPathError
from app.dataModel.fields.fieldRef import FieldRef
from app.dataModel.fields.validatedFieldPath import (
    FieldSegment, IndexSegment, KeySegment, ModelIdentity, ValidatedFieldPath, VariantSegment,
)
from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError
from app.dataModel.validation.diagnostics.validatorAggregationHelper import (
    IssueAdmissionError, ValidatorAggregationHelper,
)


class Leaf(BaseModel):
    uid: str


class Cat(BaseModel):
    lives: int


class Dog(BaseModel):
    bark: str


class Root(BaseModel):
    name: str
    leaf: Leaf | None = None
    leaves: tuple[Leaf, ...] = ()
    pair: tuple[str, int] = ("a", 1)
    scores: dict[str, int] = {}
    pet: Cat | Dog = Cat(lives=9)
    labelled: Annotated[list[Leaf], "meta"] = []
    children: list[Annotated[Leaf, "meta"]] = []


class Code(StrEnum):
    MISSING = "missing"


class Foreign(StrEnum):
    MISSING = "missing"


class RootTypeError(FieldPathError[Code]):
    pass


class OtherTypeError(FieldPathError[Code]):
    pass


ROOT_NAME = FieldRef(lambda: Root, lambda pojo: pojo.name)
ROOT_LEAF = FieldRef(lambda: Root, lambda pojo: pojo.leaf)
ROOT_LEAVES = FieldRef(lambda: Root, lambda pojo: pojo.leaves)
ROOT_PAIR = FieldRef(lambda: Root, lambda pojo: pojo.pair)
ROOT_SCORES = FieldRef(lambda: Root, lambda pojo: pojo.scores)
ROOT_PET = FieldRef(lambda: Root, lambda pojo: pojo.pet)
ROOT_LABELLED = FieldRef(lambda: Root, lambda pojo: pojo.labelled)
ROOT_CHILDREN = FieldRef(lambda: Root, lambda pojo: pojo.children)
LEAF_UID = FieldRef(lambda: Leaf, lambda pojo: pojo.uid)
CAT_LIVES = FieldRef(lambda: Cat, lambda pojo: pojo.lives)


def _name_path() -> ValidatedFieldPath:
    return CheckedPath.root(Root).field(ROOT_NAME).freeze()


class CheckedPathTests(unittest.TestCase):
    def test_steps_freeze_into_typed_segments(self) -> None:
        path = CheckedPath.root(Root).field(ROOT_LEAVES).item(2).field(LEAF_UID).freeze()
        self.assertEqual(path.root, ModelIdentity.of(Root))
        self.assertEqual(path.segments, (
            FieldSegment(owner=ModelIdentity.of(Root), name="leaves"),
            IndexSegment(index=2),
            FieldSegment(owner=ModelIdentity.of(Leaf), name="uid"),
        ))
        self.assertEqual(path.projection(), ("leaves", 2, "uid"))

    def test_nullable_key_fixed_tuple_variant_and_annotated(self) -> None:
        root = CheckedPath.root(Root)
        self.assertEqual(root.field(ROOT_LEAF).present().field(LEAF_UID).freeze().projection(), ("leaf", "uid"))
        self.assertEqual(root.field(ROOT_SCORES).key("x").freeze().segments[-1], KeySegment(key="x"))
        self.assertEqual(root.field(ROOT_PAIR).item(1).freeze().projection(), ("pair", 1))
        pet = root.field(ROOT_PET).variant(Cat).field(CAT_LIVES).freeze()
        self.assertEqual(pet.segments[1], VariantSegment(branch=ModelIdentity.of(Cat)))
        self.assertEqual(pet.projection(), ("pet", "lives"))
        self.assertEqual(root.field(ROOT_LABELLED).item(0).field(LEAF_UID).freeze().projection(), ("labelled", 0, "uid"))

    def test_mismatched_steps_are_rejected(self) -> None:
        root = CheckedPath.root(Root)
        cases = [
            lambda: root.field(LEAF_UID),
            lambda: root.field(ROOT_LEAF).field(LEAF_UID),
            lambda: root.field(ROOT_NAME).present(),
            lambda: root.field(ROOT_SCORES).item(0),
            lambda: root.field(ROOT_NAME).key("a"),
            lambda: root.field(ROOT_PAIR).item(5),
            lambda: root.field(ROOT_PET).variant(Leaf),
            lambda: root.freeze(),
            lambda: root.field(ROOT_SCORES).key(4),
            lambda: root.field(ROOT_PAIR).item(-3),
            lambda: root.field(ROOT_LEAVES).item(-1),
        ]
        for case in cases:
            with self.subTest(case=case), self.assertRaises(CheckedPathError):
                case()  # type: ignore[call-arg]

    def test_pydantic_loc_resolution(self) -> None:
        with self.assertRaises(ValidationError) as caught:
            Root.model_validate({"name": "n", "leaves": [{"uid": "a"}, {}], "leaf": {}})
        resolved = {CheckedPath.from_pydantic_loc(Root, err["loc"]).projection() for err in caught.exception.errors()}  # type: ignore[union-attr]
        self.assertEqual(resolved, {("leaves", 1, "uid"), ("leaf", "uid")})
        self.assertIsNone(CheckedPath.from_pydantic_loc(Root, ("unknown",)))
        self.assertIsNone(CheckedPath.from_pydantic_loc(Root, ()))
        for loc in (("scores", 4), ("pair", -3), ("leaves", -1), ("pair", 7)):
            with self.subTest(loc=loc):
                self.assertIsNone(CheckedPath.from_pydantic_loc(Root, loc))

    def test_annotated_element_type_is_navigable(self) -> None:
        expected = ("children", 0, "uid")
        self.assertEqual(CheckedPath.root(Root).field(ROOT_CHILDREN).item(0).field(LEAF_UID).freeze().projection(), expected)
        self.assertEqual(CheckedPath.from_pydantic_loc(Root, expected).projection(), expected)  # type: ignore[union-attr]

    def test_validated_path_must_start_at_root_field(self) -> None:
        with self.assertRaises(ValidationError):
            ValidatedFieldPath(root=ModelIdentity.of(Root), segments=(IndexSegment(index=0),))
        with self.assertRaises(ValidationError):
            ValidatedFieldPath(root=ModelIdentity.of(Root),
                               segments=(FieldSegment(owner=ModelIdentity.of(Leaf), name="uid"),))
        with self.assertRaises(ValidationError):
            ValidatedFieldPath(root=ModelIdentity.of(Root), segments=())


class FieldPathErrorTests(unittest.TestCase):
    def test_concrete_subclass_admits_only_its_code(self) -> None:
        issue = RootTypeError(code=Code.MISSING, path=_name_path(), message="required")
        self.assertIs(issue.code, Code.MISSING)
        with self.assertRaises(ValidationError):
            RootTypeError(code=Foreign.MISSING, path=_name_path(), message="required")  # type: ignore[arg-type]
        with self.assertRaises(ValidationError):
            RootTypeError(code="missing", path=_name_path(), message="required")  # type: ignore[arg-type]

    def test_bare_or_parameterized_generic_is_rejected(self) -> None:
        for kind in (FieldPathError, FieldPathError[Code]):
            with self.subTest(kind=kind), self.assertRaises(TypeError):
                kind(code=Code.MISSING, path=_name_path(), message="x")

    def test_copy_bypass_is_rejected_by_strict_carrier(self) -> None:
        class Carrier(BaseModel):
            model_config = {"strict": True, "frozen": True, "revalidate_instances": "always"}
            issue: RootTypeError

        forged = RootTypeError(code=Code.MISSING, path=_name_path(), message="x").model_copy(
            update={"code": Foreign.MISSING})
        with self.assertRaises(ValidationError):
            Carrier(issue=forged)


class CollectorTests(unittest.TestCase):
    def test_exact_admission_order_and_failure(self) -> None:
        collector = ValidatorAggregationHelper((RootTypeError,))
        first = RootTypeError(code=Code.MISSING, path=_name_path(), message="a")
        second = RootTypeError(code=Code.MISSING, path=_name_path(), message="b")
        collector.add(first)
        collector.add(second)
        self.assertEqual(collector.snapshot(), (first, second))
        with self.assertRaises(IssueAdmissionError):
            collector.add(OtherTypeError(code=Code.MISSING, path=_name_path(), message="c"))  # type: ignore[arg-type]
        with self.assertRaises(LookupError) as caught:
            collector.raise_if_any(lambda issues: LookupError(issues))
        self.assertEqual(caught.exception.args[0], (first, second))

    def test_forged_code_is_not_admitted(self) -> None:
        collector = ValidatorAggregationHelper((RootTypeError,))
        forged = RootTypeError(code=Code.MISSING, path=_name_path(), message="a").model_copy(
            update={"code": Foreign.MISSING})
        with self.assertRaises(IssueAdmissionError):
            collector.add(forged)
        self.assertEqual(collector.snapshot(), ())

    def test_empty_collector_does_not_raise_and_needs_admitted_classes(self) -> None:
        ValidatorAggregationHelper((RootTypeError,)).raise_if_any(lambda issues: LookupError(issues))
        with self.assertRaises(IssueAdmissionError):
            ValidatorAggregationHelper(())


if __name__ == "__main__":
    unittest.main()
