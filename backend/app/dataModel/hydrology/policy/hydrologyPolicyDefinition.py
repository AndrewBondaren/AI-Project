"""Generation cases over resolved cascade inputs; no local gate or resolver."""

from app.dataModel.cascade.cascadeSpec import FieldRef
from app.dataModel.hydrology.enums.planning.hydrologyExecutionMode import HydrologyExecutionMode as Mode
from app.dataModel.hydrology.generation.generationContext import WaterGenerationContext
from app.dataModel.hydrology.generation.waterGenerationSettings import WorldHydrologyGenerationFields
from app.dataModel.hydrology.policy.hydrologyGenerationDecision import WaterPolicyReason
from app.dataModel.policy.objectAdmissionPolicyDefinition import EnabledGate, ObjectAdmissionPolicyDefinition
from app.dataModel.policy.policyEnums import PolicyOperation, PolicyRuleId, PolicyStage, RulePrecedence
from app.dataModel.policy.policyReferences import DirectValueRef
from app.dataModel.policy.policyRules import Equal, PolicyRule, SelectBehaviorEffect
from app.dataModel.policy.policySpec import ValueSelectionPolicySpec


_ENABLED = DirectValueRef(FieldRef(lambda: WorldHydrologyGenerationFields, lambda h: h.enabled))
_AUTORESOLVE = DirectValueRef(FieldRef(lambda: WaterGenerationContext, lambda c: c.autoresolve))


class HydrologyPolicyDefinition:
    @staticmethod
    def generation() -> ValueSelectionPolicySpec[Mode, WaterPolicyReason]:
        return ObjectAdmissionPolicyDefinition.bind_value_selection(
            ValueSelectionPolicySpec[Mode, WaterPolicyReason](
                operation=PolicyOperation.VALUE_SELECTION, expected_behavior_type=Mode,
                disabled_behavior=Mode.DISABLED, fallback_rules=(), rules=(
                    PolicyRule(id=PolicyRuleId("hydrology.generation.declared_only"),
                        stage=PolicyStage.BEHAVIOR, precedence=RulePrecedence(0),
                        conditions=(Equal(_AUTORESOLVE, False),),
                        effect=SelectBehaviorEffect(Mode.DECLARED_ONLY), domain_reason=WaterPolicyReason.DECLARED_ONLY),
                    PolicyRule(id=PolicyRuleId("hydrology.generation.autoresolve"),
                        stage=PolicyStage.BEHAVIOR, precedence=RulePrecedence(0),
                        conditions=(Equal(_AUTORESOLVE, True),),
                        effect=SelectBehaviorEffect(Mode.AUTORESOLVE), domain_reason=WaterPolicyReason.AUTORESOLVE),
                )), enabled_gates=(EnabledGate(_ENABLED),))
