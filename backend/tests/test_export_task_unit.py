import json
import pytest
from unittest.mock import patch, MagicMock

from app.tasks.export_task import execute_export
from app.models.job import BackgroundJob
from app.models.delivery import ExternalDeliveryRecord
from app.services.export_service import SharePointSyncError, EmailSendError

@patch('app.tasks.export_task.SessionLocal')
@patch('app.tasks.export_task.OutboxService')
@patch('app.tasks.export_task.JobService')
@patch('app.tasks.export_task.get_latest_export')
@patch('app.tasks.export_task.sync_and_notify')
def test_export_task_partial_failure(mock_sync, mock_latest, mock_js, mock_outbox, mock_session):
    # Setup mocks
    db_mock = MagicMock()
    mock_session.return_value = db_mock
    
    job_mock = MagicMock(spec=BackgroundJob)
    job_mock.job_id = "test-job-123"
    job_mock.payload_reference = json.dumps({
        "session_id": 1,
        "report_id": "OPR",
        "sharepoint_site": "https://company.sharepoint.com/sites/qa",
        "email_distribution_list": ["test@example.com"]
    })
    
    # Query logic mock
    def query_side_effect(model):
        q = MagicMock()
        def filter_by_side_effect(*args, **kwargs):
            m = MagicMock()
            m.first.return_value = None
            return m
        def filter_side_effect(*args, **kwargs):
            m = MagicMock()
            m.first.return_value = job_mock
            return m
        q.filter_by = filter_by_side_effect
        q.filter = filter_side_effect
        return q
        
    db_mock.query.side_effect = query_side_effect
    mock_latest.return_value = MagicMock()
    
    # Mock partial failure
    mock_sync.return_value = {
        "sharepoint_url": None,
        "sharepoint_error": "Connection Timeout",
        "email_sent": False,
        "email_error": "SMTP Error"
    }
    
    with pytest.raises(Exception):
        # We need to pass mock self to celery task to avoid errors
        task_mock = MagicMock()
        task_mock.request.hostname = "localhost"
        task_mock.request.retries = 0
        task_mock.retry.side_effect = Exception("Retry Triggered")
        execute_export.bind(task_mock)("outbox-1", "job-1")
        
    # Assert DB add wasn't called for ExternalDeliveryRecord
    db_adds = [call[0][0] for call in db_mock.add.call_args_list if isinstance(call[0][0], ExternalDeliveryRecord)]
    assert len(db_adds) == 0, "Should not record DELIVERED on partial failure"


@patch('app.tasks.export_task.SessionLocal')
@patch('app.tasks.export_task.OutboxService')
@patch('app.tasks.export_task.JobService')
@patch('app.tasks.export_task.get_latest_export')
@patch('app.tasks.export_task.sync_and_notify')
def test_export_task_multi_recipient(mock_sync, mock_latest, mock_js, mock_outbox, mock_session):
    # Setup mocks
    db_mock = MagicMock()
    mock_session.return_value = db_mock
    
    job_mock = MagicMock(spec=BackgroundJob)
    job_mock.job_id = "test-job-456"
    job_mock.payload_reference = json.dumps({
        "session_id": 1,
        "report_id": "OPR",
        "email_distribution_list": ["a@test.com", "b@test.com", "c@test.com"]
    })
    
    def query_side_effect(model):
        q = MagicMock()
        def filter_by_side_effect(*args, **kwargs):
            m = MagicMock()
            m.first.return_value = None
            return m
        def filter_side_effect(*args, **kwargs):
            m = MagicMock()
            m.first.return_value = job_mock
            return m
        q.filter_by = filter_by_side_effect
        q.filter = filter_side_effect
        return q
        
    db_mock.query.side_effect = query_side_effect
    mock_latest.return_value = MagicMock()
    
    # Mock success
    mock_sync.return_value = {
        "email_sent": True
    }
    
    task_mock = MagicMock()
    task_mock.request.hostname = "localhost"
    task_mock.request.retries = 0
    execute_export.bind(task_mock)("outbox-2", "job-2")
    
    # Assert 3 delivery records added
    db_adds = [call[0][0] for call in db_mock.add.call_args_list if isinstance(call[0][0], ExternalDeliveryRecord)]
    assert len(db_adds) == 3
    addresses = [rec.target_address for rec in db_adds]
    assert "a@test.com" in addresses
    assert "b@test.com" in addresses
    assert "c@test.com" in addresses
