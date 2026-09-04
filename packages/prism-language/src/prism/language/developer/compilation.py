# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Lower checked Prism modules into executable runtime IR."""

from __future__ import annotations

import hashlib
from typing import Any

from prism.language.core import CallableContract, CoreType, TypedModule
from prism.language.effects import Binary as IRBinary
from prism.language.effects import CallArgument as IRCallArgument
from prism.language.effects import CallExpression as IRCallExpression
from prism.language.effects import Conditional as IRConditional
from prism.language.effects import (
    ExecutableProgram,
    FunctionDefinition,
    RecordDefinition,
    ValueBinding,
)
from prism.language.effects import Execute as IRExecute
from prism.language.effects import Field as IRField
from prism.language.effects import Index as IRIndex
from prism.language.effects import ListValue as IRListValue
from prism.language.effects import Literal as IRLiteral
from prism.language.effects import MapValue as IRMapValue
from prism.language.effects import ReasoningInvocation as IRReasoningInvocation
from prism.language.effects import Reference as IRReference
from prism.language.effects import Return as IRReturn
from prism.language.effects import Solve as IRSolve
from prism.language.effects import Try as IRTry
from prism.language.effects import TupleValue as IRTupleValue
from prism.language.effects import Unary as IRUnary
from prism.language.evidence import MaterialInference as IRMaterialInference
from prism.language.workflows import Agent as IRAgent
from prism.language.workflows import Choice as IRChoice
from prism.language.workflows import ChoiceArm as IRChoiceArm
from prism.language.workflows import GuardedExit as IRGuardedExit
from prism.language.workflows import NodeOccurrence as IRNodeOccurrence
from prism.language.workflows import Parallel as IRParallel
from prism.language.workflows import ReasoningDefinition as IRReasoningDefinition
from prism.language.workflows import RelationDefinition as IRRelationDefinition
from prism.language.workflows import Repeat as IRRepeat
from prism.language.workflows import Sequence as IRSequence
from prism.language.workflows import Tool as IRTool
from prism.language.workflows import WorkflowDefinition as IRWorkflowDefinition

from .checking.helpers import (
    _expand_aliases,
    _expression_name,
    _expression_references,
)
from .syntax.ast import (
    AgentDecl,
    BinaryExpr,
    Binding,
    CallExpr,
    ChoiceComposition,
    ConditionalExpr,
    Exact,
    ExecuteExpr,
    Expression,
    ExpressionStatement,
    FieldExpr,
    FunctionDecl,
    IndexExpr,
    ListExpr,
    LiteralExpr,
    MapExpr,
    MaterialInferenceExpr,
    NameExpr,
    NodeOccurrence,
    ParallelComposition,
    ReasoningDecl,
    RelationDecl,
    RepeatComposition,
    Return,
    SequenceComposition,
    SolveExpr,
    TheoremDecl,
    ToolDecl,
    TryExpr,
    TupleExpr,
    UnaryExpr,
    WorkflowDecl,
)


def compile(module: TypedModule) -> ExecutableProgram:
    if not isinstance(module, TypedModule):
        raise TypeError("compile expects an elaborated TypedModule")
    definitions: list[Any] = []
    for name, record in module.record_contracts.items():
        definitions.append(
            RecordDefinition(
                name, tuple((field.name, field.type) for field in record.fields)
            )
        )
    local_binding_ids = {
        id(item) for item in module.declarations if isinstance(item, Binding)
    }
    for name, binding in module.globals.items():
        declaration = binding.value
        if not isinstance(declaration, Binding) or id(declaration) in local_binding_ids:
            continue
        definitions.append(
            _lower_binding(
                declaration,
                module,
                namespace=name.rpartition(".")[0] or None,
            )
        )
    local_tool_ids = {
        id(item) for item in module.declarations if isinstance(item, ToolDecl)
    }
    for name, binding in module.globals.items():
        declaration = binding.value
        if not isinstance(declaration, ToolDecl) or id(declaration) in local_tool_ids:
            continue
        definitions.append(
            IRTool(
                name,
                binding.type.arguments[0],
                _lower_expression(
                    declaration.callable,
                    module,
                    namespace=name.rpartition(".")[0] or None,
                ),
            )
        )
    for name, contract in module.callable_contracts.items():
        binding = module.globals.get(name)
        declaration = binding.value if binding else None
        if not isinstance(
            declaration,
            FunctionDecl
            | WorkflowDecl
            | ReasoningDecl
            | RelationDecl
            | TheoremDecl
            | AgentDecl,
        ):
            continue
        definitions.append(_lower_callable(name, contract, declaration, module))
    for declaration in module.declarations:
        if isinstance(declaration, Binding):
            definitions.append(_lower_binding(declaration, module))
        elif isinstance(declaration, ToolDecl):
            definitions.append(
                IRTool(
                    declaration.name,
                    module.globals[declaration.name].type.arguments[0],
                    _lower_expression(declaration.callable, module),
                )
            )
    functions = [item for item in definitions if isinstance(item, FunctionDefinition)]
    entry = next(
        (item.name for item in functions if item.name == "main" and item.kind == "def"),
        None,
    )
    return ExecutableProgram(
        path=module.path,
        source_hash=hashlib.sha256(module.source.encode()).hexdigest(),
        declarations=tuple(definitions),
        entry_callable=entry,
        module_hashes=module.module_hashes,
        aliases=module.aliases,
        variants=module.variants,
        checked_module=module.checked_module,
    )


