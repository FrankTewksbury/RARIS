from app.eval.metrics import manifest_accuracy, scrape_completion, source_recall


def test_manifest_accuracy_perfect():
    gt = [
        {"regulatory_body": "naic", "type": "guidance"},
        {"regulatory_body": "hhs", "type": "statute"},
    ]
    predicted = [
        {"regulatory_body": "naic", "type": "guidance"},
        {"regulatory_body": "hhs", "type": "statute"},
        {"regulatory_body": "dol", "type": "regulation"},
    ]
    result = manifest_accuracy(predicted, gt)
    assert result.value == 1.0
    assert result.passed is True


def test_manifest_accuracy_partial():
    gt = [
        {"regulatory_body": "naic", "type": "guidance"},
        {"regulatory_body": "hhs", "type": "statute"},
        {"regulatory_body": "dol", "type": "regulation"},
    ]
    predicted = [
        {"regulatory_body": "naic", "type": "guidance"},
    ]
    result = manifest_accuracy(predicted, gt)
    assert 0.3 <= result.value <= 0.4
    assert result.passed is False


def test_source_recall_full():
    gt = [
        {"regulatory_body": "naic", "name": "Model Laws"},
        {"regulatory_body": "hhs", "name": "ACA"},
    ]
    predicted = [
        {"regulatory_body": "naic", "name": "Model Laws"},
        {"regulatory_body": "hhs", "name": "ACA"},
    ]
    result = source_recall(predicted, gt)
    assert result.value == 1.0
    assert result.passed is True


def test_scrape_completion():
    result = scrape_completion(90, 100)
    assert result.value == 0.90
    assert result.passed is True

    result = scrape_completion(50, 100)
    assert result.passed is False
