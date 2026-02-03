"""Convert user-facing filter dicts to Qdrant filter objects."""

from __future__ import annotations

from qdrant_client import models

from code_search.exceptions import InvalidFilterError

FILTERABLE_FIELDS: set[str] = {"language", "chunk_type", "app_name", "layer", "is_test"}


def build_qdrant_filter(filters: dict[str, str]) -> models.Filter | None:
    """Build a Qdrant ``Filter`` from a flat key/value filter dict.

    Parameters
    ----------
    filters:
        Mapping of field name to desired value.  Only keys present in
        ``FILTERABLE_FIELDS`` are accepted.

    Returns
    -------
    models.Filter | None
        A ``Filter`` with ``must`` conditions, or ``None`` when *filters* is
        empty.

    Raises
    ------
    InvalidFilterError
        If a key is not in ``FILTERABLE_FIELDS``.
    """
    if not filters:
        return None

    valid_fields = sorted(FILTERABLE_FIELDS)
    conditions: list[models.Condition] = []

    for key, value in filters.items():
        if key not in FILTERABLE_FIELDS:
            raise InvalidFilterError(
                filter_name=key,
                value=value,
                valid_values=valid_fields,
            )

        if key == "is_test":
            match_value = models.MatchValue(value=value.lower() == "true")
        else:
            match_value = models.MatchValue(value=value)

        conditions.append(
            models.FieldCondition(key=key, match=match_value),
        )

    return models.Filter(must=conditions)