def _lower_callable(
    name: str,
    contract: CallableContract,
    declaration: (
        FunctionDecl
        | WorkflowDecl
        | ReasoningDecl
        | RelationDecl
        | TheoremDecl
        | AgentDecl
    ),
    module: TypedModule,
) -> Any:
    # Qualified imported declarations need their source-module namespace so
    # unqualified private references remain local to that module. Authored
    # declaration names are simple identifiers; dots only arise here through
    # module qualification.
    namespace = (
        name.rpartition(".")[0] or None
        if all(declaration is not item for item in module.declarations)
        else None
    )
    if isinstance(declaration, TheoremDecl):
        exact = next(item for item in declaration.body if isinstance(item, Exact))
        return FunctionDefinition(
            name,
            tuple((item.name, item.type) for item in contract.parameters),
            contract.result,
            (),
            (IRReturn(_lower_expression(exact.proof, module, namespace=namespace)),),
            "theorem",
        )
    if isinstance(declaration, ReasoningDecl):
        return _lower_reasoning(name, declaration, contract, module, namespace)
    if isinstance(declaration, RelationDecl):
        return IRRelationDefinition(
            name,
            tuple((item.name, item.type) for item in contract.parameters),
            contract.result,
            contract.type_parameters,
            module.callable_origins.get(name),
        )
    if isinstance(declaration, WorkflowDecl):
        return IRWorkflowDefinition(
            name,
            tuple((item.name, item.type) for item in contract.parameters),
            contract.result,
            contract.failure or CoreType("Never"),
            contract.effects,
            _lower_composition(declaration.composition, module, namespace=namespace),
            declaration.result_alias,
        )
    if isinstance(declaration, AgentDecl):
        capabilities = {item.name: item for item in declaration.capabilities}
        return IRAgent(
            name,
            tuple((item.name, item.type) for item in contract.parameters),
            contract.result,
            contract.effects,
            *(
                (
                    _lower_expression(
                        capabilities[key].value, module, namespace=namespace
                    )
                    if key in capabilities
                    else None
                )
                for key in ("tools", "skills", "hooks")
            ),
        )
    body = tuple(
        _lower_statement(item, module, namespace=namespace) for item in declaration.body
    )
    return FunctionDefinition(
        name,
        tuple((item.name, item.type) for item in contract.parameters),
        contract.result,
        contract.effects,
        body,
        "proposition" if declaration.is_proposition_declaration else "def",
    )


def _lower_reasoning(
    name: str,
    declaration: ReasoningDecl,
    contract: CallableContract,
    module: TypedModule,
    namespace: str | None,
) -> IRReasoningDefinition:
    return IRReasoningDefinition(
        name,
        tuple((item.name, item.type) for item in contract.parameters),
        contract.result,
        _lower_composition(declaration.composition, module, namespace=namespace),
        tuple(
            IRGuardedExit(
                item.occurrence,
                item.selector,
                item.action,
                (
                    f"{namespace}.{item.target}"
                    if namespace and item.target and "." not in item.target
                    else item.target
                ),
            )
            for item in declaration.exits
        ),
        declaration.result_alias,
    )


