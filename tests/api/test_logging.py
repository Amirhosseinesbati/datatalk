import json
import logging

from datatalk.logging_utils import SafeJsonFormatter


def test_structured_log_keeps_correlation_ids_without_raw_analysis_data():
    record = logging.LogRecord("datatalk.analysis", logging.INFO, __file__, 1, "analysis_started", (), None)
    record.analysis_id = "analysis-123"
    record.request_id = "request-456"
    record.question = "private customer question"
    record.sql = "SELECT private_value FROM secret_table"
    record.rows = [{"private_value": "secret"}]

    payload = json.loads(SafeJsonFormatter().format(record))

    assert payload["analysis_id"] == "analysis-123"
    assert payload["request_id"] == "request-456"
    assert payload["event"] == "analysis_started"
    assert "question" not in payload
    assert "sql" not in payload
    assert "rows" not in payload
