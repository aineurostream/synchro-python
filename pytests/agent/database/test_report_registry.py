import pytest

from synchroagent.database.client_registry import ClientCreate
from synchroagent.database.report_registry import ReportCreate


def test_report_create(report_registry, test_client_item):
    report_content = "<html><body><h1>Test Report</h1></body></html>"
    report_create = ReportCreate(
        client_id=test_client_item.id,
        content=report_content,
    )
    report = report_registry.create(report_create)
    assert report.id is not None
    assert report.client_id == test_client_item.id
    assert report.content == report_content
    assert report.size == len(report_content.encode("utf-8"))
    assert report.generated_at is not None


def test_report_create_with_custom_date(report_registry, test_client_item):
    custom_date = "2023-01-01T00:00:00Z"
    report_create = ReportCreate(
        client_id=test_client_item.id,
        content="Test content",
        generated_at=custom_date,
    )
    report = report_registry.create(report_create)
    assert report.generated_at == custom_date


def test_report_get_by_id(report_registry, test_client_item):
    report_create = ReportCreate(
        client_id=test_client_item.id,
        content="Get by ID test",
    )
    created_report = report_registry.create(report_create)
    report = report_registry.get_by_id(created_report.id)
    assert report is not None
    assert report.id == created_report.id
    assert report.client_id == test_client_item.id
    assert report.content == "Get by ID test"


def test_report_delete(report_registry, test_client_item):
    report_create = ReportCreate(
        client_id=test_client_item.id,
        content="Delete test",
    )
    created_report = report_registry.create(report_create)

    assert report_registry.exists(created_report.id)

    result = report_registry.delete(created_report.id)

    assert result is True
    assert not report_registry.exists(created_report.id)
    assert report_registry.get_by_id(created_report.id) is None


def test_report_get_reports_by_client_id(
    report_registry,
    client_registry,
    test_config_item,
):
    client1 = client_registry.create(
        ClientCreate(name="report_client_1", config_id=test_config_item.id),
    )
    client2 = client_registry.create(
        ClientCreate(name="report_client_2", config_id=test_config_item.id),
    )

    report_registry.create(
        ReportCreate(client_id=client1.id, content="Client 1 Report 1"),
    )
    report_registry.create(
        ReportCreate(client_id=client1.id, content="Client 1 Report 2"),
    )
    report_registry.create(
        ReportCreate(client_id=client2.id, content="Client 2 Report"),
    )

    client1_reports = report_registry.get_reports_by_client_id(client1.id)

    assert len(client1_reports) == 2
    report_contents = [report.content for report in client1_reports]
    assert "Client 1 Report 1" in report_contents
    assert "Client 1 Report 2" in report_contents
    assert "Client 2 Report" not in report_contents

    client2_reports = report_registry.get_reports_by_client_id(client2.id)

    assert len(client2_reports) == 1
    assert client2_reports[0].content == "Client 2 Report"


def test_report_update_not_supported(report_registry, test_client_item):
    report_create = ReportCreate(
        client_id=test_client_item.id,
        content="Original content",
    )
    report = report_registry.create(report_create)

    with pytest.raises(NotImplementedError):
        report_registry.update(report.id, None)
