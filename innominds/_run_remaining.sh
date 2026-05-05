#!/bin/bash
# Run after current ingest (bel6kag0d) finishes the first failed PDF.
# Process the other 2 failed PDFs sequentially.
set -e
cd "c:/Users/parav/Workspace/IGEL/IGEL Automation_Suit_AI/innominds"
export PYTHONIOENCODING=utf-8

echo "=== Re-ingesting IGEL OS Base System 12.7.3.pdf ==="
py -3.12 -m knowledge_base.ingest --file "IGEL OS Base System 12.7.3.pdf" 2>&1 | grep -vE "INFO HTTP" | tail -25

echo ""
echo "=== Re-ingesting Universal Management Suite (UMS) 12.09.110 EN.pdf ==="
py -3.12 -m knowledge_base.ingest --file "Universal Management Suite (UMS) 12.09.110 EN.pdf" 2>&1 | grep -vE "INFO HTTP" | tail -25

echo ""
echo "=== All 3 failed PDFs re-ingested ==="
py -3.12 -c "
from knowledge_base.db.client import init_pool
from knowledge_base.db.schema import get_stats
init_pool()
print(get_stats())
"
