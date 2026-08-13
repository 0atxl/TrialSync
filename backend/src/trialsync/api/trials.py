from __future__ import annotations

import uuid
from decimal import Decimal

from fastapi import APIRouter, Response, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload
from sqlalchemy.orm.interfaces import LoaderOption

from trialsync.api.deps import CurrentUser, SessionDep
from trialsync.api.errors import ApplicationError
from trialsync.db.models import Criterion, FactType, Trial, TrialVersion, VersionStatus
from trialsync.domain.rules import (
    RuleValidationIssue,
    validate_rule,
)
from trialsync.patient_data import PatientFactInputKind
from trialsync.patient_data.catalog import (
    active_catalog_entries,
    active_catalog_entry_by_key,
    rule_fact_specs,
)
from trialsync.schemas import (
    CriterionCreate,
    CriterionRead,
    GuidedCriterionCreate,
    TrialCreate,
    TrialRead,
    TrialUpdate,
    UnsupportedCriterionCreate,
    VersionCreate,
    VersionRead,
)

router = APIRouter(prefix="/api/v1/trials", tags=["trials"])


def criterion_value_error(message: str, field: str) -> ApplicationError:
    return ApplicationError(
        code="TRIAL_CRITERION_VALUE_INVALID",
        message=message,
        status_code=422,
        field=field,
    )


def display_number(value: Decimal) -> str:
    return format(value, "f").rstrip("0").rstrip(".")


def json_number(value: Decimal) -> int | float:
    return int(value) if value == value.to_integral_value() else float(value)


def _rule_error_details(
    issues: tuple[RuleValidationIssue, ...],
    *,
    criterion: Criterion | None = None,
) -> list[dict[str, object]]:
    return [
        {
            "criterion_id": str(criterion.id) if criterion is not None else None,
            "criterion_order": criterion.order if criterion is not None else None,
            "code": issue.code,
            "path": issue.path,
            "message": issue.message,
        }
        for issue in issues
    ]


async def validate_rule_for_session(
    session: SessionDep,
    expression: object,
    *,
    criterion: Criterion | None = None,
) -> None:
    entries = await active_catalog_entries(session)
    issues = validate_rule(expression, fact_specs=rule_fact_specs(entries))
    if not issues:
        return
    prefix = f"Criterion {criterion.order}: " if criterion is not None else "Criterion: "
    raise ApplicationError(
        code="TRIAL_RULE_INVALID",
        message=prefix + issues[0].message,
        status_code=422,
        field=(f"criteria.{criterion.order}.normalized_rule" if criterion else "normalized_rule"),
        details=_rule_error_details(issues, criterion=criterion),
    )


