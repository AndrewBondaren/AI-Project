import unittest

from pydantic import BaseModel

from app.dataModel.fields.checkedPath import CheckedPath
from app.dataModel.fields.fieldRef import FieldRef
from app.dataModel.fields.validatedFieldPath import ModelIdentity, ModelIdentityError


class Box[T](BaseModel):
    value: T


class NamedBox(Box[int]):
    pass


class Container(BaseModel):
    choice: Box[int] | str


class ModelIdentityTests(unittest.TestCase):
    def test_owner_admission(self):
        for model in (Container, NamedBox):
            self.assertEqual(ModelIdentity.of(model), ModelIdentity(module=__name__, qualname=model.__name__))
            self.assertEqual(CheckedPath.from_pydantic_loc(model, (next(iter(model.model_fields)),)).root,
                             ModelIdentity.of(model))
        for model in (Box, Box[int], int, NamedBox(value=3)):
            with self.subTest(model=model), self.assertRaises(ModelIdentityError):
                ModelIdentity.of(model)
            with self.subTest(root=model), self.assertRaises(ModelIdentityError):
                CheckedPath.root(model)

    def test_field_owner_variant_and_loc_propagate_rejection(self):
        with self.assertRaises(ModelIdentityError):
            CheckedPath.root(NamedBox).field(FieldRef(lambda: Box[int], lambda box: box.value))
        with self.assertRaises(ModelIdentityError):
            CheckedPath.root(Container).field(FieldRef(lambda: Container, lambda c: c.choice)).variant(Box[int])
        with self.assertRaises(ModelIdentityError):
            CheckedPath.from_pydantic_loc(Container, ("choice", Box[int].__name__, "value"))
