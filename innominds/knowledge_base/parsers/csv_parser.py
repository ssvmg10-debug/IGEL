"""
CSV / Excel Parser
Strategy:
  - Each sheet = one logical document group
  - Rows are grouped into chunks by logical context (not arbitrary row counts)
  - Column headers are always preserved in every chunk (critical for context)
  - Defect/Jira CSVs: group by module/component column if present
"""
import re
from pathlib import Path
from knowledge_base.parsers.markdown_parser import Section


_GROUP_COLUMNS = ["module", "component", "area", "feature", "category", "type", "status"]
_ROWS_PER_CHUNK = 20   # max rows per chunk when no grouping column found


def parse_csv(file_path: Path) -> list[Section]:
    import pandas as pd
    suffix = file_path.suffix.lower()

    if suffix in (".xlsx", ".xls"):
        xl = pd.ExcelFile(str(file_path))
        sections: list[Section] = []
        for sheet_name in xl.sheet_names:
            df = xl.parse(sheet_name)
            sections.extend(_dataframe_to_sections(df, f"{file_path.stem} - {sheet_name}"))
        return sections

    elif suffix == ".csv":
        try:
            df = pd.read_csv(str(file_path), encoding="utf-8")
        except UnicodeDecodeError:
            df = pd.read_csv(str(file_path), encoding="latin-1")
        return _dataframe_to_sections(df, file_path.stem)

    raise ValueError(f"Unsupported tabular type: {suffix}")


def _dataframe_to_sections(df, source_name: str) -> list[Section]:
    import pandas as pd

    # Clean up: drop fully empty rows/columns
    df = df.dropna(how="all").dropna(axis=1, how="all")
    df = df.fillna("")
    df.columns = [str(c).strip() for c in df.columns]

    if df.empty:
        return []

    # Find grouping column
    group_col = _find_group_column(df.columns.tolist())

    if group_col:
        return _group_by_column(df, group_col, source_name)
    else:
        return _chunk_by_rows(df, source_name)


def _find_group_column(columns: list[str]) -> str | None:
    col_lower = {c.lower(): c for c in columns}
    for key in _GROUP_COLUMNS:
        if key in col_lower:
            return col_lower[key]
    return None


def _group_by_column(df, group_col: str, source_name: str) -> list[Section]:
    sections: list[Section] = []
    headers = df.columns.tolist()
    header_line = "| " + " | ".join(headers) + " |"
    divider = "| " + " | ".join(["---"] * len(headers)) + " |"

    for group_val, group_df in df.groupby(group_col, sort=False):
        if group_df.empty:
            continue
        rows_md = _rows_to_markdown(group_df, headers)
        content = f"{header_line}\n{divider}\n{rows_md}"
        sections.append(Section(
            title=f"{source_name} - {group_col}: {group_val}",
            level=2,
            content=content,
            metadata={
                "is_table": True,
                "row_count": len(group_df),
                "group_by": group_col,
                "group_value": str(group_val),
            },
        ))

    return sections


def _chunk_by_rows(df, source_name: str) -> list[Section]:
    sections: list[Section] = []
    headers = df.columns.tolist()
    header_line = "| " + " | ".join(headers) + " |"
    divider = "| " + " | ".join(["---"] * len(headers)) + " |"

    for start in range(0, len(df), _ROWS_PER_CHUNK):
        chunk_df = df.iloc[start:start + _ROWS_PER_CHUNK]
        rows_md = _rows_to_markdown(chunk_df, headers)
        content = f"{header_line}\n{divider}\n{rows_md}"
        end = min(start + _ROWS_PER_CHUNK, len(df))
        sections.append(Section(
            title=f"{source_name} (rows {start+1}-{end})",
            level=2,
            content=content,
            metadata={
                "is_table": True,
                "row_count": len(chunk_df),
                "row_start": start + 1,
                "row_end": end,
            },
        ))

    return sections


def _rows_to_markdown(df, headers: list[str]) -> str:
    lines = []
    for _, row in df.iterrows():
        cells = [str(row[col]).strip().replace("\n", " ") for col in headers]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)