async def guided_criterion_values(
    session: SessionDep,
    payload: GuidedCriterionCreate,
) -> tuple[str, dict[str, object]]:
    if payload.subject_key == "age":
        if payload.operator not in {"gte", "lte", "between"}:
            raise criterion_value_error(
                "Age supports minimum, maximum, or range criteria.",
                "operator",
            )
        if payload.operator == "between":
            if (
                payload.minimum is None
                or payload.maximum is None
                or payload.minimum > payload.maximum
            ):
                raise criterion_value_error(
                    "Enter an age range with the minimum at or below the maximum.",
                    "minimum",
                )
            minimum = display_number(payload.minimum)
            maximum = display_number(payload.maximum)
            return (
                f"Age between {minimum} and {maximum} years",
                {
                    "op": "between",
                    "fact": "demographic.age",
                    "min": json_number(payload.minimum),
                    "max": json_number(payload.maximum),
                    "unit": "year",
                },
            )
        if payload.value is None:
            raise criterion_value_error("Enter an age value.", "value")
        value = display_number(payload.value)
        label = "at least" if payload.operator == "gte" else "at most"
        return (
            f"Age {label} {value} years",
            {
                "op": payload.operator,
                "fact": "demographic.age",
                "value": json_number(payload.value),
                "unit": "year",
            },
        )

    if payload.subject_key == "biological_sex":
        if payload.operator != "is" or payload.biological_sex is None:
            raise criterion_value_error(
                "Choose Male or Female for the biological-sex criterion.",
                "biological_sex",
            )
        label = payload.biological_sex.value.capitalize()
        return (
            f"Biological sex is {label}",
            {
                "op": "concept_is",
                "fact_type": "demographic",
                "concept": payload.biological_sex.value,
            },
        )

    entry = await active_catalog_entry_by_key(session, payload.subject_key)
    if entry is None:
        raise criterion_value_error(
            "Choose a supported criterion from the catalog.",
            "subject_key",
        )
    if not entry.screening_supported:
        raise criterion_value_error(
            f"{entry.display_label} is available for patient records but not trial screening.",
            "subject_key",
        )
    fact = f"{entry.fact_type.value}.{entry.concept}"
    if entry.input_kind is not PatientFactInputKind.numeric:
        if payload.operator not in {"present", "absent"}:
            raise criterion_value_error(
                f"{entry.display_label} supports present or absent criteria.",
                "operator",
            )
        wording = "is present" if payload.operator == "present" else "is absent"
        return (
            f"{entry.display_label} {wording}",
            {"op": payload.operator, "fact": fact},
        )

    if entry.fact_type is not FactType.observation:
        raise criterion_value_error("Numeric criteria must use an observation.", "subject_key")
    if payload.operator not in {"gte", "lte", "between"}:
        raise criterion_value_error(
            f"{entry.display_label} supports minimum, maximum, or range criteria.",
            "operator",
        )
    unit = entry.fixed_unit or entry.allowed_units[0]
    if payload.operator == "between":
        if (
            payload.minimum is None
            or payload.maximum is None
            or payload.minimum > payload.maximum
        ):
            raise criterion_value_error(
                "Enter a range with the minimum at or below the maximum.",
                "minimum",
            )
        minimum = display_number(payload.minimum)
        maximum = display_number(payload.maximum)
        return (
            f"{entry.display_label} between {minimum} and {maximum} {unit}",
            {
                "op": "between",
                "fact": fact,
                "min": json_number(payload.minimum),
                "max": json_number(payload.maximum),
                "unit": unit,
                "selection": "latest",
            },
        )
    if payload.value is None:
        raise criterion_value_error("Enter a numeric threshold.", "value")
    value = display_number(payload.value)
    label = "at least" if payload.operator == "gte" else "at most"
    return (
        f"{entry.display_label} {label} {value} {unit}",
        {
            "op": payload.operator,
            "fact": fact,
            "value": json_number(payload.value),
            "unit": unit,
            "selection": "latest",
        },
    )


def trial_options() -> LoaderOption:
    return selectinload(Trial.versions).selectinload(TrialVersion.criteria)


async def owned_trial(session: SessionDep, user: CurrentUser, trial_id: uuid.UUID) -> Trial:
    trial = await session.scalar(
        select(Trial)
        .options(trial_options())
        .where(Trial.id == trial_id, Trial.owner_id == user.id)
    )
    if trial is None:
        raise ApplicationError(
            code="TRIAL_NOT_FOUND", message="Trial was not found.", status_code=404
        )
    return trial


async def owned_version(
    session: SessionDep, user: CurrentUser, trial_id: uuid.UUID, version_id: uuid.UUID
) -> TrialVersion:
    await owned_trial(session, user, trial_id)
    version = await session.scalar(
        select(TrialVersion)
        .options(selectinload(TrialVersion.criteria))
        .where(TrialVersion.id == version_id, TrialVersion.trial_id == trial_id)
    )
    if version is None:
        raise ApplicationError(
            code="TRIAL_VERSION_NOT_FOUND", message="Trial version was not found.", status_code=404
        )
    return version


def require_draft(version: TrialVersion) -> None:
    if version.status is not VersionStatus.draft:
        raise ApplicationError(
            code="APPROVED_VERSION_IMMUTABLE",
            message="Approved trial versions cannot be changed.",
            status_code=409,
        )


