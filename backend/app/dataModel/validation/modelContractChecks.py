"""Shared typed inspection of Pydantic model configuration and validators."""

from inspect import ismethod

from pydantic import BaseModel, ConfigDict


class ModelContractChecks:
    """Pure construction checks; no model instantiation or domain validation."""

    @staticmethod
    def same_validation_config(actual: ConfigDict, expected: ConfigDict) -> bool:
        return (
            actual.get("strict") == expected.get("strict")
            and actual.get("frozen") == expected.get("frozen")
            and actual.get("extra") == expected.get("extra")
            and actual.get("revalidate_instances") == expected.get("revalidate_instances")
        )

    @staticmethod
    def same_validators(actual: type[BaseModel], expected: type[BaseModel]) -> bool:
        actual_info = actual.__pydantic_decorators__
        expected_info = expected.__pydantic_decorators__
        for actual_group, expected_group in (
            (actual_info.validators, expected_info.validators),
            (actual_info.field_validators, expected_info.field_validators),
            (actual_info.root_validators, expected_info.root_validators),
            (actual_info.model_validators, expected_info.model_validators),
        ):
            if actual_group.keys() != expected_group.keys():
                return False
            for name, decorator in actual_group.items():
                if decorator.info != expected_group[name].info:
                    return False
                actual_func = decorator.func
                expected_func = expected_group[name].func
                if ismethod(actual_func):
                    actual_func = actual_func.__func__
                if ismethod(expected_func):
                    expected_func = expected_func.__func__
                if actual_func is not expected_func:
                    return False
        return True