def _lower_composition(
    composition: Any,
    module: TypedModule,
    *,
    namespace: str | None = None,
) -> Any:
    if isinstance(composition, NodeOccurrence):
        relation_type = module.expression_types.get(id(composition))
        method_type = (
            module.expression_types.get(id(composition.component.callee))
            if isinstance(composition.component, CallExpr)
            else None
        )
        logical_input = (
            composition.component.arguments[0].value
            if isinstance(composition.component, CallExpr)
            and len(composition.component.arguments) == 1
            else None
        )
        return IRNodeOccurrence(
            _lower_expression(composition.component, module, namespace=namespace),
            composition.alias,
            composition.relation,
            tuple(
                ref
                for argument in (
                    composition.component.arguments
                    if isinstance(composition.component, CallExpr)
                    else ()
                )
                for ref in _expression_references(argument.value)
            ),
            (
                _lower_expression(logical_input, module, namespace=namespace)
                if logical_input is not None
                else None
            ),
            (
                IRReference(f"{composition.alias}_input")
                if composition.alias
                and logical_input is not None
                and method_type is not None
                and method_type.parameters
                and _expand_aliases(
                    module.expression_types[id(logical_input)],
                    module.aliases,
                    module.type_parameters,
                )
                != _expand_aliases(
                    method_type.parameters[0][1],
                    module.aliases,
                    module.type_parameters,
                )
                else None
            ),
            (method_type),
            (
                module.expression_types.get(id(logical_input))
                if logical_input is not None
                else None
            ),
            (
                method_type.parameters[0][1]
                if method_type is not None and method_type.parameters
                else None
            ),
            module.expression_types.get(id(composition.component)),
            relation_type,
            (
                relation_type.arguments[3]
                if relation_type is not None
                and relation_type.name == "Relation"
                and len(relation_type.arguments) == 4
                else None
            ),
        )
    if isinstance(composition, SequenceComposition):
        return IRSequence(
            tuple(
                _lower_composition(item, module, namespace=namespace)
                for item in composition.children
            ),
            composition.relation,
        )
    if isinstance(composition, ParallelComposition):
        return IRParallel(
            tuple(
                _lower_composition(item, module, namespace=namespace)
                for item in composition.children
            ),
            composition.relation,
        )
    if isinstance(composition, ChoiceComposition):
        return IRChoice(
            _lower_composition(composition.router, module, namespace=namespace),
            tuple(
                IRChoiceArm(
                    arm.pattern,
                    tuple(
                        _lower_composition(item, module, namespace=namespace)
                        for item in arm.children
                    ),
                )
                for arm in composition.arms
            ),
            composition.relation,
        )
    if isinstance(composition, RepeatComposition):
        return IRRepeat(
            _lower_expression(composition.policy, module, namespace=namespace),
            tuple(
                _lower_composition(item, module, namespace=namespace)
                for item in composition.children
            ),
            composition.relation,
            (
                _lower_expression(composition.until, module, namespace=namespace)
                if composition.until is not None
                else None
            ),
        )
    raise TypeError(f"cannot lower composition `{type(composition).__name__}`")


def _lower_statement(
    statement: Any,
    module: TypedModule,
    *,
    namespace: str | None = None,
) -> Any:
    if isinstance(statement, Binding):
        return _lower_binding(statement, module, namespace=namespace)
    if isinstance(statement, Return):
        return IRReturn(_lower_expression(statement.value, module, namespace=namespace))
    if isinstance(statement, ExpressionStatement):
        return _lower_expression(statement.value, module, namespace=namespace)
    raise TypeError(f"cannot lower statement `{type(statement).__name__}`")


def _lower_binding(
    binding: Binding,
    module: TypedModule,
    *,
    namespace: str | None = None,
) -> Any:
    return ValueBinding(
        binding.name,
        _lower_expression(binding.value, module, namespace=namespace),
        module.expression_types[id(binding.value)],
    )