async def require_approvable(session: SessionDep, version: TrialVersion) -> None:
    if not version.criteria:
        raise ApplicationError(
            code="TRIAL_VERSION_REVIEW_INCOMPLETE",
            message="Add at least one reviewed criterion before approval.",
            status_code=422,
        )
    if any(
        not isinstance(criterion.normalized_rule, dict) or not criterion.normalized_rule
        for criterion in version.criteria
    ):
        raise ApplicationError(
            code="TRIAL_VERSION_REVIEW_INCOMPLETE",
            message="Every criterion needs a deterministic rule before approval.",
            status_code=422,
        )
    entries = await active_catalog_entries(session)
    fact_specs = rule_fact_specs(entries)
    invalid: list[tuple[Criterion, tuple[RuleValidationIssue, ...]]] = []
    for criterion in version.criteria:
        issues = validate_rule(criterion.normalized_rule, fact_specs=fact_specs)
        if issues:
            invalid.append((criterion, issues))
    if invalid:
        criterion, issues = invalid[0]
        raise ApplicationError(
            code="TRIAL_RULE_INVALID",
            message=f"Criterion {criterion.order}: {issues[0].message}",
            status_code=422,
            field=f"criteria.{criterion.order}.normalized_rule",
            details=[
                detail
                for item, item_issues in invalid
                for detail in _rule_error_details(item_issues, criterion=item)
            ],
        )


@router.get("", response_model=list[TrialRead])
async def list_trials(session: SessionDep, user: CurrentUser) -> list[Trial]:
    result = await session.scalars(
        select(Trial)
        .options(trial_options())
        .where(Trial.owner_id == user.id)
        .order_by(Trial.updated_at.desc())
        .limit(100)
    )
    return list(result.unique())


@router.post("", response_model=TrialRead, status_code=status.HTTP_201_CREATED)
async def create_trial(payload: TrialCreate, session: SessionDep, user: CurrentUser) -> Trial:
    trial = Trial(
        owner_id=user.id,
        registry_id=payload.registry_id or f"SYN-TRIAL-{uuid.uuid4().hex[:10].upper()}",
        title=payload.title,
        condition=payload.condition,
        phase=payload.phase,
    )
    session.add(trial)
    try:
        await session.commit()
    except IntegrityError as exception:
        await session.rollback()
        raise ApplicationError(
            code="TRIAL_REGISTRY_ID_EXISTS",
            message="This registry ID is already in use.",
            status_code=409,
            field="registry_id",
        ) from exception
    return await owned_trial(session, user, trial.id)


@router.get("/{trial_id}", response_model=TrialRead)
async def get_trial(trial_id: uuid.UUID, session: SessionDep, user: CurrentUser) -> Trial:
    return await owned_trial(session, user, trial_id)


@router.patch("/{trial_id}", response_model=TrialRead)
async def update_trial(
    payload: TrialUpdate, trial_id: uuid.UUID, session: SessionDep, user: CurrentUser
) -> Trial:
    trial = await owned_trial(session, user, trial_id)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(trial, key, value)
    try:
        await session.commit()
    except IntegrityError as exception:
        await session.rollback()
        raise ApplicationError(
            code="TRIAL_REGISTRY_ID_EXISTS",
            message="This registry ID is already in use.",
            status_code=409,
            field="registry_id",
        ) from exception
    return await owned_trial(session, user, trial.id)


@router.delete("/{trial_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_trial(trial_id: uuid.UUID, session: SessionDep, user: CurrentUser) -> Response:
    trial = await owned_trial(session, user, trial_id)
    await session.delete(trial)
    try:
        await session.commit()
    except IntegrityError as exception:
        await session.rollback()
        raise ApplicationError(
            code="TRIAL_HAS_SCREENING_HISTORY",
            message="Trials used by saved screenings cannot be deleted.",
            status_code=409,
        ) from exception
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{trial_id}/versions", response_model=VersionRead, status_code=status.HTTP_201_CREATED
)
async def create_version(
    payload: VersionCreate, trial_id: uuid.UUID, session: SessionDep, user: CurrentUser
) -> TrialVersion:
    await owned_trial(session, user, trial_id)
    if payload.status is VersionStatus.approved:
        raise ApplicationError(
            code="TRIAL_VERSION_REVIEW_INCOMPLETE",
            message="Create a draft version, add validated criteria, then approve it.",
            status_code=422,
            field="status",
        )
    version = TrialVersion(trial_id=trial_id, **payload.model_dump())
    session.add(version)
    try:
        await session.commit()
    except IntegrityError as exception:
        await session.rollback()
        raise ApplicationError(
            code="TRIAL_VERSION_EXISTS",
            message="This trial version already exists.",
            status_code=409,
            field="version",
        ) from exception
    return await owned_version(session, user, trial_id, version.id)


