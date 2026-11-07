"""Compile common analytic intents from permitted CSV identifiers."""

import re
from sqlglot import exp, parse_one


METRIC_NAMES = (
    {
        "salary", "salaries", "pay", "wage", "wages", "earnings",
        "compensation", "base salary", "annual salary",
    },
    {"quantity", "qty", "units"},
    {"revenue", "sales revenue"},
    {"cost", "costs", "expense", "expenses"},
)
AGGREGATES = {
    "sum": "SUM", "total": "SUM", "average": "AVG", "mean": "AVG",
    "minimum": "MIN", "lowest": "MIN", "maximum": "MAX", "highest": "MAX",
}
INTRO = r"(?:what is |show(?: me)? |calculate |give me )?(?:the )?"
MEASURE_WORDS = set().union(*METRIC_NAMES) | {
    "age", "amount", "balance", "distance", "duration", "price", "rate",
    "score", "temperature", "total", "weight",
}


def numeric_candidates(columns):
    return {
        name for name in columns
        if (tokens := name.lower().split("_"))[-1] in MEASURE_WORDS
        and not {"id", "code", "postal", "zip", "category"}.intersection(tokens)
    }


def question_examples(columns):
    if not columns:
        return []
    examples = ["How many records are there?"]
    category = next(
        (column for column in columns
         if column.lower() in {"city", "department", "region", "category", "status"}),
        None,
    )
    metric = next(iter(sorted(numeric_candidates(columns))), None)
    if category:
        examples.append(f"Count records by {category}")
    if metric:
        grouped = f" by {category}" if category else ""
        examples.append(f"What is the average {metric}{grouped}?")
        examples.append(f"Top 5 by {metric}")
    return examples


class NumericMetricRequiresConversion(ValueError):
    pass


def validate_numeric_operations(sql, measures):
    if not measures:
        return
    for operation in parse_one(sql, read="sqlite").find_all(
        exp.Sum, exp.Avg, exp.Min, exp.Max, exp.Ordered
    ):
        value = operation.this
        if (
            isinstance(operation, exp.Ordered)
            and isinstance(value, exp.Column)
            and not value.table
        ):
            select = operation.find_ancestor(exp.Select)
            if select:
                value = next(
                    (
                        item.this for item in select.expressions
                        if isinstance(item, exp.Alias) and item.alias == value.name
                    ),
                    value,
                )
        if isinstance(value, exp.Column) and value.table and value.name.lower() in measures:
            raise NumericMetricRequiresConversion


def matching_columns(label, columns, *, implicit=False):
    label = label.replace("_", " ")
    if not implicit and label in columns:
        return [columns[label]]
    for names in METRIC_NAMES:
        if label in names:
            return sorted(columns[name] for name in columns.keys() & names)
    return []


class ColumnClarification(ValueError):
    def __init__(self, choices):
        super().__init__("Several permitted columns match that metric. Which column should MORPHY use?")
        self.choices = choices


def analytics_sql(question, permitted_columns, *, exact_columns=False):
    """Return a draft for a recognized intent, or defer to the model."""
    question = " ".join(question.lower().split()).rstrip(" ?.!")
    columns = {name.lower().replace("_", " "): name for name in permitted_columns}

    def resolve(label, span=None):
        if exact_columns:
            column = columns.get(label.replace("_", " "))
            return f'"{column}"' if column else None
        matches = matching_columns(label, columns, implicit=span is None)
        if len(matches) > 1:
            if span is None:
                direction = "lowest" if question.split()[-1] in {"least", "lowest"} else "highest"
                choices = [
                    {"column": column, "question": f"Who has the {direction} {column}?"}
                    for column in matches
                ]
            else:
                start, end = span
                choices = [
                    {"column": column, "question": question[:start] + column + question[end:]}
                    for column in matches
                ]
            raise ColumnClarification(choices)
        return f'"{matches[0]}"' if matches else None

    count = re.fullmatch(
        r"(?:count (?:the )?|how many )(?:rows|records)(?: are there)?(?:(?: by | per )(.+))?",
        question,
    )
    if count and columns:
        if count[1]:
            category = resolve(count[1], count.span(1))
            if category:
                return (
                    f"SELECT {category}, COUNT(*) AS row_count FROM records "
                    f"GROUP BY {category} ORDER BY {category}"
                )
        else:
            return "SELECT COUNT(*) AS row_count FROM records"

    earnings = re.fullmatch(r"who earns (?:the )?(lowest|least|highest|most)", question)
    person = re.fullmatch(r"who has (?:the )?(lowest|highest) (.+)", question)
    top = re.fullmatch(r"(top|bottom) ([1-9][0-9]{0,2})(?: rows| records)? by (.+)", question)
    aggregate = re.fullmatch(
        INTRO + r"(sum|total|average|mean|minimum|lowest|maximum|highest) (?:of (?:the )?)?(.+?)(?: by (.+))?",
        question,
    )
    if aggregate:
        operation, metric, group = aggregate.groups()
        value = resolve(metric, aggregate.span(2))
        category = resolve(group, aggregate.span(3)) if value and group else None
        if value and (category or not group):
            calculation = f"{AGGREGATES[operation]}(morphy_number({value}))"
            if category:
                return (
                    f"SELECT {category}, {calculation} AS {operation} FROM records "
                    f"GROUP BY {category} ORDER BY {category}"
                )
            return f"SELECT {calculation} AS {operation} FROM records"
    if not (earnings or person or top):
        return None

    label = "compensation" if earnings else person[2] if person else top[3]
    span = None if earnings else person.span(2) if person else top.span(3)
    value = resolve(label, span)
    if not value:
        if earnings or label in METRIC_NAMES[0]:
            raise ValueError("Choose a permitted pay column to rank.")
        return None

    identity = [columns[key] for key in ("first name", "last name") if key in columns]
    if not identity:
        labels = [columns[key] for key in ("full name", "employee name", "name") if key in columns]
        other_labels = [column for key, column in columns.items() if key.endswith(" name")]
        identifiers = [columns[key] for key in ("employee id", "id") if key in columns]
        identity = (labels or (other_labels if len(other_labels) == 1 else []) or identifiers)[:1]
    if (earnings or person) and not identity:
        raise ValueError("This question requires a permitted name or ID column.")
    fields = ", ".join(dict.fromkeys([*(f'"{name}"' for name in identity), value]))
    number = f"morphy_number({value})"
    if top:
        direction = "DESC" if top[1] == "top" else "ASC"
        return (
            f"SELECT {fields} FROM records WHERE {number} IS NOT NULL "
            f"ORDER BY {number} {direction} LIMIT {int(top[2])}"
        )
    direction = (earnings or person)[1]
    operation = "MIN" if direction in {"lowest", "least"} else "MAX"
    return (
        f"SELECT {fields} FROM records WHERE {number} = "
        f"(SELECT {operation}({number}) FROM records)"
    )