def _lower_expression(
    expression: Expression,
    module: TypedModule,
    *,
    namespace: str | None = None,
) -> Any:
    if isinstance(expression, LiteralExpr):
        return IRLiteral(expression.value)
    if isinstance(expression, NameExpr):
        qualified = (
            f"{namespace}.{expression.name}"
            if namespace and "." not in expression.name
            else None
        )
        if qualified and (
            qualified in module.callable_contracts
            or qualified in module.record_contracts
            or (
                qualified in module.globals
                and isinstance(module.globals[qualified].value, AgentDecl | Binding)
            )
        ):
            return IRReference(qualified)
        return IRReference(expression.name)
    if isinstance(expression, ListExpr):
        return IRListValue(
            tuple(
                _lower_expression(item, module, namespace=namespace)
                for item in expression.items
            )
        )
    if isinstance(expression, TupleExpr):
        return IRTupleValue(
            tuple(
                _lower_expression(item, module, namespace=namespace)
                for item in expression.items
            )
        )
    if isinstance(expression, MapExpr):
        return IRMapValue(
            tuple(
                (
                    _lower_expression(key, module, namespace=namespace),
                    _lower_expression(value, module, namespace=namespace),
                )
                for key, value in expression.items
            )
        )
    if isinstance(expression, FieldExpr):
        qualified = _expression_name(expression)
        if (
            qualified in module.callable_contracts
            or qualified in module.record_contracts
            or (
                qualified in module.globals
                and isinstance(module.globals[qualified].value, AgentDecl | Binding)
            )
        ):
            return IRReference(qualified)
        return IRField(
            _lower_expression(expression.value, module, namespace=namespace),
            expression.field,
        )
    if isinstance(expression, CallExpr):
        return IRCallExpression(
            _lower_expression(expression.callee, module, namespace=namespace),
            tuple(
                IRCallArgument(
                    _lower_expression(item.value, module, namespace=namespace),
                    item.name,
                )
                for item in expression.arguments
            ),
            module.expression_types[id(expression)],
            module.expression_terms.get(id(expression)),
        )
    if isinstance(expression, ConditionalExpr):
        return IRConditional(
            _lower_expression(expression.condition, module, namespace=namespace),
            _lower_expression(expression.when_true, module, namespace=namespace),
            _lower_expression(expression.when_false, module, namespace=namespace),
        )
    if isinstance(expression, IndexExpr):
        return IRIndex(
            _lower_expression(expression.value, module, namespace=namespace),
            _lower_expression(expression.index, module, namespace=namespace),
        )
    if isinstance(expression, TryExpr):
        return IRTry(_lower_expression(expression.value, module, namespace=namespace))
    if isinstance(expression, SolveExpr):
        return IRSolve(
            _lower_reasoning_invocation(
                expression.reasoning, module, namespace=namespace
            ),
            _lower_expression(expression.workflow, module, namespace=namespace),
        )
    if isinstance(expression, ExecuteExpr):
        return IRExecute(
            _lower_reasoning_invocation(
                expression.reasoning, module, namespace=namespace
            ),
            _lower_expression(expression.workflow, module, namespace=namespace),
        )
    if isinstance(expression, MaterialInferenceExpr):
        return IRMaterialInference(
            _lower_expression(expression.evidence, module, namespace=namespace),
            _expression_name(expression.policy),
            _lower_expression(expression.proposition, module, namespace=namespace),
        )
    if isinstance(expression, UnaryExpr):
        return IRUnary(
            expression.operator,
            _lower_expression(expression.operand, module, namespace=namespace),
        )
    if isinstance(expression, BinaryExpr):
        return IRBinary(
            _lower_expression(expression.left, module, namespace=namespace),
            expression.operator,
            _lower_expression(expression.right, module, namespace=namespace),
        )
    raise TypeError(f"cannot lower expression `{type(expression).__name__}`")


def _lower_reasoning_invocation(
    expression: Expression | None,
    module: TypedModule,
    *,
    namespace: str | None,
) -> IRReasoningInvocation | None:
    if expression is None:
        return None
    if not isinstance(expression, CallExpr):
        raise TypeError("checked reasoning invocation is not a call")
    return IRReasoningInvocation(
        _lower_expression(expression.callee, module, namespace=namespace),
        tuple(
            IRCallArgument(
                _lower_expression(argument.value, module, namespace=namespace),
                argument.name,
            )
            for argument in expression.arguments
        ),
    )
