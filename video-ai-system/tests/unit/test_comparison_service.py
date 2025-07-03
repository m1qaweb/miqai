import pytest
from video_ai_system.services.comparison_service import ComparisonService

@pytest.fixture
def comparison_service():
    """
    Pytest fixture for a ComparisonService instance.
    """
    return ComparisonService()

def test_compare_and_log_identical_outputs(comparison_service):
    """
    Test that logging identical outputs results in a discrepancy of 0.
    """
    prod_output = {'class': 'A', 'confidence': 0.9}
    cand_output = {'class': 'A', 'confidence': 0.9}
    comparison_service.compare_and_log(prod_output, cand_output, 'req-1')
    
    assert len(comparison_service.log) == 1
    log_entry = comparison_service.log[0]
    assert log_entry['request_id'] == 'req-1'
    assert log_entry['production_output'] == prod_output
    assert log_entry['candidate_output'] == cand_output
    assert log_entry['discrepancy'] == 0.0

def test_compare_and_log_different_outputs(comparison_service):
    """
    Test that logging different outputs results in a discrepancy of 1.
    """
    prod_output = {'class': 'A', 'confidence': 0.9}
    cand_output = {'class': 'B', 'confidence': 0.8}
    comparison_service.compare_and_log(prod_output, cand_output, 'req-2')
    
    assert len(comparison_service.log) == 1
    log_entry = comparison_service.log[0]
    assert log_entry['discrepancy'] == 1.0

def test_get_discrepancy_rate(comparison_service):
    """
    Test the discrepancy rate calculation.
    """
    # 1 discrepancy out of 3 requests
    comparison_service.compare_and_log({'class': 'A'}, {'class': 'A'}, 'req-1')
    comparison_service.compare_and_log({'class': 'A'}, {'class': 'B'}, 'req-2')
    comparison_service.compare_and_log({'class': 'C'}, {'class': 'C'}, 'req-3')
    
    # (1 / 3) * 100 = 33.33...
    assert pytest.approx(comparison_service.get_discrepancy_rate(), 0.01) == 33.33

def test_get_discrepancy_rate_no_logs(comparison_service):
    """
    Test that the discrepancy rate is 0 when there are no logs.
    """
    assert comparison_service.get_discrepancy_rate() == 0.0

def test_get_discrepancy_rate_all_discrepancies(comparison_service):
    """
    Test that the discrepancy rate is 100 when all logs have discrepancies.
    """
    comparison_service.compare_and_log({'class': 'A'}, {'class': 'B'}, 'req-1')
    comparison_service.compare_and_log({'class': 'C'}, {'class': 'D'}, 'req-2')
    
    assert comparison_service.get_discrepancy_rate() == 100.0