@router.post(
    "/{trial_id}/versions/draft",
    response_model=VersionRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_guided_draft(
    trial_id: uuid.UUID,
    session: SessionDep,
    user: CurrentUser,
) -> TrialVersion:
    trial = await owned_trial(session, user, trial_id)
    existing_draft = next(
        (version for version in trial.versions if version.status is VersionStatus.draft),
        None,
    )
    if existing_draft is not None:
        raise ApplicationError(
            code="TRIAL_DRAFT_EXISTS",
            message="This trial already has an editable draft.",
            status_code=409,
            details=[{"version_id": str(existing_draft.id)}],
        )
    latest = trial.versions[-1] if trial.versions else None
    version = TrialVersion(
        trial_id=trial_id,
        version=(latest.version + 1) if latest else 1,
        status=VersionStatus.draft,
        source_text=latest.source_text if latest else None,
    )
    session.add(version)
    await session.flush()
    if latest is not None:
        for criterion in latest.criteria:
            session.add(
                Criterion(
                    trial_version_id=version.id,
                    kind=criterion.kind,
                    order=criterion.order,
                    source_text=criterion.source_text,
                    normalized_rule=criterion.normalized_rule,
                    required=criterion.required,
                )
            )
    await session.commit()
    return await owned_version(session, user, trial_id, version.id)


@router.put("/{trial_id}/versions/{version_id}", response_model=VersionRead)
async def update_version(
    payload: VersionCreate,
    trial_id: uuid.UUID,
    version_id: uuid.UUID,
    session: SessionDep,
    user: CurrentUser,
) -> TrialVersion:
    version = await owned_version(session, user, trial_id, version_id)
    require_draft(version)
    if payload.status is VersionStatus.approved:
        await require_approvable(session, version)
    for key, value in payload.model_dump().items():
        setattr(version, key, value)
    try:
        await session.commit()
    except IntegrityError as exception:
        await session.rollback()
        raise ApplicationError(
            code="TRIAL_VERSION_EXISTS",
            message="This trial version already exists.",
            status_code=409,
            field="version",
        ) from exception
    return await owned_version(session, user, trial_id, version_id)


@router.delete("/{trial_id}/versions/{version_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_version(
    trial_id: uuid.UUID,
    version_id: uuid.UUID,
    session: SessionDep,
    user: CurrentUser,
) -> Response:
    version = await owned_version(session, user, trial_id, version_id)
    require_draft(version)
    await session.delete(version)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{trial_id}/versions/{version_id}/criteria",
    response_model=CriterionRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_criterion(
    payload: CriterionCreate,
    trial_id: uuid.UUID,
    version_id: uuid.UUID,
    session: SessionDep,
    user: CurrentUser,
) -> Criterion:
    version = await owned_version(session, user, trial_id, version_id)
    require_draft(version)
    if payload.normalized_rule is not None:
        await validate_rule_for_session(session, payload.normalized_rule)
    criterion = Criterion(trial_version_id=version_id, **payload.model_dump())
    session.add(criterion)
    try:
        await session.commit()
    except IntegrityError as exception:
        await session.rollback()
        raise ApplicationError(
            code="CRITERION_ORDER_EXISTS",
            message="Criterion order must be unique within a version.",
            status_code=409,
            field="order",
        ) from exception
    await session.refresh(criterion)
    return criterion


@router.post(
    "/{trial_id}/versions/{version_id}/guided-criteria",
    response_model=CriterionRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_guided_criterion(
    payload: GuidedCriterionCreate,
    trial_id: uuid.UUID,
    version_id: uuid.UUID,
    session: SessionDep,
    user: CurrentUser,
) -> Criterion:
    version = await owned_version(session, user, trial_id, version_id)
    require_draft(version)
    source_text, normalized_rule = await guided_criterion_values(session, payload)
    await validate_rule_for_session(session, normalized_rule)
    last_order = await session.scalar(
        select(func.max(Criterion.order)).where(Criterion.trial_version_id == version_id)
    )
    criterion = Criterion(
        trial_version_id=version_id,
        kind=payload.kind,
        order=(last_order or 0) + 1,
        source_text=source_text,
        normalized_rule=normalized_rule,
        required=True,
    )
    session.add(criterion)
    await session.commit()
    await session.refresh(criterion)
    return criterion


@router.post(
    "/{trial_id}/versions/{version_id}/unsupported-criteria",
    response_model=CriterionRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_unsupported_criterion(
    payload: UnsupportedCriterionCreate,
    trial_id: uuid.UUID,
    version_id: uuid.UUID,
    session: SessionDep,
    user: CurrentUser,
) -> Criterion:
    version = await owned_version(session, user, trial_id, version_id)
    require_draft(version)
    last_order = await session.scalar(
        select(func.max(Criterion.order)).where(Criterion.trial_version_id == version_id)
    )
    criterion = Criterion(
        trial_version_id=version_id,
        kind=payload.kind,
        order=(last_order or 0) + 1,
        source_text=payload.source_text,
        normalized_rule=None,
        required=True,
    )
    session.add(criterion)
    await session.commit()
    await session.refresh(criterion)
    return criterion


@router.put(
    "/{trial_id}/versions/{version_id}/criteria/{criterion_id}", response_model=CriterionRead
)
async def update_criterion(
    payload: CriterionCreate,
    trial_id: uuid.UUID,
    version_id: uuid.UUID,
    criterion_id: uuid.UUID,
    session: SessionDep,
    user: CurrentUser,
) -> Criterion:
    version = await owned_version(session, user, trial_id, version_id)
    require_draft(version)
    criterion = await session.scalar(
        select(Criterion).where(
            Criterion.id == criterion_id, Criterion.trial_version_id == version_id
        )
    )
    if criterion is None:
        raise ApplicationError(
            code="CRITERION_NOT_FOUND", message="Criterion was not found.", status_code=404
        )
    for key, value in payload.model_dump().items():
        if key == "normalized_rule" and value is not None:
            await validate_rule_for_session(session, value)
        setattr(criterion, key, value)
    try:
        await session.commit()
    except IntegrityError as exception:
        await session.rollback()
        raise ApplicationError(
            code="CRITERION_ORDER_EXISTS",
            message="Criterion order must be unique within a version.",
            status_code=409,
            field="order",
        ) from exception
    await session.refresh(criterion)
    return criterion


@router.put(
    "/{trial_id}/versions/{version_id}/guided-criteria/{criterion_id}",
    response_model=CriterionRead,
)
async def update_guided_criterion(
    payload: GuidedCriterionCreate,
    trial_id: uuid.UUID,
    version_id: uuid.UUID,
    criterion_id: uuid.UUID,
    session: SessionDep,
    user: CurrentUser,
) -> Criterion:
    version = await owned_version(session, user, trial_id, version_id)
    require_draft(version)
    criterion = await session.scalar(
        select(Criterion).where(
            Criterion.id == criterion_id,
            Criterion.trial_version_id == version_id,
        )
    )
    if criterion is None:
        raise ApplicationError(
            code="CRITERION_NOT_FOUND",
            message="Criterion was not found.",
            status_code=404,
        )
    source_text, normalized_rule = await guided_criterion_values(session, payload)
    await validate_rule_for_session(session, normalized_rule)
    criterion.kind = payload.kind
    criterion.source_text = source_text
    criterion.normalized_rule = normalized_rule
    criterion.required = True
    await session.commit()
    await session.refresh(criterion)
    return criterion


@router.delete(
    "/{trial_id}/versions/{version_id}/criteria/{criterion_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_criterion(
    trial_id: uuid.UUID,
    version_id: uuid.UUID,
    criterion_id: uuid.UUID,
    session: SessionDep,
    user: CurrentUser,
) -> Response:
    version = await owned_version(session, user, trial_id, version_id)
    require_draft(version)
    criterion = await session.scalar(
        select(Criterion).where(
            Criterion.id == criterion_id, Criterion.trial_version_id == version_id
        )
    )
    if criterion is None:
        raise ApplicationError(
            code="CRITERION_NOT_FOUND", message="Criterion was not found.", status_code=404
        )
    await session.delete(criterion)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
